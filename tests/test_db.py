"""Tests for the optional SQLite metrics store."""

from __future__ import annotations

import sqlite3

import pytest

from aicp.core.db import query_tasks, rebuild_db, record_task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(record_id: str = "test_001", backend: str = "local") -> dict:
    return {
        "id": record_id,
        "timestamp": "2026-03-27T12:00:00Z",
        "mode": "think",
        "backend": backend,
        "model": "hermes",
        "project": "/tmp/test-project",
        "duration_seconds": 1.5,
        "prompt_tokens": 50,
        "completion_tokens": 100,
        "total_tokens": 150,
        "estimated_cost_usd": 0.0,
        "error": None,
        "prompt": "Test prompt for db tests",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_record_task_no_db_file(monkeypatch):
    """record_task() is a no-op when AICP_DB_FILE is not set."""
    monkeypatch.delenv("AICP_DB_FILE", raising=False)
    record_task(_make_record())  # should not raise


def test_record_and_query(tmp_path, monkeypatch):
    """record_task() writes to SQLite; query_tasks() reads it back."""
    db = tmp_path / "test.db"
    monkeypatch.setenv("AICP_DB_FILE", str(db))

    record_task(_make_record("r1", backend="local"))
    record_task(_make_record("r2", backend="claude"))

    all_tasks = query_tasks(limit=10)
    assert len(all_tasks) == 2

    local_tasks = query_tasks(backend="local", limit=10)
    assert len(local_tasks) == 1
    assert local_tasks[0]["id"] == "r1"

    claude_tasks = query_tasks(backend="claude", limit=10)
    assert len(claude_tasks) == 1
    assert claude_tasks[0]["id"] == "r2"


def test_query_no_db_returns_empty(monkeypatch, tmp_path):
    """query_tasks() returns [] when no DB file exists."""
    monkeypatch.setenv("AICP_DB_FILE", str(tmp_path / "nonexistent.db"))
    result = query_tasks(limit=10)
    assert result == []


def test_record_task_upsert(tmp_path, monkeypatch):
    """Inserting same ID twice updates the record (INSERT OR REPLACE)."""
    db = tmp_path / "test.db"
    monkeypatch.setenv("AICP_DB_FILE", str(db))

    r = _make_record("dup_id")
    record_task(r)

    r2 = dict(r)
    r2["duration_seconds"] = 99.9
    record_task(r2)

    tasks = query_tasks(limit=10)
    assert len(tasks) == 1
    assert tasks[0]["duration_seconds"] == 99.9


def test_rebuild_db_no_env(monkeypatch):
    """rebuild_db() raises when AICP_DB_FILE is not set."""
    monkeypatch.delenv("AICP_DB_FILE", raising=False)
    with pytest.raises(RuntimeError, match="AICP_DB_FILE"):
        rebuild_db()


def test_rebuild_db_from_history(tmp_path, monkeypatch):
    """rebuild_db() imports existing JSON history files into the DB."""
    import json

    # Set up a fake history directory with two task records
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    monkeypatch.setenv("AICP_HISTORY_DIR", str(history_dir))

    for i, backend in enumerate(["local", "claude"]):
        r = _make_record(f"hist_{i}", backend=backend)
        (history_dir / f"hist_{i}.json").write_text(json.dumps(r))

    db = tmp_path / "rebuild.db"
    monkeypatch.setenv("AICP_DB_FILE", str(db))

    count = rebuild_db()
    assert count == 2

    tasks = query_tasks(limit=10)
    assert len(tasks) == 2


def test_schema_has_expected_columns(tmp_path, monkeypatch):
    """The tasks table has all required columns."""
    db = tmp_path / "schema_test.db"
    monkeypatch.setenv("AICP_DB_FILE", str(db))
    record_task(_make_record())  # triggers schema creation

    conn = sqlite3.connect(str(db))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    conn.close()

    required = {
        "id", "timestamp", "mode", "backend", "model", "project",
        "duration_seconds", "prompt_tokens", "completion_tokens",
        "total_tokens", "estimated_cost_usd", "error", "prompt_preview",
    }
    assert required.issubset(cols)
