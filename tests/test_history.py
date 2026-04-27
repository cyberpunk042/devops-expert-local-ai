"""Tests for task history."""


from aicp.core.history import get_task, list_tasks, save_task


def test_save_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))

    rid = save_task(
        prompt="What is 2+2?",
        mode="think",
        backend="local",
        project="/tmp/test",
        response="4",
        duration_seconds=1.5,
    )

    assert rid is not None
    assert (tmp_path / f"{rid}.json").exists()

    records = list_tasks(10)
    assert len(records) == 1
    assert records[0]["prompt"] == "What is 2+2?"
    assert records[0]["response"] == "4"
    assert records[0]["duration_seconds"] == 1.5


def test_save_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))

    rid = save_task(
        prompt="fail",
        mode="think",
        backend="local",
        project="/tmp/test",
        response="",
        duration_seconds=0.1,
        error="something broke",
    )

    record = get_task(rid)
    assert record is not None
    assert record["error"] == "something broke"


def test_get_task_by_id(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))

    rid = save_task(
        prompt="hello",
        mode="think",
        backend="claude",
        project="/tmp/test",
        response="hi",
        duration_seconds=2.0,
    )

    record = get_task(rid)
    assert record is not None
    assert record["backend"] == "claude"


def test_list_tasks_order(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))

    # Create two records with different names to ensure order
    import time
    save_task("first", "think", "local", "/tmp", "a", 1.0)
    time.sleep(0.01)  # ensure different filenames
    save_task("second", "think", "local", "/tmp", "b", 1.0)

    records = list_tasks(10)
    assert len(records) == 2
    # newest first
    assert records[0]["prompt"] == "second"
    assert records[1]["prompt"] == "first"


def test_get_task_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HISTORY_DIR", str(tmp_path))
    assert get_task("nonexistent") is None
