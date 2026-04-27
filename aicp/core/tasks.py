"""Task lifecycle state machine for AICP.

Provides real-time task tracking during execution, complementing the
post-hoc history in history.py. Fleet agents can query task status
while execution is in progress.

Inspired by Claude Code's Task.ts + framework.ts.

State machine:
  pending → running → completed
                   → failed
                   → killed (cancelled by user/timeout)
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("aicp.tasks")

# Task ID prefix by type
_ID_PREFIX = {
    "inference": "i",
    "tool": "t",
    "agent": "a",
    "warmup": "w",
    "retry": "r",
}


class TaskStatus(str, Enum):
    """Task lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"

    @property
    def is_terminal(self) -> bool:
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED)


class TaskType(str, Enum):
    """Types of tasks AICP can track."""
    INFERENCE = "inference"
    TOOL = "tool"
    AGENT = "agent"
    WARMUP = "warmup"
    RETRY = "retry"


@dataclass
class TaskProgress:
    """Real-time progress tracking for a task."""
    tool_use_count: int = 0
    token_count: int = 0
    last_activity: str = ""
    last_activity_time: float = 0.0
    recent_activities: list[str] = field(default_factory=list)

    _MAX_RECENT = 5

    def record_activity(self, description: str) -> None:
        """Record a tool/action activity."""
        self.last_activity = description
        self.last_activity_time = time.time()
        self.recent_activities.append(description)
        if len(self.recent_activities) > self._MAX_RECENT:
            self.recent_activities = self.recent_activities[-self._MAX_RECENT:]

    def record_tool_use(self, tool_name: str, tokens: int = 0) -> None:
        """Record a tool invocation."""
        self.tool_use_count += 1
        self.token_count += tokens
        self.record_activity(f"Called {tool_name}")


@dataclass
class TaskState:
    """Full state of a tracked task."""
    id: str
    task_type: TaskType
    status: TaskStatus
    prompt: str
    mode: str = ""
    backend: str = ""
    project: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: str | None = None
    error: str | None = None
    progress: TaskProgress = field(default_factory=TaskProgress)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        """Elapsed time from start to completion (or now if running)."""
        if self.started_at is None:
            return None
        end = self.completed_at or time.time()
        return round(end - self.started_at, 2)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API responses."""
        return {
            "id": self.id,
            "type": self.task_type.value,
            "status": self.status.value,
            "prompt": self.prompt[:200],  # truncate for API
            "mode": self.mode,
            "backend": self.backend,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "progress": {
                "tool_use_count": self.progress.tool_use_count,
                "token_count": self.progress.token_count,
                "last_activity": self.progress.last_activity,
            },
        }


def generate_task_id(task_type: TaskType) -> str:
    """Generate a unique task ID with type prefix.

    Format: <prefix><8 random alphanumeric chars>
    Example: i3k5m7n9 (inference task)
    """
    prefix = _ID_PREFIX.get(task_type.value, "x")
    suffix = secrets.token_hex(4)  # 8 hex chars
    return f"{prefix}{suffix}"


class TaskManager:
    """Thread-safe task lifecycle manager.

    Tracks active and recently-completed tasks. Emits events on state
    transitions via an optional EventEmitter.
    """

    def __init__(
        self,
        max_completed: int = 100,
        eviction_delay: float = 30.0,
        event_emitter=None,
    ) -> None:
        self._tasks: dict[str, TaskState] = {}
        self._lock = threading.Lock()
        self._max_completed = max_completed
        self._eviction_delay = eviction_delay
        self._emitter = event_emitter

    def _emit(self, event: str, task: TaskState) -> None:
        """Emit an event if emitter is available."""
        if self._emitter:
            try:
                self._emitter.emit(event, task.to_dict())
            except Exception:
                pass  # never break task flow due to event failure

    def register(
        self,
        prompt: str,
        task_type: TaskType = TaskType.INFERENCE,
        mode: str = "",
        backend: str = "",
        project: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TaskState:
        """Register a new task. Returns the task state with generated ID."""
        task_id = generate_task_id(task_type)
        task = TaskState(
            id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            prompt=prompt,
            mode=mode,
            backend=backend,
            project=project,
            metadata=metadata or {},
        )

        with self._lock:
            self._tasks[task_id] = task
            self._evict_old()

        self._emit("task_start", task)
        logger.debug("Registered task %s (%s)", task_id, task_type.value)
        return task

    def start(self, task_id: str) -> TaskState | None:
        """Transition task from PENDING to RUNNING."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.status != TaskStatus.PENDING:
                logger.warning("Cannot start task %s in state %s", task_id, task.status.value)
                return task
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()

        return task

    def complete(self, task_id: str, result: str = "") -> TaskState | None:
        """Transition task to COMPLETED with result."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.status.is_terminal:
                logger.warning("Cannot complete already-terminal task %s", task_id)
                return task
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result

        self._emit("task_complete", task)
        logger.debug("Task %s completed (%.1fs)", task_id, task.duration_seconds or 0)
        return task

    def fail(self, task_id: str, error: str = "") -> TaskState | None:
        """Transition task to FAILED with error."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.status.is_terminal:
                logger.warning("Cannot fail already-terminal task %s", task_id)
                return task
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            task.error = error

        self._emit("task_failed", task)
        logger.debug("Task %s failed: %s", task_id, error[:100])
        return task

    def kill(self, task_id: str, reason: str = "cancelled") -> TaskState | None:
        """Transition task to KILLED (user or timeout cancellation)."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.status.is_terminal:
                return task
            task.status = TaskStatus.KILLED
            task.completed_at = time.time()
            task.error = reason

        self._emit("task_failed", task)
        logger.debug("Task %s killed: %s", task_id, reason)
        return task

    def update_progress(
        self,
        task_id: str,
        tool_name: str | None = None,
        tokens: int = 0,
        activity: str | None = None,
    ) -> TaskState | None:
        """Update task progress (tool use, tokens, activity)."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if tool_name:
                task.progress.record_tool_use(tool_name, tokens)
            elif activity:
                task.progress.record_activity(activity)
            elif tokens:
                task.progress.token_count += tokens
        return task

    def get(self, task_id: str) -> TaskState | None:
        """Get task state by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        task_type: TaskType | None = None,
        limit: int = 50,
    ) -> list[TaskState]:
        """List tasks, optionally filtered by status or type."""
        with self._lock:
            tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]

        # Sort by created_at descending
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    @property
    def active_count(self) -> int:
        """Number of non-terminal tasks."""
        with self._lock:
            return sum(1 for t in self._tasks.values() if not t.status.is_terminal)

    @property
    def total_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    def _evict_old(self) -> None:
        """Evict old terminal tasks to prevent memory growth.

        Must be called while holding self._lock.
        """
        terminal = [
            (tid, t) for tid, t in self._tasks.items()
            if t.status.is_terminal and t.completed_at
            and (time.time() - t.completed_at) > self._eviction_delay
        ]
        if len(terminal) > self._max_completed:
            # Sort by completion time, evict oldest
            terminal.sort(key=lambda x: x[1].completed_at or 0)
            for tid, _ in terminal[:len(terminal) - self._max_completed]:
                del self._tasks[tid]

    def clear(self) -> None:
        """Clear all tasks (for testing)."""
        with self._lock:
            self._tasks.clear()


# ── Module-level singleton ────────────────────────────────────────────────────

_global_manager: TaskManager | None = None
_global_lock = threading.Lock()


def get_task_manager(event_emitter=None) -> TaskManager:
    """Get or create the global TaskManager singleton."""
    global _global_manager
    if _global_manager is None:
        with _global_lock:
            if _global_manager is None:
                _global_manager = TaskManager(event_emitter=event_emitter)
    return _global_manager


def reset_task_manager() -> None:
    """Reset the global TaskManager (for testing)."""
    global _global_manager
    with _global_lock:
        _global_manager = None
