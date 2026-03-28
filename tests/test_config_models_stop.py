"""Tests for config-driven model names & stop sequences (M77)."""

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


# ── Config-Driven Specialized Models ────────────────────────────────────────


class TestConfigDrivenModels:
    """Verify specialized model names are configurable via __init__."""

    def test_default_model_names(self):
        backend = _make_backend()
        assert backend.reranker_model == "bge-reranker-v2-m3"
        assert backend.image_model == "stablediffusion"
        assert backend.sound_model == "transformers-musicgen"
        assert backend.whisper_model == "whisper-1"
        assert backend.tts_model == "piper-tts"

    def test_custom_model_names(self):
        backend = _make_backend(
            reranker_model="my-reranker",
            image_model="sdxl",
            sound_model="audiogen",
            whisper_model="whisper-large-v3",
            tts_model="bark",
        )
        assert backend.reranker_model == "my-reranker"
        assert backend.image_model == "sdxl"
        assert backend.sound_model == "audiogen"
        assert backend.whisper_model == "whisper-large-v3"
        assert backend.tts_model == "bark"

    def test_empty_string_uses_default(self):
        """Passing empty string should use built-in defaults."""
        backend = _make_backend(reranker_model="", image_model="", sound_model="")
        assert backend.reranker_model == "bge-reranker-v2-m3"
        assert backend.image_model == "stablediffusion"
        assert backend.sound_model == "transformers-musicgen"


class TestRerankerUsesConfigModel:
    def test_rerank_uses_self_model(self):
        backend = _make_backend(reranker_model="custom-reranker")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"index": 0, "relevance_score": 0.9}]}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.rerank("query", ["doc1"])

        assert captured["model"] == "custom-reranker"

    def test_rerank_explicit_override(self):
        """Explicit model arg should override config."""
        backend = _make_backend(reranker_model="config-reranker")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.rerank("query", ["doc1"], model="explicit-reranker")

        assert captured["model"] == "explicit-reranker"


class TestImageModelUsesConfig:
    def test_generate_image_uses_self_model(self):
        backend = _make_backend(image_model="sdxl-turbo")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"b64_json": "AAAA"}]}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.generate_image("cat", Path("/tmp/img.png"))

        assert captured["model"] == "sdxl-turbo"


class TestSoundModelUsesConfig:
    def test_generate_sound_uses_self_model(self):
        backend = _make_backend(sound_model="audiogen-medium")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake-audio-bytes"
        mock_resp.headers = {"content-type": "audio/wav"}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.generate_sound("rain sounds", Path("/tmp/sound.wav"))

        assert captured["model"] == "audiogen-medium"


class TestWhisperModelUsesConfig:
    def test_transcribe_uses_self_model(self):
        backend = _make_backend(whisper_model="whisper-large-v3")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "hello"}

        captured = {}

        def capture_post(url, files=None, data=None, **kw):
            captured.update(data or {})
            return mock_resp

        audio = Path("/tmp/test_audio.wav")
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("httpx.post", side_effect=capture_post):
                    backend.transcribe(audio)

        assert captured["model"] == "whisper-large-v3"


class TestTtsModelUsesConfig:
    def test_speak_uses_self_model(self):
        backend = _make_backend(tts_model="bark-v2")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio-bytes"
        mock_resp.headers = {"content-type": "audio/wav"}

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch.object(Path, "parent", new_callable=lambda: property(lambda s: MagicMock())):
            with patch("httpx.post", side_effect=capture_post):
                backend.speak("hello", Path("/tmp/out.wav"))

        assert captured["model"] == "bark-v2"


# ── Config Wiring Through _build_backends ───────────────────────────────────


class TestBuildBackendsModels:
    def test_specialized_models_wired(self):
        from aicp.cli.main import _build_backends
        config = {
            "backends": {
                "local": {
                    "base_url": "http://localhost:8090",
                    "model": "hermes",
                    "reranker_model": "my-reranker",
                    "image_model": "sdxl",
                    "sound_model": "musicgen-large",
                    "whisper_model": "whisper-v3",
                    "tts_model": "bark",
                },
                "claude": {},
            }
        }
        backends = _build_backends(config)
        local = backends["local"]
        assert local.reranker_model == "my-reranker"
        assert local.image_model == "sdxl"
        assert local.sound_model == "musicgen-large"
        assert local.whisper_model == "whisper-v3"
        assert local.tts_model == "bark"

    def test_missing_config_uses_defaults(self):
        from aicp.cli.main import _build_backends
        config = {
            "backends": {
                "local": {
                    "base_url": "http://localhost:8090",
                    "model": "hermes",
                },
                "claude": {},
            }
        }
        backends = _build_backends(config)
        local = backends["local"]
        assert local.reranker_model == "bge-reranker-v2-m3"
        assert local.image_model == "stablediffusion"
        assert local.sound_model == "transformers-musicgen"


# ── Stop Sequences ──────────────────────────────────────────────────────────


class TestStopSequences:
    def test_execute_with_stop(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "result"}}],
            "usage": {},
        }

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.execute("test", Mode.THINK, Path("/tmp"), stop=["###", "\n\n"])

        assert captured["stop"] == ["###", "\n\n"]

    def test_execute_without_stop(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "result"}}],
            "usage": {},
        }

        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return mock_resp

        with patch("httpx.post", side_effect=capture_post):
            backend.execute("test", Mode.THINK, Path("/tmp"))

        assert "stop" not in captured

    def test_execute_stream_with_stop(self):
        backend = _make_backend()

        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(["data: [DONE]"])
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_resp)
        ctx.__exit__ = MagicMock(return_value=False)

        def capture_stream(method, url, json=None, **kw):
            captured.update(json or {})
            return ctx

        with patch("httpx.stream", side_effect=capture_stream):
            list(backend.execute_stream("test", Mode.THINK, Path("/tmp"), stop=["END"]))

        assert captured["stop"] == ["END"]

    def test_execute_stream_without_stop(self):
        backend = _make_backend()

        captured = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(["data: [DONE]"])
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_resp)
        ctx.__exit__ = MagicMock(return_value=False)

        def capture_stream(method, url, json=None, **kw):
            captured.update(json or {})
            return ctx

        with patch("httpx.stream", side_effect=capture_stream):
            list(backend.execute_stream("test", Mode.THINK, Path("/tmp")))

        assert "stop" not in captured
