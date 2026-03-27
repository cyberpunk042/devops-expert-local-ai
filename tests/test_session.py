"""Tests for session continuity (aicp/core/session.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aicp.core.session import (
    load_session, save_session, delete_session, list_sessions, _safe_name,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msgs(*pairs: tuple) -> list:
    """Build a message list from (role, content) pairs."""
    return [{"role": r, "content": c} for r, c in pairs]


# ---------------------------------------------------------------------------
# _safe_name
# ---------------------------------------------------------------------------

def test_safe_name_alphanum():
    assert _safe_name("myproject") == "myproject"


def test_safe_name_replaces_spaces():
    assert _safe_name("my project") == "my_project"


def test_safe_name_allows_hyphens_dots():
    assert _safe_name("my-session.v2") == "my-session.v2"


def test_safe_name_truncates_to_64():
    long_name = "a" * 100
    assert len(_safe_name(long_name)) == 64


# ---------------------------------------------------------------------------
# load / save / delete round-trip
# ---------------------------------------------------------------------------

def test_load_nonexistent_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    result = load_session("no-such-session")
    assert result == []


def test_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    messages = _msgs(("user", "hello"), ("assistant", "hi there"))
    save_session("test", messages)

    loaded = load_session("test")
    assert len(loaded) == 2
    assert loaded[0]["role"] == "user"
    assert loaded[0]["content"] == "hello"
    assert loaded[1]["content"] == "hi there"


def test_save_overwrites_previous(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    save_session("s1", _msgs(("user", "first")))
    save_session("s1", _msgs(("user", "second"), ("assistant", "ok")))
    loaded = load_session("s1")
    assert len(loaded) == 2
    assert loaded[0]["content"] == "second"


def test_delete_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    save_session("todelete", _msgs(("user", "bye")))
    assert delete_session("todelete") is True
    assert load_session("todelete") == []


def test_delete_nonexistent(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    assert delete_session("ghost") is False


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------

def test_list_sessions_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    assert list_sessions() == []


def test_list_sessions_returns_all(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    save_session("alpha", _msgs(("user", "a"), ("assistant", "b")))
    save_session("beta", _msgs(("user", "x")))

    sessions = list_sessions()
    names = {s["name"] for s in sessions}
    assert "alpha" in names
    assert "beta" in names


def test_list_sessions_turn_count(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    # 2 user+assistant pairs = 4 messages (excluding system = turns=2)
    msgs = _msgs(("user", "q1"), ("assistant", "a1"), ("user", "q2"), ("assistant", "a2"))
    save_session("counted", msgs)
    sessions = list_sessions()
    s = next(s for s in sessions if s["name"] == "counted")
    assert s["turns"] == 2


def test_session_file_format(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    save_session("fmt", _msgs(("user", "test")))
    session_dir = tmp_path / "sessions"
    files = list(session_dir.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert "name" in data
    assert "updated" in data
    assert "messages" in data
    assert "message_count" in data


def test_session_survives_corrupt_file(tmp_path, monkeypatch):
    """list_sessions() skips corrupt files gracefully."""
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    session_dir = tmp_path / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "corrupt.json").write_text("{invalid json")
    save_session("good", _msgs(("user", "hi")))

    sessions = list_sessions()
    names = [s["name"] for s in sessions]
    assert "good" in names
    # corrupt file should be skipped, not raise
