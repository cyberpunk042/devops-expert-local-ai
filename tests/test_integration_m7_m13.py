"""Integration tests for M7-M13 features.

These tests require backends to be available. Skipped when not.
"""

import shutil
from pathlib import Path

import pytest

from aicp.core.modes import Mode

has_localai = False
try:
    import httpx
    r = httpx.get("http://localhost:8090/v1/models", timeout=3.0)
    if r.status_code == 200:
        # Verify the hermes model can actually respond (not just that the API is up)
        probe = httpx.post(
            "http://localhost:8090/v1/chat/completions",
            json={"model": "hermes", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=30.0,
        )
        has_localai = probe.status_code == 200
except Exception:
    pass

has_claude = shutil.which("claude") is not None

PROJECT = Path(__file__).parent.parent


@pytest.mark.skipif(not has_localai, reason="LocalAI not available")
class TestLocalAIIntegration:

    def test_token_tracking(self):
        """Verify token counts are captured from LocalAI."""
        from aicp.backends.localai import LocalAIBackend
        b = LocalAIBackend(base_url="http://localhost:8090", model="hermes")
        b.execute("Say hello.", Mode.THINK, PROJECT)
        assert b.last_usage.get("prompt_tokens", 0) > 0
        assert b.last_usage.get("completion_tokens", 0) > 0

    def test_benchmark(self):
        """Verify benchmark works."""
        from aicp.core.models import benchmark_model
        result = benchmark_model("hermes", base_url="http://localhost:8090")
        assert result["tokens_per_second"] > 0
        assert result["latency_seconds"] > 0

    def test_gpu_detection(self):
        """Verify GPU detection works on this system."""
        from aicp.core.gpu import detect_gpus
        gpus = detect_gpus()
        assert len(gpus) >= 1
        assert gpus[0].vram_total_mb > 0

    def test_auto_config(self):
        """Verify auto-config produces sensible results."""
        from aicp.core.gpu import calculate_optimal_config, detect_gpus
        gpus = detect_gpus()
        gguf = PROJECT / "models" / "Hermes-3-Llama-3.2-3B-Q4_K_M.gguf"
        if gguf.exists():
            cfg = calculate_optimal_config(gguf, gpus)
            assert cfg["gpu_layers"] > 0  # should offload to GPU
            assert cfg["context_size"] >= 512


@pytest.mark.skipif(not has_localai, reason="LocalAI not available")
class TestPipelineIntegration:

    def test_simple_pipeline(self):
        """Run a 2-step pipeline against real LocalAI."""
        from aicp.backends.localai import LocalAIBackend
        from aicp.core.pipeline import run_pipeline

        backends = {
            "local": LocalAIBackend(base_url="http://localhost:8090", model="hermes"),
        }
        steps = [
            {"prompt": "What is 2+2? Just the number.", "mode": "think", "backend": "local"},
            {"prompt": "Double the number from step 1: {step_0}", "mode": "think", "backend": "local"},
        ]
        results = run_pipeline(steps, backends, PROJECT)
        assert len(results) == 2
        assert results[0]["error"] is None
        assert results[1]["error"] is None


@pytest.mark.skipif(not has_claude, reason="Claude not available")
class TestClaudeIntegration:

    def test_json_output_parsing(self):
        """Verify Claude Code JSON output is parsed correctly."""
        from aicp.backends.claude_code import ClaudeCodeBackend
        b = ClaudeCodeBackend(model="sonnet", max_turns=3, max_budget_usd=0.10)
        result = b.execute("Say hello in one word.", Mode.THINK, PROJECT)
        assert len(result.strip()) > 0
        # Should have parsed usage from JSON
        assert b.last_usage.get("model") is not None


@pytest.mark.skipif(not has_localai, reason="LocalAI not available")
class TestRouterIntegration:

    def test_auto_routing_executes(self):
        """Verify auto-routed task actually executes."""
        from aicp.backends.claude_code import ClaudeCodeBackend
        from aicp.backends.localai import LocalAIBackend
        from aicp.core.router import classify_task_with_reason

        backends = {
            "local": LocalAIBackend(base_url="http://localhost:8090", model="hermes"),
            "claude": ClaudeCodeBackend(model="sonnet"),
        }
        backend_name, reason = classify_task_with_reason(
            "What is Python?", Mode.THINK, backends
        )
        assert backend_name == "local"

        backend = backends[backend_name]
        result = backend.execute("What is Python? One sentence.", Mode.THINK, PROJECT)
        assert len(result.strip()) > 0
