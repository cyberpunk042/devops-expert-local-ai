"""Tests for Text-to-Speech (M92)."""

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


def _audio_response(audio_bytes=b"\x00\x01\x02\x03" * 100):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = audio_bytes
    mock_resp.headers = {"content-type": "audio/wav"}
    return mock_resp


def _json_error_response(msg="model not found"):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b""
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.text = json.dumps({"error": msg})
    return mock_resp


# ── Backend tts() ────────────────────────────────────────────────────────


class TestTts:
    def test_basic(self, tmp_path):
        backend = _make_backend()
        out = tmp_path / "out.wav"

        with patch("httpx.post", return_value=_audio_response()):
            result = backend.tts("Hello world", out)

        assert result == out
        assert out.exists()
        assert out.stat().st_size > 0

    def test_uses_speech_endpoint(self, tmp_path):
        backend = _make_backend()
        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return _audio_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.tts("test", tmp_path / "out.wav")

        assert "/v1/audio/speech" in captured_url["url"]

    def test_sends_model(self, tmp_path):
        backend = _make_backend(tts_model="piper-tts")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _audio_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.tts("test", tmp_path / "out.wav")

        assert captured["model"] == "piper-tts"

    def test_custom_model(self, tmp_path):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _audio_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.tts("test", tmp_path / "out.wav", model="coqui-tts")

        assert captured["model"] == "coqui-tts"

    def test_sends_voice(self, tmp_path):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _audio_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.tts("test", tmp_path / "out.wav", voice="en-us-amy-low")

        assert captured["voice"] == "en-us-amy-low"

    def test_no_voice_omits_key(self, tmp_path):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _audio_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.tts("test", tmp_path / "out.wav")

        assert "voice" not in captured

    def test_sends_speed(self, tmp_path):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _audio_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.tts("test", tmp_path / "out.wav", speed=1.5)

        assert captured["speed"] == 1.5

    def test_clamps_speed_low(self, tmp_path):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _audio_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.tts("test", tmp_path / "out.wav", speed=0.1)

        assert captured["speed"] == 0.25

    def test_clamps_speed_high(self, tmp_path):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _audio_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.tts("test", tmp_path / "out.wav", speed=10.0)

        assert captured["speed"] == 4.0

    def test_sends_format(self, tmp_path):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _audio_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.tts("test", tmp_path / "out.mp3", response_format="mp3")

        assert captured["response_format"] == "mp3"

    def test_tracks_usage(self, tmp_path):
        backend = _make_backend()

        with patch("httpx.post", return_value=_audio_response()):
            backend.tts("hello", tmp_path / "out.wav", voice="test-voice")

        assert backend.last_usage["tts"] is True
        assert backend.last_usage["voice"] == "test-voice"
        assert backend.last_usage["output_bytes"] > 0

    def test_creates_parent_dirs(self, tmp_path):
        backend = _make_backend()
        out = tmp_path / "sub" / "dir" / "out.wav"

        with patch("httpx.post", return_value=_audio_response()):
            backend.tts("test", out)

        assert out.exists()

    def test_connection_error(self, tmp_path):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.tts("test", tmp_path / "out.wav")

    def test_timeout_error(self, tmp_path):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.tts("test", tmp_path / "out.wav")

    def test_http_error(self, tmp_path):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.tts("test", tmp_path / "out.wav")

    def test_json_error_response(self, tmp_path):
        backend = _make_backend()

        with patch("httpx.post", return_value=_json_error_response()):
            with pytest.raises(RuntimeError, match="error"):
                backend.tts("test", tmp_path / "out.wav")


# ── Backend tts_voices() ─────────────────────────────────────────────────


class TestTtsVoices:
    def test_returns_voices(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"voices": ["amy", "bob", "claire"]}

        with patch("httpx.get", return_value=mock_resp):
            voices = backend.tts_voices()

        assert voices == ["amy", "bob", "claire"]

    def test_metadata_fallback(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"metadata": {"voices": ["v1", "v2"]}}

        with patch("httpx.get", return_value=mock_resp):
            voices = backend.tts_voices()

        assert voices == ["v1", "v2"]

    def test_empty_when_no_voices(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "piper-tts"}

        with patch("httpx.get", return_value=mock_resp):
            voices = backend.tts_voices()

        assert voices == []

    def test_connection_error_returns_empty(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            voices = backend.tts_voices()

        assert voices == []

    def test_http_error_returns_empty(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        with patch("httpx.get", return_value=mock_resp):
            voices = backend.tts_voices()

        assert voices == []

    def test_custom_model(self):
        backend = _make_backend()
        captured_url = {}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"voices": []}

        def capture_get(url, **kw):
            captured_url["url"] = url
            return mock_resp

        with patch("httpx.get", side_effect=capture_get):
            backend.tts_voices(model="coqui-tts")

        assert "coqui-tts" in captured_url["url"]


# ── MCP: aicp_tts ────────────────────────────────────────────────────────


class TestMcpTts:
    def test_returns_json(self, tmp_path):
        from aicp.mcp.server import aicp_tts

        mock_backend = MagicMock()
        out = tmp_path / "out.wav"
        out.write_bytes(b"\x00" * 500)
        mock_backend.tts.return_value = out

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_tts("Hello", output_path=str(out))

        parsed = json.loads(result)
        assert parsed["size_bytes"] == 500
        assert parsed["format"] == "wav"

    def test_passes_voice(self, tmp_path):
        from aicp.mcp.server import aicp_tts

        mock_backend = MagicMock()
        out = tmp_path / "out.wav"
        out.write_bytes(b"\x00")
        mock_backend.tts.return_value = out

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_tts("Hello", output_path=str(out), voice="amy")

        call_kwargs = mock_backend.tts.call_args
        assert call_kwargs.kwargs["voice"] == "amy"

    def test_passes_speed(self, tmp_path):
        from aicp.mcp.server import aicp_tts

        mock_backend = MagicMock()
        out = tmp_path / "out.wav"
        out.write_bytes(b"\x00")
        mock_backend.tts.return_value = out

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_tts("Hello", output_path=str(out), speed=1.5)

        call_kwargs = mock_backend.tts.call_args
        assert call_kwargs.kwargs["speed"] == 1.5


class TestMcpTtsVoices:
    def test_returns_json_array(self):
        from aicp.mcp.server import aicp_tts_voices

        mock_backend = MagicMock()
        mock_backend.tts_voices.return_value = ["amy", "bob"]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_tts_voices()

        parsed = json.loads(result)
        assert parsed == ["amy", "bob"]

    def test_passes_model(self):
        from aicp.mcp.server import aicp_tts_voices

        mock_backend = MagicMock()
        mock_backend.tts_voices.return_value = []

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_tts_voices(model="coqui")

        mock_backend.tts_voices.assert_called_once_with(model="coqui")


# ── Interactive /tts ─────────────────────────────────────────────────────


class TestInteractiveTts:
    def test_basic(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tts.return_value = Path("/tmp/aicp_tts_output.wav")

        # Mock the stat call on the output path
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value = MagicMock(st_size=5000)
            _handle_slash("/tts Hello world", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "TTS saved" in output

    def test_with_voice(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tts.return_value = Path("/tmp/aicp_tts_output.wav")

        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value = MagicMock(st_size=5000)
            _handle_slash("/tts en-us-amy-low Hello world", [], backend, {}, Mode.THINK, Path("/tmp"))

        call_kwargs = backend.tts.call_args
        assert call_kwargs.kwargs.get("voice") == "en-us-amy-low" or call_kwargs[1].get("voice") == "en-us-amy-low"

    def test_with_voice_and_speed(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tts.return_value = Path("/tmp/aicp_tts_output.wav")

        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value = MagicMock(st_size=5000)
            _handle_slash("/tts en-us-amy-low 1.5 Hello world", [], backend, {}, Mode.THINK, Path("/tmp"))

        call_kwargs = backend.tts.call_args
        assert "1.5" in str(call_kwargs) or call_kwargs.kwargs.get("speed") == 1.5

    def test_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/tts", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/tts hello", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tts.side_effect = RuntimeError("connection refused")

        _handle_slash("/tts hello world", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()


# ── Interactive /voices ──────────────────────────────────────────────────


class TestInteractiveVoices:
    def test_with_voices(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tts_voices.return_value = ["amy", "bob"]

        _handle_slash("/voices", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "amy" in output
        assert "bob" in output

    def test_no_voices(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tts_voices.return_value = []

        _handle_slash("/voices", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "No voice" in output

    def test_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/voices", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tts_voices.side_effect = RuntimeError("failed")

        _handle_slash("/voices", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()
