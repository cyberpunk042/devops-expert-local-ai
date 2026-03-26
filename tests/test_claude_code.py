"""Tests for Claude Code backend — unit tests for command building."""

from pathlib import Path

from aicp.backends.claude_code import ClaudeCodeBackend
from aicp.core.modes import Mode


def test_think_mode_uses_plan_permission():
    backend = ClaudeCodeBackend(model="sonnet")
    cmd = backend._build_command("hello", Mode.THINK, Path("/tmp/project"))
    assert "--permission-mode" in cmd
    assert "plan" in cmd
    # Think mode should NOT have disallowedTools
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
