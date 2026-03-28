"""Tests for multimodal tools (vision, audio, image gen, KB search)."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import json

import pytest

from aicp.core.tools import (
    execute_tool,
    get_tools_for_mode,
    ALL_TOOLS,
    THINK_TOOLS,
    EDIT_TOOLS,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_backend():
    backend = MagicMock()
    backend.base_url = "http://localhost:8090"
    return backend


# ── Tool set tests ──────────────────────────────────────────────────────────

class TestToolSets:
    def test_think_mode_has_read_only_tools(self):
        tools = get_tools_for_mode("think")
        names = {t["function"]["name"] for t in tools}
        assert "file_read" in names
        assert "grep" in names
        assert "image_analyze" in names
        assert "audio_transcribe" in names
        assert "kb_search" in names
        # No write tools in think mode
        assert "shell" not in names
        assert "text_to_speech" not in names
        assert "image_generate" not in names

    def test_edit_mode_has_multimodal_write(self):
        tools = get_tools_for_mode("edit")
        names = {t["function"]["name"] for t in tools}
        assert "image_analyze" in names
        assert "text_to_speech" in names
        assert "image_generate" in names
        assert "shell" not in names

    def test_act_mode_has_all_tools(self):
        tools = get_tools_for_mode("act")
        names = {t["function"]["name"] for t in tools}
        assert "shell" in names
        assert "image_analyze" in names
        assert "text_to_speech" in names
        assert "image_generate" in names
        assert "kb_search" in names

    def test_all_tools_count(self):
        # 4 basic + 8 multimodal (5 read + 3 write) = 12
        assert len(ALL_TOOLS) == 12

    def test_think_tools_count(self):
        # 3 basic read-only + 5 multimodal read-only = 8
        assert len(THINK_TOOLS) == 8

    def test_edit_tools_count(self):
        # 3 basic + 5 read + 3 write = 11
        assert len(EDIT_TOOLS) == 11


# ── image_analyze ───────────────────────────────────────────────────────────

class TestImageAnalyze:
    def test_analyze_returns_description(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        backend = _mock_backend()
        backend.execute_vision.return_value = "A red square."
        result = execute_tool(
            "image_analyze",
            json.dumps({"path": str(img)}),
            tmp_path,
            backend=backend,
        )
        assert result == "A red square."

    def test_analyze_file_not_found(self, tmp_path):
        backend = _mock_backend()
        result = execute_tool(
            "image_analyze",
            json.dumps({"path": "/nonexistent.png"}),
            tmp_path,
            backend=backend,
        )
        assert "not found" in result

    def test_analyze_custom_prompt(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 50)
        backend = _mock_backend()
        backend.execute_vision.return_value = "Blue"
        execute_tool(
            "image_analyze",
            json.dumps({"path": str(img), "prompt": "What color?"}),
            tmp_path,
            backend=backend,
        )
        call_args = backend.execute_vision.call_args
        assert call_args[0][0] == "What color?"

    def test_analyze_no_backend(self, tmp_path):
        result = execute_tool(
            "image_analyze",
            json.dumps({"path": "/test.png"}),
            tmp_path,
        )
        assert "requires a LocalAI backend" in result


# ── audio_transcribe ────────────────────────────────────────────────────────

class TestAudioTranscribe:
    def test_transcribe_returns_text(self, tmp_path):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"\x00" * 100)
        backend = _mock_backend()
        backend.transcribe.return_value = {"text": "Hello world."}
        result = execute_tool(
            "audio_transcribe",
            json.dumps({"path": str(wav)}),
            tmp_path,
            backend=backend,
        )
        assert result == "Hello world."

    def test_transcribe_file_not_found(self, tmp_path):
        backend = _mock_backend()
        result = execute_tool(
            "audio_transcribe",
            json.dumps({"path": "/nonexistent.wav"}),
            tmp_path,
            backend=backend,
        )
        assert "not found" in result

    def test_transcribe_custom_language(self, tmp_path):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"\x00" * 100)
        backend = _mock_backend()
        backend.transcribe.return_value = {"text": "Bonjour."}
        execute_tool(
            "audio_transcribe",
            json.dumps({"path": str(wav), "language": "fr"}),
            tmp_path,
            backend=backend,
        )
        assert backend.transcribe.call_args[1]["language"] == "fr"


# ── text_to_speech ──────────────────────────────────────────────────────────

class TestTextToSpeech:
    def test_tts_returns_path(self, tmp_path):
        output = tmp_path / "out.wav"
        backend = _mock_backend()
        backend.speak.return_value = output
        result = execute_tool(
            "text_to_speech",
            json.dumps({"text": "Hello", "output_path": str(output)}),
            tmp_path,
            backend=backend,
        )
        assert str(output) in result
        backend.speak.assert_called_once()

    def test_tts_default_path(self, tmp_path):
        backend = _mock_backend()
        backend.speak.return_value = Path("/tmp/aicp_tool_tts.wav")
        result = execute_tool(
            "text_to_speech",
            json.dumps({"text": "Hello"}),
            tmp_path,
            backend=backend,
        )
        assert "/tmp/aicp_tool_tts.wav" in result


# ── image_generate ──────────────────────────────────────────────────────────

class TestImageGenerate:
    def test_generate_returns_path(self, tmp_path):
        output = tmp_path / "out.png"
        backend = _mock_backend()
        backend.generate_image.return_value = output
        result = execute_tool(
            "image_generate",
            json.dumps({"prompt": "A cat", "output_path": str(output)}),
            tmp_path,
            backend=backend,
        )
        assert str(output) in result

    def test_generate_custom_size(self, tmp_path):
        backend = _mock_backend()
        backend.generate_image.return_value = Path("/tmp/out.png")
        execute_tool(
            "image_generate",
            json.dumps({"prompt": "test", "size": "768x768"}),
            tmp_path,
            backend=backend,
        )
        assert backend.generate_image.call_args[1]["size"] == "768x768"


# ── kb_search ───────────────────────────────────────────────────────────────

class TestKbSearch:
    def test_kb_search_returns_results(self, tmp_path):
        backend = _mock_backend()
        mock_kb = MagicMock()
        mock_kb.search.return_value = [
            {"text": "chunk", "source": "file.md", "score": 0.9}
        ]
        mock_kb_module = MagicMock()
        mock_kb_module.KnowledgeBase.return_value = mock_kb
        with patch.dict("sys.modules", {"aicp.core.kb": mock_kb_module}):
            result = execute_tool(
                "kb_search",
                json.dumps({"query": "test"}),
                tmp_path,
                backend=backend,
            )
        parsed = json.loads(result)
        assert len(parsed) == 1

    def test_kb_search_no_backend(self, tmp_path):
        result = execute_tool(
            "kb_search",
            json.dumps({"query": "test"}),
            tmp_path,
        )
        assert "requires a LocalAI backend" in result


# ── execute_tool unknown ────────────────────────────────────────────────────

class TestExecuteTool:
    def test_unknown_tool(self, tmp_path):
        result = execute_tool("nonexistent", "{}", tmp_path)
        assert "unknown tool" in result

    def test_invalid_json(self, tmp_path):
        result = execute_tool("file_read", "not json", tmp_path)
        assert "invalid arguments" in result
