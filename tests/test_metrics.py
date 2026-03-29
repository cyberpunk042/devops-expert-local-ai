"""Tests for metrics aggregation."""

from aicp.core.history import save_task
from aicp.core.metrics import aggregate, offload_report


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
