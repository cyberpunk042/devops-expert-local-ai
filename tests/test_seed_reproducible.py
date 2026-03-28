"""Tests for Seed & Reproducible Inference (M84)."""

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


def _mock_chat_response(content="hello"):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5},
    }
    return mock_resp


# ── Backend: execute() with seed ──────────────────────────────────────────


class TestExecuteSeed:
    def test_per_call_seed(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_chat_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute("test", Mode.THINK, Path("/tmp"), seed=42)

        assert captured["seed"] == 42

    def test_session_seed(self):
        backend = _make_backend()
        backend.seed = 123
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_chat_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute("test", Mode.THINK, Path("/tmp"))

        assert captured["seed"] == 123

    def test_per_call_overrides_session(self):
        backend = _make_backend()
        backend.seed = 100
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_chat_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute("test", Mode.THINK, Path("/tmp"), seed=42)

        assert captured["seed"] == 42

    def test_no_seed_by_default(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_chat_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute("test", Mode.THINK, Path("/tmp"))

        assert "seed" not in captured

    def test_seed_zero_is_valid(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_chat_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute("test", Mode.THINK, Path("/tmp"), seed=0)

        assert captured["seed"] == 0


# ── Backend: execute_stream() with seed ───────────────────────────────────


class TestExecuteStreamSeed:
    def test_seed_in_stream_payload(self):
        backend = _make_backend()
        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = ['data: {"choices":[{"delta":{"content":"hi"}}]}', "data: [DONE]"]

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_resp)
        ctx.__exit__ = MagicMock(return_value=False)

        def capture_stream(method, url, json=None, **kw):
            captured.update(json or {})
            return ctx

        with patch("httpx.stream", side_effect=capture_stream):
            chunks = list(backend.execute_stream("test", Mode.THINK, Path("/tmp"), seed=77))

        assert captured["seed"] == 77

    def test_session_seed_in_stream(self):
        backend = _make_backend()
        backend.seed = 55
        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = ["data: [DONE]"]

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_resp)
        ctx.__exit__ = MagicMock(return_value=False)

        def capture_stream(method, url, json=None, **kw):
            captured.update(json or {})
            return ctx

        with patch("httpx.stream", side_effect=capture_stream):
            list(backend.execute_stream("test", Mode.THINK, Path("/tmp")))

        assert captured["seed"] == 55


# ── Backend: execute_json() with seed ─────────────────────────────────────


class TestExecuteJsonSeed:
    def test_seed_in_json_mode(self):
        backend = _make_backend()
        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"x": 1}'}}],
            "usage": {},
        }

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_json("test", Mode.THINK, Path("/tmp"), seed=99)

        assert captured["seed"] == 99

    def test_session_seed_in_json_mode(self):
        backend = _make_backend()
        backend.seed = 33
        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"x": 1}'}}],
            "usage": {},
        }

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_json("test", Mode.THINK, Path("/tmp"))

        assert captured["seed"] == 33


# ── Backend: infill() with seed ───────────────────────────────────────────


class TestInfillSeed:
    def test_seed_in_infill(self):
        backend = _make_backend()
        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "filled"}],
            "usage": {},
        }

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.infill("prefix", "suffix", seed=88)

        assert captured["seed"] == 88

    def test_session_seed_in_infill(self):
        backend = _make_backend()
        backend.seed = 44
        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "x"}],
            "usage": {},
        }

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.infill("a", "b")

        assert captured["seed"] == 44


# ── Session seed property ─────────────────────────────────────────────────


class TestSessionSeed:
    def test_default_seed_is_none(self):
        backend = _make_backend()
        assert backend.seed is None

    def test_set_and_clear_seed(self):
        backend = _make_backend()
        backend.seed = 42
        assert backend.seed == 42
        backend.seed = None
        assert backend.seed is None


# ── MCP: aicp_seed ────────────────────────────────────────────────────────


class TestMcpSeed:
    def test_set_seed(self):
        from aicp.mcp.server import aicp_seed

        mock_backend = MagicMock()
        mock_backend.seed = None

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_seed(42)

        assert mock_backend.seed == 42
        assert "42" in result

    def test_clear_seed(self):
        from aicp.mcp.server import aicp_seed

        mock_backend = MagicMock()
        mock_backend.seed = 42

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_seed(-1)

        assert mock_backend.seed is None
        assert "cleared" in result.lower()

    def test_chat_with_seed(self):
        from aicp.mcp.server import aicp_chat

        mock_backend = MagicMock()
        mock_backend.execute.return_value = "response"

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_chat("test", seed=42)

        mock_backend.execute.assert_called_once()
        call_kwargs = mock_backend.execute.call_args
        assert call_kwargs.kwargs["seed"] == 42

    def test_chat_no_seed(self):
        from aicp.mcp.server import aicp_chat

        mock_backend = MagicMock()
        mock_backend.execute.return_value = "response"

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_chat("test")

        call_kwargs = mock_backend.execute.call_args
        assert call_kwargs.kwargs["seed"] is None

    def test_json_with_seed(self):
        from aicp.mcp.server import aicp_json

        mock_backend = MagicMock()
        mock_backend.execute_json.return_value = {"x": 1}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_json("test", seed=77)

        call_kwargs = mock_backend.execute_json.call_args
        assert call_kwargs.kwargs["seed"] == 77


# ── Interactive /seed ──────────────────────────────────────────────────────


class TestInteractiveSeed:
    def test_set_seed(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.seed = None

        _handle_slash("/seed 42", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "42" in output
        assert backend.seed == 42

    def test_clear_seed(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.seed = 42

        _handle_slash("/seed clear", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "cleared" in output.lower()
        assert backend.seed is None

    def test_clear_seed_none(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.seed = 42

        _handle_slash("/seed none", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "cleared" in output.lower()
        assert backend.seed is None

    def test_clear_seed_random(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.seed = 42

        _handle_slash("/seed random", [], backend, {}, Mode.THINK, Path("/tmp"))

        assert backend.seed is None

    def test_seed_no_arg_clears(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.seed = 42

        _handle_slash("/seed", [], backend, {}, Mode.THINK, Path("/tmp"))

        assert backend.seed is None

    def test_seed_invalid_value(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()

        _handle_slash("/seed abc", [], backend, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "integer" in err.lower()

    def test_seed_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/seed 42", [], None, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "backend" in err.lower()
