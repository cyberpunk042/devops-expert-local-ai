"""Tests for aicp.core.model_coordinator — GPU VRAM swap management."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.core.model_coordinator import (
    GpuState,
    ModelCoordinator,
    SwapConfig,
)


@pytest.fixture
def swap_config():
    return SwapConfig(
        llm_model="qwen3-8b",
        image_model="sd35-medium",
        batch_window_seconds=0.2,  # short for tests
        swap_timeout_seconds=5.0,
        warmup_timeout_seconds=5.0,
    )


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.model_shutdown.return_value = True
    backend.model_warmup.return_value = {"loaded": True, "model": "qwen3-8b", "duration_ms": 100}
    backend.generate_image.return_value = Path("/tmp/test.png")
    return backend


@pytest.fixture
def mock_emitter():
    return MagicMock()


@pytest.fixture
def coordinator(mock_backend, swap_config, mock_emitter):
    return ModelCoordinator(
        backend=mock_backend,
        config=swap_config,
        emitter=mock_emitter,
    )


# ── State Machine Tests ─────────────────────────────────────────────────


class TestStateTransitions:
    def test_initial_state_is_llm_loaded(self, coordinator):
        assert coordinator.state == GpuState.LLM_LOADED

    def test_generate_image_swaps_to_sd(self, coordinator, mock_backend):
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        assert mock_backend.model_shutdown.called
        mock_backend.model_shutdown.assert_any_call("qwen3-8b")

    def test_generate_image_returns_path(self, coordinator):
        result = coordinator.generate_image("a cat", Path("/tmp/test.png"))
        assert result == Path("/tmp/test.png")

    def test_state_is_sd_loaded_after_generate(self, coordinator):
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        assert coordinator.state == GpuState.SD_LOADED

    def test_batch_timer_swaps_back_to_llm(self, coordinator, mock_backend):
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        assert coordinator.state == GpuState.SD_LOADED
        # Wait for batch timer to fire (0.2s + margin)
        time.sleep(0.5)
        assert coordinator.state == GpuState.LLM_LOADED
        # Should have shut down SD and warmed up LLM
        mock_backend.model_shutdown.assert_any_call("sd35-medium")
        mock_backend.model_warmup.assert_called_once_with("qwen3-8b", timeout=5.0)

    def test_full_cycle_llm_sd_llm(self, coordinator, mock_backend):
        assert coordinator.state == GpuState.LLM_LOADED
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        assert coordinator.state == GpuState.SD_LOADED
        time.sleep(0.5)
        assert coordinator.state == GpuState.LLM_LOADED


# ── Batch Window Tests ───────────────────────────────────────────────────


class TestBatchWindow:
    def test_second_image_reuses_sd(self, coordinator, mock_backend):
        coordinator.generate_image("a cat", Path("/tmp/test1.png"))
        shutdown_count_after_first = mock_backend.model_shutdown.call_count
        coordinator.generate_image("a dog", Path("/tmp/test2.png"))
        # Should NOT have shut down again — SD was already loaded
        assert mock_backend.model_shutdown.call_count == shutdown_count_after_first

    def test_batch_timer_resets_on_new_image(self, coordinator, mock_backend):
        coordinator.generate_image("a cat", Path("/tmp/test1.png"))
        time.sleep(0.1)
        coordinator.generate_image("a dog", Path("/tmp/test2.png"))
        # Timer reset — should still be in SD_LOADED after 0.15s
        time.sleep(0.15)
        assert coordinator.state == GpuState.SD_LOADED
        # But swaps back after full window from last image
        time.sleep(0.3)
        assert coordinator.state == GpuState.LLM_LOADED

    def test_text_request_cancels_batch_timer(self, coordinator, mock_backend):
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        assert coordinator.state == GpuState.SD_LOADED
        # Text request forces immediate swap-back
        coordinator.ensure_llm()
        assert coordinator.state == GpuState.LLM_LOADED


# ── ensure_llm Tests ─────────────────────────────────────────────────────


class TestEnsureLlm:
    def test_noop_when_llm_loaded(self, coordinator):
        coordinator.ensure_llm()  # should not raise or block
        assert coordinator.state == GpuState.LLM_LOADED

    def test_immediate_swap_back_when_sd_idle(self, coordinator, mock_backend):
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        coordinator.ensure_llm()
        assert coordinator.state == GpuState.LLM_LOADED
        mock_backend.model_warmup.assert_called_once()

    def test_blocks_during_active_generation(self, coordinator, mock_backend):
        """If an image is generating, ensure_llm blocks until swap-back."""
        # Make generate_image take some time
        def slow_generate(*a, **kw):
            time.sleep(0.3)
            return Path("/tmp/test.png")
        mock_backend.generate_image.side_effect = slow_generate

        # Start image generation in another thread
        gen_thread = threading.Thread(
            target=coordinator.generate_image,
            args=("a cat", Path("/tmp/test.png")),
        )
        gen_thread.start()
        time.sleep(0.05)  # let it start

        # ensure_llm should block until generation + swap-back
        start = time.monotonic()
        coordinator.ensure_llm(timeout=3.0)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.2  # had to wait
        assert coordinator.state == GpuState.LLM_LOADED
        gen_thread.join()

    def test_timeout_raises_when_image_pending(self, coordinator, mock_backend):
        """If image is generating and timeout expires, ensure_llm raises."""
        # Make generate_image block for a long time
        def slow_generate(*a, **kw):
            time.sleep(5)
            return Path("/tmp/test.png")
        mock_backend.generate_image.side_effect = slow_generate

        # Start image generation in background
        gen_thread = threading.Thread(
            target=coordinator.generate_image,
            args=("a cat", Path("/tmp/test.png")),
        )
        gen_thread.daemon = True
        gen_thread.start()
        time.sleep(0.05)  # let it start

        # ensure_llm should timeout (image is pending, can't swap back)
        with pytest.raises(RuntimeError, match="LLM not available"):
            coordinator.ensure_llm(timeout=0.1)


# ── Concurrency Tests ────────────────────────────────────────────────────


class TestConcurrency:
    def test_concurrent_image_requests_serialized(self, coordinator, mock_backend):
        """Multiple image requests should share the SD_LOADED state."""
        results = []

        def gen(prompt):
            r = coordinator.generate_image(prompt, Path(f"/tmp/{prompt}.png"))
            results.append(r)

        threads = [threading.Thread(target=gen, args=(f"img{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(results) == 3
        # LLM should only have been shut down once
        shutdown_calls = [
            c for c in mock_backend.model_shutdown.call_args_list
            if c[0][0] == "qwen3-8b"
        ]
        assert len(shutdown_calls) == 1


# ── Metrics Tests ────────────────────────────────────────────────────────


class TestMetrics:
    def test_swap_metrics_initial(self, coordinator):
        m = coordinator.swap_metrics
        assert m["swap_count"] == 0
        assert m["current_state"] == "llm_loaded"
        assert m["pending_images"] == 0

    def test_swap_count_increments(self, coordinator):
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        time.sleep(0.5)  # wait for swap-back
        assert coordinator.swap_metrics["swap_count"] == 1

    def test_metrics_collector_called(self, mock_backend, swap_config):
        metrics = MagicMock()
        c = ModelCoordinator(
            backend=mock_backend, config=swap_config, metrics=metrics,
        )
        c.generate_image("a cat", Path("/tmp/test.png"))
        metrics.record_model_unload.assert_called_with("qwen3-8b")
        time.sleep(0.5)
        metrics.record_model_unload.assert_any_call("sd35-medium")
        metrics.record_model_load.assert_called_with("qwen3-8b")


# ── Event Tests ──────────────────────────────────────────────────────────


class TestEvents:
    def test_swap_start_emitted(self, coordinator, mock_emitter):
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        mock_emitter.emit.assert_any_call("model_swap_start", {
            "from": "qwen3-8b",
            "to": "sd35-medium",
            "reason": "image_generation",
        })

    def test_swap_complete_emitted(self, coordinator, mock_emitter):
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        time.sleep(0.5)
        swap_complete_calls = [
            c for c in mock_emitter.emit.call_args_list
            if c[0][0] == "model_swap_complete"
        ]
        assert len(swap_complete_calls) == 1
        data = swap_complete_calls[0][0][1]
        assert data["from"] == "sd35-medium"
        assert data["to"] == "qwen3-8b"
        assert "duration_seconds" in data
        assert data["swap_count"] == 1


# ── Error Handling Tests ─────────────────────────────────────────────────


class TestErrorHandling:
    def test_generate_image_failure_still_starts_timer(self, coordinator, mock_backend):
        mock_backend.generate_image.side_effect = RuntimeError("SD failed")
        with pytest.raises(RuntimeError, match="SD failed"):
            coordinator.generate_image("a cat", Path("/tmp/test.png"))
        # State should still be SD_LOADED (timer running)
        assert coordinator.state == GpuState.SD_LOADED
        # Timer should swap back
        time.sleep(0.5)
        assert coordinator.state == GpuState.LLM_LOADED

    def test_shutdown_failure_continues(self, coordinator, mock_backend):
        mock_backend.model_shutdown.side_effect = RuntimeError("shutdown failed")
        # Should not raise — coordinator logs and continues
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        assert mock_backend.generate_image.called

    def test_warmup_failure_logs_but_completes(self, mock_backend, swap_config):
        mock_backend.model_warmup.return_value = {
            "loaded": False, "error": "timeout",
        }
        c = ModelCoordinator(backend=mock_backend, config=swap_config)
        c.generate_image("a cat", Path("/tmp/test.png"))
        time.sleep(0.5)
        # Should still transition to LLM_LOADED (best-effort)
        assert c.state == GpuState.LLM_LOADED


# ── wait_for_llm Tests ───────────────────────────────────────────────────


class TestWaitForLlm:
    def test_returns_true_when_llm_loaded(self, coordinator):
        assert coordinator.wait_for_llm(timeout=0.1) is True

    def test_returns_true_after_swap_back(self, coordinator):
        coordinator.generate_image("a cat", Path("/tmp/test.png"))
        # Will block until batch timer fires
        assert coordinator.wait_for_llm(timeout=2.0) is True
        assert coordinator.state == GpuState.LLM_LOADED
