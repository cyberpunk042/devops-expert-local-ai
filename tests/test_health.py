"""Tests for backend health checks."""

import shutil

from aicp.backends.claude_code import ClaudeCodeBackend
from aicp.backends.localai import LocalAIBackend


class TestLocalAIHealth:
    def test_unavailable_when_not_running(self):
        """LocalAI on a random port should be unavailable."""
        backend = LocalAIBackend(base_url="http://localhost:19999")
        assert backend.is_available() is False

    def test_status_detail_when_unavailable(self):
        backend = LocalAIBackend(base_url="http://localhost:19999")
        detail = backend.status_detail()
        assert "UNAVAILABLE" in detail


class TestClaudeCodeHealth:
    def test_available_when_installed(self):
        """If claude is on PATH, it should report available."""
        if not shutil.which("claude"):
            return  # skip if not installed
        backend = ClaudeCodeBackend()
        assert backend.is_available() is True

    def test_status_detail_shows_version(self):
        if not shutil.which("claude"):
            return
        backend = ClaudeCodeBackend()
        detail = backend.status_detail()
        assert "OK" in detail
        assert "version" in detail
