"""Tests for startup model pre-warming and enhanced health endpoint (Stage 4 Phase 2+3)."""

import time
from io import BytesIO
from unittest.mock import MagicMock, patch

from aicp.agent.server import AgentHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(server_attrs=None):
    """Create an AgentHandler with a mock server for testing."""
    handler = AgentHandler.__new__(AgentHandler)
    handler.server = MagicMock()
    handler.server._warming = False
    handler.server._warming_model = ""
    handler.server.controller = MagicMock()
    handler.server.controller.backends = {}

    if server_attrs:
        for k, v in server_attrs.items():
            setattr(handler.server, k, v)

    # Mock response writing
    handler.wfile = BytesIO()
    handler._headers_buffer = []
    handler.request_version = "HTTP/1.1"
    handler.requestline = "GET /health HTTP/1.1"
    return handler


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_ok_when_not_warming(self):
        handler = _make_handler()
        local = MagicMock()
        local.is_available.return_value = True
        handler.server.controller.backends = {"local": local}

        response = {}
        handler._respond_json = lambda status, data: response.update({"status_code": status, **data})
        handler._handle_health()

        assert response["status"] == "ok"
        assert response["backends"]["local"] is True
        assert response["warming"] is False

    def test_health_degraded_when_backend_down(self):
        handler = _make_handler()
        local = MagicMock()
        local.is_available.return_value = False
        handler.server.controller.backends = {"local": local}

        response = {}
        handler._respond_json = lambda status, data: response.update({"status_code": status, **data})
        handler._handle_health()

        assert response["status"] == "degraded"
        assert response["backends"]["local"] is False

    def test_health_warming_state(self):
        handler = _make_handler({"_warming": True, "_warming_model": "qwen3-8b"})

        response = {}
        handler._respond_json = lambda status, data: response.update({"status_code": status, **data})
        handler._handle_health()

        assert response["status"] == "warming"
        assert response["model"] == "qwen3-8b"

    def test_health_ok_when_no_backends(self):
        handler = _make_handler()
        handler.server.controller.backends = {}

        response = {}
        handler._respond_json = lambda status, data: response.update({"status_code": status, **data})
        handler._handle_health()

        assert response["status"] == "ok"

    def test_health_handles_backend_exception(self):
        handler = _make_handler()
        local = MagicMock()
        local.is_available.side_effect = RuntimeError("connection error")
        handler.server.controller.backends = {"local": local}

        response = {}
        handler._respond_json = lambda status, data: response.update({"status_code": status, **data})
        handler._handle_health()

        assert response["status"] == "degraded"
        assert response["backends"]["local"] is False


# ---------------------------------------------------------------------------
# Warmup configuration tests
# ---------------------------------------------------------------------------


class TestWarmupConfig:
    def test_warmup_disabled_by_default(self):
        """Default profile has warmup.enabled=false."""
        from aicp.config.loader import DEFAULT_CONFIG_PATH, load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        warmup = config.get("warmup", {})
        assert warmup.get("enabled", False) is False

    def test_fleet_light_warmup_enabled(self):
        """Fleet-light profile has warmup enabled with gemma4-e2b."""
        from aicp.config.loader import DEFAULT_CONFIG_PATH, load_config
        config = load_config(DEFAULT_CONFIG_PATH, profile="fleet-light")
        warmup = config.get("warmup", {})
        assert warmup.get("enabled") is True
        assert "gemma4-e2b" in warmup.get("models", [])

    def test_warmup_profile_validation(self):
        """Warmup section validates as dict."""
        from aicp.core.profiles import validate_profile
        profile = {
            "name": "test",
            "description": "test",
            "warmup": {"enabled": True, "models": ["qwen3-8b"], "timeout": 60},
        }
        errors = validate_profile(profile)
        assert errors == []

    def test_warmup_wrong_type_rejected(self):
        from aicp.core.profiles import validate_profile
        profile = {"name": "test", "description": "test", "warmup": "not-a-dict"}
        errors = validate_profile(profile)
        assert any("warmup" in e for e in errors)


# ---------------------------------------------------------------------------
# Warmup execution tests
# ---------------------------------------------------------------------------


class TestWarmupExecution:
    def test_warmup_calls_model_warmup(self):
        """Warmup sequence calls backend.model_warmup for each model."""
        from unittest.mock import MagicMock, patch

        from aicp.agent.server import run_agent

        warmup_calls = []
        mock_backend = MagicMock()
        mock_backend.model_warmup.side_effect = lambda model_name, timeout: (
            warmup_calls.append(model_name) or
            {"loaded": True, "model": model_name, "duration_ms": 100, "already_loaded": False}
        )
        mock_backend.is_available.return_value = True

        config = {
            "warmup": {"enabled": True, "models": ["qwen3-8b", "nomic-embed"], "timeout": 60},
            "backends": {
                "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
                "claude": {"model": "opus"},
            },
        }

        # Patch to avoid actually starting the HTTP server
        with patch("aicp.agent.server.load_config", return_value=config), \
             patch("aicp.agent.server.get_backend_config", side_effect=lambda c, n: c["backends"][n]), \
             patch("aicp.agent.server.LocalAIBackend", return_value=mock_backend), \
             patch("aicp.agent.server.ClaudeCodeBackend", return_value=MagicMock()), \
             patch("aicp.agent.server.HTTPServer") as mock_server_cls:

            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server
            mock_server.serve_forever.side_effect = KeyboardInterrupt

            try:
                run_agent(port=19100, token="test")
            except (KeyboardInterrupt, SystemExit):
                pass

            # Give warmup thread time to run
            time.sleep(0.5)

        assert "qwen3-8b" in warmup_calls
        assert "nomic-embed" in warmup_calls

    def test_warmup_skipped_when_disabled(self):
        """No warmup calls when warmup.enabled is false."""
        from aicp.agent.server import run_agent

        config = {
            "warmup": {"enabled": False},
            "backends": {
                "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
                "claude": {"model": "opus"},
            },
        }

        mock_backend = MagicMock()

        with patch("aicp.agent.server.load_config", return_value=config), \
             patch("aicp.agent.server.get_backend_config", side_effect=lambda c, n: c["backends"][n]), \
             patch("aicp.agent.server.LocalAIBackend", return_value=mock_backend), \
             patch("aicp.agent.server.ClaudeCodeBackend", return_value=MagicMock()), \
             patch("aicp.agent.server.HTTPServer") as mock_server_cls:

            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server
            mock_server.serve_forever.side_effect = KeyboardInterrupt

            try:
                run_agent(port=19101, token="test")
            except (KeyboardInterrupt, SystemExit):
                pass

        mock_backend.model_warmup.assert_not_called()
