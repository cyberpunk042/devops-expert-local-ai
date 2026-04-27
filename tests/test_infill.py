"""Tests for Fill-in-the-Middle (FIM) code completion (M80)."""

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


# ── Backend infill() ────────────────────────────────────────────────────────


class TestInfill:
    def test_basic_infill(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            result = backend.infill("def fibonacci(n):", "print(fibonacci(10))")

        assert "fibonacci" in result
        assert captured["prompt"] == "def fibonacci(n):"
        assert captured["suffix"] == "print(fibonacci(10))"

    def test_uses_code_model(self):
        backend = _make_backend(code_model="codellama")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "filled"}], "usage": {}}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.infill("prefix", "suffix")

        assert captured["model"] == "codellama"

    def test_explicit_model_override(self):
        backend = _make_backend(code_model="codellama")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "filled"}], "usage": {}}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.infill("prefix", "suffix", model="custom-model")

        assert captured["model"] == "custom-model"

    def test_falls_back_to_default_model(self):
        backend = _make_backend()  # no code_model

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "ok"}], "usage": {}}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.infill("a", "b")

        assert captured["model"] == "hermes"

    def test_max_tokens(self):
        backend = _make_backend()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "x"}], "usage": {}}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.infill("a", "b", max_tokens=512)

        assert captured["max_tokens"] == 512

    def test_stop_sequences(self):
        backend = _make_backend()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "x"}], "usage": {}}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.infill("a", "b", stop=["\n\n"])

        assert captured["stop"] == ["\n\n"]

    def test_no_stop_by_default(self):
        backend = _make_backend()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "x"}], "usage": {}}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.infill("a", "b")

        assert "stop" not in captured

    def test_tracks_usage(self):
        backend = _make_backend(code_model="codellama")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "filled"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 10},
        }

        with patch("httpx.post", return_value=mock_resp):
            backend.infill("a", "b")

        assert backend.last_usage["infill"] is True
        assert backend.last_usage["model"] == "codellama"
        assert backend.last_usage["prompt_tokens"] == 5
        assert backend.last_usage["completion_tokens"] == 10

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.infill("a", "b")

    def test_timeout_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.infill("a", "b")

    def test_http_error(self):
        backend = _make_backend()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "internal error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.infill("a", "b")

    def test_uses_completions_endpoint(self):
        backend = _make_backend()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "x"}], "usage": {}}

        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.infill("a", "b")

        assert "/v1/completions" in captured_url["url"]


# ── Interactive /infill ─────────────────────────────────────────────────────


class TestInteractiveInfill:
    def test_infill_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.infill.return_value = "    return n * 2\n"

        _handle_slash("/infill def double(n): | print(double(5))", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "return n * 2" in output
        backend.infill.assert_called_once_with("def double(n):", "print(double(5))")

    def test_infill_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/infill", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_infill_no_pipe(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/infill just text no pipe", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_infill_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/infill a | b", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_infill_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.infill.side_effect = RuntimeError("model not available")

        _handle_slash("/infill a | b", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()


# ── MCP: aicp_infill ───────────────────────────────────────────────────────


class TestMcpInfill:
    def test_returns_infill_text(self):
        from aicp.mcp.server import aicp_infill

        mock_backend = MagicMock()
        mock_backend.infill.return_value = "    pass\n"

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_infill("def foo():", "foo()")

        assert result == "    pass\n"
        mock_backend.infill.assert_called_once_with("def foo():", "foo()", max_tokens=256)

    def test_custom_max_tokens(self):
        from aicp.mcp.server import aicp_infill

        mock_backend = MagicMock()
        mock_backend.infill.return_value = "x"

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_infill("a", "b", max_tokens=1024)

        mock_backend.infill.assert_called_once_with("a", "b", max_tokens=1024)
