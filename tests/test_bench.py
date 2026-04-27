"""Tests for benchmark observability functions."""

import json
from unittest.mock import MagicMock, patch

from aicp.core.observability import (
    measure_embedding,
    measure_grammar,
    measure_request,
    measure_rerank,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_stream_response(content="OK", status_code=200):
    """Build a mock streaming response for measure_request."""
    mock = MagicMock()
    mock.status_code = status_code
    chunk = json.dumps({
        "choices": [{"delta": {"content": content}}],
    })
    mock.iter_lines.return_value = [f"data: {chunk}", "data: [DONE]"]
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def _mock_json_response(data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = data
    return mock


# ── measure_request tests ────────────────────────────────────────────────────

class TestMeasureRequest:
    def test_returns_timing_data(self):
        mock_resp = _mock_stream_response("OK")
        with patch("httpx.stream", return_value=mock_resp):
            result = measure_request("http://localhost:8090")
        assert "total_ms" in result
        assert "ttft_ms" in result
        assert "tokens_per_sec" in result
        assert result.get("error") is None

    def test_handles_connect_error(self):
        import httpx
        with patch("httpx.stream", side_effect=httpx.ConnectError("refused")):
            result = measure_request("http://localhost:8090")
        assert result.get("error") is not None

    def test_handles_http_error(self):
        mock_resp = _mock_stream_response(status_code=500)
        mock_resp.read.return_value = b"error"
        with patch("httpx.stream", return_value=mock_resp):
            result = measure_request("http://localhost:8090")
        assert result.get("error") is not None


# ── measure_embedding tests ──────────────────────────────────────────────────

class TestMeasureEmbedding:
    def test_returns_dimensions(self):
        mock_resp = _mock_json_response({
            "data": [{"embedding": [0.1] * 768}],
        })
        with patch("httpx.post", return_value=mock_resp):
            result = measure_embedding("http://localhost:8090")
        assert result["dimensions"] == 768
        assert result["total_ms"] >= 0
        assert result.get("error") is None

    def test_handles_error(self):
        mock_resp = _mock_json_response({}, status_code=500)
        with patch("httpx.post", return_value=mock_resp):
            result = measure_embedding("http://localhost:8090")
        assert result.get("error") is not None

    def test_handles_connect_error(self):
        import httpx
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            result = measure_embedding("http://localhost:8090")
        assert result.get("error") is not None


# ── measure_rerank tests ─────────────────────────────────────────────────────

class TestMeasureRerank:
    def test_returns_results(self):
        mock_resp = _mock_json_response({
            "results": [
                {"index": 1, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.3},
            ],
        })
        with patch("httpx.post", return_value=mock_resp):
            result = measure_rerank("http://localhost:8090")
        assert result["documents"] == 5
        assert result["results"] == 2
        assert result["total_ms"] >= 0

    def test_handles_error(self):
        mock_resp = _mock_json_response({}, status_code=500)
        with patch("httpx.post", return_value=mock_resp):
            result = measure_rerank("http://localhost:8090")
        assert result.get("error") is not None


# ── measure_grammar tests ───────────────────────────────────────────────────

class TestMeasureGrammar:
    def test_returns_response(self):
        mock_resp = _mock_json_response({
            "choices": [{"message": {"content": "yes"}}],
        })
        with patch("httpx.post", return_value=mock_resp):
            result = measure_grammar("http://localhost:8090")
        assert result["response"] == "yes"
        assert result["total_ms"] >= 0

    def test_handles_error(self):
        mock_resp = _mock_json_response({}, status_code=400)
        with patch("httpx.post", return_value=mock_resp):
            result = measure_grammar("http://localhost:8090")
        assert result.get("error") is not None
