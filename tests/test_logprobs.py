"""Tests for Logprobs & Token Probabilities (M85)."""

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


def _logprobs_response(text="Hello world", tokens=None, logprobs_data=None):
    """Build a mock chat completions response with logprobs."""
    if tokens is None:
        tokens = ["Hello", " world"]
    if logprobs_data is None:
        logprobs_data = [
            {
                "token": t,
                "logprob": -0.5,
                "top_logprobs": [
                    {"token": t, "logprob": -0.5},
                    {"token": "alt", "logprob": -2.0},
                ],
            }
            for t in tokens
        ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{
            "message": {"content": text},
            "logprobs": {"content": logprobs_data},
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": len(tokens)},
    }
    return mock_resp


# ── Backend execute_logprobs() ─────────────────────────────────────────────


class TestExecuteLogprobs:
    def test_basic_logprobs(self):
        backend = _make_backend()

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            result = backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))

        assert result["text"] == "Hello world"
        assert result["tokens"] == ["Hello", " world"]
        assert len(result["logprobs"]) == 2
        assert result["avg_logprob"] == -0.5

    def test_sends_logprobs_params(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_logprobs("test", Mode.THINK, Path("/tmp"), top_logprobs=10)

        assert captured["logprobs"] is True
        assert captured["top_logprobs"] == 10

    def test_clamps_top_logprobs(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_logprobs("test", Mode.THINK, Path("/tmp"), top_logprobs=50)

        assert captured["top_logprobs"] == 20

    def test_clamps_top_logprobs_minimum(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_logprobs("test", Mode.THINK, Path("/tmp"), top_logprobs=0)

        assert captured["top_logprobs"] == 1

    def test_seed_passed(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_logprobs("test", Mode.THINK, Path("/tmp"), seed=42)

        assert captured["seed"] == 42

    def test_uses_chat_completions_endpoint(self):
        backend = _make_backend()
        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return _logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))

        assert "/v1/chat/completions" in captured_url["url"]

    def test_tracks_usage(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_logprobs_response()):
            backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))

        assert backend.last_usage["logprobs"] is True
        assert backend.last_usage["prompt_tokens"] == 10
        assert backend.last_usage["completion_tokens"] == 2

    def test_avg_logprob_calculation(self):
        backend = _make_backend()
        lp_data = [
            {"token": "a", "logprob": -1.0, "top_logprobs": []},
            {"token": "b", "logprob": -3.0, "top_logprobs": []},
        ]

        with patch("httpx.post", return_value=_logprobs_response(
            text="ab", tokens=["a", "b"], logprobs_data=lp_data
        )):
            result = backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))

        assert result["avg_logprob"] == -2.0

    def test_empty_logprobs(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {"content": "hi"},
                "logprobs": {"content": []},
            }],
            "usage": {},
        }

        with patch("httpx.post", return_value=mock_resp):
            result = backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))

        assert result["text"] == "hi"
        assert result["tokens"] == []
        assert result["avg_logprob"] == 0.0

    def test_no_logprobs_in_response(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {"content": "hi"},
                "logprobs": None,
            }],
            "usage": {},
        }

        with patch("httpx.post", return_value=mock_resp):
            result = backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))

        assert result["text"] == "hi"
        assert result["tokens"] == []
        assert result["avg_logprob"] == 0.0

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))

    def test_timeout_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))

    def test_unexpected_response(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"bad": "format"}

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Unexpected"):
                backend.execute_logprobs("test", Mode.THINK, Path("/tmp"))


# ── MCP: aicp_logprobs ────────────────────────────────────────────────────


class TestMcpLogprobs:
    def test_returns_json(self):
        from aicp.mcp.server import aicp_logprobs

        mock_backend = MagicMock()
        mock_backend.execute_logprobs.return_value = {
            "text": "hello",
            "tokens": ["hello"],
            "logprobs": [{"token": "hello", "logprob": -0.5}],
            "avg_logprob": -0.5,
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_logprobs("test")

        parsed = json.loads(result)
        assert parsed["text"] == "hello"
        assert parsed["avg_logprob"] == -0.5

    def test_passes_top_logprobs(self):
        from aicp.mcp.server import aicp_logprobs

        mock_backend = MagicMock()
        mock_backend.execute_logprobs.return_value = {
            "text": "x", "tokens": [], "logprobs": [], "avg_logprob": 0,
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_logprobs("test", top_logprobs=10)

        call_kwargs = mock_backend.execute_logprobs.call_args
        assert call_kwargs.kwargs["top_logprobs"] == 10

    def test_passes_seed(self):
        from aicp.mcp.server import aicp_logprobs

        mock_backend = MagicMock()
        mock_backend.execute_logprobs.return_value = {
            "text": "x", "tokens": [], "logprobs": [], "avg_logprob": 0,
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_logprobs("test", seed=42)

        call_kwargs = mock_backend.execute_logprobs.call_args
        assert call_kwargs.kwargs["seed"] == 42

    def test_no_seed(self):
        from aicp.mcp.server import aicp_logprobs

        mock_backend = MagicMock()
        mock_backend.execute_logprobs.return_value = {
            "text": "x", "tokens": [], "logprobs": [], "avg_logprob": 0,
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_logprobs("test")

        call_kwargs = mock_backend.execute_logprobs.call_args
        assert call_kwargs.kwargs["seed"] is None


# ── Interactive /logprobs ──────────────────────────────────────────────────


class TestInteractiveLogprobs:
    def test_logprobs_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_logprobs.return_value = {
            "text": "Hello world",
            "tokens": ["Hello", " world"],
            "logprobs": [
                {"token": "Hello", "logprob": -0.5, "top_logprobs": [
                    {"token": "Hello", "logprob": -0.5},
                ]},
                {"token": " world", "logprob": -0.8, "top_logprobs": [
                    {"token": " world", "logprob": -0.8},
                ]},
            ],
            "avg_logprob": -0.65,
        }

        _handle_slash("/logprobs Say hello", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "Hello world" in output
        assert "Avg logprob" in output
        assert "-0.65" in output

    def test_logprobs_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/logprobs", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_logprobs_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/logprobs test", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_logprobs_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_logprobs.side_effect = RuntimeError("model error")

        _handle_slash("/logprobs test", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_logprobs_appends_messages(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_logprobs.return_value = {
            "text": "hi",
            "tokens": ["hi"],
            "logprobs": [{"token": "hi", "logprob": -0.1, "top_logprobs": []}],
            "avg_logprob": -0.1,
        }
        messages = []

        _handle_slash("/logprobs test", messages, backend, {}, Mode.THINK, Path("/tmp"))

        assert len(messages) == 2
        assert "[Logprobs]" in messages[0]["content"]
