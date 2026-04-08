"""Circuit breaker — prevent thundering herd on backend failures.

When a backend fails repeatedly, the breaker OPENS and subsequent calls
fail fast (no wait), allowing the failover chain to handle routing
immediately. After a recovery timeout, the breaker moves to HALF_OPEN
and allows one probe request through to test recovery.

States:
  CLOSED   → normal operation, requests pass through
  OPEN     → backend known-bad, fail fast, skip to failover
  HALF_OPEN → allow one probe request, decide based on result

Profile-configurable via config["circuit_breaker"]:
  failure_threshold: consecutive failures to open (default: 3)
  recovery_timeout:  seconds before half-open probe (default: 30)
  half_open_max:     concurrent probes allowed (default: 1)
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger("aicp.circuit_breaker")

T = TypeVar("T")


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and the call is rejected."""

    def __init__(self, backend: str, since: float) -> None:
        elapsed = time.time() - since
        super().__init__(
            f"Circuit breaker OPEN for backend '{backend}' "
            f"(open for {elapsed:.1f}s). Failover should handle this."
        )
        self.backend = backend
        self.open_since = since


class CircuitBreaker:
    """Per-backend circuit breaker with thread-safe state transitions."""

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = State.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._open_since: float = 0.0
        self._half_open_active: int = 0
        self._lock = threading.Lock()

        # Metrics callbacks (set by controller/prometheus)
        self._on_state_change: Optional[Callable[[str, str], None]] = None
        self._on_trip: Optional[Callable[[str], None]] = None

    @property
    def state(self) -> State:
        with self._lock:
            # Auto-transition OPEN → HALF_OPEN after recovery timeout
            if self._state == State.OPEN:
                if time.time() - self._open_since >= self.recovery_timeout:
                    self._transition(State.HALF_OPEN)
            return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def call(self, fn: Callable[[], T]) -> T:
        """Execute fn through the circuit breaker.

        Raises CircuitBreakerOpen if the breaker is OPEN and no probe
        slot is available. Otherwise, calls fn and records success/failure.
        """
        state = self.state  # triggers auto-transition check

        if state == State.OPEN:
            raise CircuitBreakerOpen(self.name, self._open_since)

        if state == State.HALF_OPEN:
            with self._lock:
                if self._half_open_active >= self.half_open_max:
                    raise CircuitBreakerOpen(self.name, self._open_since)
                self._half_open_active += 1

        try:
            result = fn()
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    def _record_success(self) -> None:
        with self._lock:
            if self._state == State.HALF_OPEN:
                self._half_open_active = max(0, self._half_open_active - 1)
            self._failure_count = 0
            if self._state != State.CLOSED:
                self._transition(State.CLOSED)

    def _record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == State.HALF_OPEN:
                self._half_open_active = max(0, self._half_open_active - 1)
                self._transition(State.OPEN)
            elif self._state == State.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._transition(State.OPEN)

    def _transition(self, new_state: State) -> None:
        """Transition to a new state (must be called under lock)."""
        old_state = self._state
        self._state = new_state

        if new_state == State.OPEN:
            self._open_since = time.time()
            self._half_open_active = 0
            logger.warning(
                "Circuit breaker %s: %s → OPEN (after %d failures)",
                self.name, old_state.value, self._failure_count,
            )
            if self._on_trip:
                self._on_trip(self.name)
        elif new_state == State.HALF_OPEN:
            logger.info(
                "Circuit breaker %s: OPEN → HALF_OPEN (recovery probe allowed)",
                self.name,
            )
        elif new_state == State.CLOSED:
            logger.info(
                "Circuit breaker %s: %s → CLOSED (recovered)",
                self.name, old_state.value,
            )

        if self._on_state_change:
            self._on_state_change(self.name, new_state.value)

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED state."""
        with self._lock:
            self._failure_count = 0
            self._half_open_active = 0
            self._transition(State.CLOSED)

    def status(self) -> Dict[str, Any]:
        """Return current breaker status for diagnostics."""
        state = self.state  # triggers auto-transition
        return {
            "name": self.name,
            "state": state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "open_since": self._open_since if state != State.CLOSED else None,
        }


def build_breakers(
    backend_names: list[str],
    config: Dict[str, Any] = None,
) -> Dict[str, CircuitBreaker]:
    """Create a circuit breaker for each backend from config.

    Reads config["circuit_breaker"] for thresholds.
    """
    config = config or {}
    cb_cfg = config.get("circuit_breaker", {})

    threshold = cb_cfg.get("failure_threshold", 3)
    timeout = cb_cfg.get("recovery_timeout", 30.0)
    max_probes = cb_cfg.get("half_open_max", 1)

    return {
        name: CircuitBreaker(
            name=name,
            failure_threshold=threshold,
            recovery_timeout=timeout,
            half_open_max=max_probes,
        )
        for name in backend_names
    }
