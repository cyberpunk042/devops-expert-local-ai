"""Tests for metrics aggregation."""

from aicp.core.history import save_task
from aicp.core.metrics import aggregate


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
