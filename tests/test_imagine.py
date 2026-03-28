"""Tests for image generation capabilities (Stable Diffusion)."""

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.backends.localai import LocalAIBackend


# ── Helpers ──────────────────────────────────────────────────────────────────

def _backend(**kwargs) -> LocalAIBackend:
    return LocalAIBackend(
        base_url="http://localhost:8090",
        model="hermes",
        **kwargs,
    )


def _fake_image_response(width: int = 4, height: int = 4) -> MagicMock:
    """Create a mock response with a tiny base64-encoded PNG."""
    # Minimal 1x1 PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    )
    b64 = base64.b64encode(png_bytes).decode()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"b64_json": b64}],
    }
    return mock_resp


# ── Generate image tests ────────────────────────────────────────────────────

class TestGenerateImage:
    def test_generate_writes_png(self, tmp_path):
        output = tmp_path / "output.png"
        mock_resp = _fake_image_response()
        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            result = backend.generate_image("A red square", output)
        assert result == output
        assert output.exists()
        assert output.read_bytes().startswith(b"\x89PNG")
        assert backend.last_usage["image_generation"] is True

    def test_generate_creates_parent_dirs(self, tmp_path):
        output = tmp_path / "sub" / "dir" / "output.png"
        mock_resp = _fake_image_response()
        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            backend.generate_image("test", output)
        assert output.exists()

    def test_generate_api_error(self, tmp_path):
        output = tmp_path / "output.png"
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "backend error"
        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Image generation error"):
                backend.generate_image("test", output)

    def test_generate_empty_response(self, tmp_path):
        output = tmp_path / "output.png"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}
        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="No images returned"):
                backend.generate_image("test", output)

    def test_generate_custom_model(self, tmp_path):
        output = tmp_path / "output.png"
        mock_resp = _fake_image_response()
        backend = _backend()
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.generate_image("test", output, model="sdxl")
            call_json = mock_post.call_args[1]["json"]
            assert call_json["model"] == "sdxl"

    def test_generate_custom_size(self, tmp_path):
        output = tmp_path / "output.png"
        mock_resp = _fake_image_response()
        backend = _backend()
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.generate_image("test", output, size="768x768")
            call_json = mock_post.call_args[1]["json"]
            assert call_json["size"] == "768x768"

    def test_generate_with_steps(self, tmp_path):
        output = tmp_path / "output.png"
        mock_resp = _fake_image_response()
        backend = _backend()
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.generate_image("test", output, step=50)
            call_json = mock_post.call_args[1]["json"]
            assert call_json["step"] == 50

    def test_generate_negative_prompt(self, tmp_path):
        output = tmp_path / "output.png"
        mock_resp = _fake_image_response()
        backend = _backend()
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.generate_image("a landscape|blurry, distorted", output)
            call_json = mock_post.call_args[1]["json"]
            assert "|" in call_json["prompt"]

    def test_generate_timeout(self, tmp_path):
        import httpx
        output = tmp_path / "output.png"
        backend = _backend()
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.generate_image("test", output)

    def test_generate_url_response(self, tmp_path):
        """Test handling of URL-based response (LocalAI serves image at a URL)."""
        output = tmp_path / "output.png"
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

        # First call returns the generation response with a URL
        gen_resp = MagicMock()
        gen_resp.status_code = 200
        gen_resp.json.return_value = {
            "data": [{"url": "http://localhost:8090/generated-images/test.png"}]
        }

        # Second call (httpx.get) downloads the actual image
        img_resp = MagicMock()
        img_resp.status_code = 200
        img_resp.content = png_bytes

        backend = _backend()
        with patch("httpx.post", return_value=gen_resp), \
             patch("httpx.get", return_value=img_resp):
            result = backend.generate_image("test", output)
        assert output.exists()
        assert output.read_bytes() == png_bytes


# ── MCP tool tests ──────────────────────────────────────────────────────────

class TestAicpImagine:
    def test_imagine_returns_path(self, tmp_path):
        from aicp.mcp.server import aicp_imagine
        output = str(tmp_path / "out.png")
        backend = MagicMock()
        backend.base_url = "http://localhost:8090"
        config = {
            "backends": {"local": {"image_model": "stablediffusion"}},
        }
        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=backend),
            _config=config,
        ):
            result = aicp_imagine("A cat", output_path=output)
        assert result == output
        backend.generate_image.assert_called_once()
