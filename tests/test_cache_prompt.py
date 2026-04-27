"""Tests for prompt caching feature."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode


def _backend(**kwargs) -> LocalAIBackend:
    return LocalAIBackend(
        base_url="http://localhost:8090",
        model="hermes",
        **kwargs,
    )


class TestCachePrompt:
    def test_cache_prompt_enabled_by_default(self):
        backend = _backend()
        assert backend.cache_prompt is True
        params = backend._sampling_params()
        assert params["cache_prompt"] is True

    def test_cache_prompt_disabled(self):
        backend = _backend(cache_prompt=False)
        assert backend.cache_prompt is False
        params = backend._sampling_params()
        assert "cache_prompt" not in params

    def test_cache_prompt_in_execute_payload(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hello"}}],
            "usage": {},
        }
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.execute("test", Mode.THINK, Path.cwd())

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["cache_prompt"] is True

    def test_cache_prompt_in_grammar_payload(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "yes"}}],
            "usage": {},
        }
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.execute_grammar("test", 'root ::= ("yes" | "no")', Mode.THINK, Path.cwd())

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["cache_prompt"] is True
        assert payload["grammar"] == 'root ::= ("yes" | "no")'

    def test_cache_prompt_in_vision_payload(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "a photo"}}],
            "usage": {},
        }
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.execute_vision("describe", "base64data", Mode.THINK, Path.cwd())

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["cache_prompt"] is True

    def test_cache_prompt_not_in_payload_when_disabled(self):
        backend = _backend(cache_prompt=False)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hello"}}],
            "usage": {},
        }
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.execute("test", Mode.THINK, Path.cwd())

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "cache_prompt" not in payload
