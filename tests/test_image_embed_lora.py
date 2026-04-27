"""Tests for image embeddings & LoRA adapter management (M81)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

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


# ── embed_image ─────────────────────────────────────────────────────────────


class TestEmbedImage:
    def test_basic_image_embedding(self):
        backend = _make_backend(vision_model="clip")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3] * 100}],
        }

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        m = mock_open(read_data=b"fake-image-bytes")
        with patch("builtins.open", m):
            with patch("httpx.post", side_effect=capture_post):
                vec = backend.embed_image(Path("/tmp/photo.jpg"))

        assert len(vec) == 300
        assert captured["model"] == "clip"
        assert captured["input"].startswith("data:image/jpeg;base64,")

    def test_png_mime_type(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"embedding": [0.1] * 10}]}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        m = mock_open(read_data=b"png-data")
        with patch("builtins.open", m):
            with patch("httpx.post", side_effect=capture_post):
                backend.embed_image(Path("/tmp/photo.png"))

        assert "image/png" in captured["input"]

    def test_uses_vision_model_first(self):
        backend = _make_backend(vision_model="clip", embedding_model="nomic")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"embedding": [0.1]}]}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        m = mock_open(read_data=b"img")
        with patch("builtins.open", m):
            with patch("httpx.post", side_effect=capture_post):
                backend.embed_image(Path("/tmp/img.jpg"))

        assert captured["model"] == "clip"

    def test_explicit_model_override(self):
        backend = _make_backend(vision_model="clip")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"embedding": [0.1]}]}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        m = mock_open(read_data=b"img")
        with patch("builtins.open", m):
            with patch("httpx.post", side_effect=capture_post):
                backend.embed_image(Path("/tmp/img.jpg"), model="custom-clip")

        assert captured["model"] == "custom-clip"

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        m = mock_open(read_data=b"img")
        with patch("builtins.open", m):
            with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
                with pytest.raises(RuntimeError, match="Cannot connect"):
                    backend.embed_image(Path("/tmp/img.jpg"))

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        m = mock_open(read_data=b"img")
        with patch("builtins.open", m):
            with patch("httpx.post", return_value=mock_resp):
                with pytest.raises(RuntimeError, match="500"):
                    backend.embed_image(Path("/tmp/img.jpg"))

    def test_tracks_usage(self):
        backend = _make_backend(vision_model="clip")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"embedding": [0.1] * 5}]}

        m = mock_open(read_data=b"img")
        with patch("builtins.open", m):
            with patch("httpx.post", return_value=mock_resp):
                backend.embed_image(Path("/tmp/img.jpg"))

        assert backend.last_usage["image_embedding"] is True
        assert backend.last_usage["model"] == "clip"


# ── LoRA Management ────────────────────────────────────────────────────────


class TestLoraLoad:
    def test_load_adapter(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"uuid": "job-123", "status": "loading"}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            result = backend.lora_load("hermes", "/models/my-adapter.gguf")

        assert result["uuid"] == "job-123"
        assert captured["id"] == "hermes"
        assert captured["lora_adapter"] == "/models/my-adapter.gguf"

    def test_load_404(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="not available"):
                backend.lora_load("hermes", "/adapter.gguf")

    def test_load_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.lora_load("hermes", "/adapter.gguf")


class TestLoraList:
    def test_list_with_adapters(self):
        backend = _make_backend()

        with patch.object(backend, "models_available", return_value=[
            {"name": "hermes", "lora_adapter": "/models/coding.gguf"},
            {"name": "codellama", "config": {"lora_adapter": "/models/python.gguf"}},
            {"name": "phi3"},  # no adapter
        ]):
            result = backend.lora_list()

        assert len(result) == 2
        assert result[0]["name"] == "hermes"
        assert result[1]["name"] == "codellama"

    def test_filter_by_model(self):
        backend = _make_backend()

        with patch.object(backend, "models_available", return_value=[
            {"name": "hermes", "lora_adapter": "/adapter.gguf"},
            {"name": "other", "lora_adapter": "/other.gguf"},
        ]):
            result = backend.lora_list(model_name="hermes")

        assert len(result) == 1
        assert result[0]["name"] == "hermes"

    def test_empty_list(self):
        backend = _make_backend()

        with patch.object(backend, "models_available", return_value=[
            {"name": "hermes"},
        ]):
            result = backend.lora_list()

        assert result == []


# ── MCP Tools ──────────────────────────────────────────────────────────────


class TestMcpEmbedImage:
    def test_returns_embedding_info(self):
        from aicp.mcp.server import aicp_embed_image

        mock_backend = MagicMock()
        mock_backend.embed_image.return_value = [0.1] * 768

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_embed_image("/tmp/photo.jpg")

        parsed = json.loads(result)
        assert parsed["dimensions"] == 768
        assert len(parsed["embedding"]) == 10  # truncated


class TestMcpLoraLoad:
    def test_load_returns_json(self):
        from aicp.mcp.server import aicp_lora_load

        mock_backend = MagicMock()
        mock_backend.lora_load.return_value = {"status": "ok"}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_lora_load("hermes", "/adapter.gguf")

        parsed = json.loads(result)
        assert parsed["status"] == "ok"


class TestMcpLoraList:
    def test_list_returns_json(self):
        from aicp.mcp.server import aicp_lora_list

        mock_backend = MagicMock()
        mock_backend.lora_list.return_value = [{"name": "hermes", "lora_adapter": "/a.gguf"}]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_lora_list()

        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        assert len(parsed["lora_models"]) == 1


# ── Interactive Slash Commands ─────────────────────────────────────────────


class TestInteractiveEmbedImage:
    def test_embed_image_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.embed_image.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

        _handle_slash("/embed-image /tmp/photo.jpg", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "Dimensions: 5" in output
        assert "0.1" in output

    def test_embed_image_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/embed-image", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_embed_image_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/embed-image /tmp/img.jpg", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()


class TestInteractiveLora:
    def test_lora_load_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.lora_load.return_value = {"status": "ok"}

        _handle_slash("/lora load hermes /adapter.gguf", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "loaded" in output.lower()

    def test_lora_list_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.lora_list.return_value = [
            {"name": "hermes", "lora_adapter": "/coding.gguf"},
        ]

        _handle_slash("/lora list", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "hermes" in output
        assert "coding.gguf" in output

    def test_lora_list_empty(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.lora_list.return_value = []

        _handle_slash("/lora list", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "No models" in output

    def test_lora_no_subcommand(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/lora", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_lora_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/lora list", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()
