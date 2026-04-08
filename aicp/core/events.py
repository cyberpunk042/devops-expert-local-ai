"""Lightweight event emitter for AICP controller lifecycle events.

Inspired by Claude Code's hook system. The controller emits events at key
lifecycle points; registered callbacks handle them asynchronously.

Events emitted by AICP:
  task_start       — task execution begins
  task_complete    — task execution finished (success or failure)
  task_failed      — task failed after all failover attempts
  model_swap       — GPU model changed
  circuit_open     — circuit breaker opened for a backend
  circuit_close    — circuit breaker closed (recovered)
  dlq_enqueue      — task added to dead-letter queue
  warmup_start     — model warmup begins
  warmup_complete  — model warmup finished
  health_change    — backend health status changed
  quality_escalate — response quality triggered escalation
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("aicp.events")

# Type alias for event callbacks
EventCallback = Callable[[str, Dict[str, Any]], None]

# Maximum listeners per event to prevent memory leaks
_MAX_LISTENERS = 50


class EventEmitter:
    """Thread-safe event emitter with fire-and-forget semantics.

    Callbacks are invoked synchronously but errors are swallowed and logged.
    For truly async dispatch, wrap callbacks in threading.Thread.
    """

    def __init__(self, max_listeners: int = _MAX_LISTENERS) -> None:
        self._listeners: Dict[str, List[EventCallback]] = defaultdict(list)
        self._lock = threading.Lock()
        self._max_listeners = max_listeners

    def on(self, event: str, callback: EventCallback) -> None:
        """Register a callback for an event.

        Raises ValueError if max_listeners would be exceeded.
        """
        with self._lock:
            listeners = self._listeners[event]
            if len(listeners) >= self._max_listeners:
                raise ValueError(
                    f"Max listeners ({self._max_listeners}) exceeded for event '{event}'"
                )
            listeners.append(callback)

    def off(self, event: str, callback: EventCallback) -> None:
        """Remove a callback for an event. No-op if not registered."""
        with self._lock:
            listeners = self._listeners.get(event, [])
            try:
                listeners.remove(callback)
            except ValueError:
                pass

    def emit(self, event: str, data: Optional[Dict[str, Any]] = None) -> int:
        """Emit an event, invoking all registered callbacks.

        Callbacks are invoked synchronously. Errors are logged but never
        propagated — the emitter must never break the caller's flow.

        Returns the number of callbacks invoked.
        """
        with self._lock:
            listeners = list(self._listeners.get(event, []))

        if not listeners:
            return 0

        count = 0
        for callback in listeners:
            try:
                callback(event, data or {})
                count += 1
            except Exception:
                logger.exception("Event callback failed for '%s'", event)

        return count

    def once(self, event: str, callback: EventCallback) -> None:
        """Register a callback that fires only once, then auto-removes."""
        def _wrapper(evt: str, data: Dict[str, Any]) -> None:
            self.off(event, _wrapper)
            callback(evt, data)

        self.on(event, _wrapper)

    def listener_count(self, event: str) -> int:
        """Return the number of listeners for an event."""
        with self._lock:
            return len(self._listeners.get(event, []))

    def clear(self, event: Optional[str] = None) -> None:
        """Remove all listeners, or all listeners for a specific event."""
        with self._lock:
            if event is None:
                self._listeners.clear()
            else:
                self._listeners.pop(event, None)

    @property
    def events(self) -> List[str]:
        """Return list of events that have registered listeners."""
        with self._lock:
            return [e for e, ls in self._listeners.items() if ls]


# Module-level singleton for global event bus
_global_emitter: Optional[EventEmitter] = None
_global_lock = threading.Lock()


def get_emitter() -> EventEmitter:
    """Get or create the global event emitter singleton."""
    global _global_emitter
    if _global_emitter is None:
        with _global_lock:
            if _global_emitter is None:
                _global_emitter = EventEmitter()
    return _global_emitter


def reset_emitter() -> None:
    """Reset the global emitter (for testing)."""
    global _global_emitter
    with _global_lock:
        _global_emitter = None
