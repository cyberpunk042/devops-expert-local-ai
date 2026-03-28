"""Tests for Model Warm-up & Preloading (M89)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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


def _models_response(model_ids):
    """Build a mock /v1/models response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"id": m} for m in model_ids],
    }
    return mock_resp


def _chat_response():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "hi"}}],
        "usage": {},
    }
    return mock_resp


# ── Backend model_loaded() ────────────────────────────────────────────────


class TestModelLoaded:
    def test_model_is_loaded(self):
        backend = _make_backend()

        with patch("httpx.get", return_value=_models_response(["hermes", "codellama"])):
            assert backend.model_loaded() is True

    def test_model_not_loaded(self):
        backend = _make_backend()

        with patch("httpx.get", return_value=_models_response(["codellama"])):
            assert backend.model_loaded() is False

    def test_check_specific_model(self):
        backend = _make_backend()

        with patch("httpx.get", return_value=_models_response(["hermes", "llava"])):
            assert backend.model_loaded("llava") is True
            assert backend.model_loaded("codellama") is False

    def test_connection_error_returns_false(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            assert backend.model_loaded() is False

    def test_timeout_returns_false(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
            assert backend.model_loaded() is False

    def test_empty_models_list(self):
        backend = _make_backend()

        with patch("httpx.get", return_value=_models_response([])):
            assert backend.model_loaded() is False


# ── Backend models_loaded() ───────────────────────────────────────────────


class TestModelsLoaded:
    def test_returns_model_ids(self):
        backend = _make_backend()

        with patch("httpx.get", return_value=_models_response(["hermes", "codellama"])):
            models = backend.models_loaded()

        assert models == ["hermes", "codellama"]

    def test_empty_list(self):
        backend = _make_backend()

        with patch("httpx.get", return_value=_models_response([])):
            assert backend.models_loaded() == []

    def test_connection_error_returns_empty(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            assert backend.models_loaded() == []


# ── Backend model_warmup() ────────────────────────────────────────────────


class TestModelWarmup:
    def test_already_loaded(self):
        backend = _make_backend()

        with patch("httpx.get", return_value=_models_response(["hermes"])):
            result = backend.model_warmup()

        assert result["loaded"] is True
        assert result["already_loaded"] is True
        assert result["model"] == "hermes"
        assert result["duration_ms"] == 0

    def test_triggers_load(self):
        backend = _make_backend()
        call_count = {"n": 0}

        def mock_get(url, **kw):
            # First call: model not loaded, second: loaded
            call_count["n"] += 1
            return _models_response([])

        def mock_post(url, json=None, **kw):
            return _chat_response()

        with patch("httpx.get", side_effect=mock_get):
            with patch("httpx.post", side_effect=mock_post):
                result = backend.model_warmup()

        assert result["loaded"] is True
        assert result["already_loaded"] is False
        assert result["model"] == "hermes"
        assert result["duration_ms"] >= 0

    def test_warmup_specific_model(self):
        backend = _make_backend()
        captured = {}

        with patch("httpx.get", return_value=_models_response([])):
            def capture_post(url, json=None, **kw):
                captured.update(json or {})
                return _chat_response()

            with patch("httpx.post", side_effect=capture_post):
                result = backend.model_warmup("codellama")

        assert result["model"] == "codellama"
        assert captured["model"] == "codellama"

    def test_minimal_inference(self):
        backend = _make_backend()
        captured = {}

        with patch("httpx.get", return_value=_models_response([])):
            def capture_post(url, json=None, **kw):
                captured.update(json or {})
                return _chat_response()

            with patch("httpx.post", side_effect=capture_post):
                backend.model_warmup()

        assert captured["max_tokens"] == 1
        assert captured["temperature"] == 0

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", return_value=_models_response([])):
            with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
                with pytest.raises(RuntimeError, match="Cannot connect"):
                    backend.model_warmup()

    def test_timeout_returns_failure(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", return_value=_models_response([])):
            with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
                result = backend.model_warmup()

        assert result["loaded"] is False
        assert "Timed out" in result["error"]

    def test_http_error_returns_failure(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"

        with patch("httpx.get", return_value=_models_response([])):
            with patch("httpx.post", return_value=mock_resp):
                result = backend.model_warmup()

        assert result["loaded"] is False
        assert "500" in result["error"]


# ── MCP: aicp_warmup ──────────────────────────────────────────────────────


class TestMcpWarmup:
    def test_warmup_default(self):
        from aicp.mcp.server import aicp_warmup

        mock_backend = MagicMock()
        mock_backend.model_warmup.return_value = {
            "loaded": True, "model": "hermes", "duration_ms": 500, "already_loaded": False,
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_warmup()

        parsed = json.loads(result)
        assert parsed["loaded"] is True
        mock_backend.model_warmup.assert_called_once_with(None)

    def test_warmup_named_model(self):
        from aicp.mcp.server import aicp_warmup

        mock_backend = MagicMock()
        mock_backend.model_warmup.return_value = {"loaded": True, "model": "codellama"}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_warmup("codellama")

        mock_backend.model_warmup.assert_called_once_with("codellama")


class TestMcpModelsLoaded:
    def test_returns_json_array(self):
        from aicp.mcp.server import aicp_models_loaded

        mock_backend = MagicMock()
        mock_backend.models_loaded.return_value = ["hermes", "codellama"]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_models_loaded()

        parsed = json.loads(result)
        assert parsed == ["hermes", "codellama"]


# ── Interactive /warmup and /loaded ────────────────────────────────────────


class TestInteractiveWarmup:
    def test_warmup_default_model(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model = "hermes"
        backend.model_warmup.return_value = {
            "loaded": True, "model": "hermes", "duration_ms": 1200, "already_loaded": False,
        }

        _handle_slash("/warmup", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "Loaded" in output
        assert "1200ms" in output

    def test_warmup_specific_model(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model_warmup.return_value = {
            "loaded": True, "model": "codellama", "duration_ms": 800, "already_loaded": False,
        }

        _handle_slash("/warmup codellama", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "codellama" in output

    def test_warmup_already_loaded(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model = "hermes"
        backend.model_warmup.return_value = {
            "loaded": True, "model": "hermes", "duration_ms": 0, "already_loaded": True,
        }

        _handle_slash("/warmup", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "Already loaded" in output

    def test_warmup_failure(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model = "hermes"
        backend.model_warmup.return_value = {
            "loaded": False, "model": "hermes", "error": "Timed out after 120s",
        }

        _handle_slash("/warmup", [], backend, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "Failed" in err

    def test_warmup_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/warmup", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_warmup_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model = "hermes"
        backend.model_warmup.side_effect = RuntimeError("connection refused")

        _handle_slash("/warmup", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()


class TestInteractiveLoaded:
    def test_loaded_models(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.models_loaded.return_value = ["hermes", "codellama"]

        _handle_slash("/loaded", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "hermes" in output
        assert "codellama" in output

    def test_no_models_loaded(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.models_loaded.return_value = []

        _handle_slash("/loaded", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "No models" in output

    def test_loaded_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/loaded", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()
