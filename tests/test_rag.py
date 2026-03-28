"""Tests for aicp.core.rag — vector store and RAG pipeline."""

import json
import math
import pytest
from pathlib import Path

from aicp.core.rag import VectorStore, RAGPipeline, _cosine_similarity


# ── Vector math ──────────────────────────────────────────────────────────────


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        assert _cosine_similarity(a, b) == 0.0


# ── VectorStore ──────────────────────────────────────────────────────────────


class TestVectorStore:
    @pytest.fixture
    def store(self, tmp_path):
        vs = VectorStore(tmp_path / "test.db")
        yield vs
        vs.close()

    def test_add_and_search(self, store):
        store.add(
            store="test",
            texts=["hello world", "foo bar"],
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            sources=["a.txt", "b.txt"],
            chunk_indices=[0, 0],
        )
        results = store.search("test", [1.0, 0.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0]["text"] == "hello world"
        assert results[0]["similarity"] == pytest.approx(1.0)

    def test_search_empty_store(self, store):
        results = store.search("empty", [1.0, 0.0], top_k=5)
        assert results == []

    def test_search_respects_threshold(self, store):
        store.add(
            store="test",
            texts=["relevant", "irrelevant"],
            embeddings=[[1.0, 0.0], [0.0, 1.0]],
            sources=["a.txt", "b.txt"],
            chunk_indices=[0, 0],
        )
        results = store.search("test", [1.0, 0.0], top_k=10, threshold=0.5)
        assert len(results) == 1
        assert results[0]["text"] == "relevant"

    def test_list_sources(self, store):
        store.add(
            store="test",
            texts=["chunk 1", "chunk 2", "chunk 3"],
            embeddings=[[1, 0], [0, 1], [1, 1]],
            sources=["a.txt", "a.txt", "b.txt"],
            chunk_indices=[0, 1, 0],
        )
        sources = store.list_sources("test")
        assert len(sources) == 2
        names = {s["source"] for s in sources}
        assert names == {"a.txt", "b.txt"}
        a_info = next(s for s in sources if s["source"] == "a.txt")
        assert a_info["chunks"] == 2

    def test_delete_source(self, store):
        store.add(
            store="test",
            texts=["keep", "remove"],
            embeddings=[[1, 0], [0, 1]],
            sources=["keep.txt", "remove.txt"],
            chunk_indices=[0, 0],
        )
        deleted = store.delete_source("test", "remove.txt")
        assert deleted == 1
        sources = store.list_sources("test")
        assert len(sources) == 1
        assert sources[0]["source"] == "keep.txt"

    def test_stats(self, store):
        store.add(
            store="test",
            texts=["a", "b", "c"],
            embeddings=[[1], [2], [3]],
            sources=["x.txt", "x.txt", "y.txt"],
            chunk_indices=[0, 1, 0],
        )
        info = store.stats("test")
        assert info["total_chunks"] == 3
        assert info["total_sources"] == 2

    def test_separate_stores(self, store):
        store.add("alpha", ["in alpha"], [[1, 0]], ["a.txt"], [0])
        store.add("beta", ["in beta"], [[0, 1]], ["b.txt"], [0])
        assert store.stats("alpha")["total_chunks"] == 1
        assert store.stats("beta")["total_chunks"] == 1
        # Search in alpha shouldn't find beta's data
        results = store.search("alpha", [0, 1], top_k=10)
        assert len(results) == 1  # only alpha's single chunk


# ── RAGPipeline ──────────────────────────────────────────────────────────────


def _fake_embed(text: str) -> list:
    """Deterministic fake embedding: hash-based 8-dim vector."""
    h = hash(text) % (10**8)
    vec = [(h >> i & 0xFF) / 255.0 for i in range(0, 64, 8)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0 else vec


def _fake_embed_batch(texts: list) -> list:
    return [_fake_embed(t) for t in texts]


class TestRAGPipeline:
    @pytest.fixture
    def pipeline(self, tmp_path):
        vs = VectorStore(tmp_path / "rag.db")
        p = RAGPipeline(
            vector_store=vs,
            embed_fn=_fake_embed,
            embed_batch_fn=_fake_embed_batch,
            store_name="test",
            chunk_size=100,
            chunk_overlap=20,
            top_k=3,
            threshold=0.0,
        )
        yield p
        vs.close()

    def test_ingest_text(self, pipeline):
        count = pipeline.ingest_text("Hello world, this is a test document.", source="test.txt")
        assert count >= 1
        info = pipeline.stats()
        assert info["total_chunks"] >= 1

    def test_ingest_file(self, pipeline, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("This is a test document.\nIt has multiple lines.\n" * 10)
        count = pipeline.ingest_file(f)
        assert count >= 1

    def test_retrieve_returns_results(self, pipeline):
        pipeline.ingest_text("Python is a programming language.", source="python.txt")
        pipeline.ingest_text("Rust is a systems programming language.", source="rust.txt")
        results = pipeline.retrieve("What is Python?")
        assert len(results) >= 1

    def test_augment_prompt(self, pipeline):
        pipeline.ingest_text("AICP is an AI Control Platform.", source="about.txt")
        augmented = pipeline.augment_prompt("What is AICP?")
        assert "Context:" in augmented
        assert "AICP" in augmented
        assert "Question: What is AICP?" in augmented

    def test_augment_prompt_empty_kb(self, pipeline):
        result = pipeline.augment_prompt("What is AICP?")
        # With empty KB, should return the original query
        assert result == "What is AICP?"

    def test_list_sources(self, pipeline):
        pipeline.ingest_text("content a", source="a.txt")
        pipeline.ingest_text("content b", source="b.txt")
        sources = pipeline.list_sources()
        names = {s["source"] for s in sources}
        assert "a.txt" in names
        assert "b.txt" in names

    def test_delete_source(self, pipeline):
        pipeline.ingest_text("content", source="to_delete.txt")
        assert pipeline.stats()["total_chunks"] >= 1
        pipeline.delete_source("to_delete.txt")
        assert pipeline.stats()["total_chunks"] == 0
