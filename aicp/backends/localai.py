"""LocalAI backend — calls a local OpenAI-compatible API."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterator, List, Optional

import httpx

from aicp.backends.base import Backend
from aicp.core.context import build_project_context
from aicp.core.modes import Mode

# How long to wait for a model to finish loading on cold start
_COLD_START_TIMEOUT = 60.0   # seconds
_COLD_START_INTERVAL = 5.0   # seconds between polls


class LocalAIBackend(Backend):
    """Backend that talks to a LocalAI instance via OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8090",
        model: str = "default",
        max_tokens: int = 2048,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens

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

    def _is_model_loaded(self) -> bool:
        """Check if the configured model is present in /v1/models."""
        try:
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=3.0)
            if resp.status_code == 200:
                ids = [m.get("id", "") for m in resp.json().get("data", [])]
                return self.model in ids
        except Exception:
            pass
        return False

    def _wait_for_model(
        self,
        timeout: float = _COLD_START_TIMEOUT,
        interval: float = _COLD_START_INTERVAL,
    ) -> bool:
        """Poll until the model appears in /v1/models or timeout is reached."""
        elapsed = 0.0
        while elapsed < timeout:
            if self._is_model_loaded():
                return True
            time.sleep(interval)
            elapsed += interval
        return False

    def execute(self, prompt: str, mode: Mode, project_path: Path) -> str:
        system = self._system_prompt(mode, project_path)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
        }

        last_error: Optional[str] = None
        response = None

        for attempt in range(3):
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

                    if attempt < 2:
                        # Model may still be cold-loading — wait for it to appear
                        # before retrying rather than sleeping a fixed amount.
                        self._wait_for_model()
                        continue

                    raise RuntimeError(f"LocalAI error ({response.status_code}): {msg}")

                if response.status_code >= 400:
                    raise RuntimeError(f"LocalAI error ({response.status_code}): {response.text}")

                break  # success

            except httpx.ConnectError:
                raise RuntimeError(self._connect_error_message())
            except httpx.TimeoutException:
                raise RuntimeError(
                    f"LocalAI timed out at {self.base_url}.\n"
                    "The model may still be loading. Check logs: make local-logs"
                )

        if response is None:
            raise RuntimeError(f"LocalAI failed after retries. Last error: {last_error}")

        try:
            data = response.json()
        except Exception:
            return response.text

        # Capture usage metadata for observability
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "model": data.get("model", self.model) if isinstance(data, dict) else self.model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected LocalAI response: {str(data)[:200]}")

    def execute_stream(self, prompt: str, mode: Mode, project_path: Path) -> Iterator[str]:
        """Stream the response token-by-token using SSE.

        Yields string chunks as they arrive. The caller is responsible for
        assembling them into the full response if needed.

        Usage::
            for chunk in backend.execute_stream(prompt, mode, path):
                print(chunk, end="", flush=True)
        """
        system = self._system_prompt(mode, project_path)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "stream": True,
        }

        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=120.0,
            ) as resp:
                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"LocalAI error ({resp.status_code}): {resp.read().decode()[:200]}"
                    )
                for line in resp.iter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        raw = line[6:]
                        try:
                            data = json.loads(raw)
                            delta = data["choices"][0].get("delta", {})
                            chunk = delta.get("content", "")
                            if chunk:
                                yield chunk
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError(
                f"LocalAI timed out at {self.base_url}. "
                "The model may still be loading. Check logs: make local-logs"
            )

    def _connect_error_message(self) -> str:
        """Build a diagnostic message when LocalAI is unreachable."""
        # Try to give a more specific hint by checking Docker state
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                capture_output=True, text=True, timeout=3,
            )
            output = result.stdout.strip()
            if "localai" in output.lower():
                if '"Status":"exited"' in output or '"State":"exited"' in output:
                    hint = "Container is stopped. Start it with: make local-up"
                else:
                    hint = "Container may be starting. Check logs: make local-logs"
            elif result.returncode == 0:
                hint = "Container not found. Build and start it: make setup-local-only"
            else:
                hint = "Start LocalAI with: make local-up"
        except Exception:
            hint = "Start LocalAI with: make local-up"

        return (
            f"Cannot connect to LocalAI at {self.base_url}.\n"
            f"  {hint}\n"
            f"  Check status with: make local-status"
        )

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
