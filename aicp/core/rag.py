"""RAG pipeline — ingest, embed, store, retrieve, augment.

Uses SQLite for persistent vector storage and the LocalAI embedding
API for vector generation.  No external vector DB dependencies.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
from pathlib import Path

from aicp.core.chunking import chunk_file, chunk_text

# ── SQLite vector store ──────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    store       TEXT    NOT NULL DEFAULT 'default',
    source      TEXT    NOT NULL,
    chunk_index INTEGER NOT NULL,
    text        TEXT    NOT NULL,
    embedding   TEXT    NOT NULL,
    created_at  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_store ON chunks(store);
CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(store, source);
"""


class VectorStore:
    """Lightweight SQLite-backed vector store with cosine similarity search."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(_SCHEMA)

    def add(
        self,
        store: str,
        texts: list[str],
        embeddings: list[list[float]],
        sources: list[str],
        chunk_indices: list[int],
    ) -> int:
        """Insert chunks with their embeddings.  Returns count inserted."""
        now = time.time()
        rows = [
            (store, src, idx, txt, json.dumps(emb), now)
            for txt, emb, src, idx in zip(texts, embeddings, sources, chunk_indices)
        ]
        self._conn.executemany(
            "INSERT INTO chunks (store, source, chunk_index, text, embedding, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()
        return len(rows)

    def search(
        self,
        store: str,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> list[dict]:
        """Find the top-k most similar chunks by cosine similarity.

        Returns list of dicts: {text, source, chunk_index, similarity}
        sorted by similarity descending.
        """
        cur = self._conn.execute(
            "SELECT text, source, chunk_index, embedding FROM chunks WHERE store = ?",
            (store,),
        )
        results = []
        for text, source, chunk_index, emb_json in cur:
            emb = json.loads(emb_json)
            sim = _cosine_similarity(query_embedding, emb)
            if sim >= threshold:
                results.append({
                    "text": text,
                    "source": source,
                    "chunk_index": chunk_index,
                    "similarity": sim,
                })

        results.sort(key=lambda r: r["similarity"], reverse=True)
        return results[:top_k]

    def list_sources(self, store: str) -> list[dict]:
        """List all ingested sources with chunk counts."""
        cur = self._conn.execute(
            "SELECT source, COUNT(*) as chunks, MIN(created_at) as first_added "
            "FROM chunks WHERE store = ? GROUP BY source ORDER BY source",
            (store,),
        )
        return [
            {"source": row[0], "chunks": row[1], "added": row[2]}
            for row in cur
        ]

    def delete_source(self, store: str, source: str) -> int:
        """Remove all chunks for a given source.  Returns count deleted."""
        cur = self._conn.execute(
            "DELETE FROM chunks WHERE store = ? AND source = ?",
            (store, source),
        )
        self._conn.commit()
        return cur.rowcount

    def stats(self, store: str) -> dict:
        """Return store statistics."""
        cur = self._conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT source) FROM chunks WHERE store = ?",
            (store,),
        )
        total_chunks, total_sources = cur.fetchone()
        return {
            "store": store,
            "total_chunks": total_chunks,
            "total_sources": total_sources,
        }

    def close(self) -> None:
        self._conn.close()


# ── RAG Pipeline ─────────────────────────────────────────────────────────────


class RAGPipeline:
    """Orchestrates ingestion, retrieval, and prompt augmentation.

    Requires a backend with embed() and embed_batch() methods
    (e.g. LocalAIBackend).
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embed_fn,
        embed_batch_fn,
        store_name: str = "default",
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> None:
        self.store = vector_store
        self.embed = embed_fn
        self.embed_batch = embed_batch_fn
        self.store_name = store_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.threshold = threshold

    def ingest_file(self, path: Path) -> int:
        """Chunk, embed, and store a single file.  Returns chunk count."""
        chunks = chunk_file(path, self.chunk_size, self.chunk_overlap)
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        embeddings = self.embed_batch(texts)

        return self.store.add(
            store=self.store_name,
            texts=texts,
            embeddings=embeddings,
            sources=[c["source"] for c in chunks],
            chunk_indices=[c["chunk_index"] for c in chunks],
        )

    def ingest_text(self, text: str, source: str = "inline") -> int:
        """Chunk, embed, and store raw text.  Returns chunk count."""
        raw_chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)
        if not raw_chunks:
            return 0

        embeddings = self.embed_batch(raw_chunks)

        return self.store.add(
            store=self.store_name,
            texts=raw_chunks,
            embeddings=embeddings,
            sources=[source] * len(raw_chunks),
            chunk_indices=list(range(len(raw_chunks))),
        )

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        """Embed the query and return the most relevant chunks."""
        query_emb = self.embed(query)
        return self.store.search(
            store=self.store_name,
            query_embedding=query_emb,
            top_k=top_k or self.top_k,
            threshold=self.threshold,
        )

    def augment_prompt(self, query: str, max_context_chars: int = 3000) -> str:
        """Build a RAG-augmented prompt by prepending retrieved context.

        Returns the full prompt string with context block + original query.
        """
        results = self.retrieve(query)
        if not results:
            return query

        context_parts: list[str] = []
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

    def list_sources(self) -> list[dict]:
        return self.store.list_sources(self.store_name)

    def delete_source(self, source: str) -> int:
        return self.store.delete_source(self.store_name, source)

    def stats(self) -> dict:
        return self.store.stats(self.store_name)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_rag_pipeline(
    backend,
    db_path: Path,
    store_name: str = "default",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    top_k: int = 5,
    threshold: float = 0.3,
) -> RAGPipeline:
    """Convenience factory: build a RAGPipeline from a backend instance."""
    vs = VectorStore(db_path)
    return RAGPipeline(
        vector_store=vs,
        embed_fn=backend.embed,
        embed_batch_fn=backend.embed_batch,
        store_name=store_name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        top_k=top_k,
        threshold=threshold,
    )
