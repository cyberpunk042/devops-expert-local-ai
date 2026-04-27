"""Tests for streaming tool calls & multi-turn tool execution (M76)."""

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


def _sse_lines(events: list[dict]) -> list[str]:
    """Convert a list of SSE event dicts into raw SSE line strings."""
    lines = []
    for evt in events:
        lines.append(f"data: {json.dumps(evt)}")
    lines.append("data: [DONE]")
    return lines


# ── Backend: execute_with_tools_stream ──────────────────────────────────────


class TestExecuteWithToolsStream:

    def _mock_stream(self, sse_lines_list: list[list[str]]):
        """Create mock httpx.stream context managers for sequential calls.

        Each entry in sse_lines_list is one streaming response.
        """
        managers = []
        for sse_lines in sse_lines_list:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.iter_lines.return_value = iter(sse_lines)
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_resp)
            ctx.__exit__ = MagicMock(return_value=False)
            managers.append(ctx)
        return managers

    def test_text_only_no_tools(self):
        """When model returns only text, yield chunks without tool calls."""
        backend = _make_backend()
        sse = _sse_lines([
            {"choices": [{"delta": {"content": "Hello "}}]},
            {"choices": [{"delta": {"content": "world"}}]},
        ])
        managers = self._mock_stream([sse])

        with patch("httpx.stream", side_effect=managers):
            with patch("aicp.core.tools.get_tools_for_mode", return_value=[]):
                chunks = list(backend.execute_with_tools_stream("hi", Mode.THINK, Path("/tmp")))

        assert chunks == ["Hello ", "world"]

    def test_tool_call_then_text(self):
        """Model calls a tool in round 1, then returns text in round 2."""
        backend = _make_backend()

        # Round 1: model emits a tool call via delta.tool_calls
        round1_sse = _sse_lines([
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_0", "function": {"name": "read_file", "arguments": '{"pa'}}
            ]}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": 'th": "/tmp/x"}'}}
            ]}}]},
        ])

        # Round 2: model returns text answer
        round2_sse = _sse_lines([
            {"choices": [{"delta": {"content": "File "}}]},
            {"choices": [{"delta": {"content": "contents here"}}]},
        ])

        managers = self._mock_stream([round1_sse, round2_sse])

        mock_execute_tool = MagicMock(return_value="file data")

        with patch("httpx.stream", side_effect=managers):
            with patch("aicp.core.tools.get_tools_for_mode", return_value=[{"function": {"name": "read_file"}}]):
                with patch("aicp.core.tools.execute_tool", mock_execute_tool):
                    chunks = list(backend.execute_with_tools_stream("read /tmp/x", Mode.THINK, Path("/tmp")))

        # Only text from round 2 should be yielded
        assert chunks == ["File ", "contents here"]
        # Tool should have been called
        mock_execute_tool.assert_called_once()
        call_args = mock_execute_tool.call_args
        assert call_args[0][0] == "read_file"

    def test_parallel_tool_calls(self):
        """Model calls multiple tools in parallel (different indices)."""
        backend = _make_backend()

        round1_sse = _sse_lines([
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_a", "function": {"name": "tool_a", "arguments": "{}"}}
            ]}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 1, "id": "call_b", "function": {"name": "tool_b", "arguments": "{}"}}
            ]}}]},
        ])

        round2_sse = _sse_lines([
            {"choices": [{"delta": {"content": "Done"}}]},
        ])

        managers = self._mock_stream([round1_sse, round2_sse])
        mock_execute_tool = MagicMock(return_value="ok")

        with patch("httpx.stream", side_effect=managers):
            with patch("aicp.core.tools.get_tools_for_mode", return_value=[]):
                with patch("aicp.core.tools.execute_tool", mock_execute_tool):
                    chunks = list(backend.execute_with_tools_stream("do both", Mode.THINK, Path("/tmp")))

        assert chunks == ["Done"]
        assert mock_execute_tool.call_count == 2

    def test_max_rounds_exhausted(self):
        """When max_rounds is reached, stop gracefully."""
        backend = _make_backend()

        # Every round returns a tool call (never text)
        tool_sse = _sse_lines([
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_0", "function": {"name": "loop_tool", "arguments": "{}"}}
            ]}}]},
        ])

        # Create enough for max_rounds=2
        managers = self._mock_stream([tool_sse, tool_sse])
        mock_execute_tool = MagicMock(return_value="again")

        with patch("httpx.stream", side_effect=managers):
            with patch("aicp.core.tools.get_tools_for_mode", return_value=[]):
                with patch("aicp.core.tools.execute_tool", mock_execute_tool):
                    chunks = list(backend.execute_with_tools_stream(
                        "loop", Mode.THINK, Path("/tmp"), max_rounds=2
                    ))

        assert chunks == []  # No text yielded, all rounds were tool calls
        assert mock_execute_tool.call_count == 2

    def test_tag_fallback(self):
        """Falls back to <tool_call> tag parsing when no native tool_calls in delta."""
        backend = _make_backend()

        round1_sse = _sse_lines([
            {"choices": [{"delta": {"content": '<tool_call>\n{"name": "my_tool", "arguments": {}}\n</tool_call>'}}]},
        ])
        round2_sse = _sse_lines([
            {"choices": [{"delta": {"content": "final answer"}}]},
        ])

        managers = self._mock_stream([round1_sse, round2_sse])
        mock_execute_tool = MagicMock(return_value="tool result")

        with patch("httpx.stream", side_effect=managers):
            with patch("aicp.core.tools.get_tools_for_mode", return_value=[]):
                with patch("aicp.core.tools.execute_tool", mock_execute_tool):
                    chunks = list(backend.execute_with_tools_stream("test", Mode.THINK, Path("/tmp")))

        # Round 1 content is yielded (including the tag), round 2 is clean text
        all_text = "".join(chunks)
        assert "final answer" in all_text
        mock_execute_tool.assert_called_once()

    def test_connect_error(self):
        """Connection error raises RuntimeError."""
        import httpx
        backend = _make_backend()

        with patch("httpx.stream", side_effect=httpx.ConnectError("refused")):
            with patch("aicp.core.tools.get_tools_for_mode", return_value=[]):
                with pytest.raises(RuntimeError, match="Cannot connect"):
                    list(backend.execute_with_tools_stream("hi", Mode.THINK, Path("/tmp")))

    def test_http_error(self):
        """HTTP 500 raises RuntimeError."""
        backend = _make_backend()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.read.return_value = b"internal error"
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_resp)
        ctx.__exit__ = MagicMock(return_value=False)

        with patch("httpx.stream", return_value=ctx):
            with patch("aicp.core.tools.get_tools_for_mode", return_value=[]):
                with pytest.raises(RuntimeError, match="500"):
                    list(backend.execute_with_tools_stream("hi", Mode.THINK, Path("/tmp")))

    def test_mode_sampling_applied(self):
        """Verify mode sampling params are included in the streaming request."""
        backend = _make_backend()
        sse = _sse_lines([{"choices": [{"delta": {"content": "ok"}}]}])
        managers = []
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(sse)
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_resp)
        ctx.__exit__ = MagicMock(return_value=False)

        captured_payload = {}

        def capture_stream(method, url, json=None, **kw):
            captured_payload.update(json or {})
            return ctx

        with patch("httpx.stream", side_effect=capture_stream):
            with patch("aicp.core.tools.get_tools_for_mode", return_value=[]):
                list(backend.execute_with_tools_stream("hi", Mode.ACT, Path("/tmp")))

        assert captured_payload.get("temperature") == 0.1
        assert captured_payload.get("stream") is True
        assert "tools" in captured_payload


# ── Interactive /tools --stream ─────────────────────────────────────────────


class TestInteractiveToolsStream:

    def test_tools_stream_flag(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_with_tools_stream.return_value = iter(["chunk1", "chunk2"])

        _handle_slash("/tools --stream test prompt", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "chunk1" in output
        assert "chunk2" in output

    def test_tools_stream_flag_at_end(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_with_tools_stream.return_value = iter(["ok"])

        _handle_slash("/tools my prompt --stream", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "ok" in output
        # Verify the correct method was called
        backend.execute_with_tools_stream.assert_called_once()

    def test_tools_without_stream(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_with_native_tools.return_value = "result"

        _handle_slash("/tools test prompt", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "result" in output
        backend.execute_with_native_tools.assert_called_once()

    def test_tools_stream_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_with_tools_stream.side_effect = RuntimeError("connection failed")

        _handle_slash("/tools --stream fail", [], backend, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_tools_no_arg_shows_stream_hint(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/tools", [], backend, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "--stream" in err


# ── MCP: aicp_tools_stream ──────────────────────────────────────────────────


class TestMcpToolsStream:

    def test_returns_concatenated_text(self):
        from aicp.mcp.server import aicp_tools_stream

        mock_backend = MagicMock()
        mock_backend.execute_with_tools_stream.return_value = iter(["Hello ", "world"])

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_tools_stream("test prompt")

        assert result == "Hello world"

    def test_mode_passed_through(self):
        from aicp.mcp.server import aicp_tools_stream

        mock_backend = MagicMock()
        mock_backend.execute_with_tools_stream.return_value = iter(["ok"])

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_tools_stream("test", mode="act")

        call_args = mock_backend.execute_with_tools_stream.call_args
        assert call_args[0][1] == Mode.ACT

    def test_empty_response(self):
        from aicp.mcp.server import aicp_tools_stream

        mock_backend = MagicMock()
        mock_backend.execute_with_tools_stream.return_value = iter([])

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_tools_stream("silence")

        assert result == ""
