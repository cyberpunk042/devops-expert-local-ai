"""Claude Code backend — invokes the Claude Code CLI as a subprocess."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from aicp.backends.base import Backend
from aicp.core.modes import Mode


class ClaudeCodeBackend(Backend):
    """Backend that shells out to the `claude` CLI."""

    def __init__(self, model: str = "opus") -> None:
        self.model = model

    @property
    def name(self) -> str:
        return "claude"

    def execute(self, prompt: str, mode: Mode, project_path: Path) -> str:
        cmd = self._build_command(prompt, mode, project_path)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(project_path),
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude Code failed: {result.stderr}")
        return result.stdout

    def _build_command(self, prompt: str, mode: Mode, project_path: Path) -> list[str]:
        cmd = ["claude", "-p", "--output-format", "text"]

        if self.model:
            cmd.extend(["--model", self.model])

        # Map AICP modes to Claude Code permission modes
        if mode == Mode.THINK:
            cmd.extend(["--permission-mode", "plan"])
            cmd.extend(["--tools", "Read"])
        elif mode == Mode.EDIT:
            cmd.extend(["--allowedTools", "Read", "Edit", "Write", "Glob", "Grep"])
        # ACT mode: no extra restrictions

        cmd.append(prompt)
        return cmd
