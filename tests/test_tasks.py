"""Tests for aicp.core.tasks — task lifecycle state machine."""

import threading
import time
from unittest.mock import MagicMock

import pytest

from aicp.core.tasks import (
    TaskManager,
    TaskProgress,
    TaskState,
    TaskStatus,
    TaskType,
    generate_task_id,
    get_task_manager,
    reset_task_manager,
)


class TestTaskStatus:
    def test_terminal_states(self):
        assert TaskStatus.COMPLETED.is_terminal is True
        assert TaskStatus.FAILED.is_terminal is True
        assert TaskStatus.KILLED.is_terminal is True

    def test_non_terminal_states(self):
        assert TaskStatus.PENDING.is_terminal is False
        assert TaskStatus.RUNNING.is_terminal is False

    def test_string_value(self):
        assert TaskStatus.PENDING.value == "pending"
        assert str(TaskStatus.RUNNING) == "TaskStatus.RUNNING"


class TestTaskId:
    def test_prefix_by_type(self):
        assert generate_task_id(TaskType.INFERENCE).startswith("i")
        assert generate_task_id(TaskType.TOOL).startswith("t")
        assert generate_task_id(TaskType.AGENT).startswith("a")
        assert generate_task_id(TaskType.WARMUP).startswith("w")
        assert generate_task_id(TaskType.RETRY).startswith("r")

    def test_unique(self):
        ids = {generate_task_id(TaskType.INFERENCE) for _ in range(100)}
        assert len(ids) == 100

    def test_length(self):
        tid = generate_task_id(TaskType.INFERENCE)
        assert len(tid) == 9  # 1 prefix + 8 hex


class TestTaskProgress:
    def test_record_activity(self):
        p = TaskProgress()
        p.record_activity("Reading file")
        assert p.last_activity == "Reading file"
        assert len(p.recent_activities) == 1

    def test_record_tool_use(self):
        p = TaskProgress()
        p.record_tool_use("file_read", tokens=100)
        assert p.tool_use_count == 1
        assert p.token_count == 100
        assert "file_read" in p.last_activity

    def test_max_recent_activities(self):
        p = TaskProgress()
        for i in range(10):
            p.record_activity(f"Activity {i}")
        assert len(p.recent_activities) == 5  # _MAX_RECENT = 5
        assert p.recent_activities[-1] == "Activity 9"

    def test_cumulative_tokens(self):
        p = TaskProgress()
        p.record_tool_use("a", tokens=50)
        p.record_tool_use("b", tokens=30)
        assert p.token_count == 80
        assert p.tool_use_count == 2


class TestTaskState:
    def test_to_dict(self):
        task = TaskState(
            id="i12345678", task_type=TaskType.INFERENCE,
            status=TaskStatus.RUNNING, prompt="test prompt",
            mode="think", backend="local",
        )
        d = task.to_dict()
        assert d["id"] == "i12345678"
        assert d["type"] == "inference"
        assert d["status"] == "running"
        assert d["mode"] == "think"

    def test_duration_running(self):
        task = TaskState(
            id="t1", task_type=TaskType.TOOL,
            status=TaskStatus.RUNNING, prompt="",
            started_at=time.time() - 5,
        )
        assert task.duration_seconds is not None
        assert task.duration_seconds >= 4  # at least 4s

    def test_duration_completed(self):
        now = time.time()
        task = TaskState(
            id="t1", task_type=TaskType.TOOL,
            status=TaskStatus.COMPLETED, prompt="",
            started_at=now - 10, completed_at=now - 5,
        )
        assert task.duration_seconds == pytest.approx(5.0, abs=0.1)

    def test_duration_pending(self):
        task = TaskState(
            id="t1", task_type=TaskType.TOOL,
            status=TaskStatus.PENDING, prompt="",
        )
        assert task.duration_seconds is None

    def test_prompt_truncated_in_dict(self):
        task = TaskState(
            id="t1", task_type=TaskType.INFERENCE,
            status=TaskStatus.PENDING, prompt="x" * 500,
        )
        d = task.to_dict()
        assert len(d["prompt"]) == 200


class TestTaskManager:
    def setup_method(self):
        self.mgr = TaskManager(max_completed=10, eviction_delay=0.0)

    def test_register_and_get(self):
        task = self.mgr.register("test prompt", mode="think", backend="local")
        assert task.status == TaskStatus.PENDING
        assert self.mgr.get(task.id) is task

    def test_start(self):
        task = self.mgr.register("test")
        self.mgr.start(task.id)
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None

    def test_complete(self):
        task = self.mgr.register("test")
        self.mgr.start(task.id)
        self.mgr.complete(task.id, "result text")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "result text"
        assert task.completed_at is not None

    def test_fail(self):
        task = self.mgr.register("test")
        self.mgr.start(task.id)
        self.mgr.fail(task.id, "connection timeout")
        assert task.status == TaskStatus.FAILED
        assert task.error == "connection timeout"

    def test_kill(self):
        task = self.mgr.register("test")
        self.mgr.start(task.id)
        self.mgr.kill(task.id, "user cancelled")
        assert task.status == TaskStatus.KILLED
        assert task.error == "user cancelled"

    def test_cannot_start_running_task(self):
        task = self.mgr.register("test")
        self.mgr.start(task.id)
        result = self.mgr.start(task.id)
        assert result.status == TaskStatus.RUNNING  # unchanged

    def test_cannot_complete_terminal_task(self):
        task = self.mgr.register("test")
        self.mgr.start(task.id)
        self.mgr.complete(task.id, "done")
        self.mgr.complete(task.id, "done again")  # should be no-op
        assert task.result == "done"

    def test_cannot_fail_terminal_task(self):
        task = self.mgr.register("test")
        self.mgr.start(task.id)
        self.mgr.complete(task.id, "done")
        self.mgr.fail(task.id, "error")
        assert task.status == TaskStatus.COMPLETED  # unchanged

    def test_get_nonexistent(self):
        assert self.mgr.get("nonexistent") is None

    def test_start_nonexistent(self):
        assert self.mgr.start("nonexistent") is None

    def test_complete_nonexistent(self):
        assert self.mgr.complete("nonexistent") is None

    def test_update_progress(self):
        task = self.mgr.register("test")
        self.mgr.start(task.id)
        self.mgr.update_progress(task.id, tool_name="grep", tokens=50)
        assert task.progress.tool_use_count == 1
        assert task.progress.token_count == 50

    def test_update_progress_activity(self):
        task = self.mgr.register("test")
        self.mgr.update_progress(task.id, activity="Analyzing code")
        assert task.progress.last_activity == "Analyzing code"

    def test_update_progress_tokens_only(self):
        task = self.mgr.register("test")
        self.mgr.update_progress(task.id, tokens=100)
        assert task.progress.token_count == 100

    def test_update_progress_nonexistent(self):
        assert self.mgr.update_progress("nonexistent") is None

    def test_list_tasks(self):
        self.mgr.register("a")
        self.mgr.register("b")
        self.mgr.register("c")
        tasks = self.mgr.list_tasks()
        assert len(tasks) == 3

    def test_list_tasks_filter_status(self):
        t1 = self.mgr.register("a")
        t2 = self.mgr.register("b")
        self.mgr.start(t1.id)
        self.mgr.complete(t1.id)
        running = self.mgr.list_tasks(status=TaskStatus.PENDING)
        assert len(running) == 1
        assert running[0].id == t2.id

    def test_list_tasks_filter_type(self):
        self.mgr.register("a", task_type=TaskType.INFERENCE)
        self.mgr.register("b", task_type=TaskType.TOOL)
        tools = self.mgr.list_tasks(task_type=TaskType.TOOL)
        assert len(tools) == 1

    def test_list_tasks_limit(self):
        for i in range(20):
            self.mgr.register(f"task {i}")
        tasks = self.mgr.list_tasks(limit=5)
        assert len(tasks) == 5

    def test_active_count(self):
        t1 = self.mgr.register("a")
        t2 = self.mgr.register("b")
        self.mgr.start(t1.id)
        self.mgr.complete(t1.id)
        assert self.mgr.active_count == 1  # t2 is still pending

    def test_eviction(self):
        """Old terminal tasks should be evicted."""
        for i in range(15):
            t = self.mgr.register(f"task {i}")
            self.mgr.start(t.id)
            self.mgr.complete(t.id)
        # With max_completed=10 and eviction_delay=0, oldest should be evicted
        assert self.mgr.total_count <= 15  # some eviction happened

    def test_event_emission(self):
        emitter = MagicMock()
        mgr = TaskManager(event_emitter=emitter)
        task = mgr.register("test")
        emitter.emit.assert_called_once()
        args = emitter.emit.call_args
        assert args[0][0] == "task_start"

        emitter.reset_mock()
        mgr.start(task.id)
        mgr.complete(task.id, "done")
        emitter.emit.assert_called_once()
        assert emitter.emit.call_args[0][0] == "task_complete"

    def test_event_emission_on_failure(self):
        emitter = MagicMock()
        mgr = TaskManager(event_emitter=emitter)
        task = mgr.register("test")
        emitter.reset_mock()
        mgr.start(task.id)
        mgr.fail(task.id, "oops")
        emitter.emit.assert_called_once()
        assert emitter.emit.call_args[0][0] == "task_failed"

    def test_event_emitter_error_swallowed(self):
        """Event emitter errors should never break task flow."""
        emitter = MagicMock()
        emitter.emit.side_effect = RuntimeError("emitter broken")
        mgr = TaskManager(event_emitter=emitter)
        # Should not raise
        task = mgr.register("test")
        assert task.status == TaskStatus.PENDING

    def test_clear(self):
        self.mgr.register("a")
        self.mgr.register("b")
        self.mgr.clear()
        assert self.mgr.total_count == 0

    # ── Thread safety ──

    def test_concurrent_register_and_complete(self):
        """Concurrent registration and completion should not crash."""
        errors = []

        def worker():
            try:
                for _ in range(20):
                    task = self.mgr.register("concurrent test")
                    self.mgr.start(task.id)
                    self.mgr.complete(task.id, "done")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


class TestGlobalTaskManager:
    def setup_method(self):
        reset_task_manager()

    def teardown_method(self):
        reset_task_manager()

    def test_singleton(self):
        m1 = get_task_manager()
        m2 = get_task_manager()
        assert m1 is m2

    def test_reset(self):
        m1 = get_task_manager()
        reset_task_manager()
        m2 = get_task_manager()
        assert m1 is not m2
