"""Tests for voice pipeline (transcribe → LLM → TTS)."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call
import json

import pytest

from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode


# ── Helpers ──────────────────────────────────────────────────────────────────

def _backend(**kwargs) -> LocalAIBackend:
    return LocalAIBackend(
        base_url="http://localhost:8090",
        model="hermes",
        **kwargs,
    )


# ── Voice pipeline tests ───────────────────────────────────────────────────

class TestVoicePipeline:
    def test_full_pipeline(self, tmp_path):
        audio_in = tmp_path / "input.wav"
        audio_in.write_bytes(b"\x00" * 100)
        audio_out = tmp_path / "output.wav"

        backend = _backend()

        # Mock the three stages
        with patch.object(backend, "transcribe") as mock_stt, \
             patch.object(backend, "execute") as mock_llm, \
             patch.object(backend, "speak") as mock_tts:

            mock_stt.return_value = {"text": "What is the weather today?"}
            mock_llm.return_value = "It is sunny and 72 degrees."
            mock_tts.return_value = audio_out

            result = backend.voice_pipeline(
                audio_in, audio_out, Mode.THINK, tmp_path,
            )

        assert result["transcription"] == "What is the weather today?"
        assert result["response"] == "It is sunny and 72 degrees."
        assert result["audio_output"] == str(audio_out)

        # Verify call chain
        mock_stt.assert_called_once_with(audio_in, model="whisper-1")
        mock_llm.assert_called_once_with("What is the weather today?", Mode.THINK, tmp_path)
        mock_tts.assert_called_once_with("It is sunny and 72 degrees.", audio_out, model="piper-tts")

    def test_pipeline_custom_models(self, tmp_path):
        audio_in = tmp_path / "input.wav"
        audio_in.write_bytes(b"\x00" * 100)
        audio_out = tmp_path / "output.wav"

        backend = _backend()
        with patch.object(backend, "transcribe") as mock_stt, \
             patch.object(backend, "execute") as mock_llm, \
             patch.object(backend, "speak") as mock_tts:

            mock_stt.return_value = {"text": "test"}
            mock_llm.return_value = "ok"
            mock_tts.return_value = audio_out

            backend.voice_pipeline(
                audio_in, audio_out, Mode.THINK, tmp_path,
                whisper_model="whisper-large",
                tts_model="custom-tts",
            )

        mock_stt.assert_called_once_with(audio_in, model="whisper-large")
        mock_tts.assert_called_once_with("ok", audio_out, model="custom-tts")

    def test_pipeline_no_speech(self, tmp_path):
        audio_in = tmp_path / "silence.wav"
        audio_in.write_bytes(b"\x00" * 100)
        audio_out = tmp_path / "output.wav"

        backend = _backend()
        with patch.object(backend, "transcribe") as mock_stt:
            mock_stt.return_value = {"text": ""}
            with pytest.raises(RuntimeError, match="No speech detected"):
                backend.voice_pipeline(audio_in, audio_out, Mode.THINK, tmp_path)

    def test_pipeline_input_not_found(self, tmp_path):
        audio_out = tmp_path / "output.wav"
        backend = _backend()
        with pytest.raises(FileNotFoundError):
            backend.voice_pipeline(
                tmp_path / "nonexistent.wav", audio_out, Mode.THINK, tmp_path,
            )

    def test_pipeline_modes(self, tmp_path):
        """Pipeline should pass mode through to execute()."""
        audio_in = tmp_path / "input.wav"
        audio_in.write_bytes(b"\x00" * 100)
        audio_out = tmp_path / "output.wav"

        backend = _backend()
        with patch.object(backend, "transcribe") as mock_stt, \
             patch.object(backend, "execute") as mock_llm, \
             patch.object(backend, "speak") as mock_tts:

            mock_stt.return_value = {"text": "do something"}
            mock_llm.return_value = "done"
            mock_tts.return_value = audio_out

            backend.voice_pipeline(audio_in, audio_out, Mode.ACT, tmp_path)

        assert mock_llm.call_args[0][1] == Mode.ACT


# ── MCP tool tests ──────────────────────────────────────────────────────────

class TestAicpVoicePipeline:
    def test_mcp_tool_returns_json(self, tmp_path):
        from aicp.mcp.server import aicp_voice_pipeline

        audio_in = tmp_path / "input.wav"
        audio_in.write_bytes(b"\x00" * 100)
        audio_out = str(tmp_path / "output.wav")

        backend = MagicMock()
        backend.base_url = "http://localhost:8090"
        backend.voice_pipeline.return_value = {
            "transcription": "hello",
            "response": "hi there",
            "audio_output": audio_out,
            "usage": {},
        }
        config = {
            "backends": {
                "local": {
                    "whisper_model": "whisper-1",
                    "tts_model": "piper-tts",
                }
            }
        }
        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=backend),
            _config=config,
        ):
            result = aicp_voice_pipeline(str(audio_in), audio_output=audio_out)

        parsed = json.loads(result)
        assert parsed["transcription"] == "hello"
        assert parsed["response"] == "hi there"

    def test_mcp_tool_file_not_found(self):
        from aicp.mcp.server import aicp_voice_pipeline

        backend = MagicMock()
        config = {"backends": {"local": {}}}
        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=backend),
            _config=config,
        ):
            with pytest.raises(FileNotFoundError):
                aicp_voice_pipeline("/nonexistent/file.wav")
