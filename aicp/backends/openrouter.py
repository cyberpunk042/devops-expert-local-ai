"""OpenRouter backend — cloud LLM gateway with 200+ models (29 free).

OpenRouter provides an OpenAI-compatible API at https://openrouter.ai/api/v1.
It supports auto-routing across providers, free models, and paid models.
Used as a middle tier between LocalAI (free, local) and Claude (expensive).

Pricing tiers:
  - Free models: $0 (community, rate-limited, best-effort)
  - Paid models: varies per model
  - Claude via OpenRouter: possible but AICP prefers direct Claude Code

Environment:
  OPENROUTER_API_KEY — required, get from https://openrouter.ai/keys
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import httpx

from aicp.backends.base import Backend
from aicp.core.context import build_project_context
from aicp.core.modes import Mode


# Free models that are generally available on OpenRouter (updated 2026-04)
# These have $0 input and $0 output pricing.
FREE_MODELS = [
    "qwen/qwen3-8b:free",
    "qwen/qwen3-4b:free",
    "qwen/qwen3-1.7b:free",
    "qwen/qwen3-0.6b:free",
    "google/gemma-3-4b-it:free",
    "google/gemma-3-1b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "deepseek/deepseek-r1-0528:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "microsoft/phi-4-reasoning:free",
    "meta-llama/llama-4-maverick:free",
    "meta-llama/llama-4-scout:free",
]

# Default model for each use case
DEFAULT_FREE_MODEL = "qwen/qwen3-8b:free"
DEFAULT_PAID_MODEL = "qwen/qwen3-32b"


class OpenRouterBackend(Backend):
    """Backend that talks to OpenRouter's OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        free_model: str = "",
        max_tokens: int = 4096,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 120.0,
        free_only: bool = False,
    ) -> None:
        self.api_key = api_key
        self.model = model or (DEFAULT_FREE_MODEL if free_only else DEFAULT_PAID_MODEL)
        self.free_model = free_model or DEFAULT_FREE_MODEL
        self.max_tokens = max_tokens
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.free_only = free_only

    @property
    def name(self) -> str:
        return "openrouter"

    def is_available(self) -> bool:
        """Check if OpenRouter API is reachable and key is valid."""
        if not self.api_key:
            return False
        try:
            resp = httpx.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10.0,
            )
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def status_detail(self) -> str:
        if not self.api_key:
            return "UNAVAILABLE: OPENROUTER_API_KEY not set"
        try:
            resp = httpx.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                count = len(data.get("data", []))
                tier = "free-only" if self.free_only else "all tiers"
                return f"OK ({count} models available, {tier}, default: {self.model})"
            if resp.status_code == 401:
                return "UNAVAILABLE: invalid API key"
            return f"ERROR: status {resp.status_code}"
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            return f"UNAVAILABLE: {e}"

    def execute(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion request to OpenRouter."""
        if not self.api_key:
            raise RuntimeError(
                "OpenRouter API key not configured. "
                "Set OPENROUTER_API_KEY in .env or config."
            )

        selected_model = model or self.model
        t_start = time.perf_counter()

        # Build messages
        system = self._build_system(mode, project_path)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
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
            raise RuntimeError("Cannot reach OpenRouter API at openrouter.ai")
        except httpx.TimeoutException:
            raise RuntimeError(f"OpenRouter request timed out after {self.timeout}s")

        if resp.status_code == 401:
            raise RuntimeError("OpenRouter: invalid API key")
        if resp.status_code == 402:
            raise RuntimeError("OpenRouter: insufficient credits")
        if resp.status_code == 429:
            raise RuntimeError("OpenRouter: rate limited — try again later")
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenRouter error ({resp.status_code}): {resp.text[:200]}")

        try:
            data = resp.json()
        except Exception:
            return resp.text

        t_end = time.perf_counter()

        # Capture usage
        usage = data.get("usage", {})
        self.last_usage = {
            "model": data.get("model", selected_model),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_ms": round((t_end - t_start) * 1000, 1),
            "estimated_cost_usd": self._estimate_cost(usage, selected_model),
            "backend": "openrouter",
        }

        # Extract content (handle reasoning field like Qwen3)
        try:
            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            reasoning = message.get("reasoning") or ""
            return content if content else reasoning
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected OpenRouter response: {str(data)[:200]}")

    def execute_stream(
        self, prompt: str, mode: Mode, project_path: Path,
    ) -> Generator[str, None, None]:
        """Stream response chunks from OpenRouter."""
        if not self.api_key:
            raise RuntimeError("OpenRouter API key not configured.")

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
            raise RuntimeError(f"OpenRouter stream error: {e}")

    def list_free_models(self) -> list[Dict[str, Any]]:
        """Fetch the list of free models from OpenRouter."""
        try:
            resp = httpx.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=15.0,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            free = []
            for m in data.get("data", []):
                pricing = m.get("pricing", {})
                prompt_cost = float(pricing.get("prompt", "1"))
                completion_cost = float(pricing.get("completion", "1"))
                if prompt_cost == 0 and completion_cost == 0:
                    free.append({
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "context_length": m.get("context_length"),
                    })
            return free
        except Exception:
            return []

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/aicp",
            "X-Title": "AICP",
        }

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

    @staticmethod
    def _estimate_cost(usage: Dict, model: str) -> Optional[float]:
        """Rough cost estimate. Free models return 0."""
        if ":free" in model:
            return 0.0
        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0
        # Generic estimate: $0.50/M input, $1.50/M output (varies per model)
        cost = (prompt_tokens * 0.5 + completion_tokens * 1.5) / 1_000_000
        return round(cost, 6) if cost > 0 else None
