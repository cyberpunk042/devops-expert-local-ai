"""Tests for away summary and task integration in agent server."""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from aicp.agent.server import (
    _generate_away_summary,
    save_away_summary,
    load_away_summary,
    _AWAY_SUMMARY_PATH,
)


class TestGenerateAwaySummary:
    def test_with_tasks(self):
        tasks = [
            {"id": "t1", "prompt": "Deploy the new auth module", "mode": "act",
             "backend": "local", "error": None, "response": "Deployed."},
            {"id": "t2", "prompt": "Check health status", "mode": "think",
             "backend": "local", "error": None, "response": "All ok."},
        ]
        with patch("aicp.core.history.list_tasks", return_value=tasks):
            summary = _generate_away_summary({})
            assert "Deploy" in summary
            assert len(summary) > 10

    def test_with_errors(self):
        tasks = [
            {"id": "t1", "prompt": "Run tests", "mode": "act",
             "backend": "local", "error": "Connection refused", "response": ""},
        ]
        with patch("aicp.core.history.list_tasks", return_value=tasks):
            summary = _generate_away_summary({})
            assert "error" in summary.lower() or "Connection" in summary

    def test_empty_history(self):
        with patch("aicp.core.history.list_tasks", return_value=[]):
            summary = _generate_away_summary({})
            assert summary == ""

    def test_exception_handling(self):
        with patch("aicp.core.history.list_tasks", side_effect=RuntimeError("db error")):
            summary = _generate_away_summary({})
            assert "unavailable" in summary


class TestAwaySummaryPersistence:
    def test_save_and_load(self, tmp_path, monkeypatch):
        summary_path = tmp_path / "away_summary.txt"
        monkeypatch.setattr("aicp.agent.server._AWAY_SUMMARY_PATH", summary_path)

        save_away_summary("Working on auth module. Next: deploy to staging.")
        loaded = load_away_summary()
        assert "auth module" in loaded

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("aicp.agent.server._AWAY_SUMMARY_PATH", tmp_path / "nope.txt")
        assert load_away_summary() == ""

    def test_save_creates_directory(self, tmp_path, monkeypatch):
        deep_path = tmp_path / "deep" / "nested" / "summary.txt"
        monkeypatch.setattr("aicp.agent.server._AWAY_SUMMARY_PATH", deep_path)
        save_away_summary("test summary")
        assert deep_path.exists()

    def test_save_overwrites(self, tmp_path, monkeypatch):
        summary_path = tmp_path / "away.txt"
        monkeypatch.setattr("aicp.agent.server._AWAY_SUMMARY_PATH", summary_path)
        save_away_summary("old summary")
        save_away_summary("new summary")
        assert "new summary" in load_away_summary()
