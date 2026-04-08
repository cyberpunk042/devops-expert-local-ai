"""Model coordinator — manages GPU VRAM swaps between LLM and image models.

On an 8GB VRAM machine, qwen3-8b (~6.5GB) and SD 3.5 Medium (~3-5GB)
cannot coexist. This coordinator handles the swap lifecycle:

  unload LLM → generate image(s) → unload SD → reload LLM

Features:
  - Serialized swap access (one swap at a time via threading.Lock)
  - Batch window: keeps SD loaded for additional requests before swapping back
  - Circuit breaker bypassed: swaps use model_shutdown/model_warmup directly
  - Swap metrics: count, duration, downtime
  - Event emission: model_swap_start, model_swap_complete
  - Text request gating: blocks until LLM is reloaded during swap
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("aicp.model_coordinator")


class GpuState(Enum):
    """Current GPU model state."""

    LLM_LOADED = "llm_loaded"
    SWAPPING_TO_SD = "swapping_to_sd"
    SD_LOADED = "sd_loaded"
    SWAPPING_TO_LLM = "swapping_to_llm"


@dataclass
class SwapConfig:
    """Configuration for model swap behaviour."""

    llm_model: str = "qwen3-8b"
    image_model: str = "sd35-medium"
    batch_window_seconds: float = 30.0
    swap_timeout_seconds: float = 60.0
    warmup_timeout_seconds: float = 45.0


class ModelCoordinator:
    """Orchestrates GPU model swaps between LLM and image generation models.

    Thread-safe: all state transitions are serialized via ``_swap_lock``.
    Text requests call :meth:`ensure_llm` before inference so they never
    hit the circuit breaker while the LLM is unloaded.
    """

    def __init__(
        self,
        backend: Any,
        config: Optional[SwapConfig] = None,
        metrics: Any = None,
        emitter: Any = None,
    ) -> None:
        self._backend = backend
        self._config = config or SwapConfig()
        self._metrics = metrics
        self._emitter = emitter

        # State machine
        self._state = GpuState.LLM_LOADED
        self._swap_lock = threading.Lock()
        self._llm_ready = threading.Event()
        self._llm_ready.set()

        # Batch window
        self._batch_timer: Optional[threading.Timer] = None
        self._pending_image_count = 0

        # Metrics
        self._swap_count = 0
        self._total_swap_duration = 0.0
        self._total_downtime = 0.0
        self._last_swap_start: float = 0.0

    # ── Public API ──────────────────────────────────────────────────────

    @property
    def state(self) -> GpuState:
        """Current GPU state."""
        return self._state

    @property
    def swap_metrics(self) -> Dict[str, Any]:
        """Swap metrics for diagnostics / Prometheus."""
        return {
            "swap_count": self._swap_count,
            "total_swap_duration_seconds": round(self._total_swap_duration, 2),
            "total_downtime_seconds": round(self._total_downtime, 2),
            "current_state": self._state.value,
            "pending_images": self._pending_image_count,
        }

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        model: str = "",
        size: str = "512x512",
        step: Optional[int] = None,
    ) -> Path:
        """Generate an image with full swap lifecycle management.

        If LLM is loaded: swaps to SD first.
        If SD already loaded (batch window): generates immediately, resets timer.
        """
        image_model = model or self._config.image_model

        with self._swap_lock:
            if self._state == GpuState.LLM_LOADED:
                self._swap_to_sd(image_model)
            elif self._state == GpuState.SD_LOADED:
                self._cancel_batch_timer()
            elif self._state in (GpuState.SWAPPING_TO_SD, GpuState.SWAPPING_TO_LLM):
                # Another thread is swapping — wait for it to finish
                pass  # lock release + re-acquire below handles serialization

            self._pending_image_count += 1

        # Generate outside the lock (slow I/O)
        try:
            result = self._backend.generate_image(
                prompt, output_path, model=image_model, size=size, step=step,
            )
        except Exception:
            with self._swap_lock:
                self._pending_image_count -= 1
                if self._pending_image_count == 0:
                    self._start_batch_timer()
            raise

        with self._swap_lock:
            self._pending_image_count -= 1
            self._start_batch_timer()

        return result

    def ensure_llm(self, timeout: Optional[float] = None) -> None:
        """Ensure LLM is loaded before text inference.

        - If LLM is loaded: returns immediately.
        - If SD is loaded and no images pending: triggers immediate swap-back.
        - If swapping or images pending: blocks until LLM is ready.

        Raises RuntimeError if timeout expires.
        """
        if self._state == GpuState.LLM_LOADED:
            return

        # Try immediate swap-back if SD is idle
        with self._swap_lock:
            if (
                self._state == GpuState.SD_LOADED
                and self._pending_image_count == 0
            ):
                self._cancel_batch_timer()
                self._swap_back_to_llm_locked()
                return

        # Block until LLM is ready
        wait_timeout = timeout or self._config.swap_timeout_seconds
        if not self._llm_ready.wait(timeout=wait_timeout):
            raise RuntimeError(
                f"LLM not available after {wait_timeout}s — "
                f"swap in progress (state={self._state.value})"
            )

    def wait_for_llm(self, timeout: Optional[float] = None) -> bool:
        """Block until LLM is loaded. Returns True if ready, False on timeout."""
        return self._llm_ready.wait(
            timeout=timeout or self._config.swap_timeout_seconds,
        )

    # ── Internal swap methods ───────────────────────────────────────────

    def _swap_to_sd(self, image_model: str) -> None:
        """Unload LLM, prepare for SD. Must hold _swap_lock."""
        self._state = GpuState.SWAPPING_TO_SD
        self._llm_ready.clear()
        self._last_swap_start = time.monotonic()

        logger.info("Swap: unloading LLM %s for image generation", self._config.llm_model)

        if self._emitter:
            self._emitter.emit("model_swap_start", {
                "from": self._config.llm_model,
                "to": image_model,
                "reason": "image_generation",
            })

        # Unload LLM
        try:
            self._backend.model_shutdown(self._config.llm_model)
        except Exception as e:
            logger.error("Failed to unload LLM: %s", e)
            # Try to continue — LocalAI may LRU-evict it anyway

        if self._metrics:
            self._metrics.record_model_unload(self._config.llm_model)

        self._state = GpuState.SD_LOADED
        logger.info("Swap: SD ready (batch window %ss)", self._config.batch_window_seconds)

    def _swap_back_to_llm_locked(self) -> None:
        """Unload SD, reload LLM. Must hold _swap_lock."""
        self._state = GpuState.SWAPPING_TO_LLM

        logger.info("Swap: reloading LLM %s", self._config.llm_model)

        # Unload SD
        try:
            self._backend.model_shutdown(self._config.image_model)
        except Exception as e:
            logger.warning("Failed to unload SD model: %s", e)

        if self._metrics:
            self._metrics.record_model_unload(self._config.image_model)

        # Warmup LLM
        result = self._backend.model_warmup(
            self._config.llm_model,
            timeout=self._config.warmup_timeout_seconds,
        )

        if self._metrics:
            self._metrics.record_model_load(self._config.llm_model)

        # Calculate swap metrics
        swap_duration = time.monotonic() - self._last_swap_start
        self._swap_count += 1
        self._total_swap_duration += swap_duration
        self._total_downtime += swap_duration

        loaded = result.get("loaded", False) if isinstance(result, dict) else False
        if not loaded:
            logger.error(
                "LLM warmup may have failed: %s (continuing anyway)", result,
            )

        self._state = GpuState.LLM_LOADED
        self._llm_ready.set()

        if self._emitter:
            self._emitter.emit("model_swap_complete", {
                "from": self._config.image_model,
                "to": self._config.llm_model,
                "duration_seconds": round(swap_duration, 2),
                "swap_count": self._swap_count,
            })

        logger.info(
            "Swap: LLM %s ready (swap took %.1fs, total swaps: %d)",
            self._config.llm_model, swap_duration, self._swap_count,
        )

    def _swap_back_callback(self) -> None:
        """Batch timer callback — runs in timer thread."""
        with self._swap_lock:
            if self._pending_image_count > 0:
                # Images still generating — re-arm timer
                logger.debug("Swap-back deferred: %d images pending", self._pending_image_count)
                self._start_batch_timer()
                return
            if self._state != GpuState.SD_LOADED:
                return  # already swapped or swapping
            self._swap_back_to_llm_locked()

    # ── Timer management ────────────────────────────────────────────────

    def _start_batch_timer(self) -> None:
        """Start or restart the batch window timer. Must hold _swap_lock."""
        self._cancel_batch_timer()
        self._batch_timer = threading.Timer(
            self._config.batch_window_seconds,
            self._swap_back_callback,
        )
        self._batch_timer.daemon = True
        self._batch_timer.start()

    def _cancel_batch_timer(self) -> None:
        """Cancel the batch window timer if running. Must hold _swap_lock."""
        if self._batch_timer is not None:
            self._batch_timer.cancel()
            self._batch_timer = None
