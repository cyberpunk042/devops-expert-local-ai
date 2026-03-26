"""Tests for smart routing."""

from aicp.core.modes import Mode
from aicp.core.router import classify_task_with_reason


class _MockBackend:
    def __init__(self, name, available=True):
        self._name = name
        self._available = available

    @property
    def name(self):
        return self._name

    def is_available(self):
        return self._available


def _backends(local_avail=True, claude_avail=True):
    return {
        "local": _MockBackend("local", local_avail),
        "claude": _MockBackend("claude", claude_avail),
    }


def test_simple_question_routes_to_local():
    backend, reason = classify_task_with_reason(
        "What is Python?", Mode.THINK, _backends()
    )
    assert backend == "local"


def test_complex_task_routes_to_claude():
    backend, reason = classify_task_with_reason(
        "Refactor the authentication module", Mode.THINK, _backends()
    )
    assert backend == "claude"
    assert "refactor" in reason.lower()


def test_edit_mode_routes_to_claude():
    backend, reason = classify_task_with_reason(
        "Fix the typo", Mode.EDIT, _backends()
    )
    assert backend == "claude"
    assert "edit" in reason.lower()


def test_act_mode_routes_to_claude():
    backend, reason = classify_task_with_reason(
        "Run the tests", Mode.ACT, _backends()
    )
    assert backend == "claude"


def test_long_prompt_routes_to_claude():
    backend, reason = classify_task_with_reason(
        "x " * 300, Mode.THINK, _backends()
    )
    assert backend == "claude"
    assert "long" in reason.lower()


def test_only_local_available():
    backend, reason = classify_task_with_reason(
        "Refactor everything", Mode.THINK, _backends(claude_avail=False)
    )
    assert backend == "local"
    assert "unavailable" in reason.lower()


def test_only_claude_available():
    backend, reason = classify_task_with_reason(
        "Hello", Mode.THINK, _backends(local_avail=False)
    )
    assert backend == "claude"
    assert "unavailable" in reason.lower()


def test_default_think_mode():
    backend, reason = classify_task_with_reason(
        "some random prompt with no keywords", Mode.THINK, _backends()
    )
    assert backend == "local"
    assert "default" in reason.lower()
