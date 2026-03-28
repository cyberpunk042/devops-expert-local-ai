"""Tests for Tokenization & Detokenization (M94)."""

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


def _detokenize_response(text="Hello world"):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"content": text}
    return mock_resp


def _tokenize_response(tokens=None):
    if tokens is None:
        tokens = [15496, 995]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"tokens": tokens}
    return mock_resp


# ── Backend detokenize() ─────────────────────────────────────────────────


class TestDetokenize:
    def test_basic(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_detokenize_response("Hello")):
            result = backend.detokenize([15496])

        assert result == "Hello"

    def test_uses_detokenize_endpoint(self):
        backend = _make_backend()
        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return _detokenize_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.detokenize([1, 2, 3])

        assert "/v1/detokenize" in captured_url["url"]

    def test_sends_tokens(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _detokenize_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.detokenize([100, 200, 300])

        assert captured["tokens"] == [100, 200, 300]

    def test_sends_model(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _detokenize_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.detokenize([1], model="codellama")

        assert captured["model"] == "codellama"

    def test_default_model(self):
        backend = _make_backend(model="hermes")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _detokenize_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.detokenize([1])

        assert captured["model"] == "hermes"

    def test_tracks_usage(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_detokenize_response()):
            backend.detokenize([1, 2, 3])

        assert backend.last_usage["detokenize"] is True
        assert backend.last_usage["token_count"] == 3

    def test_empty_tokens(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_detokenize_response("")):
            result = backend.detokenize([])

        assert result == ""

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.detokenize([1])

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.detokenize([1])

    def test_text_key_fallback(self):
        """Some backends return 'text' instead of 'content'."""
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "fallback"}

        with patch("httpx.post", return_value=mock_resp):
            result = backend.detokenize([1])

        assert result == "fallback"


# ── Backend token_count() ────────────────────────────────────────────────


class TestTokenCount:
    def test_basic(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_tokenize_response([1, 2, 3])):
            count = backend.token_count("Hello world")

        assert count == 3

    def test_empty_text(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_tokenize_response([])):
            count = backend.token_count("")

        assert count == 0

    def test_custom_model(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _tokenize_response([1])

        with patch("httpx.post", side_effect=capture_post):
            backend.token_count("test", model="codellama")

        assert captured["model"] == "codellama"

    def test_returns_int(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_tokenize_response([1, 2])):
            count = backend.token_count("hi")

        assert isinstance(count, int)


# ── MCP: aicp_detokenize ─────────────────────────────────────────────────


class TestMcpDetokenize:
    def test_returns_json(self):
        from aicp.mcp.server import aicp_detokenize

        mock_backend = MagicMock()
        mock_backend.detokenize.return_value = "Hello world"

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_detokenize("[100, 200]")

        parsed = json.loads(result)
        assert parsed["text"] == "Hello world"
        assert parsed["token_count"] == 2

    def test_passes_model(self):
        from aicp.mcp.server import aicp_detokenize

        mock_backend = MagicMock()
        mock_backend.detokenize.return_value = ""

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_detokenize("[1]", model="codellama")

        mock_backend.detokenize.assert_called_once_with([1], model="codellama")

    def test_empty_model_passes_none(self):
        from aicp.mcp.server import aicp_detokenize

        mock_backend = MagicMock()
        mock_backend.detokenize.return_value = ""

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_detokenize("[1]", model="")

        mock_backend.detokenize.assert_called_once_with([1], model=None)


# ── MCP: aicp_token_count ────────────────────────────────────────────────


class TestMcpTokenCount:
    def test_returns_json(self):
        from aicp.mcp.server import aicp_token_count

        mock_backend = MagicMock()
        mock_backend.token_count.return_value = 5

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_token_count("Hello world")

        parsed = json.loads(result)
        assert parsed["count"] == 5
        assert parsed["text_length"] == 11

    def test_passes_model(self):
        from aicp.mcp.server import aicp_token_count

        mock_backend = MagicMock()
        mock_backend.token_count.return_value = 1

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_token_count("hi", model="codellama")

        mock_backend.token_count.assert_called_once_with("hi", model="codellama")


# ── Interactive /detokenize ──────────────────────────────────────────────


class TestInteractiveDetokenize:
    def test_basic(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.detokenize.return_value = "Hello world"

        _handle_slash("/detokenize 100 200 300", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "Hello world" in output
        assert "3 tokens" in output

    def test_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/detokenize", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_invalid_ids(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/detokenize abc def", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "integer" in err.lower()

    def test_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/detokenize 100", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.detokenize.side_effect = RuntimeError("failed")

        _handle_slash("/detokenize 100", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()


# ── Interactive /token-count ─────────────────────────────────────────────


class TestInteractiveTokenCount:
    def test_basic(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.token_count.return_value = 7

        _handle_slash("/token-count Hello world how are you doing today", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "7" in output

    def test_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/token-count", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/token-count hello", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.token_count.side_effect = RuntimeError("failed")

        _handle_slash("/token-count hello", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()
