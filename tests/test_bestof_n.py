"""Tests for N Completions & Best-of-N Selection (M86)."""

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


def _n_response(texts, finish_reasons=None):
    """Build a mock response with N choices."""
    choices = []
    for i, text in enumerate(texts):
        fr = finish_reasons[i] if finish_reasons else "stop"
        choices.append({
            "index": i,
            "message": {"content": text},
            "finish_reason": fr,
        })
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": choices,
        "usage": {"prompt_tokens": 10, "completion_tokens": 20 * len(texts)},
    }
    return mock_resp


# ── Backend execute_n() ───────────────────────────────────────────────────


class TestExecuteN:
    def test_basic_n_completions(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _n_response(["one", "two", "three"])

        with patch("httpx.post", side_effect=capture_post):
            results = backend.execute_n("test", Mode.THINK, Path("/tmp"), n=3)

        assert len(results) == 3
        assert results[0]["text"] == "one"
        assert results[1]["text"] == "two"
        assert results[2]["text"] == "three"
        assert captured["n"] == 3

    def test_sends_n_parameter(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _n_response(["a"] * 5)

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_n("test", Mode.THINK, Path("/tmp"), n=5)

        assert captured["n"] == 5

    def test_clamps_n_max(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _n_response(["a"])

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_n("test", Mode.THINK, Path("/tmp"), n=50)

        assert captured["n"] == 10

    def test_clamps_n_min(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _n_response(["a"])

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_n("test", Mode.THINK, Path("/tmp"), n=0)

        assert captured["n"] == 1

    def test_default_n_is_3(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _n_response(["a", "b", "c"])

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_n("test", Mode.THINK, Path("/tmp"))

        assert captured["n"] == 3

    def test_preserves_index(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_n_response(["x", "y"])):
            results = backend.execute_n("test", Mode.THINK, Path("/tmp"), n=2)

        assert results[0]["index"] == 0
        assert results[1]["index"] == 1

    def test_finish_reasons(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_n_response(
            ["a", "b"], finish_reasons=["stop", "length"]
        )):
            results = backend.execute_n("test", Mode.THINK, Path("/tmp"), n=2)

        assert results[0]["finish_reason"] == "stop"
        assert results[1]["finish_reason"] == "length"

    def test_seed_passed(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _n_response(["a"])

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_n("test", Mode.THINK, Path("/tmp"), seed=42)

        assert captured["seed"] == 42

    def test_session_seed(self):
        backend = _make_backend()
        backend.seed = 99
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _n_response(["a"])

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_n("test", Mode.THINK, Path("/tmp"))

        assert captured["seed"] == 99

    def test_tracks_usage(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_n_response(["a", "b", "c"])):
            backend.execute_n("test", Mode.THINK, Path("/tmp"))

        assert backend.last_usage["n_completions"] == 3
        assert backend.last_usage["prompt_tokens"] == 10

    def test_uses_chat_completions_endpoint(self):
        backend = _make_backend()
        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return _n_response(["a"])

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_n("test", Mode.THINK, Path("/tmp"))

        assert "/v1/chat/completions" in captured_url["url"]

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.execute_n("test", Mode.THINK, Path("/tmp"))

    def test_timeout_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.execute_n("test", Mode.THINK, Path("/tmp"))

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.execute_n("test", Mode.THINK, Path("/tmp"))

    def test_empty_choices(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [], "usage": {}}

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Unexpected"):
                backend.execute_n("test", Mode.THINK, Path("/tmp"))


# ── MCP: aicp_bestof ──────────────────────────────────────────────────────


class TestMcpBestof:
    def test_returns_json_array(self):
        from aicp.mcp.server import aicp_bestof

        mock_backend = MagicMock()
        mock_backend.execute_n.return_value = [
            {"index": 0, "text": "one", "finish_reason": "stop"},
            {"index": 1, "text": "two", "finish_reason": "stop"},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_bestof("test", n=2)

        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["text"] == "one"

    def test_passes_n(self):
        from aicp.mcp.server import aicp_bestof

        mock_backend = MagicMock()
        mock_backend.execute_n.return_value = [{"index": 0, "text": "x", "finish_reason": "stop"}]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_bestof("test", n=7)

        call_kwargs = mock_backend.execute_n.call_args
        assert call_kwargs.kwargs["n"] == 7

    def test_passes_seed(self):
        from aicp.mcp.server import aicp_bestof

        mock_backend = MagicMock()
        mock_backend.execute_n.return_value = [{"index": 0, "text": "x", "finish_reason": "stop"}]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_bestof("test", seed=42)

        call_kwargs = mock_backend.execute_n.call_args
        assert call_kwargs.kwargs["seed"] == 42


# ── Interactive /bestof ────────────────────────────────────────────────────


class TestInteractiveBestof:
    def test_bestof_with_n(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_n.return_value = [
            {"index": 0, "text": "answer one", "finish_reason": "stop"},
            {"index": 1, "text": "answer two", "finish_reason": "stop"},
            {"index": 2, "text": "answer three", "finish_reason": "stop"},
        ]

        _handle_slash("/bestof 3 Write a haiku", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "answer one" in output
        assert "answer two" in output
        assert "3 completions" in output
        backend.execute_n.assert_called_once_with("Write a haiku", Mode.THINK, Path("/tmp"), n=3)

    def test_bestof_default_n(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_n.return_value = [
            {"index": 0, "text": "x", "finish_reason": "stop"},
        ]

        _handle_slash("/bestof Write something", [], backend, {}, Mode.THINK, Path("/tmp"))

        backend.execute_n.assert_called_once_with("Write something", Mode.THINK, Path("/tmp"), n=3)

    def test_bestof_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/bestof", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_bestof_n_only_no_prompt(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/bestof 5", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_bestof_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/bestof 3 test", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_bestof_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_n.side_effect = RuntimeError("model error")

        _handle_slash("/bestof test prompt", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_bestof_appends_messages(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_n.return_value = [
            {"index": 0, "text": "best answer", "finish_reason": "stop"},
        ]
        messages = []

        _handle_slash("/bestof test prompt", messages, backend, {}, Mode.THINK, Path("/tmp"))

        assert len(messages) == 2
        assert "[Best-of-3]" in messages[0]["content"]
        assert messages[1]["content"] == "best answer"
