"""Tests for sound generation and raw text completions (M68)."""

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


# ── Sound generation ─────────────────────────────────────────────────────────

class TestGenerateSound:
    def test_generates_and_saves_audio(self, tmp_path):
        backend = _make_backend()
        out = tmp_path / "sound.wav"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"RIFF\x00\x00\x00\x00WAVEfmt "  # fake wav header

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = backend.generate_sound("a piano melody", out)

        assert result == out
        assert out.exists()
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["input"] == "a piano melody"
        assert payload["model"] == "transformers-musicgen"
        assert "/v1/sound-generation" in str(mock_post.call_args)

    def test_custom_model_and_duration(self, tmp_path):
        backend = _make_backend()
        out = tmp_path / "sound.wav"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio-data"

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.generate_sound("rain", out, model="custom-sound", duration=5.0)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["model"] == "custom-sound"
        assert payload["duration"] == 5.0

    def test_creates_parent_dirs(self, tmp_path):
        backend = _make_backend()
        out = tmp_path / "deep" / "nested" / "sound.wav"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio"

        with patch("httpx.post", return_value=mock_resp):
            backend.generate_sound("test", out)

        assert out.exists()

    def test_http_error(self, tmp_path):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.generate_sound("test", tmp_path / "out.wav")

    def test_connect_error(self, tmp_path):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.generate_sound("test", tmp_path / "out.wav")

    def test_timeout_error(self, tmp_path):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.generate_sound("test", tmp_path / "out.wav")

    def test_usage_tracking(self, tmp_path):
        backend = _make_backend()
        out = tmp_path / "sound.wav"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio-bytes"

        with patch("httpx.post", return_value=mock_resp):
            backend.generate_sound("test", out, model="musicgen")

        assert backend.last_usage["model"] == "musicgen"
        assert backend.last_usage["sound_generation"] is True


# ── Raw text completions ─────────────────────────────────────────────────────

class TestComplete:
    def test_sends_prompt_not_messages(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "world!"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = backend.complete("Hello ")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "prompt" in payload
        assert "messages" not in payload
        assert payload["prompt"] == "Hello "
        assert "/v1/completions" in str(mock_post.call_args)
        assert result == "world!"

    def test_custom_max_tokens(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "output"}],
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.complete("test", max_tokens=100)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["max_tokens"] == 100

    def test_stop_sequences(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "output"}],
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.complete("test", stop=["###", "\n\n"])

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["stop"] == ["###", "\n\n"]

    def test_no_stop_by_default(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "x"}]}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.complete("test")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "stop" not in payload

    def test_includes_sampling_params(self):
        backend = _make_backend(temperature=0.5, top_p=0.8)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "x"}]}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.complete("test")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["temperature"] == 0.5
        assert payload["top_p"] == 0.8

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.complete("test")

    def test_connect_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.complete("test")

    def test_usage_tracking(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "result"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        with patch("httpx.post", return_value=mock_resp):
            backend.complete("test")

        assert backend.last_usage["prompt_tokens"] == 10
        assert backend.last_usage["completion_tokens"] == 5
        assert backend.last_usage["completion"] is True


# ── MCP tools ────────────────────────────────────────────────────────────────

class TestMcpSoundComplete:
    def test_aicp_sound(self):
        from aicp.mcp.server import aicp_sound

        mock_backend = MagicMock()
        mock_backend.generate_sound.return_value = Path("/tmp/test.wav")

        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=mock_backend),
            _config={"backends": {"local": {"sound_model": "my-musicgen"}}},
        ):
            result = aicp_sound("piano rain", output_path="/tmp/test.wav")

        mock_backend.generate_sound.assert_called_once()
        assert "/tmp/test.wav" in result

    def test_aicp_complete(self):
        from aicp.mcp.server import aicp_complete

        mock_backend = MagicMock()
        mock_backend.complete.return_value = "world!"

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_complete("Hello ", max_tokens=100)

        mock_backend.complete.assert_called_once_with("Hello ", max_tokens=100, stop=None)
        assert result == "world!"

    def test_aicp_complete_with_stop(self):
        from aicp.mcp.server import aicp_complete

        mock_backend = MagicMock()
        mock_backend.complete.return_value = "answer"

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_complete("Question?", stop="###,\\n")

        call_args = mock_backend.complete.call_args
        assert call_args.kwargs.get("stop") == ["###", "\\n"]


# ── Interactive slash commands ───────────────────────────────────────────────

class TestInteractiveSoundComplete:
    def test_sound_command(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.generate_sound.return_value = Path("/tmp/aicp_interactive_sound.wav")
        config = {"backends": {"local": {"sound_model": "musicgen"}}}

        result = _handle_slash(
            "/sound a cheerful guitar riff",
            [], backend, config, Mode.THINK, Path("/tmp"),
        )

        assert result is None
        backend.generate_sound.assert_called_once()
        assert "saved" in capsys.readouterr().out.lower()

    def test_sound_no_prompt(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/sound", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "Usage" in capsys.readouterr().err

    def test_complete_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.complete_stream.return_value = iter(["world!"])

        result = _handle_slash(
            "/complete Hello world",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        assert result is None
        backend.complete_stream.assert_called_once()
        output = capsys.readouterr().out
        assert "world!" in output

    def test_complete_no_text(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/complete", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "Usage" in capsys.readouterr().err

    def test_sound_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.generate_sound.side_effect = RuntimeError("model not found")

        _handle_slash(
            "/sound test",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        assert "error" in capsys.readouterr().err.lower()

    def test_complete_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.complete_stream.side_effect = RuntimeError("connection refused")

        _handle_slash(
            "/complete test text",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        assert "error" in capsys.readouterr().err.lower()
