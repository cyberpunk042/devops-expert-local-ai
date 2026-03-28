"""Tests for JSON Mode & Structured Output (M83)."""

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


# ── Backend execute_json() ─────────────────────────────────────────────────


class TestExecuteJson:
    def test_basic_json_response(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"name": "Earth", "diameter_km": 12742}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15},
        }

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            result = backend.execute_json("Name the largest planet", Mode.THINK, Path("/tmp"))

        assert result == {"name": "Earth", "diameter_km": 12742}
        assert captured["response_format"] == {"type": "json_object"}

    def test_sends_response_format(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {},
        }

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_json("test", Mode.THINK, Path("/tmp"))

        assert captured["response_format"] == {"type": "json_object"}

    def test_with_schema(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"name": "Mars", "moons": 2}'}}],
            "usage": {},
        }

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "moons": {"type": "integer"},
            },
        }

        with patch("httpx.post", side_effect=capture_post):
            result = backend.execute_json("Info about Mars", Mode.THINK, Path("/tmp"), schema=schema)

        assert result["moons"] == 2
        # Schema should appear in the system message
        system_msg = captured["messages"][0]["content"]
        assert "json" in system_msg.lower() or "schema" in system_msg.lower()

    def test_uses_chat_completions_endpoint(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"x": 1}'}}],
            "usage": {},
        }

        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_json("test", Mode.THINK, Path("/tmp"))

        assert "/v1/chat/completions" in captured_url["url"]

    def test_tracks_usage(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"a": 1}'}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 8},
        }

        with patch("httpx.post", return_value=mock_resp):
            backend.execute_json("test", Mode.THINK, Path("/tmp"))

        assert backend.last_usage["json_mode"] is True
        assert backend.last_usage["prompt_tokens"] == 5
        assert backend.last_usage["completion_tokens"] == 8

    def test_invalid_json_from_model(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "not valid json {{"}}],
            "usage": {},
        }

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="invalid JSON"):
                backend.execute_json("test", Mode.THINK, Path("/tmp"))

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.execute_json("test", Mode.THINK, Path("/tmp"))

    def test_timeout_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.execute_json("test", Mode.THINK, Path("/tmp"))

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.execute_json("test", Mode.THINK, Path("/tmp"))

    def test_mode_sampling(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"x": 1}'}}],
            "usage": {},
        }

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_json("test", Mode.ACT, Path("/tmp"))

        # Act mode should have lower temperature
        assert captured["temperature"] <= 0.2

    def test_returns_nested_json(self):
        backend = _make_backend()
        nested = {"planets": [{"name": "Earth", "moons": [{"name": "Moon"}]}]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(nested)}}],
            "usage": {},
        }

        with patch("httpx.post", return_value=mock_resp):
            result = backend.execute_json("planets", Mode.THINK, Path("/tmp"))

        assert result["planets"][0]["moons"][0]["name"] == "Moon"

    def test_unexpected_response_format(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"bad": "response"}  # no choices

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Unexpected"):
                backend.execute_json("test", Mode.THINK, Path("/tmp"))


# ── MCP: aicp_json ────────────────────────────────────────────────────────


class TestMcpJson:
    def test_returns_json_string(self):
        from aicp.mcp.server import aicp_json

        mock_backend = MagicMock()
        mock_backend.execute_json.return_value = {"answer": 42}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_json("What is the answer?")

        parsed = json.loads(result)
        assert parsed["answer"] == 42

    def test_passes_schema(self):
        from aicp.mcp.server import aicp_json

        mock_backend = MagicMock()
        mock_backend.execute_json.return_value = {"x": 1}

        schema_str = '{"type": "object", "properties": {"x": {"type": "integer"}}}'

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_json("test", schema=schema_str)

        call_kwargs = mock_backend.execute_json.call_args
        assert call_kwargs.kwargs["schema"] == json.loads(schema_str)

    def test_no_schema(self):
        from aicp.mcp.server import aicp_json

        mock_backend = MagicMock()
        mock_backend.execute_json.return_value = {"x": 1}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_json("test")

        call_kwargs = mock_backend.execute_json.call_args
        assert call_kwargs.kwargs["schema"] is None

    def test_mode_passed(self):
        from aicp.mcp.server import aicp_json

        mock_backend = MagicMock()
        mock_backend.execute_json.return_value = {"x": 1}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_json("test", mode="edit")

        call_args = mock_backend.execute_json.call_args
        assert call_args[0][1] == Mode.EDIT


# ── Interactive /json ──────────────────────────────────────────────────────


class TestInteractiveJson:
    def test_json_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_json.return_value = {"name": "Earth", "type": "planet"}

        _handle_slash("/json Describe Earth as JSON", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert '"name"' in output
        assert "Earth" in output

    def test_json_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/json", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_json_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/json test prompt", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_json_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_json.side_effect = RuntimeError("model error")

        _handle_slash("/json test prompt", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_json_appends_messages(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_json.return_value = {"result": "ok"}
        messages = []

        _handle_slash("/json test", messages, backend, {}, Mode.THINK, Path("/tmp"))

        assert len(messages) == 2
        assert "[JSON mode]" in messages[0]["content"]
        assert messages[1]["role"] == "assistant"
