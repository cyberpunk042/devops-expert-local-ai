"""Tests for LightRAG unified search."""

from unittest.mock import MagicMock, patch

from aicp.core.lightrag import LightRAG


def _mock_kb(results=None):
    kb = MagicMock()
    if results is not None:
        kb.search.return_value = results
    else:
        kb.search.return_value = [
            {"text": "Python is a language", "source": "docs/python.md", "chunk_index": 0, "score": 0.85},
            {"text": "Flask is a framework", "source": "docs/flask.md", "chunk_index": 0, "score": 0.72},
        ]
    kb.list_sources.return_value = [
        {"source": "docs/python.md", "chunks": 5, "added": 1000},
    ]
    kb._pipeline = MagicMock()
    kb._pipeline.store_name = "default"
    kb._pipeline.store._conn = MagicMock()
    return kb


def _mock_store(results=None):
    store = MagicMock()
    store.recall.return_value = results or [
        {"value": "memory: agent was deployed", "similarity": 0.9},
    ]
    store.backend = MagicMock()
    store.store = MagicMock()
    store.store.base_url = "http://localhost:8090"
    store.store.api_key = ""
    return store


def test_search_kb_only():
    kb = _mock_kb()
    rag = LightRAG(kb=kb)
    results = rag.search("what is python", sources=["kb"])
    assert len(results) == 2
    assert results[0]["source_type"] == "kb"
    kb.search.assert_called_once()


def test_search_stores_only():
    store = _mock_store()
    rag = LightRAG(kb=None, embedding_store=store)
    results = rag.search("deployment", sources=["stores"])
    assert len(results) == 1
    assert results[0]["source_type"] == "stores"
    store.recall.assert_called_once()


def test_search_both_sources():
    kb = _mock_kb()
    store = _mock_store()
    rag = LightRAG(kb=kb, embedding_store=store)
    results = rag.search("python deployment")
    assert len(results) == 3  # 2 from KB + 1 from stores


def test_search_with_reranking():
    kb = _mock_kb()
    backend = MagicMock()
    backend.rerank.return_value = [
        {"index": 1, "relevance_score": 0.95},  # flask
        {"index": 0, "relevance_score": 0.80},  # python
    ]
    rag = LightRAG(kb=kb, backend=backend, config={"rag": {"rerank": True}})
    results = rag.search("framework", top_k=1, sources=["kb"])
    # Reranker re-ordered: flask first (index 1 has higher score)
    assert results[0]["text"] == "Flask is a framework"
    backend.rerank.assert_called_once()


def test_search_rerank_fallback():
    """If reranker fails, fall back to score-sorted results."""
    kb = _mock_kb()
    backend = MagicMock()
    backend.rerank.side_effect = RuntimeError("reranker down")
    rag = LightRAG(kb=kb, backend=backend, config={"rag": {"rerank": True}})
    results = rag.search("python", sources=["kb"])
    assert len(results) == 2  # still returns results


def test_augment_prompt():
    kb = _mock_kb()
    rag = LightRAG(kb=kb)
    prompt = rag.augment_prompt("what is python", sources=["kb"])
    assert "Context:" in prompt
    assert "Question: what is python" in prompt
    assert "python.md" in prompt


def test_augment_empty():
    kb = _mock_kb(results=[])
    rag = LightRAG(kb=kb)
    prompt = rag.augment_prompt("hello", sources=["kb"])
    assert prompt == "hello"


def test_stats():
    kb = _mock_kb()
    store = _mock_store()
    rag = LightRAG(kb=kb, embedding_store=store)
    stats = rag.stats()
    assert "kb" in stats["sources"]
    assert "stores" in stats["sources"]
    assert stats["rerank_enabled"] is True


def test_stats_no_stores():
    kb = _mock_kb()
    rag = LightRAG(kb=kb)
    stats = rag.stats()
    assert stats["stores"]["available"] is False
