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

        try:
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
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot connect to LocalAI at {self.base_url}. "
                "Is it running? Start with: docker compose up -d"
            )
        except httpx.TimeoutException:
            raise RuntimeError(
                f"LocalAI timed out at {self.base_url}. "
                "The model may still be loading — try again in a moment."
            )

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
