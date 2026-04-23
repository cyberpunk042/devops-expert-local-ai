"""Tests for Model Configuration API & Context Size Management (M82)."""

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


# ── model_config() ────────────────────────────────────────────────────────


class TestModelConfig:
    def test_reads_default_model(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "hermes",
            "context_size": 4096,
            "gpu_layers": 35,
            "threads": 4,
        }

        captured_url = {}

        def capture_get(url, **kw):
            captured_url["url"] = url
            return mock_resp

        with patch("httpx.get", side_effect=capture_get):
            cfg = backend.model_config()

        assert cfg["context_size"] == 4096
        assert "/models/hermes" in captured_url["url"]

    def test_reads_named_model(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"name": "codellama", "context_size": 8192}

        captured_url = {}

        def capture_get(url, **kw):
            captured_url["url"] = url
            return mock_resp

        with patch("httpx.get", side_effect=capture_get):
            cfg = backend.model_config("codellama")

        assert cfg["name"] == "codellama"
        assert "/models/codellama" in captured_url["url"]

    def test_404_not_found(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        with patch("httpx.get", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="not found"):
                backend.model_config("nonexistent")

    def test_server_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "internal error"

        with patch("httpx.get", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.model_config()

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.model_config()


# ── model_config_update() ─────────────────────────────────────────────────


class TestModelConfigUpdate:
    def test_update_context_size(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            result = backend.model_config_update(context_size=8192)

        assert captured["id"] == "hermes"
        assert captured["context_size"] == 8192
        assert result["status"] == "ok"

    def test_update_gpu_layers(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.model_config_update(gpu_layers=-1)

        assert captured["gpu_layers"] == -1

    def test_update_multiple_params(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.model_config_update(
                context_size=4096,
                gpu_layers=30,
                threads=8,
                batch_size=512,
                f16=True,
                mmap=False,
            )

        assert captured["context_size"] == 4096
        assert captured["gpu_layers"] == 30
        assert captured["threads"] == 8
        assert captured["batch_size"] == 512
        assert captured["f16"] is True
        assert captured["mmap"] is False

    def test_update_named_model(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.model_config_update(model_name="codellama", context_size=16384)

        assert captured["id"] == "codellama"
        assert captured["context_size"] == 16384

    def test_only_sends_provided_params(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.model_config_update(threads=4)

        assert captured == {"id": "hermes", "threads": 4}

    def test_uses_models_apply_endpoint(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}

        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.model_config_update(context_size=2048)

        assert "/models/apply" in captured_url["url"]

    def test_404_not_available(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="not available"):
                backend.model_config_update(context_size=4096)

    def test_server_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.model_config_update(context_size=4096)

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.model_config_update(context_size=4096)

    def test_timeout_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.model_config_update(context_size=4096)


# ── MCP Tools ──────────────────────────────────────────────────────────────


class TestMcpModelConfig:
    def test_read_config(self):
        from aicp.mcp.server import aicp_model_config

        mock_backend = MagicMock()
        mock_backend.model_config.return_value = {
            "name": "hermes",
            "context_size": 4096,
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_config()

        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        assert parsed["config"]["context_size"] == 4096
        mock_backend.model_config.assert_called_once_with(None)

    def test_read_named_model(self):
        from aicp.mcp.server import aicp_model_config

        mock_backend = MagicMock()
        mock_backend.model_config.return_value = {"name": "codellama"}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_model_config("codellama")

        mock_backend.model_config.assert_called_once_with("codellama")

    def test_update_config(self):
        from aicp.mcp.server import aicp_model_config_update

        mock_backend = MagicMock()
        mock_backend.model_config_update.return_value = {"status": "ok"}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_model_config_update(context_size=8192, gpu_layers=-1)

        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        mock_backend.model_config_update.assert_called_once_with(
            context_size=8192, gpu_layers=-1,
        )

    def test_update_with_bool_strings(self):
        from aicp.mcp.server import aicp_model_config_update

        mock_backend = MagicMock()
        mock_backend.model_config_update.return_value = {"status": "ok"}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_model_config_update(f16="true", mmap="false")

        mock_backend.model_config_update.assert_called_once_with(
            f16=True, mmap=False,
        )


# ── Interactive /config ────────────────────────────────────────────────────


class TestInteractiveConfig:
    def test_config_read(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model_config.return_value = {
            "name": "hermes",
            "context_size": 4096,
            "gpu_layers": 35,
            "threads": 4,
        }

        _handle_slash("/config", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "context_size" in output
        assert "4096" in output
        assert "gpu_layers" in output

    def test_config_read_named_model(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model_config.return_value = {"name": "codellama", "context_size": 8192}

        _handle_slash("/config codellama", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "8192" in output
        backend.model_config.assert_called_once_with("codellama")

    def test_config_set_context_size(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model_config_update.return_value = {"status": "ok"}

        _handle_slash("/config set context_size 8192", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "updated" in output.lower()
        backend.model_config_update.assert_called_once_with(context_size=8192)

    def test_config_set_gpu_layers(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model_config_update.return_value = {"status": "ok"}

        _handle_slash("/config set gpu_layers -1", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "updated" in output.lower()
        backend.model_config_update.assert_called_once_with(gpu_layers=-1)

    def test_config_set_bool_f16(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model_config_update.return_value = {"status": "ok"}

        _handle_slash("/config set f16 true", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "updated" in output.lower()
        backend.model_config_update.assert_called_once_with(f16=True)

    def test_config_set_invalid_key(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()

        _handle_slash("/config set bogus_key 42", [], backend, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "Unknown" in err

    def test_config_set_missing_value(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()

        _handle_slash("/config set context_size", [], backend, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "Usage" in err

    def test_config_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/config", [], None, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_config_set_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model_config_update.side_effect = RuntimeError("connection refused")

        _handle_slash("/config set context_size 4096", [], backend, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_config_read_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.model_config.side_effect = RuntimeError("not found")

        _handle_slash("/config", [], backend, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_config_set_non_integer(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()

        _handle_slash("/config set context_size abc", [], backend, {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "integer" in err.lower()
