"""Tests for Speech-to-Text Detailed Transcription (M93)."""

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


def _verbose_response(
    text="Hello world",
    language="en",
    duration=5.2,
    segments=None,
    words=None,
):
    if segments is None:
        segments = [{"start": 0.0, "end": 2.5, "text": "Hello"}, {"start": 2.5, "end": 5.2, "text": "world"}]
    if words is None:
        words = [
            {"word": "Hello", "start": 0.0, "end": 1.2},
            {"word": "world", "start": 1.5, "end": 2.5},
        ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "text": text,
        "language": language,
        "duration": duration,
        "segments": segments,
        "words": words,
    }
    return mock_resp


# ── Backend transcribe_detailed() ────────────────────────────────────────


class TestTranscribeDetailed:
    def test_basic(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        with patch("httpx.post", return_value=_verbose_response()):
            result = backend.transcribe_detailed(audio)

        assert result["text"] == "Hello world"
        assert result["language"] == "en"
        assert result["duration"] == 5.2
        assert len(result["segments"]) == 2
        assert len(result["words"]) == 2

    def test_uses_transcriptions_endpoint(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)
        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return _verbose_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.transcribe_detailed(audio)

        assert "/v1/audio/transcriptions" in captured_url["url"]

    def test_sends_verbose_json_format(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)
        captured_data = {}

        def capture_post(url, files=None, data=None, **kw):
            captured_data.update(data or {})
            return _verbose_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.transcribe_detailed(audio)

        assert captured_data["response_format"] == "verbose_json"

    def test_sends_language(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)
        captured_data = {}

        def capture_post(url, files=None, data=None, **kw):
            captured_data.update(data or {})
            return _verbose_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.transcribe_detailed(audio, language="fr")

        assert captured_data["language"] == "fr"

    def test_no_language_omits_key(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)
        captured_data = {}

        def capture_post(url, files=None, data=None, **kw):
            captured_data.update(data or {})
            return _verbose_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.transcribe_detailed(audio, language="")

        assert "language" not in captured_data

    def test_sends_temperature(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)
        captured_data = {}

        def capture_post(url, files=None, data=None, **kw):
            captured_data.update(data or {})
            return _verbose_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.transcribe_detailed(audio, temperature=0.5)

        assert captured_data["temperature"] == "0.5"

    def test_custom_model(self, tmp_path):
        backend = _make_backend(whisper_model="whisper-1")
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)
        captured_data = {}

        def capture_post(url, files=None, data=None, **kw):
            captured_data.update(data or {})
            return _verbose_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.transcribe_detailed(audio, model="whisper-large")

        assert captured_data["model"] == "whisper-large"

    def test_default_whisper_model(self, tmp_path):
        backend = _make_backend(whisper_model="whisper-1")
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)
        captured_data = {}

        def capture_post(url, files=None, data=None, **kw):
            captured_data.update(data or {})
            return _verbose_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.transcribe_detailed(audio)

        assert captured_data["model"] == "whisper-1"

    def test_tracks_usage(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        with patch("httpx.post", return_value=_verbose_response()):
            backend.transcribe_detailed(audio)

        assert backend.last_usage["transcription_detailed"] is True
        assert backend.last_usage["language"] == "en"
        assert backend.last_usage["duration"] == 5.2

    def test_file_not_found(self, tmp_path):
        backend = _make_backend()
        with pytest.raises(FileNotFoundError):
            backend.transcribe_detailed(tmp_path / "nonexistent.wav")

    def test_connection_error(self, tmp_path):
        import httpx
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.transcribe_detailed(audio)

    def test_timeout_error(self, tmp_path):
        import httpx
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.transcribe_detailed(audio)

    def test_http_error(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.transcribe_detailed(audio)

    def test_word_granularity(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)
        captured_data = {}

        def capture_post(url, files=None, data=None, **kw):
            captured_data.update(data or {})
            return _verbose_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.transcribe_detailed(audio, timestamp_granularities=["word"])

        assert backend.last_usage["granularities"] == ["word"]

    def test_both_granularities(self, tmp_path):
        backend = _make_backend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        with patch("httpx.post", return_value=_verbose_response()):
            backend.transcribe_detailed(
                audio, timestamp_granularities=["word", "segment"]
            )

        assert backend.last_usage["granularities"] == ["word", "segment"]


# ── MCP: aicp_transcribe_detailed ────────────────────────────────────────


class TestMcpTranscribeDetailed:
    def test_returns_json(self, tmp_path):
        from aicp.mcp.server import aicp_transcribe_detailed

        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        mock_backend = MagicMock()
        mock_backend.transcribe_detailed.return_value = {
            "text": "Hello", "language": "en", "duration": 3.0,
            "segments": [], "words": [],
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_transcribe_detailed(str(audio))

        parsed = json.loads(result)
        assert parsed["text"] == "Hello"
        assert parsed["duration"] == 3.0

    def test_passes_language(self, tmp_path):
        from aicp.mcp.server import aicp_transcribe_detailed

        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        mock_backend = MagicMock()
        mock_backend.transcribe_detailed.return_value = {"text": "Bonjour"}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_transcribe_detailed(str(audio), language="fr")

        call_kwargs = mock_backend.transcribe_detailed.call_args.kwargs
        assert call_kwargs["language"] == "fr"

    def test_parses_granularities(self, tmp_path):
        from aicp.mcp.server import aicp_transcribe_detailed

        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        mock_backend = MagicMock()
        mock_backend.transcribe_detailed.return_value = {"text": "x"}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_transcribe_detailed(str(audio), timestamp_granularities="word,segment")

        call_kwargs = mock_backend.transcribe_detailed.call_args.kwargs
        assert call_kwargs["timestamp_granularities"] == ["word", "segment"]

    def test_passes_temperature(self, tmp_path):
        from aicp.mcp.server import aicp_transcribe_detailed

        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        mock_backend = MagicMock()
        mock_backend.transcribe_detailed.return_value = {"text": "x"}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_transcribe_detailed(str(audio), temperature=0.3)

        call_kwargs = mock_backend.transcribe_detailed.call_args.kwargs
        assert call_kwargs["temperature"] == 0.3


# ── Interactive /transcribe-detail ───────────────────────────────────────


class TestInteractiveTranscribeDetail:
    def test_basic(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        backend = MagicMock()
        backend.transcribe_detailed.return_value = {
            "text": "Hello world",
            "language": "en",
            "duration": 5.2,
            "segments": [{"start": 0.0, "end": 2.5, "text": "Hello"}],
            "words": [{"word": "Hello", "start": 0.0, "end": 1.2}],
        }

        _handle_slash(
            f"/transcribe-detail {audio}", [], backend,
            {"whisper_model": "whisper-1"}, Mode.THINK, Path("/tmp"),
        )

        output = capsys.readouterr().out
        assert "Hello world" in output
        assert "5.2s" in output
        assert "Segments" in output

    def test_with_language(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        backend = MagicMock()
        backend.transcribe_detailed.return_value = {
            "text": "Bonjour", "language": "fr", "duration": 2.0,
            "segments": [], "words": [],
        }

        _handle_slash(
            f"/transcribe-detail {audio} fr", [], backend,
            {}, Mode.THINK, Path("/tmp"),
        )

        call_kwargs = backend.transcribe_detailed.call_args.kwargs
        assert call_kwargs["language"] == "fr"

    def test_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/transcribe-detail", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_file_not_found(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash(
            "/transcribe-detail /nonexistent/file.wav", [], backend,
            {}, Mode.THINK, Path("/tmp"),
        )
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/transcribe-detail test.wav", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_error_handling(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        backend = MagicMock()
        backend.transcribe_detailed.side_effect = RuntimeError("timeout")

        _handle_slash(
            f"/transcribe-detail {audio}", [], backend,
            {}, Mode.THINK, Path("/tmp"),
        )
        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_shows_words(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        backend = MagicMock()
        backend.transcribe_detailed.return_value = {
            "text": "Hi there",
            "language": "en",
            "duration": 1.5,
            "segments": [],
            "words": [
                {"word": "Hi", "start": 0.0, "end": 0.5},
                {"word": "there", "start": 0.6, "end": 1.2},
            ],
        }

        _handle_slash(
            f"/transcribe-detail {audio}", [], backend,
            {}, Mode.THINK, Path("/tmp"),
        )

        output = capsys.readouterr().out
        assert "Words" in output
        assert "Hi" in output
