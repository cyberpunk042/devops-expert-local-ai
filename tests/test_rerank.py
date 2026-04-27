"""Tests for reranking (backend + MCP tool)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from aicp.backends.localai import LocalAIBackend

# ── Helpers ──────────────────────────────────────────────────────────────────

def _backend(**kwargs) -> LocalAIBackend:
    return LocalAIBackend(
        base_url="http://localhost:8090",
        model="hermes",
        **kwargs,
    )


SAMPLE_DOCS = [
    "Python is a programming language.",
    "The weather in Paris is sunny today.",
    "Machine learning requires large datasets.",
    "Cats are popular pets worldwide.",
]


# ── Backend rerank() tests ────────────────────────────────────────────────────

class TestRerank:
    def test_rerank_returns_sorted_results(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.3},
                {"index": 2, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.1},
                {"index": 3, "relevance_score": 0.05},
            ]
        }
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            results = backend.rerank("programming", SAMPLE_DOCS)

        assert len(results) == 4
        assert results[0]["index"] == 2
        assert results[0]["relevance_score"] == 0.9
        assert results[1]["index"] == 0
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["model"] == "bge-reranker-v2-m3"
        assert payload["query"] == "programming"
        assert len(payload["documents"]) == 4

    def test_rerank_with_top_n(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"index": 2, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.3},
            ]
        }
        with patch("httpx.post", return_value=mock_resp):
            results = backend.rerank("programming", SAMPLE_DOCS, top_n=2)

        assert len(results) == 2

    def test_rerank_custom_model(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.rerank("test", ["doc"], model="custom-reranker")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["model"] == "custom-reranker"

    def test_rerank_http_error(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Rerank error"):
                backend.rerank("test", ["doc"])

    def test_rerank_connect_error(self):
        backend = _backend()
        import httpx
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.rerank("test", ["doc"])

    def test_rerank_timeout(self):
        backend = _backend()
        import httpx
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.rerank("test", ["doc"])

    def test_rerank_sets_last_usage(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"index": 0, "relevance_score": 0.5}]}
        with patch("httpx.post", return_value=mock_resp):
            backend.rerank("test", SAMPLE_DOCS)

        assert backend.last_usage["reranking"] is True
        assert backend.last_usage["documents"] == 4

    def test_rerank_empty_results(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        with patch("httpx.post", return_value=mock_resp):
            results = backend.rerank("test", [])

        assert results == []


# ── MCP tool tests ────────────────────────────────────────────────────────────

class TestAicpRerank:
    def test_mcp_rerank_returns_json(self):
        from aicp.mcp.server import aicp_rerank

        backend = MagicMock()
        backend.base_url = "http://localhost:8090"
        backend.rerank.return_value = [
            {"index": 1, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.3},
        ]
        config = {"backends": {"local": {"reranker_model": "bge-reranker-v2-m3"}}}

        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=backend),
            _config=config,
        ):
            result = aicp_rerank("programming", SAMPLE_DOCS, top_n=2)

        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["relevance_score"] == 0.9
        assert parsed[0]["document"] == SAMPLE_DOCS[1]
        assert parsed[1]["document"] == SAMPLE_DOCS[0]

    def test_mcp_rerank_uses_config_model(self):
        from aicp.mcp.server import aicp_rerank

        backend = MagicMock()
        backend.base_url = "http://localhost:8090"
        backend.rerank.return_value = []
        config = {"backends": {"local": {"reranker_model": "my-reranker"}}}

        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=backend),
            _config=config,
        ):
            aicp_rerank("test", ["doc"])

        backend.rerank.assert_called_once_with("test", ["doc"], model="my-reranker", top_n=5)

    def test_mcp_rerank_default_model(self):
        from aicp.mcp.server import aicp_rerank

        backend = MagicMock()
        backend.base_url = "http://localhost:8090"
        backend.rerank.return_value = []
        config = {"backends": {"local": {}}}

        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=backend),
            _config=config,
        ):
            aicp_rerank("test", ["doc"])

        backend.rerank.assert_called_once_with("test", ["doc"], model="bge-reranker-v2-m3", top_n=5)
