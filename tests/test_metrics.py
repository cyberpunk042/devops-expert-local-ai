"""Tests for metrics aggregation."""

import json
from datetime import datetime, timedelta

import pytest

from aicp.core.history import save_task
from aicp.core.metrics import _parse_window, aggregate, aggregate_window, offload_report


def test_aggregate_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
    m = aggregate()
    assert m["total_tasks"] == 0
    assert m["total_tokens"] == 0


def test_aggregate_with_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))

    save_task(
        prompt="hello", mode="think", backend="local", project="/tmp",
        response="hi", duration_seconds=1.0,
        model="hermes", prompt_tokens=10, completion_tokens=5,
    )
    save_task(
        prompt="bye", mode="think", backend="claude", project="/tmp",
        response="goodbye", duration_seconds=2.0,
        model="opus", prompt_tokens=20, completion_tokens=30,
        estimated_cost_usd=0.001,
    )

    m = aggregate()
    assert m["total_tasks"] == 2
    assert m["total_prompt_tokens"] == 30
    assert m["total_completion_tokens"] == 35
    assert m["total_tokens"] == 65
    assert m["total_cost_usd"] == 0.001
    assert "local" in m["by_backend"]
    assert "claude" in m["by_backend"]
    assert m["by_backend"]["local"]["tasks"] == 1
    assert m["by_backend"]["claude"]["tasks"] == 1


def test_aggregate_error_rate(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))

    save_task("ok", "think", "local", "/tmp", "fine", 1.0)
    save_task("fail", "think", "local", "/tmp", "", 0.5, error="broke")

    m = aggregate()
    assert m["errors"] == 1
    assert m["error_rate"] == 50.0
    assert m["by_backend"]["local"]["error_rate"] == 50.0


# ---------------------------------------------------------------------------
# Offload report
# ---------------------------------------------------------------------------


def test_offload_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
    r = offload_report()
    assert r["total_tasks"] == 0
    assert r["offload_pct"] == 0
    assert r["goal_met"] is False


def test_offload_all_local(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
    for i in range(5):
        save_task(f"q{i}", "think", "local", "/tmp", "a", 1.0,
                  prompt_tokens=100, completion_tokens=50)

    r = offload_report()
    assert r["total_tasks"] == 5
    assert r["local_tasks"] == 5
    assert r["claude_tasks"] == 0
    assert r["offload_pct"] == 100.0
    assert r["goal_met"] is True


def test_offload_mixed(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
    # 8 local, 2 claude → 80% offload
    for i in range(8):
        save_task(f"local{i}", "think", "local", "/tmp", "a", 1.0,
                  prompt_tokens=100, completion_tokens=50)
    for i in range(2):
        save_task(f"claude{i}", "think", "claude", "/tmp", "a", 5.0,
                  prompt_tokens=500, completion_tokens=200, estimated_cost_usd=0.01)

    r = offload_report()
    assert r["total_tasks"] == 10
    assert r["local_tasks"] == 8
    assert r["claude_tasks"] == 2
    assert r["offload_pct"] == 80.0
    assert r["goal_met"] is True
    assert r["claude_cost_usd"] == 0.02
    assert r["estimated_savings_usd"] > 0


def test_offload_below_goal(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
    # 3 local, 7 claude → 30% offload
    for i in range(3):
        save_task(f"local{i}", "think", "local", "/tmp", "a", 1.0,
                  prompt_tokens=100, completion_tokens=50)
    for i in range(7):
        save_task(f"claude{i}", "think", "claude", "/tmp", "a", 5.0,
                  prompt_tokens=500, completion_tokens=200)

    r = offload_report()
    assert r["offload_pct"] == 30.0
    assert r["goal_met"] is False


# ---------------------------------------------------------------------------
# E011-m005: aggregate_window + window parsing
# ---------------------------------------------------------------------------


class TestParseWindow:
    def test_days(self):
        assert _parse_window("7d") == timedelta(days=7)
        assert _parse_window("30d") == timedelta(days=30)

    def test_hours(self):
        assert _parse_window("24h") == timedelta(hours=24)
        assert _parse_window("1h") == timedelta(hours=1)

    def test_minutes(self):
        assert _parse_window("30m") == timedelta(minutes=30)

    def test_bare_int_is_days(self):
        assert _parse_window("7") == timedelta(days=7)

    def test_case_insensitive(self):
        assert _parse_window("7D") == timedelta(days=7)
        assert _parse_window("24H") == timedelta(hours=24)

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            _parse_window("")

    def test_unknown_unit_rejected(self):
        with pytest.raises(ValueError, match="unknown window unit"):
            _parse_window("5y")

    def test_non_numeric_rejected(self):
        with pytest.raises(ValueError, match="unparseable"):
            _parse_window("bogus")


class TestAggregateWindow:
    def test_empty_history(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
        data = aggregate_window("7d")
        assert data["total_tasks"] == 0
        assert data["window"] == "7d"
        assert data["by_backend"] == {}

    def test_k2_6_backends_captured(self, tmp_path, monkeypatch):
        """Dynamic backend discovery — K2.6 tiers appear in by_backend without code changes."""
        monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
        for backend, cost in [("local", 0), ("k2_6_openrouter", 0.001), ("claude", 0.05)]:
            save_task(
                prompt=f"p-{backend}", mode="think", backend=backend, project="/tmp",
                response="r", duration_seconds=1.0, prompt_tokens=100, completion_tokens=50,
                estimated_cost_usd=cost,
            )

        data = aggregate_window("7d")
        assert set(data["by_backend"].keys()) == {"local", "k2_6_openrouter", "claude"}
        # Each backend got 1/3 of traffic
        for b in data["by_backend"].values():
            assert b["share_pct"] == pytest.approx(33.3, abs=0.2)
            assert b["tokens"] == 150

    def test_window_filters_old_records(self, tmp_path, monkeypatch):
        """Records outside the window are excluded."""
        monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))

        # Recent record (in-window)
        save_task(
            prompt="recent", mode="think", backend="k2_6_openrouter", project="/tmp",
            response="r", duration_seconds=1.0,
        )

        # Fabricate an old record (outside window): write the JSON directly with old timestamp
        old_ts = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"
        old_path = tmp_path / "19990101_000000_000000_claude_think.json"
        old_path.write_text(json.dumps({
            "id": "19990101_000000_000000_claude_think",
            "timestamp": old_ts,
            "backend": "claude",
            "mode": "think",
            "prompt": "old",
            "response": "r",
            "duration_seconds": 1.0,
        }))

        # 1h window excludes both old + maybe even the 'recent' if test runs slow — use 7d
        data = aggregate_window("7d")
        assert "k2_6_openrouter" in data["by_backend"]
        assert "claude" not in data["by_backend"]    # 30 days ago, outside 7d window
        assert data["total_tasks"] == 1

    def test_share_pct_and_tokens_computed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
        for _ in range(3):
            save_task("p", "think", "local", "/tmp", "r", 1.0,
                      prompt_tokens=10, completion_tokens=5)
        save_task("p", "think", "k2_6_openrouter", "/tmp", "r", 2.0,
                  prompt_tokens=100, completion_tokens=50, estimated_cost_usd=0.0003)

        data = aggregate_window("1d")
        assert data["total_tasks"] == 4
        assert data["by_backend"]["local"]["share_pct"] == 75.0
        assert data["by_backend"]["k2_6_openrouter"]["share_pct"] == 25.0
        assert data["by_backend"]["k2_6_openrouter"]["tokens"] == 150
        assert data["by_backend"]["k2_6_openrouter"]["cost"] == pytest.approx(0.0003)

    def test_bad_window_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
        with pytest.raises(ValueError):
            aggregate_window("not-a-window")
