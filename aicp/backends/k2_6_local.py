"""K2.6 local backend — Kimi K2.6 served by KTransformers on an OpenAI-compatible endpoint.

The server is launched out-of-band (see E008-m004 / `kt run` in the kvcache-ai
ktransformers install) and exposes an OpenAI-compatible HTTP API on localhost.
AICP's side is just the client adapter: speak the same request shape as the
OpenAI / OpenRouter backends, but point at the local endpoint and treat cost
as zero.

Separate class (vs reusing OpenRouterBackend) because:
- No API key — local endpoint is open
- Much longer default timeout — first load + Q2 offload to disk is slow
- No rate-limit / auth / credit error modes
- Zero cost — local always

Config contract (matches `config/default.yaml` `backends.k2_6_local`):
- `base_url` — defaults http://localhost:8091, points at sglang-kt server
- `model` — defaults `kimi-k2.6-q2`, must match `--served-model-name`
- `max_tokens` — defaults 8192
- `timeout` — defaults 600 (10 min; generous for cold paths)
- `enabled` — gates registration in `_build_backends`

E011-m003.
"""

from __future__ import annotations

import json
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx

from aicp.backends.base import Backend
from aicp.core.context import build_project_context
from aicp.core.modes import Mode

DEFAULT_BASE_URL = "http://localhost:8091"
DEFAULT_MODEL = "kimi-k2.6-q2"


class K26LocalBackend(Backend):
    """Backend that talks to KTransformers-served K2.6 on a local OpenAI-compat endpoint."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 8192,
        timeout: float = 600.0,
        name: str = "k2_6_local",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        """Probe the local endpoint cheaply."""
        try:
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=3.0)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError):
            return False

    def status_detail(self) -> str:
        try:
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                ids = [m.get("id", "?") for m in data.get("data", [])]
                return f"OK ({self.base_url}, models: {', '.join(ids) or 'none'})"
            return f"ERROR: status {resp.status_code}"
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            return f"UNAVAILABLE: {type(e).__name__} — is kt server running on {self.base_url}?"

    def execute(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion to the local K2.6 endpoint."""
        selected_model = model or self.model
        t_start = time.perf_counter()

        system = self._build_system(mode, project_path)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.2 if mode == Mode.THINK else 0.4,
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach K2.6 local endpoint at {self.base_url}. "
                "Is `kt run` running?"
            )
        except httpx.TimeoutException:
            raise RuntimeError(
                f"K2.6 local request timed out after {self.timeout}s "
                "(cold load can take minutes on first call)"
            )

        if resp.status_code >= 400:
            raise RuntimeError(
                f"K2.6 local error ({resp.status_code}): {resp.text[:200]}"
            )

        try:
            data = resp.json()
        except Exception:
            return resp.text

        t_end = time.perf_counter()

        usage = data.get("usage", {})
        self.last_usage = {
            "model": data.get("model", selected_model),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_ms": round((t_end - t_start) * 1000, 1),
            "estimated_cost_usd": 0.0,
            "backend": self._name,
        }

        try:
            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            reasoning = message.get("reasoning") or ""
            return content if content else reasoning
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected K2.6 local response: {str(data)[:200]}")

    def execute_stream(
        self, prompt: str, mode: Mode, project_path: Path,
    ) -> Generator[str, None, None]:
        """Stream response chunks from the local K2.6 endpoint."""
        system = self._build_system(mode, project_path)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.2 if mode == Mode.THINK else 0.4,
            "stream": True,
        }

        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            ) as resp:
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                        delta = data["choices"][0].get("delta", {})
                        chunk = delta.get("content", "") or delta.get("reasoning", "")
                        if chunk:
                            yield chunk
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise RuntimeError(f"K2.6 local stream error: {e}")

    def _build_system(self, mode: Mode, project_path: Path) -> str:
        """Build system prompt with mode constraints and project context."""
        parts = []
        if mode == Mode.THINK:
            parts.append("You are analyzing a project. Provide analysis only, no code changes.")
        elif mode == Mode.EDIT:
            parts.append("You are helping edit code. Provide diffs or modified code.")
        else:
            parts.append("You are an AI assistant helping with a software project.")

        context = build_project_context(project_path, max_chars=2000)
        if context:
            parts.append(f"\nProject context:\n{context}")
        return "\n".join(parts)
