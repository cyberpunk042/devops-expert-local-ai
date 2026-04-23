"""Tests for health endpoints, backend management, and feature detection (M71)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode


def _make_backend(**kwargs) -> LocalAIBackend:
    defaults = dict(
        base_url="http://localhost:8090",
        model="hermes",
        max_tokens=256,
        api_key="",
    )
    defaults.update(kwargs)
    return LocalAIBackend(**defaults)


# ── Health & Readiness ───────────────────────────────────────────────────────

class TestHealthCheck:
    def test_healthy(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.get", return_value=mock_resp):
            result = backend.health_check()

        assert result["healthy"] is True
        assert result["status_code"] == 200

    def test_unhealthy(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch("httpx.get", return_value=mock_resp):
            result = backend.health_check()

        assert result["healthy"] is False

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            with patch("time.sleep"):  # don't wait through retries
                result = backend.health_check()

        assert result["healthy"] is False
        assert "model loading" in result["error"] or "retried" in result["error"]

    def test_timeout(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
            result = backend.health_check()

        assert result["healthy"] is False
        assert "timeout" in result["error"]


class TestIsReady:
    def test_ready(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.get", return_value=mock_resp):
            assert backend.is_ready() is True

    def test_not_ready(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch("httpx.get", return_value=mock_resp):
            assert backend.is_ready() is False

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            assert backend.is_ready() is False


# ── Backend Management ───────────────────────────────────────────────────────

class TestBackendsList:
    def test_returns_list(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"name": "llama-cpp", "type": "inference"},
            {"name": "whisper", "type": "audio"},
        ]

        with patch("httpx.get", return_value=mock_resp):
            result = backend.backends_list()

        assert len(result) == 2
        assert result[0]["name"] == "llama-cpp"

    def test_empty_on_404(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("httpx.get", return_value=mock_resp):
            result = backend.backends_list()

        assert result == []

    def test_empty_on_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            result = backend.backends_list()

        assert result == []


class TestBackendApply:
    def test_success(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"uuid": "abc-123", "status": "pending"}

        with patch("httpx.post", return_value=mock_resp):
            result = backend.backend_apply("diffusers")

        assert result["uuid"] == "abc-123"

    def test_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "internal error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.backend_apply("broken")

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.backend_apply("test")


class TestBackendDelete:
    def test_success(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.post", return_value=mock_resp):
            assert backend.backend_delete("old-backend") is True

    def test_failure(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("httpx.post", return_value=mock_resp):
            assert backend.backend_delete("nonexistent") is False

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            assert backend.backend_delete("test") is False


class TestModelDelete:
    def test_success(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.post", return_value=mock_resp):
            assert backend.model_delete("old-model") is True

    def test_failure(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("httpx.post", return_value=mock_resp):
            assert backend.model_delete("nonexistent") is False


# ── Server Config & Feature Detection ────────────────────────────────────────

class TestServerConfig:
    def test_returns_structure(self):
        backend = _make_backend()

        def _mock_get(url, **kw):
            resp = MagicMock()
            if "/healthz" in url:
                resp.status_code = 200
            elif "/readyz" in url:
                resp.status_code = 200
            elif "/v1/models" in url:
                resp.status_code = 200
                resp.json.return_value = {"data": [{"id": "hermes"}]}
            elif "/api/backends" in url:
                resp.status_code = 200
                resp.json.return_value = ["llama-cpp"]
            else:
                resp.status_code = 404
            return resp

        def _mock_post(url, **kw):
            resp = MagicMock()
            if "/v1/tokenize" in url:
                resp.status_code = 200
            else:
                resp.status_code = 404
            return resp

        with patch("httpx.get", side_effect=_mock_get):
            with patch("httpx.post", side_effect=_mock_post):
                result = backend.server_config()

        assert result["healthy"] is True
        assert result["ready"] is True
        assert "hermes" in result["models"]
        assert "tokenize" in result["features"]

    def test_unhealthy_returns_early(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
                result = backend.server_config()

        assert result["healthy"] is False
        assert result["models"] == []
        assert result["features"] == []


# ── MCP Tools ────────────────────────────────────────────────────────────────

class TestMcpHealthTools:
    def test_aicp_health(self):
        from aicp.mcp.server import aicp_health

        mock_backend = MagicMock()
        mock_backend.health_check.return_value = {"healthy": True, "status_code": 200}
        mock_backend.is_ready.return_value = True

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_health()

        parsed = json.loads(result)
        assert parsed["healthy"] is True
        assert parsed["ready"] is True

    def test_aicp_backends_list(self):
        from aicp.mcp.server import aicp_backends_list

        mock_backend = MagicMock()
        mock_backend.backends_list.return_value = [{"name": "llama-cpp"}]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_backends_list()

        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        assert len(parsed["backends"]) == 1

    def test_aicp_server_config(self):
        from aicp.mcp.server import aicp_server_config

        mock_backend = MagicMock()
        mock_backend.server_config.return_value = {
            "healthy": True, "ready": True,
            "models": ["hermes"], "backends": [], "features": ["tokenize"],
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_server_config()

        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        assert parsed["config"]["healthy"] is True
        assert "tokenize" in parsed["config"]["features"]

    def test_aicp_model_delete(self):
        from aicp.mcp.server import aicp_model_delete

        mock_backend = MagicMock()
        mock_backend.model_delete.return_value = True

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_delete("old-model")

        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        assert parsed["deleted"] is True
        assert parsed["model"] == "old-model"


# ── Interactive Slash Commands ───────────────────────────────────────────────

class TestInteractiveHealthCommands:
    def test_health_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.health_check.return_value = {"healthy": True, "status_code": 200}
        backend.is_ready.return_value = True
        backend.server_config.return_value = {
            "features": ["tokenize", "stores"],
            "models": ["hermes"],
        }

        _handle_slash("/health", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "healthy" in output
        assert "ready" in output
        assert "tokenize" in output

    def test_health_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/health", [], None, {}, Mode.THINK, Path("/tmp"))
        assert "require" in capsys.readouterr().err.lower()

    def test_backends_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.backends_list.return_value = [
            {"name": "llama-cpp"},
            {"name": "whisper"},
        ]

        _handle_slash("/backends", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "llama-cpp" in output
        assert "whisper" in output

    def test_backends_empty(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.backends_list.return_value = []

        _handle_slash("/backends", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "No backends" in output

    def test_backends_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/backends", [], None, {}, Mode.THINK, Path("/tmp"))
        assert "require" in capsys.readouterr().err.lower()
