"""Claude Code backend — invokes the Claude Code CLI as a subprocess."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Generator, List, Optional

from aicp.backends.base import Backend
from aicp.core.context import build_project_context
from aicp.core.modes import Mode
from aicp.core.result import TaskResult, TokenUsage


class ClaudeCodeBackend(Backend):
    """Backend that shells out to the `claude` CLI."""

    def __init__(
        self,
        model: str = "opus",
        max_turns: int = 10,
        max_budget_usd: Optional[float] = None,
        timeout: int = 300,
        effort: Optional[str] = None,
    ) -> None:
        self.model = model
        self.max_turns = max_turns
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.effort = effort

    @property
    def name(self) -> str:
        return "claude"

    def is_available(self) -> bool:
        if not shutil.which("claude"):
            return False
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=5,
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
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return f"OK (version {version}, model: {self.model})"
            return f"ERROR: claude --version exited with code {result.returncode}"
        except subprocess.TimeoutExpired:
            return "UNAVAILABLE: claude --version timed out"
        except OSError as e:
            return f"UNAVAILABLE: {e}"

    def execute(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        session_name: Optional[str] = None,
        resume_session: Optional[str] = None,
        effort: Optional[str] = None,
        json_schema: Optional[str] = None,
    ) -> str:
        if not shutil.which("claude"):
            raise RuntimeError(
                "Claude Code CLI not found on PATH. "
                "Install it: https://docs.anthropic.com/en/docs/claude-code"
            )

        cmd = self._build_command(
            prompt, mode, project_path,
            session_name=session_name,
            resume_session=resume_session,
            effort=effort or self.effort,
            json_schema=json_schema,
        )

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

        return self._parse_response(result.stdout)

    def execute_stream(
        self, prompt: str, mode: Mode, project_path: Path,
    ) -> Generator[str, None, None]:
        """Stream Claude Code response chunks via stream-json output."""
        if not shutil.which("claude"):
            raise RuntimeError("Claude Code CLI not found on PATH.")

        cmd = self._build_command(prompt, mode, project_path, output_format="stream-json")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_path),
        )

        self.last_usage = {}
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    etype = event.get("type", "")
                    if etype == "assistant" and "message" in event:
                        # Content block
                        msg = event["message"]
                        if isinstance(msg, str):
                            yield msg
                        elif isinstance(msg, dict):
                            yield msg.get("content", "")
                    elif etype == "result":
                        # Final result with usage
                        text = event.get("result", "")
                        if text:
                            yield text
                        usage = event.get("usage", {})
                        cost = event.get("cost_usd") or event.get("cost", 0)
                        self.last_usage = {
                            "model": event.get("model", self.model),
                            "prompt_tokens": usage.get("input_tokens") or usage.get("prompt_tokens"),
                            "completion_tokens": usage.get("output_tokens") or usage.get("completion_tokens"),
                            "estimated_cost_usd": float(cost) if cost else None,
                        }
                except json.JSONDecodeError:
                    # Non-JSON line, output as-is
                    yield line
        finally:
            proc.wait()

    def list_sessions(self, project_path: Optional[Path] = None) -> List[Dict]:
        """List available Claude Code sessions."""
        # Claude stores sessions in ~/.claude/ — we parse `claude --resume` picker
        # For now, return empty list as the session API isn't publicly exposed
        return []

    def _parse_response(self, raw: str) -> str:
        """Parse Claude Code JSON output. Extracts text and usage."""
        self.last_usage = {}
        try:
            data = json.loads(raw)
            text = data.get("result", raw)
            usage = data.get("usage", {})
            cost = data.get("cost_usd") or data.get("cost", 0)
            self.last_usage = {
                "model": data.get("model", self.model),
                "prompt_tokens": usage.get("input_tokens") or usage.get("prompt_tokens"),
                "completion_tokens": usage.get("output_tokens") or usage.get("completion_tokens"),
                "estimated_cost_usd": float(cost) if cost else None,
                "session_id": data.get("session_id"),
            }
            return text
        except (json.JSONDecodeError, TypeError, KeyError):
            return raw

    def _build_command(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        session_name: Optional[str] = None,
        resume_session: Optional[str] = None,
        effort: Optional[str] = None,
        json_schema: Optional[str] = None,
        output_format: str = "json",
    ) -> List[str]:
        cmd = ["claude", "-p", "--output-format", output_format]

        if self.model:
            cmd.extend(["--model", self.model])

        if self.max_turns:
            cmd.extend(["--max-turns", str(self.max_turns)])

        if self.max_budget_usd:
            cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])

        # Session management
        if resume_session:
            cmd.extend(["--resume", resume_session])
        elif session_name:
            cmd.extend(["--name", session_name])

        # Effort level
        if effort:
            cmd.extend(["--effort", effort])

        # Structured output
        if json_schema:
            cmd.extend(["--json-schema", json_schema])

        # Project context
        context = build_project_context(project_path, max_chars=2000)
        if context:
            cmd.extend(["--append-system-prompt", f"Project context:\n{context}"])

        # Map AICP modes to Claude Code permission modes
        if mode == Mode.THINK:
            cmd.extend(["--permission-mode", "plan"])
        elif mode == Mode.EDIT:
            cmd.extend(["--allowedTools", "Read", "Edit", "Write", "Glob", "Grep"])
            cmd.extend(["--disallowedTools", "Bash"])
        # ACT mode: no extra restrictions

        cmd.append(prompt)
        return cmd
