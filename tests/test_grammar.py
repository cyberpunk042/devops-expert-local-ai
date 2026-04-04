"""Tests for GBNF grammar-constrained generation."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import json

import pytest

from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode


# ── Helpers ──────────────────────────────────────────────────────────────────

def _backend(**kwargs) -> LocalAIBackend:
    return LocalAIBackend(
        base_url="http://localhost:8090",
        model="hermes",
        **kwargs,
    )


BOOL_GRAMMAR = 'root ::= ("yes" | "no")'
RATING_GRAMMAR = 'root ::= ("1" | "2" | "3" | "4" | "5")'


# ── Backend tests ────────────────────────────────────────────────────────────

class TestExecuteGrammar:
    def test_grammar_sends_grammar_param(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "yes"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            "model": "hermes",
        }
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = backend.execute_grammar(
                "Is Python a language?", BOOL_GRAMMAR, Mode.THINK, Path.cwd(),
            )

        assert result == "yes"
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["grammar"] == BOOL_GRAMMAR
        assert payload["model"] == "hermes"

    def test_grammar_sets_last_usage(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "3"}}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 1},
            "model": "hermes",
        }
        with patch("httpx.post", return_value=mock_resp):
            backend.execute_grammar("Rate this", RATING_GRAMMAR, Mode.THINK, Path.cwd())

        assert backend.last_usage["grammar"] is True
        assert backend.last_usage["completion_tokens"] == 1

    def test_grammar_http_error(self):
        backend = _backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad grammar syntax"
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="LocalAI error"):
                backend.execute_grammar("test", "invalid", Mode.THINK, Path.cwd())

    def test_grammar_connect_error(self):
        backend = _backend()
        import httpx
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.execute_grammar("test", BOOL_GRAMMAR, Mode.THINK, Path.cwd())

    def test_grammar_timeout(self):
        backend = _backend()
        import httpx
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="timed out"):
                backend.execute_grammar("test", BOOL_GRAMMAR, Mode.THINK, Path.cwd())

    def test_grammar_uses_auto_route(self):
        backend = _backend(code_model="codellama", auto_route=True)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "yes"}}],
            "usage": {},
            "model": "codellama",
        }
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.execute_grammar(
                "Write code to fix this bug", BOOL_GRAMMAR, Mode.THINK, Path.cwd(),
            )

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        # Router returns qwen3-8b for code prompts (default code_model)
        assert payload["model"] == "qwen3-8b"

    def test_grammar_includes_sampling_params(self):
        backend = _backend(temperature=0.1, top_p=0.8)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "no"}}],
            "usage": {},
        }
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.execute_grammar("test", BOOL_GRAMMAR, Mode.THINK, Path.cwd())

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["temperature"] == 0.1
        assert payload["top_p"] == 0.8


# ── MCP tool tests ────────────────────────────────────────────────────────────

class TestAicpGrammar:
    def test_mcp_grammar_calls_backend(self):
        from aicp.mcp.server import aicp_grammar

        backend = MagicMock()
        backend.base_url = "http://localhost:8090"
        backend.execute_grammar.return_value = "yes"

        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=backend),
        ):
            result = aicp_grammar("Is Python good?", BOOL_GRAMMAR)

        assert result == "yes"
        backend.execute_grammar.assert_called_once()
        args = backend.execute_grammar.call_args
        assert args[0][1] == BOOL_GRAMMAR

    def test_mcp_grammar_mode_param(self):
        from aicp.mcp.server import aicp_grammar

        backend = MagicMock()
        backend.base_url = "http://localhost:8090"
        backend.execute_grammar.return_value = "3"

        with patch.multiple(
            "aicp.mcp.server",
            _get_backend=MagicMock(return_value=backend),
        ):
            aicp_grammar("Rate this", RATING_GRAMMAR, mode="edit")

        args = backend.execute_grammar.call_args
        assert args[0][2] == Mode.EDIT


# ── Grammar file loading tests ───────────────────────────────────────────────

class TestGrammarFile:
    def test_grammar_file_loading(self, tmp_path):
        grammar_file = tmp_path / "bool.gbnf"
        grammar_file.write_text(BOOL_GRAMMAR)
        content = grammar_file.read_text()
        assert content == BOOL_GRAMMAR
