"""Tests for Embeddings with Type Parameter (M88)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode


def _make_backend(**kwargs) -> LocalAIBackend:
    defaults = dict(
        base_url="http://localhost:8090",
        model="hermes",
        max_tokens=256,
        api_key="",
    )
    defaults.update(kwargs)
    return LocalAIBackend(**defaults)


def _embed_response(vec=None, count=1):
    """Build a mock embeddings response."""
    if vec is None:
        vec = [0.1] * 384
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"embedding": vec}] * count,
    }
    return mock_resp


# ── Backend embed_typed() ───────────���─────────────────────────────────────


class TestEmbedTyped:
    def test_query_type(self):
        backend = _make_backend(embedding_model="nomic")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _embed_response()

        with patch("httpx.post", side_effect=capture_post):
            vec = backend.embed_typed("what is AI?", embed_type="query")

        assert len(vec) == 384
        assert captured["type"] == "query"
        assert captured["model"] == "nomic"
        assert captured["input"] == "what is AI?"

    def test_document_type(self):
        backend = _make_backend(embedding_model="nomic")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _embed_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_typed("AI is artificial intelligence.", embed_type="document")

        assert captured["type"] == "document"

    def test_invalid_type(self):
        backend = _make_backend()

        with pytest.raises(ValueError, match="query.*document"):
            backend.embed_typed("test", embed_type="invalid")

    def test_uses_embedding_model(self):
        backend = _make_backend(embedding_model="bge-small")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _embed_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_typed("test", embed_type="query")

        assert captured["model"] == "bge-small"

    def test_model_override(self):
        backend = _make_backend(embedding_model="nomic")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _embed_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_typed("test", embed_type="query", model="custom-embed")

        assert captured["model"] == "custom-embed"

    def test_falls_back_to_default_model(self):
        backend = _make_backend()  # no embedding_model
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _embed_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_typed("test", embed_type="query")

        assert captured["model"] == "hermes"

    def test_uses_embeddings_endpoint(self):
        backend = _make_backend()
        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return _embed_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_typed("test", embed_type="query")

        assert "/v1/embeddings" in captured_url["url"]

    def test_tracks_usage(self):
        backend = _make_backend(embedding_model="nomic")

        with patch("httpx.post", return_value=_embed_response()):
            backend.embed_typed("test", embed_type="query")

        assert backend.last_usage["embedding_typed"] is True
        assert backend.last_usage["type"] == "query"
        assert backend.last_usage["model"] == "nomic"

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.embed_typed("test", embed_type="query")

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.embed_typed("test", embed_type="query")


# ── Backend embed_typed_batch() ───────────────────────────────────────────


class TestEmbedTypedBatch:
    def test_batch_document_embeddings(self):
        backend = _make_backend(embedding_model="nomic")
        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"embedding": [0.1] * 384},
                {"embedding": [0.2] * 384},
                {"embedding": [0.3] * 384},
            ],
        }

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            vecs = backend.embed_typed_batch(
                ["doc one", "doc two", "doc three"],
                embed_type="document",
            )

        assert len(vecs) == 3
        assert captured["type"] == "document"
        assert captured["input"] == ["doc one", "doc two", "doc three"]

    def test_batch_query_type(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _embed_response(count=2)

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_typed_batch(["q1", "q2"], embed_type="query")

        assert captured["type"] == "query"

    def test_batch_invalid_type(self):
        backend = _make_backend()

        with pytest.raises(ValueError, match="query.*document"):
            backend.embed_typed_batch(["test"], embed_type="passage")

    def test_batch_tracks_usage(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_embed_response(count=3)):
            backend.embed_typed_batch(["a", "b", "c"], embed_type="document")

        assert backend.last_usage["embedding_typed"] is True
        assert backend.last_usage["count"] == 3

    def test_batch_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.embed_typed_batch(["test"], embed_type="document")

    def test_batch_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="400"):
                backend.embed_typed_batch(["test"], embed_type="document")


# ── MCP: aicp_embed_typed ──────��────────────────────────��─────────────────


class TestMcpEmbedTyped:
    def test_returns_json(self):
        from aicp.mcp.server import aicp_embed_typed

        mock_backend = MagicMock()
        mock_backend.embed_typed.return_value = [0.1] * 768

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_embed_typed("test query", embed_type="query")

        parsed = json.loads(result)
        assert parsed["type"] == "query"
        assert parsed["dimensions"] == 768
        assert len(parsed["embedding"]) == 10  # truncated

    def test_document_type(self):
        from aicp.mcp.server import aicp_embed_typed

        mock_backend = MagicMock()
        mock_backend.embed_typed.return_value = [0.1] * 384

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_embed_typed("test doc", embed_type="document")

        mock_backend.embed_typed.assert_called_once_with("test doc", embed_type="document")


class TestMcpEmbedTypedBatch:
    def test_returns_json(self):
        from aicp.mcp.server import aicp_embed_typed_batch

        mock_backend = MagicMock()
        mock_backend.embed_typed_batch.return_value = [[0.1] * 384, [0.2] * 384]

        texts = json.dumps(["doc one", "doc two"])

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_embed_typed_batch(texts, embed_type="document")

        parsed = json.loads(result)
        assert parsed["count"] == 2
        assert parsed["type"] == "document"
        assert parsed["dimensions"] == 384


# ── Interactive /embed-typed ──────────────────────────────────────���───────


class TestInteractiveEmbedTyped:
    def test_query_embedding(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.embed_typed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

        _handle_slash("/embed-typed query What is AI?", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "query" in output.lower()
        assert "Dimensions: 5" in output

    def test_short_type_q(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.embed_typed.return_value = [0.1] * 10

        _handle_slash("/embed-typed q search text", [], backend, {}, Mode.THINK, Path("/tmp"))

        backend.embed_typed.assert_called_once_with("search text", embed_type="query")

    def test_short_type_d(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.embed_typed.return_value = [0.1] * 10

        _handle_slash("/embed-typed d document text here", [], backend, {}, Mode.THINK, Path("/tmp"))

        backend.embed_typed.assert_called_once_with("document text here", embed_type="document")

    def test_invalid_type(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/embed-typed xyz some text", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Unknown" in err

    def test_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/embed-typed", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_type_only_no_text(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/embed-typed q", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/embed-typed q test", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.embed_typed.side_effect = RuntimeError("model error")

        _handle_slash("/embed-typed q test", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()
