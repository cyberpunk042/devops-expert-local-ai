"""Tests for Multimodal Chat Messages (M87)."""

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


def _mock_vision_response(content="I see a cat"):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10},
    }
    return mock_resp


# ── Backend execute_multimodal() ──────────────────────────────────────────


class TestExecuteMultimodal:
    def test_single_image_single_message(self):
        backend = _make_backend(vision_model="llava")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_vision_response()

        messages = [{"role": "user", "content": "{img:0} What is this?"}]
        images = [{"data": "abc123", "mime": "image/jpeg"}]

        with patch("httpx.post", side_effect=capture_post):
            result = backend.execute_multimodal(messages, images, Mode.THINK, Path("/tmp"))

        assert result == "I see a cat"
        assert captured["model"] == "llava"
        # Check the user message was converted to multimodal content array
        user_msg = captured["messages"][-1]
        assert isinstance(user_msg["content"], list)
        assert user_msg["content"][0]["type"] == "image_url"
        assert "data:image/jpeg;base64,abc123" in user_msg["content"][0]["image_url"]["url"]
        assert user_msg["content"][1]["type"] == "text"
        assert "What is this?" in user_msg["content"][1]["text"]

    def test_text_before_and_after_image(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_vision_response()

        messages = [{"role": "user", "content": "Look at this {img:0} and describe it"}]
        images = [{"data": "imgdata", "mime": "image/png"}]

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_multimodal(messages, images, Mode.THINK, Path("/tmp"))

        user_msg = captured["messages"][-1]
        content = user_msg["content"]
        assert isinstance(content, list)
        # Should have: text, image, text
        types = [c["type"] for c in content]
        assert "text" in types
        assert "image_url" in types

    def test_multiple_images(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_vision_response()

        messages = [{"role": "user", "content": "Compare {img:0} with {img:1}"}]
        images = [
            {"data": "img1data", "mime": "image/png"},
            {"data": "img2data", "mime": "image/jpeg"},
        ]

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_multimodal(messages, images, Mode.THINK, Path("/tmp"))

        user_msg = captured["messages"][-1]
        content = user_msg["content"]
        image_parts = [c for c in content if c["type"] == "image_url"]
        assert len(image_parts) == 2
        assert "img1data" in image_parts[0]["image_url"]["url"]
        assert "img2data" in image_parts[1]["image_url"]["url"]

    def test_multi_turn_conversation(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_vision_response("It's a dog")

        messages = [
            {"role": "user", "content": "{img:0} What is this?"},
            {"role": "assistant", "content": "I see a cat"},
            {"role": "user", "content": "Are you sure? Look again."},
        ]
        images = [{"data": "catimg", "mime": "image/png"}]

        with patch("httpx.post", side_effect=capture_post):
            result = backend.execute_multimodal(messages, images, Mode.THINK, Path("/tmp"))

        assert result == "It's a dog"
        # System + 3 messages = 4 total
        assert len(captured["messages"]) == 4
        # First user message should be multimodal
        assert isinstance(captured["messages"][1]["content"], list)
        # Third message (second user) should be plain text
        assert isinstance(captured["messages"][3]["content"], str)

    def test_text_only_messages_pass_through(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_vision_response()

        messages = [{"role": "user", "content": "Hello, no images here"}]
        images = []

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_multimodal(messages, images, Mode.THINK, Path("/tmp"))

        user_msg = captured["messages"][-1]
        assert isinstance(user_msg["content"], str)
        assert user_msg["content"] == "Hello, no images here"

    def test_uses_vision_model(self):
        backend = _make_backend(vision_model="llava-v1.6")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_vision_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_multimodal(
                [{"role": "user", "content": "hi"}], [], Mode.THINK, Path("/tmp")
            )

        assert captured["model"] == "llava-v1.6"

    def test_falls_back_to_default_model(self):
        backend = _make_backend()  # no vision_model
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_vision_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_multimodal(
                [{"role": "user", "content": "hi"}], [], Mode.THINK, Path("/tmp")
            )

        assert captured["model"] == "hermes"

    def test_seed_passed(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_vision_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_multimodal(
                [{"role": "user", "content": "hi"}], [], Mode.THINK, Path("/tmp"), seed=42
            )

        assert captured["seed"] == 42

    def test_tracks_usage(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_mock_vision_response()):
            backend.execute_multimodal(
                [{"role": "user", "content": "hi"}],
                [{"data": "x", "mime": "image/png"}],
                Mode.THINK, Path("/tmp"),
            )

        assert backend.last_usage["multimodal"] is True
        assert backend.last_usage["images"] == 1
        assert backend.last_usage["prompt_tokens"] == 50

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.execute_multimodal(
                    [{"role": "user", "content": "hi"}], [], Mode.THINK, Path("/tmp")
                )

    def test_timeout_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.execute_multimodal(
                    [{"role": "user", "content": "hi"}], [], Mode.THINK, Path("/tmp")
                )

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.execute_multimodal(
                    [{"role": "user", "content": "hi"}], [], Mode.THINK, Path("/tmp")
                )

    def test_unexpected_response(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"bad": "format"}

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Unexpected"):
                backend.execute_multimodal(
                    [{"role": "user", "content": "hi"}], [], Mode.THINK, Path("/tmp")
                )

    def test_default_mime_type(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _mock_vision_response()

        messages = [{"role": "user", "content": "{img:0} describe"}]
        images = [{"data": "abc"}]  # no mime specified

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_multimodal(messages, images, Mode.THINK, Path("/tmp"))

        user_msg = captured["messages"][-1]
        img_part = [c for c in user_msg["content"] if c["type"] == "image_url"][0]
        assert "image/png" in img_part["image_url"]["url"]


# ── MCP: aicp_multimodal ──────────────────────────────────────────────────


class TestMcpMultimodal:
    def test_returns_response_text(self):
        from aicp.mcp.server import aicp_multimodal

        mock_backend = MagicMock()
        mock_backend.execute_multimodal.return_value = "I see a cat"

        msgs = json.dumps([{"role": "user", "content": "{img:0} What?"}])
        imgs = json.dumps([{"data": "abc", "mime": "image/png"}])

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_multimodal(msgs, imgs)

        assert result == "I see a cat"
        mock_backend.execute_multimodal.assert_called_once()

    def test_passes_mode(self):
        from aicp.mcp.server import aicp_multimodal

        mock_backend = MagicMock()
        mock_backend.execute_multimodal.return_value = "ok"

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_multimodal("[]", "[]", mode="edit")

        call_args = mock_backend.execute_multimodal.call_args
        assert call_args[0][2] == Mode.EDIT


# ── Interactive /chat-image ────────────────────────────────────────────────


class TestInteractiveChatImage:
    def test_chat_image_command(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"fake-jpeg-data")

        backend = MagicMock()
        backend.execute_multimodal.return_value = "I see a test image"

        _handle_slash(
            f"/chat-image {img_file} Describe this",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        output = capsys.readouterr().out
        assert "I see a test image" in output
        backend.execute_multimodal.assert_called_once()

    def test_chat_image_appends_messages(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        img_file = tmp_path / "photo.png"
        img_file.write_bytes(b"png-data")

        backend = MagicMock()
        backend.execute_multimodal.return_value = "A photo"
        messages = []

        _handle_slash(
            f"/chat-image {img_file} What is this?",
            messages, backend, {}, Mode.THINK, Path("/tmp"),
        )

        assert len(messages) == 2
        assert "[Image: photo.png]" in messages[0]["content"]
        assert messages[1]["content"] == "A photo"

    def test_chat_image_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/chat-image", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_chat_image_missing_prompt(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        img_file = tmp_path / "img.png"
        img_file.write_bytes(b"data")

        backend = MagicMock()
        # Only path, no prompt → needs 2 parts
        _handle_slash(f"/chat-image {img_file}", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_chat_image_file_not_found(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash(
            "/chat-image /nonexistent/image.png Describe",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_chat_image_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/chat-image img.png test", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_chat_image_error(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        img_file = tmp_path / "img.jpg"
        img_file.write_bytes(b"data")

        backend = MagicMock()
        backend.execute_multimodal.side_effect = RuntimeError("vision failed")

        _handle_slash(
            f"/chat-image {img_file} Describe",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )
        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_chat_image_includes_history(self, capsys, tmp_path):
        from aicp.cli.interactive import _handle_slash

        img_file = tmp_path / "img.jpg"
        img_file.write_bytes(b"data")

        backend = MagicMock()
        backend.execute_multimodal.return_value = "response"

        existing_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        _handle_slash(
            f"/chat-image {img_file} What is this?",
            existing_messages, backend, {}, Mode.THINK, Path("/tmp"),
        )

        # The call should include prior messages + new image message
        call_args = backend.execute_multimodal.call_args
        msgs_sent = call_args[0][0]
        assert len(msgs_sent) == 3  # 2 history + 1 new
