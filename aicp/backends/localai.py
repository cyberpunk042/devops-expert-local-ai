"""LocalAI backend — calls a local OpenAI-compatible API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import httpx

from aicp.backends.base import Backend
from aicp.core.modes import Mode

# Max chars of project context to inject into system prompt
_MAX_CONTEXT_CHARS = 800

# Files to read for project context (in priority order)
_CONTEXT_FILES = ["README.md", "CLAUDE.md", "pyproject.toml", "package.json", "Cargo.toml"]


class LocalAIBackend(Backend):
    """Backend that talks to a LocalAI instance via OpenAI-compatible API."""

    def __init__(self, base_url: str = "http://localhost:8081", model: str = "default") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    @property
    def name(self) -> str:
        return "local"

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=3.0)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            return False

    def status_detail(self) -> str:
        try:
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id", "?") for m in data.get("data", [])]
                model_list = ", ".join(models[:5]) if models else "no models loaded"
                return f"OK ({self.base_url}, models: {model_list})"
            return f"ERROR: HTTP {resp.status_code} from {self.base_url}/v1/models"
        except httpx.ConnectError:
            return f"UNAVAILABLE: cannot connect to {self.base_url}"
        except httpx.TimeoutException:
            return f"UNAVAILABLE: timeout connecting to {self.base_url}"
        except Exception as e:
            return f"UNAVAILABLE: {e}"

    def execute(self, prompt: str, mode: Mode, project_path: Path) -> str:
        system = self._system_prompt(mode, project_path)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 512,
        }

        # Retry once — the llama-cpp gRPC backend can crash on cold start
        # and LocalAI needs a second attempt to respawn it
        last_error = None
        for attempt in range(2):
            try:
                response = httpx.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    timeout=120.0,
                )
                if response.status_code >= 500:
                    try:
                        err = response.json().get("error", {})
                        msg = err.get("message", response.text) if isinstance(err, dict) else str(err)
                    except Exception:
                        msg = response.text
                    last_error = msg
                    if attempt == 0:
                        import time
                        time.sleep(3)  # Give gRPC process time to respawn
                        continue
                    raise RuntimeError(f"LocalAI error ({response.status_code}): {msg}")
                if response.status_code >= 400:
                    raise RuntimeError(f"LocalAI error ({response.status_code}): {response.text}")
                break
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Cannot connect to LocalAI at {self.base_url}. "
                    "Is it running? Start with: make local-up"
                )
            except httpx.TimeoutException:
                raise RuntimeError(
                    f"LocalAI timed out at {self.base_url}. "
                    "The model may still be loading — try again in a moment."
                )

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _system_prompt(self, mode: Mode, project_path: Path) -> str:
        parts = []

        # Mode constraints — keep concise for small context windows
        if mode == Mode.THINK:
            parts.append("You are a helpful assistant. Read-only mode: do not suggest edits or commands.")
        elif mode == Mode.EDIT:
            parts.append("You are a helpful assistant. Edit mode: you may suggest file edits but not commands.")
        else:
            parts.append("You are a helpful assistant. Full mode: you may suggest edits and commands.")

        parts.append(f"Project: {project_path.name}.")

        return " ".join(parts)

    @staticmethod
    def _build_context(project_path: Path) -> str:
        """Build project context from directory structure and key files."""
        sections = []

        # Directory tree (depth 2)
        tree = _dir_tree(project_path, max_depth=2)
        if tree:
            sections.append(f"Project structure:\n{tree}")

        # Key files content
        total_chars = sum(len(s) for s in sections)
        for filename in _CONTEXT_FILES:
            if total_chars >= _MAX_CONTEXT_CHARS:
                break
            filepath = project_path / filename
            if filepath.is_file():
                try:
                    content = filepath.read_text(errors="replace")
                    remaining = _MAX_CONTEXT_CHARS - total_chars
                    if len(content) > remaining:
                        content = content[:remaining] + "\n... (truncated)"
                    sections.append(f"Contents of {filename}:\n{content}")
                    total_chars += len(content)
                except OSError:
                    pass

        return "\n\n".join(sections)


def _dir_tree(path: Path, max_depth: int = 2, prefix: str = "") -> str:
    """Build a simple directory tree string."""
    if max_depth < 0:
        return ""
    lines = []
    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    except OSError:
        return ""

    # Filter out hidden dirs and common noise
    skip = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", "models"}
    entries = [e for e in entries if e.name not in skip]

    for i, entry in enumerate(entries[:30]):  # cap at 30 entries per level
        connector = "└── " if i == len(entries) - 1 else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir() and max_depth > 0:
            extension = "    " if i == len(entries) - 1 else "│   "
            subtree = _dir_tree(entry, max_depth - 1, prefix + extension)
            if subtree:
                lines.append(subtree)

    return "\n".join(lines)
