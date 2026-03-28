"""Knowledge Base — high-level wrapper over RAG pipeline + reranking.

Provides a single entry point for ingestion, search (with optional reranking),
and management.  Used by the MCP server, function-calling tools, and CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from aicp.core.rag import RAGPipeline, VectorStore, build_rag_pipeline


class KnowledgeBase:
    """High-level knowledge base backed by embeddings + optional cross-encoder reranking."""

    def __init__(self, backend, config: dict) -> None:
        rag_cfg = config.get("rag", {})
        self.backend = backend
        self.config = config

        db_path = Path(rag_cfg.get("db_path", ".aicp/rag.db"))
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path

        self._pipeline = build_rag_pipeline(
            backend=backend,
            db_path=db_path,
            store_name=rag_cfg.get("store_name", "default"),
            chunk_size=rag_cfg.get("chunk_size", 512),
            chunk_overlap=rag_cfg.get("chunk_overlap", 64),
            top_k=rag_cfg.get("top_k", 5),
            threshold=rag_cfg.get("threshold", 0.3),
        )

        # Reranker config
        local_cfg = config.get("backends", {}).get("local", {})
        self._reranker_model = local_cfg.get("reranker_model", "bge-reranker-v2-m3")
        self._rerank_enabled = rag_cfg.get("rerank", True)

    # ── Ingestion ────────────────────────────────────────────────────────────

    def ingest_file(self, path: Path) -> int:
        """Ingest a file into the knowledge base. Returns chunk count."""
        return self._pipeline.ingest_file(path)

    def ingest_text(self, text: str, source: str = "inline") -> int:
        """Ingest raw text into the knowledge base. Returns chunk count."""
        return self._pipeline.ingest_text(text, source=source)

    def ingest_directory(
        self,
        directory: Path,
        extensions: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> dict:
        """Ingest all matching files from a directory.

        Args:
            directory: Directory to scan.
            extensions: File extensions to include (e.g. [".py", ".md"]).
                        If None, includes common text file types.
            recursive: Whether to recurse into subdirectories.

        Returns:
            Dict with keys: files_ingested, total_chunks, errors.
        """
        if extensions is None:
            extensions = [
                ".py", ".md", ".txt", ".rst", ".yaml", ".yml",
                ".json", ".toml", ".cfg", ".ini", ".sh", ".bash",
                ".go", ".rs", ".js", ".ts", ".html", ".css",
            ]

        pattern = "**/*" if recursive else "*"
        files = [
            f for f in directory.glob(pattern)
            if f.is_file() and f.suffix.lower() in extensions
        ]

        total_chunks = 0
        errors = []
        for f in sorted(files):
            try:
                count = self._pipeline.ingest_file(f)
                total_chunks += count
            except Exception as e:
                errors.append({"file": str(f), "error": str(e)})

        return {
            "files_ingested": len(files) - len(errors),
            "total_chunks": total_chunks,
            "errors": errors,
        }

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """Search the knowledge base with optional reranking.

        Step 1: Embedding-based retrieval (fast, broad recall).
        Step 2: Cross-encoder reranking (precise relevance scoring).

        Returns list of dicts: {text, source, chunk_index, score}.
        """
        # Retrieve more candidates than needed so reranking can re-sort
        retrieve_k = top_k * 3 if self._rerank_enabled else top_k
        candidates = self._pipeline.retrieve(query, top_k=retrieve_k)

        if not candidates:
            return []

        if not self._rerank_enabled or not hasattr(self.backend, "rerank"):
            # No reranking — return embedding results directly
            return [
                {
                    "text": c["text"],
                    "source": c["source"],
                    "chunk_index": c["chunk_index"],
                    "score": round(c["similarity"], 4),
                }
                for c in candidates[:top_k]
            ]

        # Rerank candidates with cross-encoder
        doc_texts = [c["text"] for c in candidates]
        try:
            reranked = self.backend.rerank(
                query, doc_texts, model=self._reranker_model, top_n=top_k,
            )
        except Exception:
            # Reranker unavailable — fall back to embedding results
            return [
                {
                    "text": c["text"],
                    "source": c["source"],
                    "chunk_index": c["chunk_index"],
                    "score": round(c["similarity"], 4),
                }
                for c in candidates[:top_k]
            ]

        # Map reranked indices back to candidate metadata
        results = []
        for r in reranked:
            idx = r.get("index", 0)
            if 0 <= idx < len(candidates):
                c = candidates[idx]
                results.append({
                    "text": c["text"],
                    "source": c["source"],
                    "chunk_index": c["chunk_index"],
                    "score": round(r.get("relevance_score", 0), 4),
                })
        return results

    def augment_prompt(self, query: str, max_context_chars: int = 3000) -> str:
        """Build a RAG-augmented prompt with reranked context."""
        results = self.search(query)
        if not results:
            return query

        context_parts: List[str] = []
        total = 0
        for r in results:
            text = r["text"]
            if total + len(text) > max_context_chars:
                break
            source = Path(r["source"]).name if "/" in r["source"] else r["source"]
            context_parts.append(f"[{source}] {text}")
            total += len(text)

        if not context_parts:
            return query

        context_block = "\n---\n".join(context_parts)
        return (
            f"Use the following context to help answer the question.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {query}"
        )

    # ── Management ───────────────────────────────────────────────────────────

    def list_sources(self) -> List[dict]:
        """List all ingested sources with chunk counts."""
        return self._pipeline.list_sources()

    def delete_source(self, source: str) -> int:
        """Remove a source from the knowledge base. Returns chunks deleted."""
        return self._pipeline.delete_source(source)

    def stats(self) -> dict:
        """Return knowledge base statistics."""
        return self._pipeline.stats()
