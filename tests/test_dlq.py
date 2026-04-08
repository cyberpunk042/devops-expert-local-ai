"""Tests for Dead-Letter Queue (Stage 4 Phase 4)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.core.dlq import (
    count,
    enqueue,
    list_entries,
    retry_pending,
    status,
)


@pytest.fixture(autouse=True)
def dlq_dir(tmp_path, monkeypatch):
    """Redirect DLQ to temp directory for all tests."""
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    return tmp_path / "dlq"


class TestEnqueue:
    def test_enqueue_creates_file(self, dlq_dir):
        result = enqueue("hello", "think", "local", "/tmp", "LocalAI down")
        assert result is True
        assert count() == 1

    def test_enqueue_writes_correct_fields(self, dlq_dir):
        enqueue("test prompt", "edit", "local", "/project", "timeout",
                failover_chain=["local", "claude"])
        entries = list_entries()
        assert len(entries) == 1
        e = entries[0]
        assert e["prompt"] == "test prompt"
        assert e["mode"] == "edit"
        assert e["backend"] == "local"
        assert e["error"] == "timeout"
        assert e["failover_chain"] == ["local", "claude"]
        assert e["status"] == "pending"
        assert e["retry_count"] == 0

    def test_enqueue_disabled(self, dlq_dir):
        result = enqueue("hello", "think", "local", "/tmp", "fail",
                         config={"dlq": {"enabled": False}})
        assert result is False
        assert count() == 0

    def test_enqueue_multiple(self, dlq_dir):
        for i in range(5):
            enqueue(f"task {i}", "think", "local", "/tmp", f"error {i}")
        assert count() == 5

    def test_enqueue_prunes_when_full(self, dlq_dir):
        config = {"dlq": {"max_entries": 5}}
        for i in range(6):
            enqueue(f"task {i}", "think", "local", "/tmp", f"error {i}", config=config)
        # Should have pruned oldest entries
        assert count() <= 5


class TestListEntries:
    def test_list_empty(self, dlq_dir):
        assert list_entries() == []

    def test_list_returns_entries(self, dlq_dir):
        enqueue("task1", "think", "local", "/tmp", "err1")
        enqueue("task2", "think", "local", "/tmp", "err2")
        entries = list_entries()
        assert len(entries) == 2

    def test_list_respects_max_count(self, dlq_dir):
        for i in range(10):
            enqueue(f"task {i}", "think", "local", "/tmp", f"err {i}")
        entries = list_entries(max_count=3)
        assert len(entries) == 3


class TestStatus:
    def test_status_empty(self, dlq_dir):
        s = status()
        assert s["total"] == 0
        assert s["pending"] == 0
        assert s["enabled"] is True

    def test_status_with_entries(self, dlq_dir):
        enqueue("task1", "think", "local", "/tmp", "err1")
        enqueue("task2", "think", "local", "/tmp", "err2")
        s = status()
        assert s["total"] == 2
        assert s["pending"] == 2

    def test_status_reads_config(self, dlq_dir):
        s = status(config={"dlq": {"enabled": False, "max_retries": 5}})
        assert s["enabled"] is False
        assert s["max_retries"] == 5


class TestRetry:
    def test_retry_succeeds(self, dlq_dir):
        enqueue("hello", "think", "local", "/tmp", "fail",
                config={"dlq": {"retry_delay_seconds": 0}})

        mock_controller = MagicMock()
        mock_controller.run.return_value = "success"

        result = retry_pending(mock_controller,
                               config={"dlq": {"retry_delay_seconds": 0}})
        assert result["retried"] == 1
        assert result["succeeded"] == 1

    def test_retry_failure_increments_count(self, dlq_dir):
        enqueue("hello", "think", "local", "/tmp", "fail",
                config={"dlq": {"retry_delay_seconds": 0}})

        mock_controller = MagicMock()
        mock_controller.run.side_effect = RuntimeError("still broken")

        result = retry_pending(mock_controller,
                               config={"dlq": {"retry_delay_seconds": 0}})
        assert result["retried"] == 1
        assert result["failed"] == 1

    def test_retry_respects_delay(self, dlq_dir):
        enqueue("hello", "think", "local", "/tmp", "fail")
        mock_controller = MagicMock()

        # Default delay is 300s, entry was just created → not ready
        result = retry_pending(mock_controller,
                               config={"dlq": {"retry_delay_seconds": 300}})
        assert result["retried"] == 0
        mock_controller.run.assert_not_called()


class TestControllerIntegration:
    def test_dlq_written_on_failure(self, tmp_path, dlq_dir):
        from aicp.core.controller import Controller, Task
        from aicp.core.modes import Mode

        backend = MagicMock()
        backend.execute.side_effect = RuntimeError("total failure")
        backend.last_usage = {}

        ctrl = Controller(
            backends={"local": backend},
            config={"cluster": {"auto_route": False}, "dlq": {"enabled": True}},
        )
        task = Task(prompt="test", mode=Mode.THINK,
                    project_path=tmp_path, backend_name="local")

        with pytest.raises(RuntimeError, match="total failure"):
            ctrl.run(task)

        assert count() == 1
        entries = list_entries()
        assert entries[0]["error"] == "total failure"
        assert entries[0]["prompt"] == "test"
