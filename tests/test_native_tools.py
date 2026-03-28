"""Tests for native OpenAI-compatible function calling (M65)."""

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


# ── Native tool_calls response format ────────────────────────────────────────

class TestNativeToolCalls:
    def test_sends_tools_in_payload(self):
        """execute_with_native_tools sends tools array in the payload."""
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "The answer is 42.", "tool_calls": None}}]
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = backend.execute_with_native_tools(
                "What is 6*7?", Mode.THINK, Path("/tmp"),
            )

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "tools" in payload
        assert isinstance(payload["tools"], list)
        assert payload["tool_choice"] == "auto"
        assert result == "The answer is 42."

    def test_no_tools_returns_text(self):
        """When model responds with text only, return it directly."""
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Just a plain answer."}}]
        }

        with patch("httpx.post", return_value=mock_resp):
            result = backend.execute_with_native_tools(
                "Hello", Mode.THINK, Path("/tmp"),
            )

        assert result == "Just a plain answer."

    def test_native_tool_call_executes_tool(self):
        """When model returns native tool_calls, execute the tool and loop."""
        backend = _make_backend()

        # Round 1: model wants to call file_read
        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "file_read",
                            "arguments": json.dumps({"path": "/tmp/test.txt"}),
                        },
                    }],
                },
            }],
        }

        # Round 2: model gives final answer
        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "choices": [{"message": {"content": "The file contains hello world."}}]
        }

        with patch("httpx.post", side_effect=[resp1, resp2]), \
             patch("aicp.core.tools.execute_tool", return_value="hello world") as mock_exec:
            result = backend.execute_with_native_tools(
                "Read /tmp/test.txt", Mode.THINK, Path("/tmp"),
            )

        mock_exec.assert_called_once_with(
            "file_read", json.dumps({"path": "/tmp/test.txt"}), Path("/tmp"), backend=backend,
        )
        assert "hello world" in result.lower() or "file contains" in result.lower()

    def test_tool_result_sent_as_tool_role(self):
        """Tool results are sent back with role='tool' and tool_call_id."""
        backend = _make_backend()

        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_001",
                        "type": "function",
                        "function": {"name": "system_info", "arguments": "{}"},
                    }],
                },
            }],
        }

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "choices": [{"message": {"content": "LocalAI is running."}}]
        }

        with patch("httpx.post", side_effect=[resp1, resp2]) as mock_post, \
             patch("aicp.core.tools.execute_tool", return_value='{"status": "ok"}'):
            backend.execute_with_native_tools(
                "Check system", Mode.THINK, Path("/tmp"),
            )

        # Second call should have tool result message
        second_call_payload = mock_post.call_args_list[1].kwargs.get("json") or \
                              mock_post.call_args_list[1][1].get("json")
        messages = second_call_payload["messages"]
        tool_msg = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msg) == 1
        assert tool_msg[0]["tool_call_id"] == "call_001"
        assert tool_msg[0]["content"] == '{"status": "ok"}'

    def test_multiple_tool_calls_in_one_response(self):
        """Model can call multiple tools in a single response."""
        backend = _make_backend()

        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_a",
                            "type": "function",
                            "function": {"name": "file_read", "arguments": '{"path": "a.txt"}'},
                        },
                        {
                            "id": "call_b",
                            "type": "function",
                            "function": {"name": "file_read", "arguments": '{"path": "b.txt"}'},
                        },
                    ],
                },
            }],
        }

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "choices": [{"message": {"content": "Both files read."}}]
        }

        with patch("httpx.post", side_effect=[resp1, resp2]), \
             patch("aicp.core.tools.execute_tool", return_value="content") as mock_exec:
            result = backend.execute_with_native_tools(
                "Read both files", Mode.THINK, Path("/tmp"),
            )

        assert mock_exec.call_count == 2
        assert result == "Both files read."

    def test_max_rounds_exhaustion(self):
        """Stops after max_rounds even if model keeps calling tools."""
        backend = _make_backend()

        tool_resp = MagicMock()
        tool_resp.status_code = 200
        tool_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_loop",
                        "type": "function",
                        "function": {"name": "file_read", "arguments": '{"path": "x.txt"}'},
                    }],
                },
            }],
        }

        with patch("httpx.post", return_value=tool_resp), \
             patch("aicp.core.tools.execute_tool", return_value="data"):
            result = backend.execute_with_native_tools(
                "Loop forever", Mode.THINK, Path("/tmp"), max_rounds=2,
            )

        # Should have stopped after 2 rounds
        assert isinstance(result, str)


# ── Fallback to <tool_call> tags ─────────────────────────────────────────────

class TestTagFallback:
    def test_falls_back_to_tag_parsing(self):
        """If model responds with <tool_call> tags instead of native tool_calls, still works."""
        backend = _make_backend()

        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "choices": [{
                "message": {
                    "content": '<tool_call>\n{"name": "file_read", "arguments": {"path": "test.py"}}\n</tool_call>',
                },
            }],
        }

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "choices": [{"message": {"content": "File found."}}]
        }

        with patch("httpx.post", side_effect=[resp1, resp2]), \
             patch("aicp.core.tools.execute_tool", return_value="def hello(): pass"):
            result = backend.execute_with_native_tools(
                "Read test.py", Mode.THINK, Path("/tmp"),
            )

        assert result == "File found."


# ── Error handling ───────────────────────────────────────────────────────────

class TestNativeToolErrors:
    def test_connect_error(self):
        """Raises RuntimeError on connection failure."""
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.execute_with_native_tools(
                    "test", Mode.THINK, Path("/tmp"),
                )

    def test_timeout_error(self):
        """Raises RuntimeError on timeout."""
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.execute_with_native_tools(
                    "test", Mode.THINK, Path("/tmp"),
                )

    def test_http_error(self):
        """Raises RuntimeError on HTTP error."""
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.execute_with_native_tools(
                    "test", Mode.THINK, Path("/tmp"),
                )

    def test_tool_choice_passed(self):
        """tool_choice parameter is forwarded in payload."""
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.execute_with_native_tools(
                "test", Mode.THINK, Path("/tmp"), tool_choice="none",
            )

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["tool_choice"] == "none"


# ── Tool definitions ─────────────────────────────────────────────────────────

class TestToolDefinitions:
    def test_system_info_tool_exists(self):
        from aicp.core.tools import TOOL_SYSTEM_INFO
        assert TOOL_SYSTEM_INFO["function"]["name"] == "system_info"

    def test_system_info_in_all_modes(self):
        from aicp.core.tools import THINK_TOOLS, EDIT_TOOLS, ALL_TOOLS
        names = lambda tools: [t["function"]["name"] for t in tools]
        assert "system_info" in names(THINK_TOOLS)
        assert "system_info" in names(EDIT_TOOLS)
        assert "system_info" in names(ALL_TOOLS)

    def test_system_info_execution(self):
        from aicp.core.tools import execute_tool
        mock_backend = MagicMock()
        mock_backend.base_url = "http://localhost:8090"

        with patch("aicp.core.observability.get_system_info", return_value={
            "loaded_models": ["hermes"], "backends": ["cuda12-llama-cpp"],
        }), \
             patch("aicp.core.observability.get_loaded_models", return_value=["hermes"]):
            result = execute_tool("system_info", "{}", Path("/tmp"), backend=mock_backend)

        parsed = json.loads(result)
        assert parsed["active_gpu_model"] == ["hermes"]
        assert "cuda12-llama-cpp" in parsed["installed_backends"]

    def test_system_info_no_backend(self):
        from aicp.core.tools import execute_tool
        result = execute_tool("system_info", "{}", Path("/tmp"))
        assert "Error" in result


# ── MCP aicp_agent tool ──────────────────────────────────────────────────────

class TestMcpAgent:
    def test_aicp_agent_calls_native_tools(self):
        from aicp.mcp.server import aicp_agent

        mock_backend = MagicMock()
        mock_backend.execute_with_native_tools.return_value = "Agent answer."

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_agent("What files are here?", mode="think", max_rounds=3)

        mock_backend.execute_with_native_tools.assert_called_once()
        call_kwargs = mock_backend.execute_with_native_tools.call_args
        assert call_kwargs[0][0] == "What files are here?"
        assert call_kwargs[1]["max_rounds"] == 3
        assert result == "Agent answer."

    def test_aicp_agent_default_mode(self):
        from aicp.mcp.server import aicp_agent

        mock_backend = MagicMock()
        mock_backend.execute_with_native_tools.return_value = "Done."

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_agent("test")

        call_args = mock_backend.execute_with_native_tools.call_args
        assert call_args[0][1] == Mode.THINK


# ── Interactive /tools command ───────────────────────────────────────────────

class TestInteractiveToolsCommand:
    def test_tools_command_calls_backend(self):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_with_native_tools.return_value = "Tool result."
        messages = []

        result = _handle_slash(
            "/tools What files exist?",
            messages, backend, {}, Mode.THINK, Path("/tmp"),
        )

        assert result is None  # slash commands return None
        backend.execute_with_native_tools.assert_called_once()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["content"] == "Tool result."

    def test_tools_no_prompt(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        result = _handle_slash("/tools", [], backend, {}, Mode.THINK, Path("/tmp"))

        assert result is None
        assert "Usage" in capsys.readouterr().err

    def test_tools_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        result = _handle_slash("/tools list files", [], None, {}, Mode.THINK, Path("/tmp"))

        assert result is None
        assert "require" in capsys.readouterr().err.lower()

    def test_tools_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_with_native_tools.side_effect = RuntimeError("connection failed")

        result = _handle_slash(
            "/tools test", [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        assert result is None
        assert "error" in capsys.readouterr().err.lower()
