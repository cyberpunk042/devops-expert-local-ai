"""LocalAI backend — calls a local OpenAI-compatible API."""

from __future__ import annotations

from pathlib import Path

import httpx

from aicp.backends.base import Backend
from aicp.core.modes import Mode


class LocalAIBackend(Backend):
    """Backend that talks to a LocalAI instance via OpenAI-compatible API."""

    def __init__(self, base_url: str = "http://localhost:8080", model: str = "default") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    @property
    def name(self) -> str:
        return "local"

    def execute(self, prompt: str, mode: Mode, project_path: Path) -> str:
        system = self._system_prompt(mode, project_path)

        response = httpx.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _system_prompt(self, mode: Mode, project_path: Path) -> str:
        constraints = []
        if not mode.can_edit:
            constraints.append("You MUST NOT suggest any file edits or modifications.")
        if not mode.can_execute:
            constraints.append("You MUST NOT suggest running any commands.")

        base = f"You are working on the project at {project_path}. Mode: {mode.value}."
        if constraints:
            base += " " + " ".join(constraints)
        return base
