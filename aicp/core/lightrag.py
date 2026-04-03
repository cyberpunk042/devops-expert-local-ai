"""LightRAG integration — unified search across KB and LocalAI stores.

Bridges two vector stores:
  1. AICP VectorStore (SQLite, persistent) — project knowledge base
  2. LocalAI /stores/ (in-memory, ephemeral) — working memory, collections

Provides a single search interface that queries both, merges results,
and optionally reranks with the cross-encoder.

This module also handles syncing KB content to LocalAI collections
for fleet agents that connect via LocalAI's native API.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aicp.lightrag")


class LightRAG:
    """Unified RAG search across persistent KB and ephemeral stores.

    Args:
        kb: KnowledgeBase instance (SQLite-backed, persistent).
        embedding_store: EmbeddingStore instance (LocalAI /stores/, ephemeral).
        backend: LocalAI backend (for reranking).
        config: AICP config dict.
    """

    def __init__(
        self,
        kb,
        embedding_store=None,
        backend=None,
        config: Optional[Dict] = None,
    ) -> None:
        self.kb = kb
        self.embedding_store = embedding_store
        self.backend = backend
        self.config = config or {}
        rag_cfg = self.config.get("rag", {})
        self._rerank = rag_cfg.get("rerank", True)
        self._reranker_model = (
            self.config.get("backends", {}).get("local", {})
            .get("reranker_model", "bge-reranker-v2-m3")
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        sources: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search across both KB and stores, merge and rerank.

        Args:
            query: Search query.
            top_k: Number of final results.
            sources: Which sources to query. Default: all.
                     Options: ["kb"], ["stores"], ["kb", "stores"]

        Returns:
            Merged list of results sorted by relevance score.
        """
        if sources is None:
            sources = ["kb", "stores"]

        candidates: List[Dict[str, Any]] = []

        # Query persistent KB
        if "kb" in sources and self.kb:
            try:
                kb_results = self.kb.search(query, top_k=top_k * 2)
                for r in kb_results:
                    r["source_type"] = "kb"
                candidates.extend(kb_results)
            except Exception as e:
                logger.warning("KB search failed: %s", e)

        # Query ephemeral stores
        if "stores" in sources and self.embedding_store:
            try:
                store_results = self.embedding_store.recall(query, top_k=top_k * 2)
                for r in store_results:
                    candidates.append({
                        "text": r["value"],
                        "source": "working-memory",
                        "chunk_index": 0,
                        "score": r["similarity"],
                        "source_type": "stores",
                    })
            except Exception as e:
                logger.warning("Store search failed: %s", e)

        if not candidates:
            return []

        # Rerank merged results with cross-encoder
        if self._rerank and self.backend and len(candidates) > top_k:
            try:
                doc_texts = [c["text"] for c in candidates]
                reranked = self.backend.rerank(
                    query, doc_texts,
                    model=self._reranker_model,
                    top_n=top_k,
                )
                results = []
                for r in reranked:
                    idx = r.get("index", 0)
                    if 0 <= idx < len(candidates):
                        c = candidates[idx]
                        c["score"] = round(r.get("relevance_score", 0), 4)
                        results.append(c)
                return results
            except Exception as e:
                logger.warning("Reranking failed, using score-sorted: %s", e)

        # Fallback: sort by score
        candidates.sort(key=lambda c: c.get("score", 0), reverse=True)
        return candidates[:top_k]

    def augment_prompt(
        self,
        query: str,
        max_context_chars: int = 3000,
        sources: Optional[List[str]] = None,
    ) -> str:
        """Build a RAG-augmented prompt from unified search results."""
        results = self.search(query, sources=sources)
        if not results:
            return query

        parts: List[str] = []
        total = 0
        for r in results:
            text = r["text"]
            if total + len(text) > max_context_chars:
                break
            src_type = r.get("source_type", "unknown")
            source = r.get("source", "unknown")
            label = f"{src_type}:{Path(source).name}" if "/" in source else f"{src_type}:{source}"
            parts.append(f"[{label}] {text}")
            total += len(text)

        if not parts:
            return query

        context_block = "\n---\n".join(parts)
        return (
            f"Use the following context to help answer the question.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {query}"
        )

    def sync_kb_to_stores(self, store_name: str = "kb-mirror") -> int:
        """Sync persistent KB content to a LocalAI ephemeral store.

        This makes KB content available to fleet agents that connect
        via LocalAI's native /stores/ API (without needing direct
        access to the SQLite database).

        Returns count of entries synced.
        """
        if not self.kb or not self.embedding_store:
            return 0

        sources = self.kb.list_sources()
        if not sources:
            return 0

        # Create a temporary store client for the mirror
        from aicp.core.stores import EmbeddingStore
        mirror = EmbeddingStore(
            backend=self.embedding_store.backend,
            base_url=self.embedding_store.store.base_url,
            store_name=store_name,
            api_key=self.embedding_store.store.api_key,
        )

        count = 0
        for source_info in sources:
            source = source_info["source"]
            # Search KB for all chunks of this source
            try:
                # Get chunks via direct store access
                store = self.kb._pipeline.store
                cur = store._conn.execute(
                    "SELECT text FROM chunks WHERE store = ? AND source = ?",
                    (self.kb._pipeline.store_name, source),
                )
                texts = [row[0] for row in cur]
                if texts:
                    metadata = [f"kb:{Path(source).name}"] * len(texts)
                    mirror.remember_batch(texts, metadata=metadata)
                    count += len(texts)
            except Exception as e:
                logger.warning("Failed to sync source %s: %s", source, e)

        logger.info("Synced %d KB entries to store '%s'", count, store_name)
        return count

    def stats(self) -> Dict[str, Any]:
        """Return unified RAG statistics."""
        result: Dict[str, Any] = {"sources": []}

        if self.kb:
            try:
                kb_stats = self.kb.stats()
                result["kb"] = kb_stats
                result["sources"].append("kb")
            except Exception:
                result["kb"] = {"error": "unavailable"}

        if self.embedding_store:
            result["stores"] = {"available": True}
            result["sources"].append("stores")
        else:
            result["stores"] = {"available": False}

        result["rerank_enabled"] = self._rerank
        result["reranker_model"] = self._reranker_model
        return result
