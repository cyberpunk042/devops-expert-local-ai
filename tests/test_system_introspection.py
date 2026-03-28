"""Tests for system introspection (system info, backends, active model)."""

from unittest.mock import MagicMock, patch
import json

import pytest

from aicp.core.observability import get_system_info, get_backends_detail


# ── get_system_info tests ────────────────────────────────────────────────────

class TestGetSystemInfo:
    def test_returns_loaded_models(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "loaded_models": [{"id": "hermes"}],
            "backends": ["cuda12-llama-cpp", "whisper", "piper"],
        }
        with patch("httpx.get", return_value=mock_resp):
            result = get_system_info("http://localhost:8090")

        assert result["available"] is True
        assert result["loaded_models"] == ["hermes"]
        assert "cuda12-llama-cpp" in result["backends"]

    def test_no_models_loaded(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "loaded_models": [],
            "backends": ["cuda12-llama-cpp"],
        }
        with patch("httpx.get", return_value=mock_resp):
            result = get_system_info("http://localhost:8090")

        assert result["loaded_models"] == []

    def test_connection_error(self):
        import httpx
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            result = get_system_info("http://localhost:8090")

        assert result["available"] is False
        assert result["loaded_models"] == []

    def test_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("httpx.get", return_value=mock_resp):
            result = get_system_info("http://localhost:8090")

        assert result["available"] is False


# ── get_backends_detail tests ────────────────────────────────────────────────

class TestGetBackendsDetail:
    def test_returns_backend_list(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"Name": "cuda12-llama-cpp", "IsMeta": False, "Metadata": {"name": "cuda12-llama-cpp"}},
            {"Name": "whisper", "IsMeta": False, "Metadata": {"name": "whisper"}},
            {"Name": "stablediffusion-ggml", "IsMeta": False, "Metadata": {"alias": "stablediffusion-ggml", "name": "cuda12-stablediffusion-ggml"}},
        ]
        with patch("httpx.get", return_value=mock_resp):
            result = get_backends_detail("http://localhost:8090")

        assert len(result) == 3
        assert result[0]["name"] == "cuda12-llama-cpp"
        assert result[2]["alias"] == "stablediffusion-ggml"

    def test_filters_meta_backends(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"Name": "real-backend", "IsMeta": False, "Metadata": {}},
            {"Name": "meta-backend", "IsMeta": True, "Metadata": {}},
        ]
        with patch("httpx.get", return_value=mock_resp):
            result = get_backends_detail("http://localhost:8090")

        assert len(result) == 1
        assert result[0]["name"] == "real-backend"

    def test_connection_error(self):
        import httpx
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            result = get_backends_detail("http://localhost:8090")

        assert result == []


# ── get_system_status integration ────────────────────────────────────────────

class TestSystemStatusIntegration:
    def test_status_includes_loaded_models(self):
        from aicp.core.observability import get_system_status

        with patch("aicp.core.observability.get_loaded_models", return_value=["hermes", "nomic-embed"]), \
             patch("aicp.core.observability.scrape_prometheus", return_value={"available": True}), \
             patch("aicp.core.observability.get_gpu_status", return_value={"available": False}), \
             patch("aicp.core.observability.get_system_info", return_value={
                 "available": True,
                 "loaded_models": ["hermes"],
                 "backends": ["cuda12-llama-cpp"],
             }):
            status = get_system_status("http://localhost:8090")

        assert status["localai"]["loaded_models"] == ["hermes"]
        assert status["localai"]["backends"] == ["cuda12-llama-cpp"]
        assert "hermes" in status["localai"]["models"]


# ── MCP tool tests ────────────────────────────────────────────────────────────

class TestAicpSystem:
    def test_mcp_system_returns_json(self):
        from aicp.mcp.server import aicp_system

        backend = MagicMock()
        backend.base_url = "http://localhost:8090"

        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=backend),
        ), \
             patch("aicp.core.observability.get_system_info", return_value={
                 "loaded_models": ["hermes"],
                 "backends": ["cuda12-llama-cpp", "whisper"],
             }), \
             patch("aicp.core.observability.get_loaded_models", return_value=["hermes", "nomic-embed"]):
            result = aicp_system()

        parsed = json.loads(result)
        assert parsed["active_gpu_model"] == ["hermes"]
        assert "cuda12-llama-cpp" in parsed["installed_backends"]
        assert "hermes" in parsed["configured_models"]
