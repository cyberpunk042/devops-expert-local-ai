"""Tests for KnowledgeBase wrapper (KB + reranking integration)."""

from unittest.mock import MagicMock

from aicp.core.kb import KnowledgeBase

# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_backend():
    backend = MagicMock()
    backend.embed.return_value = [0.1] * 768
    backend.embed_batch.return_value = [[0.1] * 768]
    backend.rerank.return_value = [
        {"index": 0, "relevance_score": 0.9},
    ]
    return backend


def _config(rerank=True):
    return {
        "rag": {
            "db_path": "/tmp/test_kb.db",
            "store_name": "test",
            "chunk_size": 256,
            "chunk_overlap": 32,
            "top_k": 3,
            "threshold": 0.0,
            "rerank": rerank,
        },
        "backends": {
            "local": {
                "reranker_model": "bge-reranker-v2-m3",
            },
        },
    }


# ── Init tests ───────────────────────────────────────────────────────────────

class TestKBInit:
    def test_creates_kb_from_config(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        kb = KnowledgeBase(_mock_backend(), cfg)
        assert kb._rerank_enabled is True
        assert kb._reranker_model == "bge-reranker-v2-m3"

    def test_rerank_disabled(self, tmp_path):
        cfg = _config(rerank=False)
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        kb = KnowledgeBase(_mock_backend(), cfg)
        assert kb._rerank_enabled is False

    def test_default_config(self, tmp_path):
        cfg = {"rag": {"db_path": str(tmp_path / "kb.db")}, "backends": {}}
        kb = KnowledgeBase(_mock_backend(), cfg)
        assert kb._reranker_model == "bge-reranker-v2-m3"
        assert kb._rerank_enabled is True


# ── Ingest tests ─────────────────────────────────────────────────────────────

class TestKBIngest:
    def test_ingest_file(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        backend = _mock_backend()
        backend.embed_batch.return_value = [[0.1] * 768] * 3

        kb = KnowledgeBase(backend, cfg)
        f = tmp_path / "test.txt"
        f.write_text("Line one.\nLine two.\nLine three.")
        count = kb.ingest_file(f)
        assert count >= 1
        backend.embed_batch.assert_called()

    def test_ingest_text(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        backend = _mock_backend()
        kb = KnowledgeBase(backend, cfg)
        count = kb.ingest_text("Hello world, this is a test.", source="test")
        assert count >= 1

    def test_ingest_directory(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        backend = _mock_backend()
        kb = KnowledgeBase(backend, cfg)

        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text("def foo(): pass")
        (src / "b.md").write_text("# Title\nSome text.")
        (src / "c.bin").write_bytes(b"\x00" * 10)  # not a text ext

        result = kb.ingest_directory(src)
        assert result["files_ingested"] >= 2
        assert result["total_chunks"] >= 2
        assert len(result["errors"]) == 0


# ── Search tests ─────────────────────────────────────────────────────────────

class TestKBSearch:
    def _seeded_kb(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        backend = _mock_backend()
        # Return different embeddings so cosine similarity varies
        backend.embed_batch.side_effect = lambda texts: [
            [float(i) / max(len(texts), 1)] * 768 for i in range(len(texts))
        ]
        backend.embed.return_value = [1.0] * 768

        kb = KnowledgeBase(backend, cfg)
        kb.ingest_text("Python is great for AI.", source="doc1")
        kb.ingest_text("Machine learning uses data.", source="doc2")
        return kb, backend

    def test_search_with_reranking(self, tmp_path):
        kb, backend = self._seeded_kb(tmp_path)
        backend.rerank.return_value = [
            {"index": 0, "relevance_score": 5.0},
        ]
        results = kb.search("AI programming", top_k=2)
        assert len(results) >= 1
        assert results[0]["score"] == 5.0
        backend.rerank.assert_called_once()

    def test_search_without_reranking(self, tmp_path):
        cfg = _config(rerank=False)
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        backend = _mock_backend()
        backend.embed_batch.side_effect = lambda texts: [
            [float(i)] * 768 for i in range(len(texts))
        ]
        backend.embed.return_value = [1.0] * 768

        kb = KnowledgeBase(backend, cfg)
        kb.ingest_text("Test document.", source="doc")
        results = kb.search("test", top_k=2)
        # Should NOT call rerank
        backend.rerank.assert_not_called()
        assert len(results) >= 1

    def test_search_rerank_fallback_on_error(self, tmp_path):
        kb, backend = self._seeded_kb(tmp_path)
        backend.rerank.side_effect = RuntimeError("Reranker unavailable")
        results = kb.search("test")
        # Should fall back to embedding-only results
        assert len(results) >= 1
        # Score should be cosine similarity, not reranker score
        assert all(0 <= r["score"] <= 1 for r in results)

    def test_search_empty_kb(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        kb = KnowledgeBase(_mock_backend(), cfg)
        results = kb.search("anything")
        assert results == []


# ── Augment prompt ───────────────────────────────────────────────────────────

class TestKBAugmentPrompt:
    def test_augment_adds_context(self, tmp_path):
        cfg = _config(rerank=False)
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        backend = _mock_backend()
        backend.embed_batch.return_value = [[1.0] * 768]
        backend.embed.return_value = [1.0] * 768

        kb = KnowledgeBase(backend, cfg)
        kb.ingest_text("Python is a programming language.", source="intro.md")
        result = kb.augment_prompt("What is Python?")
        assert "Context:" in result
        assert "Question: What is Python?" in result

    def test_augment_no_results_returns_query(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        kb = KnowledgeBase(_mock_backend(), cfg)
        result = kb.augment_prompt("What is Python?")
        assert result == "What is Python?"


# ── Management ───────────────────────────────────────────────────────────────

class TestKBManagement:
    def test_list_sources(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        backend = _mock_backend()
        kb = KnowledgeBase(backend, cfg)
        kb.ingest_text("Hello", source="greeting.txt")
        sources = kb.list_sources()
        assert len(sources) == 1
        assert sources[0]["source"] == "greeting.txt"

    def test_delete_source(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        backend = _mock_backend()
        kb = KnowledgeBase(backend, cfg)
        kb.ingest_text("Hello", source="greeting.txt")
        deleted = kb.delete_source("greeting.txt")
        assert deleted >= 1
        assert kb.list_sources() == []

    def test_stats(self, tmp_path):
        cfg = _config()
        cfg["rag"]["db_path"] = str(tmp_path / "kb.db")
        backend = _mock_backend()
        kb = KnowledgeBase(backend, cfg)
        kb.ingest_text("Hello", source="greeting.txt")
        s = kb.stats()
        assert s["total_chunks"] >= 1
        assert s["total_sources"] == 1
