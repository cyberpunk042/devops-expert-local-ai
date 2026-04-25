"""Ollama Cloud backend — subscription-flat agentic tier.

Ollama Cloud (aka Ollama Turbo — ollama.com/turbo) is a subscription hosted
inference service exposing an OpenAI-compatible API. Different from OpenRouter
(pay-per-token) and K2.6-local (self-hosted): flat monthly cost with elastic
session caps (Pro: 5hr/7d resets, ~30M tokens/mo effective; Max: 5× Pro).

Catalog (verified 2026-04-24): kimi-k2.6, deepseek-v4-flash, glm-4.7-flash,
glm-5.1, qwen3-coder-next, qwen3.6, nemotron-3-super, gemma4, devstral-small-2,
and ~10 other open-weight models. NO proprietary Claude/GPT/Llama.

PRIVACY NOTE: shared inference pool. Never use for client-monetizable or
audit-sensitive work — route those to OpenRouter with a pinned provider, or
local K2.6 for sovereignty.

Environment:
  OLLAMA_API_KEY — required, get from https://ollama.com/
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

DEFAULT_BASE_URL = "https://ollama.com/v1"
DEFAULT_MODEL = "kimi-k2.6"


class OllamaCloudBackend(Backend):
    """Backend that talks to Ollama Cloud's OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        max_tokens: int = 8192,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 300.0,
        name: str = "ollama_cloud",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            resp = httpx.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10.0,
            )
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError):
            return False

    def status_detail(self) -> str:
        if not self.api_key:
            return "UNAVAILABLE: OLLAMA_API_KEY not set"
        try:
            resp = httpx.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                count = len(data.get("data", []))
                return f"OK ({count} models available, default: {self.model})"
            if resp.status_code == 401:
                return "UNAVAILABLE: invalid API key"
            if resp.status_code == 403:
                return "UNAVAILABLE: subscription tier does not grant access"
            return f"ERROR: status {resp.status_code}"
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            return f"UNAVAILABLE: {e}"

    def execute(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.api_key:
            raise RuntimeError(
                "Ollama Cloud API key not configured. "
                "Set OLLAMA_API_KEY in .env or config."
            )

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
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach Ollama Cloud at {self.base_url}"
            )
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Ollama Cloud request timed out after {self.timeout}s"
            )

        if resp.status_code == 401:
            raise RuntimeError("Ollama Cloud: invalid API key")
        if resp.status_code == 403:
            raise RuntimeError(
                "Ollama Cloud: subscription tier does not grant access to this model"
            )
        if resp.status_code == 429:
            # Session or weekly cap hit (Pro: 5hr/7d, Max: 5× Pro).
            raise RuntimeError(
                "Ollama Cloud: rate/quota limit reached — session or weekly cap"
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Ollama Cloud error ({resp.status_code}): {resp.text[:200]}"
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
            # Subscription is flat — per-call cost is $0 at the margin.
            "estimated_cost_usd": 0.0,
            "backend": self._name,
        }

        try:
            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            reasoning = message.get("reasoning") or ""
            return content if content else reasoning
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected Ollama Cloud response: {str(data)[:200]}")

    def execute_stream(
        self, prompt: str, mode: Mode, project_path: Path,
    ) -> Generator[str, None, None]:
        if not self.api_key:
            raise RuntimeError("Ollama Cloud API key not configured.")

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
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
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
            raise RuntimeError(f"Ollama Cloud stream error: {e}")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_system(self, mode: Mode, project_path: Path) -> str:
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
