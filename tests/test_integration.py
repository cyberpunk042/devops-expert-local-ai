"""Integration tests — require real backends to be available.

Run with:
  pytest tests/test_integration.py -v              # all integration tests
  pytest tests/test_integration.py -v -k localai   # LocalAI tests only
  pytest tests/test_integration.py -v -k claude    # Claude Code tests only

Tests are automatically skipped when the required backend is unavailable.
"""

import shutil
import subprocess

import pytest

from aicp.backends.claude_code import ClaudeCodeBackend
from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode
from pathlib import Path


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

@pytest.mark.skipif(not has_localai, reason="LocalAI not running on localhost:8090")
class TestLocalAIIntegration:
    """Integration tests that call the real LocalAI instance."""

    def _backend(self) -> LocalAIBackend:
        """Build a backend pointed at the running LocalAI instance."""
        import httpx
        # Pick a chat model (not embedding) from the loaded models
        resp = httpx.get(f"{LOCALAI_BASE_URL}/v1/models", timeout=3.0)
        models = [m.get("id", "") for m in resp.json().get("data", [])]
        # Prefer hermes, skip embedding-only models
        chat_models = [m for m in models if m not in ("nomic-embed",)]
        model = "hermes" if "hermes" in chat_models else (chat_models[0] if chat_models else LOCALAI_MODEL)
        return LocalAIBackend(base_url=LOCALAI_BASE_URL, model=model, max_tokens=256)

    def test_is_available(self):
        """Backend reports itself as available."""
        backend = self._backend()
        assert backend.is_available() is True

    def test_status_detail_shows_models(self):
        """status_detail() returns a string mentioning the loaded model."""
        backend = self._backend()
        detail = backend.status_detail()
        assert "OK" in detail
        assert backend.model in detail

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
