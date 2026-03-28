"""Tests for VAD, object detection, and configurable mode profiles (M74)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

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


# ── Configurable Mode Profiles ───────────────────────────────────────────────

class TestConfigurableModeProfiles:
    def test_default_profiles(self):
        backend = _make_backend()
        assert backend.sampling_params_for_mode(Mode.THINK)["temperature"] == 0.7
        assert backend.sampling_params_for_mode(Mode.EDIT)["temperature"] == 0.4
        assert backend.sampling_params_for_mode(Mode.ACT)["temperature"] == 0.1

    def test_custom_profiles_override(self):
        backend = _make_backend(mode_profiles={
            "think": {"temperature": 0.5},
            "act": {"temperature": 0.3, "top_p": 0.8},
        })
        assert backend.sampling_params_for_mode(Mode.THINK)["temperature"] == 0.5
        assert backend.sampling_params_for_mode(Mode.EDIT)["temperature"] == 0.4  # unchanged
        assert backend.sampling_params_for_mode(Mode.ACT)["temperature"] == 0.3
        assert backend.sampling_params_for_mode(Mode.ACT)["top_p"] == 0.8

    def test_explicit_still_overrides_profile(self):
        """Explicit config (self.temperature) overrides even custom profiles."""
        backend = _make_backend(
            temperature=0.9,
            mode_profiles={"think": {"temperature": 0.5}},
        )
        params = backend.sampling_params_for_mode(Mode.THINK)
        assert params["temperature"] == 0.9  # explicit wins

    def test_profiles_dont_affect_other_backends(self):
        """Mode profiles are per-instance, not global."""
        b1 = _make_backend(mode_profiles={"think": {"temperature": 0.1}})
        b2 = _make_backend()
        assert b1.sampling_params_for_mode(Mode.THINK)["temperature"] == 0.1
        assert b2.sampling_params_for_mode(Mode.THINK)["temperature"] == 0.7

    def test_config_wiring(self):
        """mode_profiles in config are wired through _build_backends."""
        from aicp.cli.main import _build_backends
        config = {
            "backends": {
                "local": {
                    "base_url": "http://localhost:8090",
                    "model": "hermes",
                    "mode_profiles": {
                        "think": {"temperature": 0.6},
                    },
                },
                "claude": {},
            }
        }
        backends = _build_backends(config)
        local = backends["local"]
        assert local.sampling_params_for_mode(Mode.THINK)["temperature"] == 0.6

    def test_none_profiles_uses_defaults(self):
        backend = _make_backend(mode_profiles=None)
        assert backend.sampling_params_for_mode(Mode.THINK)["temperature"] == 0.7


# ── Voice Activity Detection ────────────────────────────────────────────────

class TestVAD:
    def test_returns_segments(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "segments": [
                {"start": 0.5, "end": 2.3, "text": "Hello"},
                {"start": 3.1, "end": 5.0, "text": "World"},
            ],
        }

        m = mock_open(read_data=b"fake audio")
        with patch("builtins.open", m):
            with patch("httpx.post", return_value=mock_resp):
                result = backend.vad(Path("/tmp/audio.wav"))

        assert len(result) == 2
        assert result[0]["start"] == 0.5
        assert result[1]["text"] == "World"

    def test_404_not_available(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        m = mock_open(read_data=b"audio")
        with patch("builtins.open", m):
            with patch("httpx.post", return_value=mock_resp):
                with pytest.raises(RuntimeError, match="not available"):
                    backend.vad(Path("/tmp/audio.wav"))

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        m = mock_open(read_data=b"audio")
        with patch("builtins.open", m):
            with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
                with pytest.raises(RuntimeError, match="Cannot connect"):
                    backend.vad(Path("/tmp/audio.wav"))

    def test_empty_segments(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"segments": []}

        m = mock_open(read_data=b"audio")
        with patch("builtins.open", m):
            with patch("httpx.post", return_value=mock_resp):
                result = backend.vad(Path("/tmp/silence.wav"))

        assert result == []


# ── Object Detection ────────────────────────────────────────────────────────

class TestDetect:
    def test_returns_detections(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "detections": [
                {"label": "cat", "confidence": 0.95, "box": {"x": 10, "y": 20, "w": 100, "h": 80}},
                {"label": "dog", "confidence": 0.72, "box": {"x": 200, "y": 50, "w": 90, "h": 60}},
            ],
        }

        m = mock_open(read_data=b"fake image")
        with patch("builtins.open", m):
            with patch("httpx.post", return_value=mock_resp):
                result = backend.detect(Path("/tmp/photo.jpg"))

        assert len(result) == 2
        assert result[0]["label"] == "cat"
        assert result[0]["confidence"] == 0.95

    def test_404_not_available(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        m = mock_open(read_data=b"image")
        with patch("builtins.open", m):
            with patch("httpx.post", return_value=mock_resp):
                with pytest.raises(RuntimeError, match="not available"):
                    backend.detect(Path("/tmp/photo.jpg"))

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        m = mock_open(read_data=b"image")
        with patch("builtins.open", m):
            with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
                with pytest.raises(RuntimeError, match="Cannot connect"):
                    backend.detect(Path("/tmp/photo.jpg"))

    def test_empty_detections(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"detections": []}

        m = mock_open(read_data=b"image")
        with patch("builtins.open", m):
            with patch("httpx.post", return_value=mock_resp):
                result = backend.detect(Path("/tmp/empty.jpg"))

        assert result == []


# ── MCP Tools ────────────────────────────────────────────────────────────────

class TestMcpVadDetect:
    def test_aicp_vad(self):
        from aicp.mcp.server import aicp_vad

        mock_backend = MagicMock()
        mock_backend.vad.return_value = [
            {"start": 0.0, "end": 1.5, "text": "hi"},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_vad("/tmp/audio.wav")

        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["text"] == "hi"

    def test_aicp_detect(self):
        from aicp.mcp.server import aicp_detect

        mock_backend = MagicMock()
        mock_backend.detect.return_value = [
            {"label": "person", "confidence": 0.88},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_detect("/tmp/photo.jpg")

        parsed = json.loads(result)
        assert parsed[0]["label"] == "person"


# ── Interactive Slash Commands ───────────────────────────────────────────────

class TestInteractiveVadDetect:
    def test_vad_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.vad.return_value = [
            {"start": 0.5, "end": 2.0, "text": "Hello"},
        ]

        _handle_slash("/vad /tmp/audio.wav", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "Hello" in output
        assert "0.5" in output

    def test_vad_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/vad", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "Usage" in capsys.readouterr().err

    def test_vad_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.vad.side_effect = RuntimeError("not available")
        _handle_slash("/vad /tmp/a.wav", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "error" in capsys.readouterr().err.lower()

    def test_detect_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.detect.return_value = [
            {"label": "cat", "confidence": 0.95},
        ]

        _handle_slash("/detect /tmp/photo.jpg", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "cat" in output

    def test_detect_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/detect", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "Usage" in capsys.readouterr().err

    def test_detect_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/detect /tmp/p.jpg", [], None, {}, Mode.THINK, Path("/tmp"))
        assert "require" in capsys.readouterr().err.lower()
