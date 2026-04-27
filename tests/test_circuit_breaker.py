"""Tests for circuit breaker — state machine, integration with controller."""

import time
from unittest.mock import MagicMock

import pytest

from aicp.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    State,
    build_breakers,
)

# ---------------------------------------------------------------------------
# State machine tests
# ---------------------------------------------------------------------------


class TestStateMachine:
    def test_starts_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == State.CLOSED

    def test_stays_closed_on_success(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == State.CLOSED
        assert cb.failure_count == 0

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == State.CLOSED
        assert cb.failure_count == 2

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == State.OPEN
        assert cb.failure_count == 3

    def test_open_rejects_calls(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == State.OPEN
        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: "should not run")

    def test_open_to_half_open_after_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == State.OPEN
        time.sleep(0.15)
        assert cb.state == State.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        time.sleep(0.15)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == State.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        time.sleep(0.15)
        assert cb.state == State.HALF_OPEN
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("still broken")))
        assert cb.state == State.OPEN

    def test_half_open_limits_concurrent_probes(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1, half_open_max=1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        time.sleep(0.15)
        # Simulate first probe occupying the slot
        cb._half_open_active = 1
        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: "should be rejected")

    def test_reset_closes_breaker(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == State.OPEN
        cb.reset()
        assert cb.state == State.CLOSED
        assert cb.failure_count == 0

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        # 2 failures
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.failure_count == 2
        # 1 success resets
        cb.call(lambda: "ok")
        assert cb.failure_count == 0


# ---------------------------------------------------------------------------
# Status and diagnostics
# ---------------------------------------------------------------------------


class TestStatus:
    def test_status_closed(self):
        cb = CircuitBreaker(name="local")
        s = cb.status()
        assert s["name"] == "local"
        assert s["state"] == "closed"
        assert s["failure_count"] == 0
        assert s["open_since"] is None

    def test_status_open(self):
        cb = CircuitBreaker(name="local", failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        s = cb.status()
        assert s["state"] == "open"
        assert s["open_since"] is not None
        assert s["failure_count"] == 1


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


class TestCallbacks:
    def test_on_state_change_called(self):
        changes = []
        cb = CircuitBreaker(name="local", failure_threshold=1, recovery_timeout=0.1)
        cb._on_state_change = lambda name, state: changes.append((name, state))
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert ("local", "open") in changes

    def test_on_trip_called(self):
        trips = []
        cb = CircuitBreaker(name="local", failure_threshold=1)
        cb._on_trip = lambda name: trips.append(name)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert trips == ["local"]


# ---------------------------------------------------------------------------
# Build from config
# ---------------------------------------------------------------------------


class TestBuildBreakers:
    def test_builds_per_backend(self):
        breakers = build_breakers(["local", "claude", "openrouter"])
        assert "local" in breakers
        assert "claude" in breakers
        assert "openrouter" in breakers
        assert all(b.state == State.CLOSED for b in breakers.values())

    def test_reads_config(self):
        config = {"circuit_breaker": {"failure_threshold": 5, "recovery_timeout": 60}}
        breakers = build_breakers(["local"], config)
        assert breakers["local"].failure_threshold == 5
        assert breakers["local"].recovery_timeout == 60

    def test_defaults_without_config(self):
        breakers = build_breakers(["local"])
        assert breakers["local"].failure_threshold == 3
        assert breakers["local"].recovery_timeout == 30.0

    def test_per_backend_overrides_defaults(self):
        """E011-m004: per_backend[name] values win over global circuit_breaker defaults."""
        config = {
            "circuit_breaker": {
                "failure_threshold": 3,
                "recovery_timeout": 30,
                "per_backend": {
                    "k2_6_local": {"failure_threshold": 1, "recovery_timeout": 15},
                    "claude": {"failure_threshold": 5, "recovery_timeout": 120},
                },
            }
        }
        breakers = build_breakers(
            ["local", "k2_6_local", "k2_6_openrouter", "claude"], config,
        )
        # Overridden backends get their per_backend values
        assert breakers["k2_6_local"].failure_threshold == 1
        assert breakers["k2_6_local"].recovery_timeout == 15
        assert breakers["claude"].failure_threshold == 5
        assert breakers["claude"].recovery_timeout == 120
        # Backends without a per_backend entry use global defaults
        assert breakers["local"].failure_threshold == 3
        assert breakers["k2_6_openrouter"].failure_threshold == 3

    def test_per_backend_partial_override_merges(self):
        """Partial override (only one key) leaves other fields at global defaults."""
        config = {
            "circuit_breaker": {
                "failure_threshold": 4,
                "recovery_timeout": 45,
                "per_backend": {"local": {"failure_threshold": 2}},
            }
        }
        breakers = build_breakers(["local"], config)
        assert breakers["local"].failure_threshold == 2    # overridden
        assert breakers["local"].recovery_timeout == 45    # inherited from global

    def test_per_backend_none_is_tolerated(self):
        """Explicit per_backend: null (YAML) must not crash."""
        config = {"circuit_breaker": {"per_backend": None}}
        breakers = build_breakers(["local"], config)
        assert breakers["local"].failure_threshold == 3    # uses defaults

    def test_per_backend_empty_dict_is_tolerated(self):
        config = {"circuit_breaker": {"per_backend": {}}}
        breakers = build_breakers(["local"], config)
        assert breakers["local"].failure_threshold == 3


# ---------------------------------------------------------------------------
# Controller integration
# ---------------------------------------------------------------------------


class TestControllerIntegration:
    def test_breaker_opens_after_failures(self, tmp_path):
        from aicp.core.controller import Controller, Task
        from aicp.core.modes import Mode

        backend = MagicMock()
        backend.execute.side_effect = RuntimeError("LocalAI down")
        backend.last_usage = {}

        claude = MagicMock()
        claude.execute.return_value = "claude result"
        claude.last_usage = {}

        ctrl = Controller(
            backends={"local": backend, "claude": claude},
            config={
                "cluster": {"auto_route": True, "config_file": "/nonexistent"},
                "circuit_breaker": {"failure_threshold": 2, "recovery_timeout": 60},
            },
        )

        # First 2 calls fail → breaker opens
        # 3rd call should skip local entirely (breaker open) → failover to claude
        for i in range(3):
            task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
            result = ctrl.run(task)

        # After breaker opens, claude should be used via failover
        assert "failover:claude" in ctrl.last_route or result == "claude result"

    def test_breakers_created_for_all_backends(self):
        from aicp.core.controller import Controller

        ctrl = Controller(
            backends={"local": MagicMock(), "claude": MagicMock()},
            config={},
        )
        assert "local" in ctrl._breakers
        assert "claude" in ctrl._breakers

    def test_5_tier_failover_when_k2_6_openrouter_opens(self, tmp_path):
        """E011-m004: k2_6_openrouter breaker OPEN → router cascades to openrouter tier.

        Primes k2_6_openrouter with failures until its breaker opens, then a subsequent
        call should skip it entirely and land on the next available tier (openrouter).
        """
        from aicp.core.controller import Controller, Task
        from aicp.core.modes import Mode

        k2_6 = MagicMock()
        k2_6.execute.side_effect = RuntimeError("OpenRouter 500")
        k2_6.last_usage = {}

        openrouter = MagicMock()
        openrouter.execute.return_value = "opus fallback result"
        openrouter.last_usage = {}

        claude = MagicMock()
        claude.execute.return_value = "claude edge-case result"
        claude.last_usage = {}

        ctrl = Controller(
            backends={"k2_6_openrouter": k2_6, "openrouter": openrouter, "claude": claude},
            config={
                "cluster": {"auto_route": True, "config_file": "/nonexistent"},
                "circuit_breaker": {
                    "per_backend": {"k2_6_openrouter": {"failure_threshold": 2}},
                },
                "router": {
                    "failover_chain": [
                        "local", "k2_6_local", "k2_6_openrouter", "openrouter", "claude",
                    ],
                },
            },
        )

        # Drive enough calls to open the k2_6_openrouter breaker (threshold=2) and
        # verify the subsequent one cascades to openrouter. Unique prompts dodge the
        # response cache so each run hits the backend freshly.
        for i in range(3):
            task = Task(
                prompt=f"hello #{i}", mode=Mode.THINK, project_path=tmp_path,
                backend_name="k2_6_openrouter",
            )
            result = ctrl.run(task)

        assert ctrl._breakers["k2_6_openrouter"].state == State.OPEN
        assert result == "opus fallback result"
        assert "failover:openrouter" in ctrl.last_route
