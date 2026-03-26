"""Claude Code backend — invokes the Claude Code CLI as a subprocess."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from aicp.backends.base import Backend
from aicp.core.context import build_project_context
from aicp.core.modes import Mode


class ClaudeCodeBackend(Backend):
    """Backend that shells out to the `claude` CLI."""

    def __init__(
        self,
        model: str = "opus",
        max_turns: int = 10,
        max_budget_usd: Optional[float] = None,
        timeout: int = 300,
    ) -> None:
        self.model = model
        self.max_turns = max_turns
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "claude"

    def is_available(self) -> bool:
        if not shutil.which("claude"):
            return False
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def status_detail(self) -> str:
        if not shutil.which("claude"):
            return "UNAVAILABLE: 'claude' not found on PATH"
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return f"OK (version {version}, model: {self.model})"
            return f"ERROR: claude --version exited with code {result.returncode}"
        except subprocess.TimeoutExpired:
            return "UNAVAILABLE: claude --version timed out"
        except OSError as e:
            return f"UNAVAILABLE: {e}"

    def execute(self, prompt: str, mode: Mode, project_path: Path) -> str:
        if not shutil.which("claude"):
            raise RuntimeError(
                "Claude Code CLI not found on PATH. "
                "Install it: https://docs.anthropic.com/en/docs/claude-code"
            )

        cmd = self._build_command(prompt, mode, project_path)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(project_path),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Claude Code timed out after {self.timeout}s. "
                "Try a simpler prompt or increase timeout in config."
            )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            detail = stderr or stdout or "unknown error"
            raise RuntimeError(f"Claude Code exited with code {result.returncode}: {detail}")

        return result.stdout

    def _build_command(
        self, prompt: str, mode: Mode, project_path: Path, session_name: Optional[str] = None,
    ) -> List[str]:
        cmd = ["claude", "-p", "--output-format", "text"]

        if self.model:
            cmd.extend(["--model", self.model])

        if self.max_turns:
            cmd.extend(["--max-turns", str(self.max_turns)])

        if self.max_budget_usd:
            cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])

        # Name the session for later resume via `claude -r`
        if session_name:
            cmd.extend(["--name", session_name])

        # Inject project context so Claude knows about the project
        context = build_project_context(project_path, max_chars=2000)
        if context:
            cmd.extend(["--append-system-prompt", f"Project context:\n{context}"])

        # Map AICP modes to Claude Code permission modes and tool restrictions
        if mode == Mode.THINK:
            cmd.extend(["--permission-mode", "plan"])
        elif mode == Mode.EDIT:
            cmd.extend(["--allowedTools", "Read", "Edit", "Write", "Glob", "Grep"])
            cmd.extend(["--disallowedTools", "Bash"])

        cmd.append(prompt)
        return cmd
