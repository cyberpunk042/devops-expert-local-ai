"""Tests for audio capabilities (STT + TTS)."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import struct
import wave
import io

import pytest

from aicp.backends.localai import LocalAIBackend


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_wav(path: Path, duration_s: float = 1.0, sample_rate: int = 16000) -> Path:
    """Create a minimal WAV file with silence."""
    n_frames = int(sample_rate * duration_s)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * n_frames)
    return path


def _backend(**kwargs) -> LocalAIBackend:
    return LocalAIBackend(
        base_url="http://localhost:8090",
        model="hermes",
        **kwargs,
    )


# ── Transcribe tests ────────────────────────────────────────────────────────

class TestTranscribe:
    def test_transcribe_returns_text(self, tmp_path):
        wav = _create_wav(tmp_path / "test.wav")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "text": "Hello world.",
            "segments": [{"id": 0, "text": " Hello world.", "start": 0, "end": 1000}],
        }

        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            result = backend.transcribe(wav)

        assert result["text"] == "Hello world."
        assert backend.last_usage["transcription"] is True

    def test_transcribe_file_not_found(self, tmp_path):
        backend = _backend()
        with pytest.raises(FileNotFoundError, match="not found"):
            backend.transcribe(tmp_path / "nonexistent.wav")

    def test_transcribe_api_error(self, tmp_path):
        wav = _create_wav(tmp_path / "test.wav")
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "internal error"

        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Transcription error"):
                backend.transcribe(wav)

    def test_transcribe_custom_model(self, tmp_path):
        wav = _create_wav(tmp_path / "test.wav")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "test"}

        backend = _backend()
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.transcribe(wav, model="whisper-large")
            call_kwargs = mock_post.call_args
            assert call_kwargs[1]["data"]["model"] == "whisper-large"

    def test_transcribe_sends_correct_format(self, tmp_path):
        wav = _create_wav(tmp_path / "test.wav")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "ok"}

        backend = _backend()
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.transcribe(wav, language="fr", response_format="srt")
            call_kwargs = mock_post.call_args
            assert call_kwargs[1]["data"]["language"] == "fr"
            assert call_kwargs[1]["data"]["response_format"] == "srt"

    def test_transcribe_timeout(self, tmp_path):
        import httpx
        wav = _create_wav(tmp_path / "test.wav")
        backend = _backend()
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.transcribe(wav)


# ── Speak tests ──────────────────────────────────────────────────────────────

class TestSpeak:
    def test_speak_writes_wav(self, tmp_path):
        output = tmp_path / "output.wav"
        # Fake WAV content
        wav_bytes = b"RIFF" + b"\x00" * 100

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "audio/wav"}
        mock_resp.content = wav_bytes

        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            result = backend.speak("Hello", output)

        assert result == output
        assert output.exists()
        assert output.read_bytes() == wav_bytes
        assert backend.last_usage["tts"] is True

    def test_speak_creates_parent_dirs(self, tmp_path):
        output = tmp_path / "sub" / "dir" / "output.wav"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "audio/wav"}
        mock_resp.content = b"RIFF" + b"\x00" * 50

        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            backend.speak("Hello", output)

        assert output.exists()

    def test_speak_api_error(self, tmp_path):
        output = tmp_path / "output.wav"
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "backend not found"

        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="TTS error"):
                backend.speak("Hello", output)

    def test_speak_json_error_response(self, tmp_path):
        output = tmp_path / "output.wav"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.text = '{"error": "model not loaded"}'

        backend = _backend()
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="TTS returned error"):
                backend.speak("Hello", output)

    def test_speak_custom_model(self, tmp_path):
        output = tmp_path / "output.wav"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "audio/wav"}
        mock_resp.content = b"RIFF" + b"\x00" * 50

        backend = _backend()
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.speak("Hello", output, model="custom-tts")
            call_json = mock_post.call_args[1]["json"]
            assert call_json["model"] == "custom-tts"

    def test_speak_timeout(self, tmp_path):
        import httpx
        output = tmp_path / "output.wav"
        backend = _backend()
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="TTS timed out"):
                backend.speak("Hello", output)
