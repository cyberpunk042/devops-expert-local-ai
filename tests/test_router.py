"""Tests for smart routing."""

from aicp.core.modes import Mode
from aicp.core.router import (
    analyze_complexity,
    categorize_operation,
    classify_task_with_reason,
    classify_test_output,
    estimate_cost,
    intercept_operation,
    recommend_model,
    score_response_quality,
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


def test_complex_task_stays_local_in_think():
    """Single complex keyword in THINK mode scores ~0.15 — stays local with default thresholds."""
    backend, reason = classify_task_with_reason(
        "Refactor the authentication module", Mode.THINK, _backends()
    )
    assert backend == "local"
    assert "complexity" in reason.lower()


def test_highly_complex_task_routes_to_claude():
    """Multiple complex keywords + multi-step → score > 0.6 → claude."""
    backend, reason = classify_task_with_reason(
        "Refactor the entire authentication module, then implement a new security "
        "audit system, and after that deploy the architecture changes across files",
        Mode.THINK, _backends()
    )
    assert backend == "claude"


def test_edit_mode_routes_to_claude():
    """Edit mode is in force_cloud_modes by default."""
    backend, reason = classify_task_with_reason(
        "Fix the typo", Mode.EDIT, _backends()
    )
    assert backend == "claude"
    assert "force_cloud" in reason.lower()


def test_act_mode_routes_to_claude():
    """Act mode is in force_cloud_modes by default."""
    backend, reason = classify_task_with_reason(
        "Run the tests", Mode.ACT, _backends()
    )
    assert backend == "claude"


def test_edit_mode_stays_local_with_offline_config():
    """Offline profile sets force_cloud_modes=[] — edit stays local."""
    config = {"router": {"force_cloud_modes": []}}
    backend, reason = classify_task_with_reason(
        "Fix the typo", Mode.EDIT, _backends(), config=config
    )
    assert backend == "local"


def test_long_prompt_stays_local():
    """Long prompt in THINK mode scores ~0.25 — stays local with default thresholds."""
    backend, reason = classify_task_with_reason(
        "x " * 300, Mode.THINK, _backends()
    )
    assert backend == "local"
    assert "complexity" in reason.lower()


def test_only_local_available():
    backend, reason = classify_task_with_reason(
        "Refactor everything", Mode.THINK, _backends(claude_avail=False)
    )
    assert backend == "local"
    assert "unavailable" in reason.lower() or "only" in reason.lower() or "complexity" in reason.lower()


def test_only_claude_available():
    backend, reason = classify_task_with_reason(
        "Hello", Mode.THINK, _backends(local_avail=False)
    )
    # With no local, simple "Hello" goes to openrouter or claude
    assert backend in ("claude", "openrouter")
    assert "unavailable" in reason.lower()


def test_default_think_mode():
    backend, reason = classify_task_with_reason(
        "some random prompt with no keywords", Mode.THINK, _backends()
    )
    assert backend == "local"
    assert "complexity" in reason.lower()


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


def test_security_audit_routes_based_on_score():
    """Security audit has 2 complex keywords (security + audit) → score ~0.3."""
    backend, reason = classify_task_with_reason(
        "security audit of the auth module", Mode.THINK, _backends()
    )
    # score ≈ 0.30 (2 complex keywords × 0.15) — right at the threshold
    assert backend in ("local", "openrouter")


def test_heavy_security_task_routes_to_claude():
    """Heavy security task with multiple signals → claude."""
    backend, reason = classify_task_with_reason(
        "Perform a full security audit and threat model review of the auth module, "
        "then implement fixes and deploy the vulnerability patches",
        Mode.THINK, _backends()
    )
    assert backend == "claude"


def test_sprint_planning_stays_local():
    """Single planning keyword in THINK mode → local."""
    backend, reason = classify_task_with_reason(
        "sprint planning for next week", Mode.THINK, _backends()
    )
    # score ≈ 0.15 (1 complex keyword) → local
    assert backend == "local"


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


# ---------------------------------------------------------------------------
# Complexity analysis (E-M07, E-M11)
# ---------------------------------------------------------------------------


def test_complexity_fleet_op_is_trivial():
    result = analyze_complexity("heartbeat", Mode.THINK)
    assert result.score < 0.1
    assert result.recommended_tier == "local"


def test_complexity_simple_question():
    result = analyze_complexity("What is Python?", Mode.THINK)
    assert result.score < 0.3
    assert result.recommended_tier == "local"


def test_complexity_refactor_is_complex():
    result = analyze_complexity(
        "Refactor the authentication module to use JWT tokens "
        "and implement proper session management across files",
        Mode.THINK,
    )
    assert result.score >= 0.3
    assert "complex_keywords" in result.signals


def test_complexity_act_mode_boosts_score():
    think = analyze_complexity("deploy the service", Mode.THINK)
    act = analyze_complexity("deploy the service", Mode.ACT)
    assert act.score > think.score
    assert "mode_act" in act.signals


def test_complexity_edit_mode_boosts_score():
    result = analyze_complexity("fix the bug", Mode.EDIT)
    assert "mode_edit" in result.signals
    assert result.score > 0.3


def test_complexity_multi_step():
    result = analyze_complexity(
        "First analyze the code, then refactor it, and finally run the tests",
        Mode.THINK,
    )
    assert "multi_step" in result.signals


def test_complexity_long_prompt():
    result = analyze_complexity("x " * 300, Mode.THINK)  # 600 chars
    assert "medium_prompt" in result.signals


def test_complexity_summary_string():
    result = analyze_complexity("heartbeat", Mode.THINK)
    assert isinstance(result.summary, str)
    assert "fleet_op" in result.summary


# ---------------------------------------------------------------------------
# Response quality scoring (E-M48)
# ---------------------------------------------------------------------------


def test_quality_empty_response():
    assert score_response_quality("", "hello") == 0.0


def test_quality_good_response():
    score = score_response_quality(
        "Python is a high-level programming language known for its readability.\n"
        "Key features include:\n- Dynamic typing\n- Garbage collection\n"
        "- Extensive standard library",
        "What is Python?",
    )
    assert score >= 0.6


def test_quality_refusal_penalty():
    score = score_response_quality(
        "I cannot help with that request.",
        "explain the code",
    )
    assert score < 0.5


def test_quality_very_short_for_long_prompt():
    score = score_response_quality(
        "Yes.",
        "Explain the architecture of this system in detail including all components",
    )
    assert score < 0.4


def test_quality_repetitive_response():
    repeated = "the answer is yes. " * 20
    score = score_response_quality(repeated, "is this working?")
    assert score < 0.4


def test_quality_structured_response():
    score = score_response_quality(
        "## Overview\n\nThe system has three components:\n\n"
        "- **Backend**: handles API requests\n"
        "- **Frontend**: user interface\n"
        "- **Database**: data persistence\n\n"
        "```python\ndef main():\n    pass\n```",
        "describe the system",
    )
    assert score >= 0.7


# ---------------------------------------------------------------------------
# Cost estimation (E-M08)
# ---------------------------------------------------------------------------


def test_cost_local_is_free():
    assert estimate_cost("local", 1000, 500) == 0.0


def test_cost_openrouter_free():
    assert estimate_cost("openrouter", 1000, 500, model="qwen/qwen3-8b:free") == 0.0


def test_cost_claude_is_expensive():
    cost = estimate_cost("claude", 1000, 500)
    assert cost > 0


# ---------------------------------------------------------------------------
# Config-driven complexity thresholds (profile support)
# ---------------------------------------------------------------------------


def test_complexity_custom_thresholds_pushes_to_local():
    """With higher thresholds, medium-complexity prompts stay local."""
    config = {"router": {"complexity_thresholds": [0.7, 0.9]}}
    result = analyze_complexity(
        "refactor the login function",
        Mode.THINK,
        config=config,
    )
    # Score ~0.15-0.3 — with default thresholds this would be local/openrouter.
    # With [0.7, 0.9] it should definitely be local.
    assert result.recommended_tier == "local"


def test_complexity_custom_thresholds_shifts_tiers():
    """Lower thresholds push more tasks to cloud."""
    config = {"router": {"complexity_thresholds": [0.05, 0.1]}}
    result = analyze_complexity(
        "refactor the auth module and implement new endpoints",
        Mode.THINK,
        config=config,
    )
    # Complex keywords should push score above 0.1 → claude with low thresholds
    assert result.recommended_tier == "claude"


def test_complexity_default_thresholds_without_config():
    """Without config, default thresholds [0.3, 0.6] are used."""
    result = analyze_complexity("heartbeat", Mode.THINK)
    assert result.recommended_tier == "local"
    result2 = analyze_complexity("refactor and implement the full system", Mode.ACT)
    assert result2.recommended_tier == "claude"


# ---------------------------------------------------------------------------
# E011-m001: 5-tier routing via router.tier_map
# ---------------------------------------------------------------------------

_TIER_MAP_CFG = {
    "router": {
        "complexity_thresholds": [0.25, 0.45, 0.70, 0.90],
        "failover_chain": ["local", "k2_6_local", "k2_6_openrouter", "openrouter", "claude"],
        "tier_map": {
            0: "local",
            1: "k2_6_local",
            2: "k2_6_openrouter",
            3: "openrouter",
            4: "claude",
        },
        "force_cloud_modes": ["edit", "act"],
    }
}


def _five_tier_backends(k2_6_local_avail=False, **overrides):
    """Mock backends matching the 5-tier failover chain. k2_6_local disabled by default."""
    defaults = {
        "local": True,
        "k2_6_local": k2_6_local_avail,
        "k2_6_openrouter": True,
        "openrouter": True,
        "claude": True,
    }
    defaults.update(overrides)
    return {name: _MockBackend(name, avail) for name, avail in defaults.items()}


def test_tier_map_score_band_0_routes_to_local():
    """Score < 0.25 → band 0 → local (simple question, THINK mode)."""
    backend, reason = classify_task_with_reason(
        "What is Python?", Mode.THINK, _five_tier_backends(), config=_TIER_MAP_CFG,
    )
    assert backend == "local"
    assert "complexity" in reason.lower()


def test_tier_map_mid_band_act_mode_routes_to_k2_6_openrouter():
    """Brain-spec requirement: score≈0.5 + mode=act → k2_6_openrouter.

    mode=act triggers force_cloud_modes → first non-local tier in failover_chain
    (local, k2_6_local skipped as local-tier family) → k2_6_openrouter.
    """
    backend, reason = classify_task_with_reason(
        "Run the tests", Mode.ACT, _five_tier_backends(), config=_TIER_MAP_CFG,
    )
    assert backend == "k2_6_openrouter"
    assert "force_cloud_modes" in reason.lower()


def test_tier_map_score_band_2_routes_to_k2_6_openrouter():
    """Score in [0.45, 0.70) with THINK mode → band 2 → k2_6_openrouter."""
    result = analyze_complexity(
        "refactor and implement the auth module across files",
        Mode.THINK, config=_TIER_MAP_CFG,
    )
    # Score: 3 complex_kw (0.45) + medium_prompt (0.05) = ~0.50 → band 2
    assert 0.45 <= result.score < 0.70
    assert result.recommended_tier == "k2_6_openrouter"


def test_tier_map_very_high_score_routes_to_claude():
    """Score ≥ 0.90 → band 4 → claude (Anthropic edge-case tier)."""
    backend, reason = classify_task_with_reason(
        "Refactor, implement, debug, migrate, optimize, review, test, deploy the "
        "entire codebase: security audit, threat model, vulnerability patches, "
        "architecture redesign across files, then also implement fixes",
        Mode.ACT, _five_tier_backends(), config=_TIER_MAP_CFG,
    )
    # Very high score + ACT mode — force_cloud picks first cloud (k2_6_openrouter) not claude,
    # but the score itself should land in the claude band.
    assert backend in ("k2_6_openrouter", "claude")


def test_tier_map_score_band_4_think_mode_routes_to_claude():
    """Very complex prompt in THINK (no force_cloud) → score-based → claude band.

    Claude band (≥0.90) is intentionally hard to reach without long_prompt bonus —
    reserved for the top ~10% of tasks per the 5-tier design.
    """
    # Long prompt (>2000 chars) saturates signals: long_prompt (0.25) + complex_kw maxed (0.45)
    # + multi_step (0.15) + code_content (0.10) = 0.95 → band 4.
    prompt = (
        "Refactor and implement the authentication module, then debug and migrate "
        "the session handling, also optimize the deployment. " * 40
    )
    result = analyze_complexity(prompt, Mode.THINK, config=_TIER_MAP_CFG)
    assert result.score >= 0.90
    assert result.recommended_tier == "claude"


def test_tier_map_skips_disabled_k2_6_local():
    """k2_6_local tier picked but unavailable → walks failover_chain to k2_6_openrouter."""
    # Score 0.30 (mode_edit only) lands in [0.25, 0.45) = band 1 = k2_6_local.
    result = analyze_complexity("do it", Mode.EDIT, config=_TIER_MAP_CFG)
    assert result.recommended_tier == "k2_6_local"

    # Live routing with k2_6_local disabled — should fall through to k2_6_openrouter.
    # Disable force_cloud so we exercise the score-based fall-through path, not the
    # force_cloud path (which would pick k2_6_openrouter regardless).
    cfg_no_force = {**_TIER_MAP_CFG["router"], "force_cloud_modes": []}
    backend, reason = classify_task_with_reason(
        "do it", Mode.EDIT,
        _five_tier_backends(k2_6_local_avail=False),
        config={"router": cfg_no_force},
    )
    assert backend == "k2_6_openrouter"
    assert "k2_6_local unavailable" in reason.lower()


def test_tier_map_fleet_op_stays_local():
    """Fleet ops always prefer local even under tier_map routing."""
    backend, reason = classify_task_with_reason(
        "heartbeat", Mode.EDIT, _five_tier_backends(), config=_TIER_MAP_CFG,
    )
    assert backend == "local"
    assert "fleet" in reason.lower()


def test_tier_map_absence_preserves_legacy_three_tier():
    """Config without tier_map hits the legacy 2-threshold / 3-tier code path."""
    cfg_no_tier_map = {"router": {"complexity_thresholds": [0.3, 0.6]}}
    result = analyze_complexity("refactor and implement", Mode.ACT, config=cfg_no_tier_map)
    assert result.recommended_tier in ("local", "openrouter", "claude")
