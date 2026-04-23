"""Tests for the AICP MCP server tool handlers."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import json

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_backend(**overrides):
    """Build a mock LocalAIBackend with sane defaults."""
    backend = MagicMock()
    backend.base_url = "http://localhost:8090"
    backend.model = "hermes"
    backend.embedding_model = "nomic-embed"
    backend.vision_model = "llava"
    for k, v in overrides.items():
        setattr(backend, k, v)
    return backend


def _patch_backend(backend):
    """Context manager that patches _get_backend and _config."""
    config = {
        "backends": {
            "local": {
                "base_url": "http://localhost:8090",
                "model": "hermes",
                "whisper_model": "whisper-1",
                "tts_model": "piper-tts",
            }
        }
    }
    return patch.multiple(
        "aicp.mcp.server",
        _get_backend=MagicMock(return_value=backend),
        _config=config,
    )


# ---------------------------------------------------------------------------
# aicp_chat
# ---------------------------------------------------------------------------

class TestAicpChat:
    def test_chat_routes_through_controller(self):
        """Without seed, chat routes through the controller."""
        from aicp.mcp.server import aicp_chat
        mock_ctrl = MagicMock()
        mock_ctrl.run.return_value = "controller result"
        with patch("aicp.mcp.server._get_controller", return_value=mock_ctrl):
            result = aicp_chat("What is the answer?")
        assert result == "controller result"
        mock_ctrl.run.assert_called_once()

    def test_chat_with_seed_bypasses_controller(self):
        """With explicit seed >= 0, chat calls backend directly."""
        from aicp.mcp.server import aicp_chat
        backend = _mock_backend()
        backend.execute.return_value = "deterministic"
        with _patch_backend(backend):
            result = aicp_chat("test", seed=42)
        assert result == "deterministic"
        backend.execute.assert_called_once()
        # Verify seed was passed
        call_args = backend.execute.call_args
        assert call_args[1]["seed"] == 42

    def test_chat_invalid_mode_defaults_to_think(self):
        from aicp.mcp.server import aicp_chat
        from aicp.core.modes import Mode
        mock_ctrl = MagicMock()
        mock_ctrl.run.return_value = "ok"
        with patch("aicp.mcp.server._get_controller", return_value=mock_ctrl):
            aicp_chat("hello", mode="invalid")
        task = mock_ctrl.run.call_args[0][0]
        assert task.mode == Mode.THINK

    def test_route_uses_shared_controller(self):
        """aicp_route (without profile) uses the shared controller singleton."""
        from aicp.mcp.server import aicp_route
        mock_ctrl = MagicMock()
        mock_ctrl.run.return_value = "routed result"
        with patch("aicp.mcp.server._get_controller", return_value=mock_ctrl):
            result = aicp_route("test prompt")
        assert result == "routed result"
        mock_ctrl.run.assert_called_once()

    def test_fleet_run_delegates_to_controller(self):
        """aicp_fleet_run uses the controller for fleet-aware routing."""
        from aicp.mcp.server import aicp_fleet_run
        mock_ctrl = MagicMock()
        mock_ctrl.run.return_value = "fleet result"
        mock_ctrl.last_route = "fleet:workstation"
        with patch("aicp.mcp.server._get_controller", return_value=mock_ctrl):
            result = aicp_fleet_run("test prompt")
        parsed = json.loads(result)
        assert parsed["result"] == "fleet result"
        assert parsed["route"] == "fleet:workstation"


# ---------------------------------------------------------------------------
# aicp_transcribe
# ---------------------------------------------------------------------------

class TestAicpTranscribe:
    def test_transcribe_returns_text(self, tmp_path):
        from aicp.mcp.server import aicp_transcribe
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"\x00" * 100)
        backend = _mock_backend()
        backend.transcribe.return_value = {"text": "Hello world."}
        with _patch_backend(backend):
            result = aicp_transcribe(str(wav))
        assert result == "Hello world."
        backend.transcribe.assert_called_once()

    def test_transcribe_file_not_found(self):
        from aicp.mcp.server import aicp_transcribe
        backend = _mock_backend()
        with _patch_backend(backend):
            with pytest.raises(FileNotFoundError):
                aicp_transcribe("/nonexistent/file.wav")

    def test_transcribe_passes_language(self, tmp_path):
        from aicp.mcp.server import aicp_transcribe
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"\x00" * 100)
        backend = _mock_backend()
        backend.transcribe.return_value = {"text": "Bonjour."}
        with _patch_backend(backend):
            aicp_transcribe(str(wav), language="fr")
        call_kwargs = backend.transcribe.call_args
        assert call_kwargs[1]["language"] == "fr"


# ---------------------------------------------------------------------------
# aicp_speak
# ---------------------------------------------------------------------------

class TestAicpSpeak:
    def test_speak_returns_path(self, tmp_path):
        from aicp.mcp.server import aicp_speak
        output = str(tmp_path / "out.wav")
        backend = _mock_backend()
        backend.speak.return_value = Path(output)
        with _patch_backend(backend):
            result = aicp_speak("Hello", output_path=output)
        assert result == output
        backend.speak.assert_called_once()

    def test_speak_uses_config_model(self, tmp_path):
        from aicp.mcp.server import aicp_speak
        output = str(tmp_path / "out.wav")
        backend = _mock_backend()
        backend.speak.return_value = Path(output)
        with _patch_backend(backend):
            aicp_speak("Hello", output_path=output)
        call_kwargs = backend.speak.call_args
        assert call_kwargs[1]["model"] == "piper-tts"


# ---------------------------------------------------------------------------
# aicp_vision
# ---------------------------------------------------------------------------

class TestAicpVision:
    def test_vision_returns_description(self, tmp_path):
        from aicp.mcp.server import aicp_vision
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        backend = _mock_backend()
        backend.execute_vision.return_value = "A red square on white background."
        with _patch_backend(backend):
            result = aicp_vision(str(img))
        assert "red square" in result
        backend.execute_vision.assert_called_once()

    def test_vision_file_not_found(self):
        from aicp.mcp.server import aicp_vision
        backend = _mock_backend()
        with _patch_backend(backend):
            with pytest.raises(FileNotFoundError):
                aicp_vision("/nonexistent/image.png")

    def test_vision_custom_prompt(self, tmp_path):
        from aicp.mcp.server import aicp_vision
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
        backend = _mock_backend()
        backend.execute_vision.return_value = "Blue"
        with _patch_backend(backend):
            aicp_vision(str(img), prompt="What color is this?")
        call_args = backend.execute_vision.call_args
        assert call_args[0][0] == "What color is this?"


# ---------------------------------------------------------------------------
# aicp_embed
# ---------------------------------------------------------------------------

class TestAicpEmbed:
    def test_embed_returns_vector(self):
        from aicp.mcp.server import aicp_embed
        backend = _mock_backend()
        backend.embed.return_value = [0.1, 0.2, 0.3]
        with _patch_backend(backend):
            result = aicp_embed("test text")
        assert result == [0.1, 0.2, 0.3]
        backend.embed.assert_called_once_with("test text")


# ---------------------------------------------------------------------------
# aicp_models
# ---------------------------------------------------------------------------

class TestAicpModels:
    def test_models_returns_json(self):
        from aicp.mcp.server import aicp_models
        backend = _mock_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "hermes", "object": "model"},
                {"id": "whisper-1", "object": "model"},
            ]
        }
        with _patch_backend(backend):
            with patch("httpx.get", return_value=mock_resp):
                result = aicp_models()
        parsed = json.loads(result)
        assert "deprecated" in parsed["warning"].lower()
        models = parsed["models"]
        assert len(models) == 2
        assert models[0]["id"] == "hermes"

    def test_models_handles_error(self):
        from aicp.mcp.server import aicp_models
        backend = _mock_backend()
        with _patch_backend(backend):
            with patch("httpx.get", side_effect=Exception("connection refused")):
                result = aicp_models()
        assert "not reachable" in result


# ---------------------------------------------------------------------------
# aicp_kb_search
# ---------------------------------------------------------------------------

class TestAicpKbSearch:
    def test_kb_search_returns_results(self):
        from aicp.mcp.server import aicp_kb_search
        backend = _mock_backend()
        mock_kb = MagicMock()
        mock_kb.search.return_value = [
            {"text": "some chunk", "source": "file.md", "score": 0.95}
        ]
        mock_kb_module = MagicMock()
        mock_kb_module.KnowledgeBase.return_value = mock_kb
        with _patch_backend(backend):
            with patch.dict("sys.modules", {"aicp.core.kb": mock_kb_module}):
                result = aicp_kb_search("test query")
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["text"] == "some chunk"

    def test_kb_search_handles_import_error(self):
        from aicp.mcp.server import aicp_kb_search
        backend = _mock_backend()
        with _patch_backend(backend):
            with patch.dict("sys.modules", {"aicp.core.kb": None}):
                result = aicp_kb_search("test")
        assert isinstance(result, str)
