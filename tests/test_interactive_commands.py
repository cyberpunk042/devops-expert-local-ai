"""Tests for interactive mode slash commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from aicp.cli.interactive import _handle_slash
from aicp.core.modes import Mode

# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_backend():
    backend = MagicMock()
    backend.base_url = "http://localhost:8090"
    return backend


def _config():
    return {
        "backends": {
            "local": {
                "whisper_model": "whisper-1",
                "tts_model": "piper-tts",
                "image_model": "stablediffusion",
            }
        }
    }


# ── /help ───────────────────────────────────────────────────────────────────

class TestHelpCommand:
    def test_help_returns_none(self, capsys):
        messages = []
        result = _handle_slash("/help", messages, None, {}, Mode.THINK, Path.cwd())
        assert result is None
        captured = capsys.readouterr()
        assert "/vision" in captured.out
        assert "/transcribe" in captured.out
        assert "/kb" in captured.out
        assert "/grammar" in captured.out


# ── /vision ─────────────────────────────────────────────────────────────────

class TestVisionCommand:
    def test_vision_analyzes_image(self, tmp_path, capsys):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        messages = []
        backend = _mock_backend()
        backend.execute_vision.return_value = "A red square."

        result = _handle_slash(
            f"/vision {img}", messages, backend, _config(), Mode.THINK, tmp_path,
        )
        assert result is None  # doesn't inject as user message
        assert len(messages) == 2  # user + assistant added
        assert messages[1]["content"] == "A red square."

    def test_vision_file_not_found(self, tmp_path, capsys):
        messages = []
        backend = _mock_backend()
        result = _handle_slash(
            "/vision /nonexistent.png", messages, backend, _config(), Mode.THINK, tmp_path,
        )
        assert result is None
        assert len(messages) == 0
        assert "not found" in capsys.readouterr().err

    def test_vision_custom_prompt(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 50)
        backend = _mock_backend()
        backend.execute_vision.return_value = "Blue"

        _handle_slash(
            f"/vision {img} What color?", [], backend, _config(), Mode.THINK, tmp_path,
        )
        assert backend.execute_vision.call_args[0][0] == "What color?"


# ── /transcribe ─────────────────────────────────────────────────────────────

class TestTranscribeCommand:
    def test_transcribe_returns_text(self, tmp_path, capsys):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"\x00" * 100)
        backend = _mock_backend()
        backend.transcribe.return_value = {"text": "Hello world."}

        result = _handle_slash(
            f"/transcribe {wav}", [], backend, _config(), Mode.THINK, tmp_path,
        )
        assert result == "Hello world."

    def test_transcribe_no_speech(self, tmp_path, capsys):
        wav = tmp_path / "silence.wav"
        wav.write_bytes(b"\x00" * 100)
        backend = _mock_backend()
        backend.transcribe.return_value = {"text": ""}

        result = _handle_slash(
            f"/transcribe {wav}", [], backend, _config(), Mode.THINK, tmp_path,
        )
        assert result is None
        assert "No speech" in capsys.readouterr().err


# ── /speak ──────────────────────────────────────────────────────────────────

class TestSpeakCommand:
    def test_speak_last_response(self, tmp_path, capsys):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello there!"},
        ]
        backend = _mock_backend()

        result = _handle_slash("/speak", messages, backend, _config(), Mode.THINK, tmp_path)
        assert result is None
        backend.speak.assert_called_once()
        assert backend.speak.call_args[0][0] == "Hello there!"

    def test_speak_no_response(self, tmp_path, capsys):
        messages = []
        backend = _mock_backend()

        _handle_slash("/speak", messages, backend, _config(), Mode.THINK, tmp_path)
        assert "No AI response" in capsys.readouterr().err


# ── /imagine ────────────────────────────────────────────────────────────────

class TestImagineCommand:
    def test_imagine_generates_image(self, tmp_path, capsys):
        messages = []
        backend = _mock_backend()

        result = _handle_slash(
            "/imagine A sunset over mountains", messages, backend, _config(), Mode.THINK, tmp_path,
        )
        assert result is None
        backend.generate_image.assert_called_once()
        assert len(messages) == 2  # user + assistant

    def test_imagine_no_prompt(self, tmp_path, capsys):
        backend = _mock_backend()
        _handle_slash("/imagine", [], backend, _config(), Mode.THINK, tmp_path)
        assert "Usage" in capsys.readouterr().err


# ── /voice ──────────────────────────────────────────────────────────────────

class TestVoiceCommand:
    def test_voice_full_pipeline(self, tmp_path, capsys):
        wav = tmp_path / "input.wav"
        wav.write_bytes(b"\x00" * 100)
        messages = []
        backend = _mock_backend()
        backend.voice_pipeline.return_value = {
            "transcription": "What time is it?",
            "response": "It is 3 PM.",
            "audio_output": "/tmp/aicp_interactive_voice.wav",
        }

        result = _handle_slash(
            f"/voice {wav}", messages, backend, _config(), Mode.THINK, tmp_path,
        )
        assert result is None
        assert len(messages) == 2
        assert messages[0]["content"] == "What time is it?"
        assert messages[1]["content"] == "It is 3 PM."


# ── No backend ──────────────────────────────────────────────────────────────

class TestNoBackend:
    def test_commands_fail_without_backend(self, tmp_path, capsys):
        result = _handle_slash("/vision test.png", [], None, {}, Mode.THINK, tmp_path)
        assert result is None
        assert "require a LocalAI backend" in capsys.readouterr().err


# ── /kb ────────────────────────────────────────────────────────────────────

class TestKBCommand:
    def test_kb_search(self, tmp_path, capsys):
        backend = _mock_backend()
        mock_kb = MagicMock()
        mock_kb.search.return_value = [
            {"text": "Python is great", "source": "doc.py", "chunk_index": 0, "score": 0.9},
        ]
        with patch("aicp.config.loader.load_config", return_value={"rag": {}, "backends": {"local": {}}}), \
             patch("aicp.core.kb.KnowledgeBase", return_value=mock_kb):
            result = _handle_slash("/kb search Python", [], backend, _config(), Mode.THINK, tmp_path)
        assert result is None
        out = capsys.readouterr().out
        assert "Python is great" in out
        assert "0.900" in out

    def test_kb_search_no_results(self, tmp_path, capsys):
        backend = _mock_backend()
        mock_kb = MagicMock()
        mock_kb.search.return_value = []
        with patch("aicp.config.loader.load_config", return_value={"rag": {}, "backends": {"local": {}}}), \
             patch("aicp.core.kb.KnowledgeBase", return_value=mock_kb):
            result = _handle_slash("/kb search nothing", [], backend, _config(), Mode.THINK, tmp_path)
        assert result is None
        assert "no results" in capsys.readouterr().out

    def test_kb_no_backend(self, tmp_path, capsys):
        result = _handle_slash("/kb search test", [], None, {}, Mode.THINK, tmp_path)
        assert result is None
        assert "require" in capsys.readouterr().err.lower()

    def test_kb_invalid_subcommand(self, tmp_path, capsys):
        result = _handle_slash("/kb foobar", [], _mock_backend(), _config(), Mode.THINK, tmp_path)
        assert result is None
        assert "Usage" in capsys.readouterr().err


# ── /grammar ───────────────────────────────────────────────────────────────

class TestGrammarCommand:
    def test_grammar_constrains_output(self, tmp_path, capsys):
        backend = _mock_backend()
        backend.execute_grammar.return_value = "yes"
        messages = []
        result = _handle_slash(
            '/grammar root ::= ("yes" | "no") | Is Python good?',
            messages, backend, _config(), Mode.THINK, tmp_path,
        )
        assert result is None
        assert len(messages) == 2
        assert messages[1]["content"] == "yes"
        backend.execute_grammar.assert_called_once()

    def test_grammar_no_pipe_separator(self, tmp_path, capsys):
        backend = _mock_backend()
        result = _handle_slash(
            '/grammar root ::= ("yes" "no") prompt here',
            [], backend, _config(), Mode.THINK, tmp_path,
        )
        assert result is None
        assert "Use |" in capsys.readouterr().err

    def test_grammar_no_args(self, tmp_path, capsys):
        backend = _mock_backend()
        result = _handle_slash("/grammar", [], backend, _config(), Mode.THINK, tmp_path)
        assert result is None
        assert "Usage" in capsys.readouterr().err

    def test_grammar_no_backend(self, tmp_path, capsys):
        result = _handle_slash('/grammar test | test', [], None, {}, Mode.THINK, tmp_path)
        assert result is None
        assert "require" in capsys.readouterr().err.lower()


# ── Unknown command ─────────────────────────────────────────────────────────

class TestUnknownCommand:
    def test_unknown_command(self, capsys):
        result = _handle_slash("/foobar", [], _mock_backend(), _config(), Mode.THINK, Path.cwd())
        assert result is None
        assert "Unknown command" in capsys.readouterr().err
