"""Tests for Claude Code backend — unit tests for command building and parsing."""

from pathlib import Path

from aicp.backends.claude_code import ClaudeCodeBackend
from aicp.core.modes import Mode


def test_think_mode_uses_plan_permission():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"))
    assert "--permission-mode" in cmd
    assert "plan" in cmd
    assert "--disallowedTools" not in cmd


def test_edit_mode_allows_file_tools_blocks_bash():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("fix bug", Mode.EDIT, Path("/tmp/project"))
    assert "--allowedTools" in cmd
    assert "Read" in cmd
    assert "Edit" in cmd
    assert "Write" in cmd
    assert "--disallowedTools" in cmd
    assert "Bash" in cmd


def test_act_mode_has_no_restrictions():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("run tests", Mode.ACT, Path("/tmp/project"))
    assert "--permission-mode" not in cmd
    assert "--allowedTools" not in cmd
    assert "--disallowedTools" not in cmd


def test_max_turns_included():
    backend = ClaudeCodeBackend(model="sonnet", max_turns=5)
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"))
    assert "--max-turns" in cmd
    assert "5" in cmd


def test_max_budget_included():
    backend = ClaudeCodeBackend(model="sonnet", max_budget_usd=1.50)
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"))
    assert "--max-budget-usd" in cmd
    assert "1.5" in cmd


def test_prompt_is_last_argument():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("my prompt here", Mode.THINK, Path("/tmp/project"))
    assert cmd[-1] == "my prompt here"


def test_effort_level():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"), effort="high")
    assert "--effort" in cmd
    assert "high" in cmd


def test_effort_from_constructor():
    backend = ClaudeCodeBackend(model="sonnet", effort="low")
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"))
    # No effort passed to _build_command, but constructor default not auto-applied in _build_command
    # Effort is applied in execute() which passes self.effort
    assert cmd[-1] == "hello"


def test_resume_session():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"), resume_session="my-session")
    assert "--resume" in cmd
    assert "my-session" in cmd
    assert "--name" not in cmd  # resume takes precedence


def test_session_name():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"), session_name="feature-work")
    assert "--name" in cmd
    assert "feature-work" in cmd


def test_json_schema():
    backend = ClaudeCodeBackend(model="sonnet")
    schema = '{"type":"object","properties":{"answer":{"type":"string"}}}'
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"), json_schema=schema)
    assert "--json-schema" in cmd
    assert schema in cmd


def test_output_format_default_json():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"))
    assert "--output-format" in cmd
    idx = cmd.index("--output-format")
    assert cmd[idx + 1] == "json"


def test_output_format_stream():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"), output_format="stream-json")
    idx = cmd.index("--output-format")
    assert cmd[idx + 1] == "stream-json"


def test_parse_response_json():
    backend = ClaudeCodeBackend(model="sonnet")
    raw = '{"result":"Hello!","model":"claude-sonnet-4-6","usage":{"input_tokens":10,"output_tokens":5},"cost_usd":0.001}'
    text = backend._parse_response(raw)
    assert text == "Hello!"
    assert backend.last_usage["prompt_tokens"] == 10
    assert backend.last_usage["completion_tokens"] == 5
    assert backend.last_usage["estimated_cost_usd"] == 0.001


def test_parse_response_plain_text_fallback():
    backend = ClaudeCodeBackend(model="sonnet")
    raw = "Just plain text response"
    text = backend._parse_response(raw)
    assert text == "Just plain text response"
