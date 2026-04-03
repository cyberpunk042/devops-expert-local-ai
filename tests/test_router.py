"""Tests for smart routing."""

from aicp.core.modes import Mode
from aicp.core.router import (
    categorize_operation,
    classify_task_with_reason,
    classify_test_output,
    intercept_operation,
    recommend_model,
)


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


# ---------------------------------------------------------------------------
# Fleet operations → always local
# ---------------------------------------------------------------------------


def test_heartbeat_routes_to_local():
    backend, reason = classify_task_with_reason(
        "heartbeat", Mode.THINK, _backends()
    )
    assert backend == "local"
    assert "fleet" in reason.lower()


def test_fleet_agent_status_routes_to_local():
    backend, reason = classify_task_with_reason(
        "fleet_agent_status for node alpha-1", Mode.THINK, _backends()
    )
    assert backend == "local"
    assert "fleet" in reason.lower()


def test_fleet_ops_override_edit_mode():
    """Fleet ops should route to local even if mode is edit/act."""
    backend, reason = classify_task_with_reason(
        "heartbeat", Mode.EDIT, _backends()
    )
    assert backend == "local"
    assert "fleet" in reason.lower()


def test_security_routes_to_claude():
    backend, reason = classify_task_with_reason(
        "security audit of the auth module", Mode.THINK, _backends()
    )
    assert backend == "claude"


def test_sprint_planning_routes_to_claude():
    backend, reason = classify_task_with_reason(
        "sprint planning for next week", Mode.THINK, _backends()
    )
    assert backend == "claude"


# ---------------------------------------------------------------------------
# Model recommendation
# ---------------------------------------------------------------------------


def test_recommend_model_heartbeat():
    model = recommend_model("heartbeat")
    assert model == "qwen3-4b"


def test_recommend_model_code():
    model = recommend_model("write a function to sort a list")
    assert model == "qwen3-8b"


def test_recommend_model_simple():
    """Simple tasks route to fast model (no thinking overhead)."""
    model = recommend_model("what is Python?")
    assert model == "qwen3-8b-fast"


def test_recommend_model_default():
    """Complex or ambiguous prompts use default model (with thinking)."""
    model = recommend_model("tell me about the weather")
    assert model is None


# ---------------------------------------------------------------------------
# Operation categorization
# ---------------------------------------------------------------------------


def test_categorize_heartbeat():
    assert categorize_operation("heartbeat") == "heartbeat"


def test_categorize_ping():
    assert categorize_operation("ping the node") == "heartbeat"


def test_categorize_health_check():
    assert categorize_operation("health check") == "heartbeat"


def test_categorize_fleet_read_context():
    assert categorize_operation("fleet_read_context for agent alpha-1") == "direct"


def test_categorize_fleet_agent_status():
    assert categorize_operation("fleet_agent_status") == "direct"


def test_categorize_complex():
    assert categorize_operation("refactor the auth module") == "complex"


def test_categorize_simple():
    assert categorize_operation("what is Python?") == "simple"


def test_categorize_default():
    assert categorize_operation("random prompt with no keywords") == "default"


# ---------------------------------------------------------------------------
# Operation interception (zero-token responses)
# ---------------------------------------------------------------------------


def test_intercept_heartbeat():
    result = intercept_operation("heartbeat")
    assert result is not None
    assert "HEARTBEAT_OK" in result


def test_intercept_ping():
    result = intercept_operation("ping")
    assert result is not None
    assert "HEARTBEAT_OK" in result


def test_intercept_normal_prompt():
    result = intercept_operation("what is Python?")
    assert result is None


def test_intercept_complex_prompt():
    result = intercept_operation("refactor the auth module")
    assert result is None


def test_intercept_fleet_read_context():
    """Direct ops return None (handled by agent client, not here)."""
    result = intercept_operation("fleet_read_context")
    assert result is None


# ---------------------------------------------------------------------------
# Test output classification (zero-token review)
# ---------------------------------------------------------------------------


def test_classify_pytest_pass():
    output = "====== 42 passed, 3 warnings in 2.1s ======"
    assert classify_test_output(output) == "pass"


def test_classify_pytest_fail():
    output = "FAILED tests/test_foo.py::test_bar - AssertionError"
    assert classify_test_output(output) == "fail"


def test_classify_mixed_pass_and_fail():
    """If both pass and fail signals present, fail wins."""
    output = "10 passed, 2 failed in 5.0s"
    assert classify_test_output(output) == "fail"


def test_classify_exit_code_zero():
    output = "Build completed successfully. exit code 0"
    assert classify_test_output(output) == "pass"


def test_classify_exit_code_nonzero():
    output = "Process terminated with exit code 1"
    assert classify_test_output(output) == "fail"


def test_classify_no_test_output():
    output = "Hello, this is just a normal response about weather."
    assert classify_test_output(output) is None


def test_classify_checkmark():
    output = "✓ all assertions passed"
    assert classify_test_output(output) == "pass"


def test_classify_build_success():
    output = "BUILD SUCCESS in 12s"
    assert classify_test_output(output) == "pass"
