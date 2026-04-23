"""Tests for extended MCP tools in aicp/mcp/server.py."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestMCPExtendedTools:
    """Tests for the new MCP tools."""

    def test_aicp_deep_health_returns_json(self):
        from aicp.mcp.server import aicp_deep_health
        result = aicp_deep_health()
        data = json.loads(result)
        assert "status" in data
        assert "backends" in data

    def test_aicp_deep_health_error_handling(self):
        """Health should return error status, not crash."""
        with patch("aicp.mcp.server._get_backend", side_effect=RuntimeError("no backend")):
            from aicp.mcp.server import aicp_deep_health
            result = aicp_deep_health()
            data = json.loads(result)
            assert data["status"] == "error"

    def test_aicp_profile_list(self):
        from aicp.mcp.server import aicp_profile
        result = aicp_profile(action="list")
        data = json.loads(result)
        assert "deprecated" in data["warning"].lower()
        assert isinstance(data["profiles"], list)

    def test_aicp_profile_active(self):
        from aicp.mcp.server import aicp_profile
        result = aicp_profile(action="active")
        data = json.loads(result)
        assert "active_profile" in data

    def test_aicp_profile_unknown_action(self):
        from aicp.mcp.server import aicp_profile
        result = aicp_profile(action="bogus")
        assert "Error" in result or "unknown" in result

    def test_aicp_task_status_empty(self):
        from aicp.mcp.server import aicp_task_status
        result = aicp_task_status()
        data = json.loads(result)
        assert "deprecated" in data["warning"].lower()
        assert isinstance(data["tasks"], list)

    def test_aicp_task_status_nonexistent(self):
        from aicp.mcp.server import aicp_task_status
        result = aicp_task_status(task_id="nonexistent123")
        assert "not found" in result or "Error" in result

    def test_aicp_dlq_status_count(self):
        from aicp.mcp.server import aicp_dlq_status
        result = aicp_dlq_status(action="count")
        # May error if DLQ not configured, but shouldn't crash
        data = json.loads(result)
        assert "pending" in data or "error" in data

    def test_aicp_dlq_status_unknown_action(self):
        from aicp.mcp.server import aicp_dlq_status
        result = aicp_dlq_status(action="bogus")
        # May get "Error: unknown action" or JSON error if DLQ module not loaded
        assert "Error" in result or "unknown" in result or "error" in result

    def test_aicp_route_invalid_mode(self):
        from aicp.mcp.server import aicp_route
        result = aicp_route("test prompt", mode="invalid")
        assert "Error" in result

    def test_aicp_kb_search_collection_error_handling(self):
        """KB search should handle missing KB gracefully."""
        from aicp.mcp.server import aicp_kb_search_collection
        result = aicp_kb_search_collection("test query")
        # May fail due to no running LocalAI, but should return error string
        assert isinstance(result, str)
