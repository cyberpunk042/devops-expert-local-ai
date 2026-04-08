"""Tests for controller event emission integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.core.controller import Controller, Task
from aicp.core.events import EventEmitter, reset_emitter
from aicp.core.modes import Mode


@pytest.fixture(autouse=True)
def clean_emitter():
    reset_emitter()
    yield
    reset_emitter()


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.execute.return_value = "test response"
    backend.is_available.return_value = True
    backend.last_usage = {
        "model": "test", "prompt_tokens": 10, "completion_tokens": 20,
    }
    return backend


@pytest.fixture
def controller(mock_backend):
    return Controller(
        backends={"local": mock_backend},
        config={
            "cache": {"enabled": False},
            "quality": {"threshold": 0.0},  # disable escalation
            "router": {"failover_chain": ["local"]},
        },
    )


class TestControllerEventEmission:
    def test_emitter_stored(self, controller):
        assert controller._emitter is not None
        assert isinstance(controller._emitter, EventEmitter)

    @patch("aicp.core.controller.run_preflight_checks", return_value=[])
    @patch("aicp.core.controller.intercept_operation", return_value=None)
    @patch("aicp.core.controller.score_response_quality", return_value=0.9)
    @patch("aicp.core.controller.save_task")
    def test_emits_task_complete_on_success(
        self, mock_save, mock_quality, mock_intercept, mock_preflight,
        controller,
    ):
        cb = MagicMock()
        controller._emitter.on("task_complete", cb)

        task = Task(prompt="test", mode=Mode.THINK, project_path=Path("."))
        controller.run(task)

        cb.assert_called_once()
        event_data = cb.call_args[0][1]
        assert event_data["mode"] == "think"
        assert event_data["backend"] == "local"
        assert event_data["error"] is None

    @patch("aicp.core.controller.run_preflight_checks", return_value=[])
    @patch("aicp.core.controller.intercept_operation", return_value=None)
    @patch("aicp.core.controller.score_response_quality", return_value=0.9)
    @patch("aicp.core.controller.save_task")
    def test_emits_task_failed_on_error(
        self, mock_save, mock_quality, mock_intercept, mock_preflight,
        controller, mock_backend,
    ):
        mock_backend.execute.side_effect = RuntimeError("backend down")
        cb = MagicMock()
        controller._emitter.on("task_failed", cb)

        task = Task(prompt="test", mode=Mode.THINK, project_path=Path("."))
        with pytest.raises(RuntimeError):
            controller.run(task)

        cb.assert_called_once()
        event_data = cb.call_args[0][1]
        assert "backend down" in event_data["error"]

    @patch("aicp.core.controller.run_preflight_checks", return_value=[])
    @patch("aicp.core.controller.intercept_operation", return_value="intercepted!")
    @patch("aicp.core.controller.score_response_quality", return_value=1.0)
    @patch("aicp.core.controller.save_task")
    def test_emits_on_intercepted(
        self, mock_save, mock_quality, mock_intercept, mock_preflight,
        controller,
    ):
        cb = MagicMock()
        controller._emitter.on("task_complete", cb)

        task = Task(prompt="heartbeat", mode=Mode.THINK, project_path=Path("."))
        result = controller.run(task)

        assert result == "intercepted!"
        cb.assert_called_once()

    @patch("aicp.core.controller.run_preflight_checks", return_value=[])
    @patch("aicp.core.controller.intercept_operation", return_value=None)
    @patch("aicp.core.controller.score_response_quality", return_value=0.8)
    @patch("aicp.core.controller.save_task")
    def test_event_includes_duration(
        self, mock_save, mock_quality, mock_intercept, mock_preflight,
        controller,
    ):
        cb = MagicMock()
        controller._emitter.on("task_complete", cb)

        task = Task(prompt="test", mode=Mode.THINK, project_path=Path("."))
        controller.run(task)

        event_data = cb.call_args[0][1]
        assert "duration_seconds" in event_data
        assert event_data["duration_seconds"] >= 0

    @patch("aicp.core.controller.run_preflight_checks", return_value=[])
    @patch("aicp.core.controller.intercept_operation", return_value=None)
    @patch("aicp.core.controller.score_response_quality", return_value=0.8)
    @patch("aicp.core.controller.save_task")
    def test_emitter_error_does_not_break_task(
        self, mock_save, mock_quality, mock_intercept, mock_preflight,
        controller,
    ):
        """Event emitter errors should never break task execution."""
        bad_cb = MagicMock(side_effect=RuntimeError("emitter broken"))
        controller._emitter.on("task_complete", bad_cb)

        task = Task(prompt="test", mode=Mode.THINK, project_path=Path("."))
        result = controller.run(task)
        assert result == "test response"  # task succeeded despite emitter error
