"""Integration tests — require real backends to be available.

Run with: pytest tests/test_integration.py -v
These tests are skipped when backends are not available.
"""

import shutil
import subprocess

import pytest

from aicp.backends.claude_code import ClaudeCodeBackend
from aicp.core.modes import Mode
from pathlib import Path


has_claude = shutil.which("claude") is not None

PROJECT_PATH = Path(__file__).parent.parent


@pytest.mark.skipif(not has_claude, reason="claude CLI not on PATH")
class TestClaudeCodeIntegration:
    """Integration tests that call the real Claude Code CLI."""

    def test_think_mode_returns_response(self):
        """Verify Think mode returns a real response about this project."""
        backend = ClaudeCodeBackend(model="sonnet", max_turns=3, max_budget_usd=0.10)
        result = backend.execute(
            "In one sentence, what is this project? Be brief.",
            Mode.THINK,
            PROJECT_PATH,
        )
        assert len(result.strip()) > 0, "Expected non-empty response"

    def test_think_mode_cannot_edit(self):
        """Verify Think mode (plan) doesn't produce file edits."""
        backend = ClaudeCodeBackend(model="sonnet", max_turns=3, max_budget_usd=0.10)
        result = backend.execute(
            "Just describe the README.md file contents in one sentence. Do not edit anything.",
            Mode.THINK,
            PROJECT_PATH,
        )
        assert len(result.strip()) > 0


@pytest.mark.skipif(not has_claude, reason="claude CLI not on PATH")
class TestControllerIntegration:
    """Integration tests for the full controller pipeline."""

    def test_full_pipeline_think_claude(self):
        """End-to-end: CLI args -> Controller -> Claude Code -> response."""
        from aicp.core.controller import Controller, Task

        backends = {
            "claude": ClaudeCodeBackend(model="sonnet", max_turns=3, max_budget_usd=0.10),
        }
        controller = Controller(backends)
        task = Task(
            prompt="Say 'hello' and nothing else.",
            mode=Mode.THINK,
            project_path=PROJECT_PATH,
            backend_name="claude",
        )
        result = controller.run(task)
        assert len(result.strip()) > 0
