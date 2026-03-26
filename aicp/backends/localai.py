"""LocalAI backend — calls a local OpenAI-compatible API."""

from __future__ import annotations

from pathlib import Path
from typing import List

import httpx

from aicp.backends.base import Backend
from aicp.core.context import build_project_context
from aicp.core.modes import Mode


class LocalAIBackend(Backend):
    """Backend that talks to a LocalAI instance via OpenAI-compatible API."""

    def __init__(self, base_url: str = "http://localhost:8090", model: str = "default") -> None:
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
                        time.sleep(3)
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

        # Capture usage metadata for observability
        usage = data.get("usage", {})
        self.last_usage = {
            "model": data.get("model", self.model),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }

        return data["choices"][0]["message"]["content"]

    def _system_prompt(self, mode: Mode, project_path: Path) -> str:
        parts = []

        if mode == Mode.THINK:
            parts.append("You are a helpful assistant. Read-only mode: do not suggest edits or commands.")
        elif mode == Mode.EDIT:
            parts.append("You are a helpful assistant. Edit mode: you may suggest file edits but not commands.")
        else:
            parts.append("You are a helpful assistant. Full mode: you may suggest edits and commands.")

        parts.append(f"Project: {project_path.name}.")

        # Inject project context for richer answers
        context = build_project_context(project_path, max_chars=800)
        if context:
            parts.append(context)

        return "\n\n".join(parts)
