"""Tests for model gallery & lifecycle management (M67)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from aicp.backends.localai import LocalAIBackend


def _make_backend(**kwargs) -> LocalAIBackend:
    defaults = dict(
        base_url="http://localhost:8090",
        model="hermes",
        max_tokens=256,
        api_key="",
    )
    defaults.update(kwargs)
    return LocalAIBackend(**defaults)


# ── models_available ─────────────────────────────────────────────────────────

class TestModelsAvailable:
    def test_returns_gallery_models(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "name": "phi-2",
                "description": "Microsoft Phi-2",
                "installed": False,
                "tags": ["llm", "gguf"],
                "gallery": {"name": "huggingface"},
                "license": "MIT",
            },
            {
                "name": "hermes-2-pro",
                "description": "NousResearch Hermes",
                "installed": True,
                "tags": ["llm", "function-calling"],
                "gallery": {"name": "localai"},
                "license": "Apache-2.0",
            },
        ]

        with patch("httpx.get", return_value=mock_resp):
            result = backend.models_available()

        assert len(result) == 2
        assert result[0]["name"] == "phi-2"
        assert result[0]["installed"] is False
        assert result[1]["installed"] is True
        assert "llm" in result[0]["tags"]

    def test_empty_gallery(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        with patch("httpx.get", return_value=mock_resp):
            result = backend.models_available()

        assert result == []

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.models_available()

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("httpx.get", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.models_available()


# ── model_apply ──────────────────────────────────────────────────────────────

class TestModelApply:
    def test_returns_job_uuid(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "uuid": "abc-123-def",
            "status": "http://localhost:8090/models/jobs/abc-123-def",
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = backend.model_apply("huggingface@user/model")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["id"] == "huggingface@user/model"
        assert result["uuid"] == "abc-123-def"

    def test_with_custom_name(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"uuid": "xyz"}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.model_apply("gallery@model", name="my-model")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["name"] == "my-model"

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="400"):
                backend.model_apply("bad-model")


# ── model_job_status ─────────────────────────────────────────────────────────

class TestModelJobStatus:
    def test_in_progress(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "processed": False,
            "progress": 45.2,
            "file_size": "4.2GB",
            "downloaded_size": "1.9GB",
            "message": "downloading",
            "error": None,
        }

        with patch("httpx.get", return_value=mock_resp):
            result = backend.model_job_status("abc-123")

        assert result["processed"] is False
        assert result["progress"] == 45.2

    def test_completed(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "processed": True,
            "message": "completed",
            "error": None,
        }

        with patch("httpx.get", return_value=mock_resp):
            result = backend.model_job_status("abc-123")

        assert result["processed"] is True

    def test_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "processed": True,
            "error": "download failed: 404",
        }

        with patch("httpx.get", return_value=mock_resp):
            result = backend.model_job_status("abc-123")

        assert result["error"] is not None


# ── model_shutdown ───────────────────────────────────────────────────────────

class TestModelShutdown:
    def test_success(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = backend.model_shutdown("hermes")

        assert result is True
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["model"] == "hermes"
        assert "/backend/shutdown" in str(mock_post.call_args)

    def test_failure(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("httpx.post", return_value=mock_resp):
            result = backend.model_shutdown("hermes")

        assert result is False


# ── model_monitor ────────────────────────────────────────────────────────────

class TestModelMonitor:
    def test_returns_state_and_memory(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "state": 2,
            "memory": {
                "total": 4294967296,
                "breakdown": {"weights": 3800000000, "kv_cache": 494967296},
            },
        }

        with patch("httpx.post", return_value=mock_resp):
            result = backend.model_monitor("hermes")

        assert result["state"] == 2
        assert result["memory"]["total"] == 4294967296

    def test_model_not_loaded(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        with patch("httpx.post", return_value=mock_resp):
            result = backend.model_monitor("nonexistent")

        assert result["state"] == -1

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.model_monitor("hermes")


# ── MCP tools ────────────────────────────────────────────────────────────────

class TestMcpModelTools:
    def test_aicp_model_gallery(self):
        from aicp.mcp.server import aicp_model_gallery

        mock_backend = MagicMock()
        mock_backend.models_available.return_value = [
            {"name": "phi-2", "installed": False, "tags": ["llm"]},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_gallery(search="phi")

        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        available = parsed["available"]
        assert len(available) == 1
        assert available[0]["name"] == "phi-2"

    def test_aicp_model_gallery_no_filter(self):
        from aicp.mcp.server import aicp_model_gallery

        mock_backend = MagicMock()
        mock_backend.models_available.return_value = [
            {"name": "model-a", "installed": True, "description": "test"},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_gallery()

        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        assert len(parsed["available"]) == 1

    def test_aicp_model_install(self):
        from aicp.mcp.server import aicp_model_install

        mock_backend = MagicMock()
        mock_backend.model_apply.return_value = {"uuid": "job-123"}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_install("gallery@model", name="custom")

        mock_backend.model_apply.assert_called_once_with("gallery@model", name="custom")
        parsed = json.loads(result)
        assert parsed["uuid"] == "job-123"

    def test_aicp_model_status_job(self):
        from aicp.mcp.server import aicp_model_status

        mock_backend = MagicMock()
        mock_backend.model_job_status.return_value = {
            "processed": False, "progress": 50.0,
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_status("abc12345-6789-abcd-ef01-234567890abc")

        parsed = json.loads(result)
        assert parsed["progress"] == 50.0

    def test_aicp_model_status_model(self):
        from aicp.mcp.server import aicp_model_status

        mock_backend = MagicMock()
        mock_backend.model_monitor.return_value = {"state": 2, "memory": {}}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_status("hermes")

        parsed = json.loads(result)
        assert parsed["state_label"] == "ready"

    def test_aicp_model_unload(self):
        from aicp.mcp.server import aicp_model_unload

        mock_backend = MagicMock()
        mock_backend.model_shutdown.return_value = True

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_unload("hermes")

        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        assert parsed["unloaded"] is True
        assert parsed["model"] == "hermes"

    def test_aicp_model_unload_failure(self):
        from aicp.mcp.server import aicp_model_unload

        mock_backend = MagicMock()
        mock_backend.model_shutdown.return_value = False

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_unload("hermes")

        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        assert parsed["unloaded"] is False
        assert parsed["model"] == "hermes"
