"""Tests for LocalAI backend API methods — execute, embed, audio, vision, tools, stores."""

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_chat_response(content: str = "hello", model: str = "hermes"):
    """Build a mock 200 chat completion response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "model": model,
    }
    return resp


def _ok_embedding_response(vectors: list[list[float]] | None = None):
    """Build a mock 200 embedding response."""
    if vectors is None:
        vectors = [[0.1, 0.2, 0.3]]
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": [{"embedding": v, "index": i} for i, v in enumerate(vectors)]
    }
    return resp


def _error_response(status: int = 500, message: str = "server error"):
    resp = MagicMock()
    resp.status_code = status
    resp.text = message
    resp.json.return_value = {"error": {"message": message}}
    return resp


# ---------------------------------------------------------------------------
# Core execute
# ---------------------------------------------------------------------------


class TestExecute:
    """Tests for the main execute() path."""

    def test_execute_success_extracts_content(self, tmp_path):
        backend = LocalAIBackend()
        with patch("httpx.post", return_value=_ok_chat_response("The answer is 42")):
            result = backend.execute("test", Mode.THINK, tmp_path)
        assert result == "The answer is 42"

    def test_execute_uses_selected_model(self, tmp_path):
        """When auto_route is on, _select_model picks via router.recommend_model."""
        backend = LocalAIBackend(model="hermes", auto_route=True)
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["model"] = json["model"]
            return _ok_chat_response()

        with patch("httpx.post", side_effect=fake_post):
            with patch("aicp.core.router.recommend_model", return_value="qwen3-8b"):
                backend.execute("implement a Python function to sort", Mode.THINK, tmp_path)
        assert captured["model"] == "qwen3-8b"

    def test_execute_seed_forwarded(self, tmp_path):
        backend = LocalAIBackend()
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["payload"] = json
            return _ok_chat_response()

        with patch("httpx.post", side_effect=fake_post):
            backend.execute("test", Mode.THINK, tmp_path, seed=42)
        assert captured["payload"]["seed"] == 42

    def test_execute_stop_tokens_forwarded(self, tmp_path):
        backend = LocalAIBackend()
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["payload"] = json
            return _ok_chat_response()

        with patch("httpx.post", side_effect=fake_post):
            backend.execute("test", Mode.THINK, tmp_path, stop=["###", "END"])
        assert captured["payload"]["stop"] == ["###", "END"]

    def test_execute_400_raises(self, tmp_path):
        backend = LocalAIBackend()
        with patch("httpx.post", return_value=_error_response(400, "bad request")):
            with pytest.raises(RuntimeError, match="LocalAI error.*400"):
                backend.execute("test", Mode.THINK, tmp_path)

    def test_execute_connect_error(self, tmp_path):
        import httpx
        backend = LocalAIBackend()
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError):
                backend.execute("test", Mode.THINK, tmp_path)

    def test_execute_timeout_raises(self, tmp_path):
        import httpx
        backend = LocalAIBackend()
        with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.execute("test", Mode.THINK, tmp_path)

    def test_execute_mode_sampling_applied(self, tmp_path):
        """Sampling params from mode profile are included in payload."""
        backend = LocalAIBackend()
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["payload"] = json
            return _ok_chat_response()

        with patch("httpx.post", side_effect=fake_post):
            backend.execute("test", Mode.THINK, tmp_path)
        # Think mode should include temperature in the payload
        assert "temperature" in captured["payload"]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


class TestEmbeddings:
    """Tests for embed / embed_batch / embed_typed."""

    def test_embed_returns_vector(self):
        backend = LocalAIBackend(embedding_model="nomic-embed")
        with patch("httpx.post", return_value=_ok_embedding_response([[0.1, 0.2, 0.3]])):
            result = backend.embed("hello world")
        assert result == [0.1, 0.2, 0.3]

    def test_embed_batch_returns_multiple(self):
        backend = LocalAIBackend(embedding_model="nomic-embed")
        vecs = [[0.1, 0.2], [0.3, 0.4]]
        with patch("httpx.post", return_value=_ok_embedding_response(vecs)):
            result = backend.embed_batch(["text1", "text2"])
        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]

    def test_embed_error_raises(self):
        backend = LocalAIBackend()
        with patch("httpx.post", return_value=_error_response(400, "bad model")):
            with pytest.raises(RuntimeError, match="Embedding error"):
                backend.embed("test")

    def test_embed_typed_sends_type(self):
        backend = LocalAIBackend(embedding_model="nomic-embed")
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["payload"] = json
            return _ok_embedding_response()

        with patch("httpx.post", side_effect=fake_post):
            backend.embed_typed("search query", embed_type="query")
        assert captured["payload"]["type"] == "query"

    def test_embed_typed_invalid_type_raises(self):
        backend = LocalAIBackend()
        with pytest.raises(ValueError, match="embed_type must be"):
            backend.embed_typed("test", embed_type="invalid")

    def test_embed_uses_embedding_model(self):
        backend = LocalAIBackend(embedding_model="nomic-embed")
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["model"] = json["model"]
            return _ok_embedding_response()

        with patch("httpx.post", side_effect=fake_post):
            backend.embed("hello")
        assert captured["model"] == "nomic-embed"

    def test_embed_connect_error(self):
        import httpx
        backend = LocalAIBackend()
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError):
                backend.embed_typed("test", embed_type="query")


# ---------------------------------------------------------------------------
# Audio: transcribe, speak, tts, voice_pipeline
# ---------------------------------------------------------------------------


class TestAudio:
    """Tests for audio methods — transcribe, speak, tts, voice_pipeline."""

    def test_transcribe_returns_text(self, tmp_path):
        backend = LocalAIBackend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"text": "Hello world"}

        with patch("httpx.post", return_value=resp):
            result = backend.transcribe(audio)
        assert result["text"] == "Hello world"

    def test_transcribe_file_not_found(self, tmp_path):
        backend = LocalAIBackend()
        with pytest.raises(FileNotFoundError):
            backend.transcribe(tmp_path / "nonexistent.wav")

    def test_transcribe_error_raises(self, tmp_path):
        backend = LocalAIBackend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        with patch("httpx.post", return_value=_error_response(500, "whisper error")):
            with pytest.raises(RuntimeError, match="Transcription error"):
                backend.transcribe(audio)

    def test_speak_writes_file(self, tmp_path):
        backend = LocalAIBackend()
        output = tmp_path / "out.wav"

        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"\x00" * 1000
        resp.headers = {"content-type": "audio/wav"}

        with patch("httpx.post", return_value=resp):
            result = backend.speak("Hello world", output)
        assert result == output
        assert output.read_bytes() == b"\x00" * 1000

    def test_speak_json_error_raises(self, tmp_path):
        backend = LocalAIBackend()
        output = tmp_path / "out.wav"

        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{}'
        resp.text = '{"error": "no model"}'
        resp.headers = {"content-type": "application/json"}

        with patch("httpx.post", return_value=resp):
            with pytest.raises(RuntimeError, match="TTS returned error"):
                backend.speak("Hello", output)

    def test_voice_pipeline_chains_steps(self, tmp_path):
        """voice_pipeline calls transcribe → execute → speak in order."""
        backend = LocalAIBackend()
        audio_in = tmp_path / "in.wav"
        audio_in.write_bytes(b"\x00" * 100)
        audio_out = tmp_path / "out.wav"

        # Mock all three steps
        backend.transcribe = MagicMock(return_value={"text": "What is Python?"})
        backend.execute = MagicMock(return_value="Python is a programming language")
        backend.speak = MagicMock(return_value=audio_out)

        result = backend.voice_pipeline(audio_in, audio_out, Mode.THINK, tmp_path)

        assert result["transcription"] == "What is Python?"
        assert result["response"] == "Python is a programming language"
        backend.transcribe.assert_called_once()
        backend.execute.assert_called_once()
        backend.speak.assert_called_once()

    def test_voice_pipeline_empty_transcription_raises(self, tmp_path):
        backend = LocalAIBackend()
        audio_in = tmp_path / "in.wav"
        audio_in.write_bytes(b"\x00" * 100)
        audio_out = tmp_path / "out.wav"

        backend.transcribe = MagicMock(return_value={"text": ""})

        with pytest.raises(RuntimeError, match="No speech detected"):
            backend.voice_pipeline(audio_in, audio_out, Mode.THINK, tmp_path)


# ---------------------------------------------------------------------------
# Vision
# ---------------------------------------------------------------------------


class TestVision:
    """Tests for execute_vision and execute_multimodal."""

    def test_vision_success(self, tmp_path):
        backend = LocalAIBackend(vision_model="llava")
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["payload"] = json
            return _ok_chat_response("A cat on a table")

        with patch("httpx.post", side_effect=fake_post):
            result = backend.execute_vision("Describe this", "aGVsbG8=", Mode.THINK, tmp_path)

        assert result == "A cat on a table"
        assert captured["payload"]["model"] == "llava"
        # Check image_url is in message content
        user_content = captured["payload"]["messages"][1]["content"]
        assert any(item["type"] == "image_url" for item in user_content)

    def test_vision_error_raises(self, tmp_path):
        backend = LocalAIBackend()
        with patch("httpx.post", return_value=_error_response(400, "bad image")):
            with pytest.raises(RuntimeError, match="vision error"):
                backend.execute_vision("test", "aGVsbG8=", Mode.THINK, tmp_path)

    def test_multimodal_with_images(self, tmp_path):
        backend = LocalAIBackend(vision_model="llava")
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["payload"] = json
            return _ok_chat_response("Blue square")

        messages = [{"role": "user", "content": "What is in {img:0}?"}]
        images = [{"data": "aGVsbG8=", "mime": "image/png"}]

        with patch("httpx.post", side_effect=fake_post):
            result = backend.execute_multimodal(messages, images, Mode.THINK, tmp_path)

        assert result == "Blue square"
        # Verify image was injected
        user_msg = captured["payload"]["messages"][1]
        assert isinstance(user_msg["content"], list)

    def test_multimodal_error_raises(self, tmp_path):
        backend = LocalAIBackend()
        with patch("httpx.post", return_value=_error_response(500, "OOM")):
            with pytest.raises(RuntimeError, match="multimodal error"):
                backend.execute_multimodal(
                    [{"role": "user", "content": "test"}], [], Mode.THINK, tmp_path
                )


# ---------------------------------------------------------------------------
# Specialized: grammar, rerank, image generation, JSON mode
# ---------------------------------------------------------------------------


class TestSpecialized:
    """Tests for grammar, rerank, generate_image, execute_json."""

    def test_execute_grammar_sends_gbnf(self, tmp_path):
        backend = LocalAIBackend()
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["payload"] = json
            return _ok_chat_response("yes")

        with patch("httpx.post", side_effect=fake_post):
            result = backend.execute_grammar("answer", 'root ::= ("yes" | "no")', Mode.THINK, tmp_path)

        assert result == "yes"
        assert captured["payload"]["grammar"] == 'root ::= ("yes" | "no")'

    def test_execute_json_returns_dict(self, tmp_path):
        backend = LocalAIBackend()

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": '{"key": "value"}'}}],
            "usage": {},
        }

        with patch("httpx.post", return_value=resp):
            result = backend.execute_json("return JSON", Mode.THINK, tmp_path)
        assert result == {"key": "value"}

    def test_execute_json_invalid_json_raises(self, tmp_path):
        backend = LocalAIBackend()

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": "not json"}}],
            "usage": {},
        }

        with patch("httpx.post", return_value=resp):
            with pytest.raises(RuntimeError, match="invalid JSON"):
                backend.execute_json("return JSON", Mode.THINK, tmp_path)

    def test_execute_json_with_schema(self, tmp_path):
        backend = LocalAIBackend()
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["payload"] = json
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": '{"name": "test"}'}}],
                "usage": {},
            }
            return resp

        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        with patch("httpx.post", side_effect=fake_post):
            backend.execute_json("return JSON", Mode.THINK, tmp_path, schema=schema)
        # Schema should be appended to system prompt
        system_content = captured["payload"]["messages"][0]["content"]
        assert "name" in system_content

    def test_rerank_returns_sorted(self):
        backend = LocalAIBackend()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.3},
                {"index": 1, "relevance_score": 0.9},
            ]
        }

        with patch("httpx.post", return_value=resp):
            results = backend.rerank("query", ["doc1", "doc2"])
        # Should be sorted descending by score
        assert results[0]["relevance_score"] == 0.9
        assert results[1]["relevance_score"] == 0.3

    def test_rerank_error_raises(self):
        backend = LocalAIBackend()
        with patch("httpx.post", return_value=_error_response(400, "bad model")):
            with pytest.raises(RuntimeError, match="Rerank error"):
                backend.rerank("query", ["doc1"])

    def test_generate_image_b64(self, tmp_path):
        backend = LocalAIBackend()
        output = tmp_path / "img.png"

        image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        b64 = base64.b64encode(image_bytes).decode()

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": [{"b64_json": b64}]}

        with patch("httpx.post", return_value=resp):
            result = backend.generate_image("a cat", output)

        assert result == output
        assert output.read_bytes() == image_bytes

    def test_generate_image_url(self, tmp_path):
        backend = LocalAIBackend()
        output = tmp_path / "img.png"

        image_bytes = b"\x89PNG\r\n"

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = {"data": [{"url": "http://localhost:8090/images/gen.png"}]}

        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.content = image_bytes

        with patch("httpx.post", return_value=post_resp):
            with patch("httpx.get", return_value=get_resp):
                result = backend.generate_image("a cat", output)

        assert result == output
        assert output.read_bytes() == image_bytes

    def test_generate_image_no_data_raises(self, tmp_path):
        backend = LocalAIBackend()
        output = tmp_path / "img.png"

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": []}

        with patch("httpx.post", return_value=resp):
            with pytest.raises(RuntimeError, match="No images returned"):
                backend.generate_image("a cat", output)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class TestTools:
    """Tests for execute_with_tools and execute_with_native_tools."""

    def test_execute_with_tools_no_tool_call(self, tmp_path):
        """When model responds with plain text (no tool call), return it."""
        backend = LocalAIBackend()

        with patch("httpx.post", return_value=_ok_chat_response("Just a text answer")):
            result = backend.execute_with_tools(
                "what is Python?", Mode.THINK, tmp_path, tools=[]
            )
        assert result == "Just a text answer"

    def test_execute_with_native_tools_no_tool_calls(self, tmp_path):
        """When model responds without tool_calls, return content."""
        backend = LocalAIBackend()

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": "plain answer", "tool_calls": None}}],
            "usage": {},
        }

        with patch("httpx.post", return_value=resp):
            result = backend.execute_with_native_tools(
                "hello", Mode.THINK, tmp_path, tools=[]
            )
        assert result == "plain answer"

    def test_execute_with_native_tools_error_raises(self, tmp_path):
        backend = LocalAIBackend()
        with patch("httpx.post", return_value=_error_response(500, "OOM")):
            with pytest.raises(RuntimeError, match="LocalAI error"):
                backend.execute_with_native_tools("test", Mode.THINK, tmp_path, tools=[])

    def test_execute_with_tools_max_rounds(self, tmp_path):
        """Tool loop should respect max_rounds limit."""
        backend = LocalAIBackend()
        call_count = {"n": 0}

        def fake_post(url, json, timeout, headers=None):
            call_count["n"] += 1
            # Always return a tool call to force looping
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {
                    "content": '<tool_call>\n{"name": "dummy", "arguments": {}}\n</tool_call>',
                }}],
                "usage": {},
            }
            return resp

        with patch("httpx.post", side_effect=fake_post):
            with patch("aicp.core.tools.execute_tool", return_value="ok"):
                with patch("aicp.core.tools.get_tools_for_mode", return_value=[]):
                    backend.execute_with_tools("test", Mode.THINK, tmp_path, max_rounds=2)

        assert call_count["n"] <= 2


# ---------------------------------------------------------------------------
# Store operations
# ---------------------------------------------------------------------------


class TestStores:
    """Tests for store_set and store_find."""

    def test_store_set(self):
        backend = LocalAIBackend(embedding_model="nomic-embed")
        backend.embed_batch = MagicMock(return_value=[[0.1, 0.2], [0.3, 0.4]])

        mock_store = MagicMock()
        with patch("aicp.core.stores.LocalAIStore", return_value=mock_store):
            count = backend.store_set(["text1", "text2"], store_name="test-store")

        assert count == 2
        backend.embed_batch.assert_called_once_with(["text1", "text2"])
        mock_store.set.assert_called_once()

    def test_store_find(self):
        backend = LocalAIBackend(embedding_model="nomic-embed")
        backend.embed = MagicMock(return_value=[0.1, 0.2, 0.3])

        mock_store = MagicMock()
        mock_store.find.return_value = [
            {"value": "result1", "similarity": 0.95},
            {"value": "result2", "similarity": 0.80},
        ]
        with patch("aicp.core.stores.LocalAIStore", return_value=mock_store):
            results = backend.store_find("search query", top_k=2)

        assert len(results) == 2
        assert results[0]["value"] == "result1"
        assert results[0]["similarity"] == 0.95
        backend.embed.assert_called_once_with("search query")

    def test_store_find_respects_top_k(self):
        backend = LocalAIBackend()
        backend.embed = MagicMock(return_value=[0.1])

        mock_store = MagicMock()
        mock_store.find.return_value = []
        with patch("aicp.core.stores.LocalAIStore", return_value=mock_store):
            backend.store_find("query", top_k=3)

        mock_store.find.assert_called_once_with([0.1], top_k=3)


# ---------------------------------------------------------------------------
# TTS advanced
# ---------------------------------------------------------------------------


class TestTTSAdvanced:
    """Tests for the tts() method with voice/speed/format options."""

    def test_tts_writes_file(self, tmp_path):
        backend = LocalAIBackend()
        output = tmp_path / "speech.wav"

        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"\x00" * 500
        resp.headers = {"content-type": "audio/wav"}

        with patch("httpx.post", return_value=resp):
            result = backend.tts("Hello", output, voice="en-us-amy-low")
        assert result == output
        assert output.exists()

    def test_tts_speed_clamped(self, tmp_path):
        backend = LocalAIBackend()
        output = tmp_path / "speech.wav"
        captured = {}

        def fake_post(url, json, timeout, headers=None):
            captured["payload"] = json
            resp = MagicMock()
            resp.status_code = 200
            resp.content = b"\x00" * 100
            resp.headers = {"content-type": "audio/wav"}
            return resp

        with patch("httpx.post", side_effect=fake_post):
            backend.tts("Hello", output, speed=10.0)  # should clamp to 4.0
        assert captured["payload"]["speed"] == 4.0


# ---------------------------------------------------------------------------
# Transcribe detailed
# ---------------------------------------------------------------------------


class TestTranscribeDetailed:

    def test_transcribe_detailed_returns_segments(self, tmp_path):
        backend = LocalAIBackend()
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"\x00" * 100)

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "text": "Hello world",
            "language": "en",
            "duration": 2.5,
            "segments": [{"start": 0.0, "end": 2.5, "text": "Hello world"}],
        }

        with patch("httpx.post", return_value=resp):
            result = backend.transcribe_detailed(audio)
        assert result["text"] == "Hello world"
        assert result["duration"] == 2.5
        assert len(result["segments"]) == 1
