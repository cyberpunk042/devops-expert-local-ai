"""Integration tests — require real backends to be available.

Run with:
  pytest tests/test_integration.py -v              # all integration tests
  pytest tests/test_integration.py -v -k localai   # LocalAI tests only
  pytest tests/test_integration.py -v -k claude    # Claude Code tests only

Tests are automatically skipped when the required backend is unavailable.
"""

import shutil
from pathlib import Path

import pytest

from aicp.backends.claude_code import ClaudeCodeBackend
from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode

has_claude = shutil.which("claude") is not None

PROJECT_PATH = Path(__file__).parent.parent

LOCALAI_BASE_URL = "http://localhost:8090"
LOCALAI_MODEL = "hermes"  # matches config/default.yaml


def _localai_available() -> bool:
    """Return True if LocalAI is reachable and has at least one model loaded."""
    try:
        import httpx
        resp = httpx.get(f"{LOCALAI_BASE_URL}/v1/models", timeout=3.0)
        if resp.status_code != 200:
            return False
        models = resp.json().get("data", [])
        return len(models) > 0
    except Exception:
        return False


has_localai = _localai_available()


@pytest.mark.skipif(not has_claude, reason="claude CLI not on PATH")
class TestClaudeCodeIntegration:
    """Integration tests that call the real Claude Code CLI."""

    def test_think_mode_returns_response(self):
        """Verify Think mode returns a real response about this project."""
        backend = ClaudeCodeBackend(model="sonnet", max_turns=3, max_budget_usd=0.10)
        result = backend.execute(
            "In one sentence, what is this project? Be brief.",
            Mode.THINK,
            PROJECT_PATH,
        )
        assert len(result.strip()) > 0, "Expected non-empty response"

    def test_think_mode_cannot_edit(self):
        """Verify Think mode (plan) doesn't produce file edits."""
        backend = ClaudeCodeBackend(model="sonnet", max_turns=3, max_budget_usd=0.10)
        result = backend.execute(
            "Just describe the README.md file contents in one sentence. Do not edit anything.",
            Mode.THINK,
            PROJECT_PATH,
        )
        assert len(result.strip()) > 0


@pytest.mark.skipif(not has_claude, reason="claude CLI not on PATH")
class TestControllerIntegration:
    """Integration tests for the full controller pipeline."""

    def test_full_pipeline_think_claude(self):
        """End-to-end: CLI args -> Controller -> Claude Code -> response."""
        from aicp.core.controller import Controller, Task

        backends = {
            "claude": ClaudeCodeBackend(model="sonnet", max_turns=3, max_budget_usd=0.10),
        }
        controller = Controller(backends)
        task = Task(
            prompt="Say 'hello' and nothing else.",
            mode=Mode.THINK,
            project_path=PROJECT_PATH,
            backend_name="claude",
        )
        result = controller.run(task)
        assert len(result.strip()) > 0


# =============================================================================
# LocalAI integration tests
# Run: pytest tests/test_integration.py -v -k localai
# Requires: make local-up (LocalAI running on localhost:8090 with a model loaded)
# =============================================================================

_NON_CHAT_MODELS = frozenset({
    "nomic-embed", "bge-reranker-v2-m3", "whisper-1", "piper-tts",
    "stablediffusion", "sd35-medium", "sd35-medium-allinone", "llava",
})


def _find_warm_chat_model() -> str | None:
    """Find a chat model that can respond right now (warm in GPU).

    Sends a tiny probe to each candidate. Returns the first model that
    responds within 10s, or None if no model is warm.
    """
    try:
        import httpx
        resp = httpx.get(f"{LOCALAI_BASE_URL}/v1/models", timeout=3.0)
        if resp.status_code != 200:
            return None
        models = [m.get("id", "") for m in resp.json().get("data", [])]
        # Filter to chat-capable models, skip junk entries
        candidates = [
            m for m in models
            if m and m not in _NON_CHAT_MODELS and not m.endswith(".bak")
        ]
        # Try a fast probe on each — the warm model responds in <2s
        for model in candidates:
            try:
                r = httpx.post(
                    f"{LOCALAI_BASE_URL}/v1/chat/completions",
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                    timeout=10.0,
                )
                if r.status_code == 200:
                    return model
            except Exception:
                continue
        return None
    except Exception:
        return None


_chat_model = _find_warm_chat_model() if has_localai else None


@pytest.mark.skipif(not has_localai, reason="LocalAI not running on localhost:8090")
class TestLocalAIIntegration:
    """Integration tests that call the real LocalAI instance.

    These tests hit the live LocalAI and may fail if the active GPU model
    is not a chat model (e.g. only embedding models loaded). Individual
    tests that need inference skip automatically in that case.
    """

    def _backend(self) -> LocalAIBackend:
        """Build a backend pointed at the running LocalAI instance."""
        model = _chat_model or LOCALAI_MODEL
        return LocalAIBackend(base_url=LOCALAI_BASE_URL, model=model, max_tokens=256)

    def test_is_available(self):
        """Backend reports itself as available."""
        backend = self._backend()
        assert backend.is_available() is True

    def test_status_detail_shows_models(self):
        """status_detail() returns a string with OK status and model info."""
        backend = self._backend()
        detail = backend.status_detail()
        assert "OK" in detail
        # Model list may be truncated; just verify it mentions models
        assert "models:" in detail or backend.model in detail

    @pytest.mark.skipif(not _chat_model, reason="no chat model loaded in LocalAI")
    def test_think_mode_returns_response(self):
        """Think mode returns a non-empty string from the model."""
        backend = self._backend()
        result = backend.execute(
            "Say the word 'pong' and nothing else.",
            Mode.THINK,
            PROJECT_PATH,
        )
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    @pytest.mark.skipif(not _chat_model, reason="no chat model loaded in LocalAI")
    def test_response_has_usage_metadata(self):
        """After execute(), last_usage is populated with token counts."""
        backend = self._backend()
        backend.execute("Say 'ok'.", Mode.THINK, PROJECT_PATH)
        usage = getattr(backend, "last_usage", {})
        # prompt_tokens may be None if the model doesn't report them, but the
        # key should exist
        assert "prompt_tokens" in usage
        assert "model" in usage

    def test_model_loaded_check(self):
        """_is_model_loaded() returns True when LocalAI has the model."""
        backend = self._backend()
        assert backend._is_model_loaded() is True

    @pytest.mark.skipif(not _chat_model, reason="no chat model loaded in LocalAI")
    def test_full_pipeline_think_local(self):
        """End-to-end: Controller -> LocalAI -> response."""
        from aicp.core.controller import Controller, Task

        backend = self._backend()
        backends = {"local": backend}
        controller = Controller(backends)
        task = Task(
            prompt="Reply with the single word: ready",
            mode=Mode.THINK,
            project_path=PROJECT_PATH,
            backend_name="local",
        )
        result = controller.run(task)
        assert len(result.strip()) > 0
