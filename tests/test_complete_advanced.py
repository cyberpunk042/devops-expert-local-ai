"""Tests for Completion Logprobs & N Completions (M90)."""

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


# ── Backend complete_logprobs() ───────────────────────────────────────────


class TestCompleteLogprobs:
    def _logprobs_response(self, text="world", tokens=None, token_logprobs=None):
        if tokens is None:
            tokens = ["wor", "ld"]
        if token_logprobs is None:
            token_logprobs = [-0.5, -0.8]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "text": text,
                "logprobs": {
                    "tokens": tokens,
                    "token_logprobs": token_logprobs,
                    "top_logprobs": [{t: lp} for t, lp in zip(tokens, token_logprobs)],
                },
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": len(tokens)},
        }
        return mock_resp

    def test_basic_logprobs(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=self._logprobs_response()):
            result = backend.complete_logprobs("Hello ")

        assert result["text"] == "world"
        assert result["tokens"] == ["wor", "ld"]
        assert result["token_logprobs"] == [-0.5, -0.8]
        assert result["avg_logprob"] == -0.65

    def test_sends_logprobs_param(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return self._logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.complete_logprobs("test", top_logprobs=10)

        assert captured["logprobs"] == 10

    def test_clamps_logprobs(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return self._logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.complete_logprobs("test", top_logprobs=50)

        assert captured["logprobs"] == 20

    def test_seed_passed(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return self._logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.complete_logprobs("test", seed=42)

        assert captured["seed"] == 42

    def test_uses_completions_endpoint(self):
        backend = _make_backend()
        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return self._logprobs_response()

        with patch("httpx.post", side_effect=capture_post):
            backend.complete_logprobs("test")

        assert "/v1/completions" in captured_url["url"]

    def test_tracks_usage(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=self._logprobs_response()):
            backend.complete_logprobs("test")

        assert backend.last_usage["completion_logprobs"] is True
        assert backend.last_usage["prompt_tokens"] == 5

    def test_empty_logprobs(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "hi", "logprobs": None}],
            "usage": {},
        }

        with patch("httpx.post", return_value=mock_resp):
            result = backend.complete_logprobs("test")

        assert result["text"] == "hi"
        assert result["tokens"] == []
        assert result["avg_logprob"] == 0.0

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.complete_logprobs("test")

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.complete_logprobs("test")


# ── Backend complete_n() ──────────────────────────────────────────────────


class TestCompleteN:
    def _n_response(self, texts):
        choices = [{"index": i, "text": t, "finish_reason": "stop"} for i, t in enumerate(texts)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": choices, "usage": {}}
        return mock_resp

    def test_basic_n(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return self._n_response(["one", "two", "three"])

        with patch("httpx.post", side_effect=capture_post):
            results = backend.complete_n("Hello", n=3)

        assert len(results) == 3
        assert results[0]["text"] == "one"
        assert captured["n"] == 3

    def test_clamps_n(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return self._n_response(["a"])

        with patch("httpx.post", side_effect=capture_post):
            backend.complete_n("test", n=50)

        assert captured["n"] == 10

    def test_seed_passed(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return self._n_response(["a"])

        with patch("httpx.post", side_effect=capture_post):
            backend.complete_n("test", seed=42)

        assert captured["seed"] == 42

    def test_uses_completions_endpoint(self):
        backend = _make_backend()
        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return self._n_response(["a"])

        with patch("httpx.post", side_effect=capture_post):
            backend.complete_n("test")

        assert "/v1/completions" in captured_url["url"]

    def test_empty_choices_raises(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [], "usage": {}}

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Unexpected"):
                backend.complete_n("test")

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.complete_n("test")


# ── MCP tools ─────────────────────────────────────────────────────────────


class TestMcpCompleteLogprobs:
    def test_returns_json(self):
        from aicp.mcp.server import aicp_complete_logprobs

        mock_backend = MagicMock()
        mock_backend.complete_logprobs.return_value = {
            "text": "world", "tokens": ["wor", "ld"],
            "token_logprobs": [-0.5, -0.8], "top_logprobs": [],
            "avg_logprob": -0.65,
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_complete_logprobs("Hello ")

        parsed = json.loads(result)
        assert parsed["text"] == "world"
        assert parsed["avg_logprob"] == -0.65

    def test_passes_params(self):
        from aicp.mcp.server import aicp_complete_logprobs

        mock_backend = MagicMock()
        mock_backend.complete_logprobs.return_value = {
            "text": "x", "tokens": [], "token_logprobs": [],
            "top_logprobs": [], "avg_logprob": 0,
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_complete_logprobs("test", max_tokens=100, top_logprobs=10, seed=42)

        call_kwargs = mock_backend.complete_logprobs.call_args
        assert call_kwargs.kwargs["max_tokens"] == 100
        assert call_kwargs.kwargs["top_logprobs"] == 10
        assert call_kwargs.kwargs["seed"] == 42


class TestMcpCompleteN:
    def test_returns_json_array(self):
        from aicp.mcp.server import aicp_complete_n

        mock_backend = MagicMock()
        mock_backend.complete_n.return_value = [
            {"index": 0, "text": "one", "finish_reason": "stop"},
            {"index": 1, "text": "two", "finish_reason": "stop"},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_complete_n("Hello", n=2)

        parsed = json.loads(result)
        assert len(parsed) == 2


# ── Interactive slash commands ─────────────────────────────────────────────


class TestInteractiveCompleteLp:
    def test_complete_lp_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.complete_logprobs.return_value = {
            "text": "world",
            "tokens": ["wor", "ld"],
            "token_logprobs": [-0.5, -0.8],
            "top_logprobs": [],
            "avg_logprob": -0.65,
        }

        _handle_slash("/complete-lp Hello ", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "world" in output
        assert "-0.65" in output

    def test_complete_lp_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/complete-lp", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_complete_lp_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/complete-lp test", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_complete_lp_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.complete_logprobs.side_effect = RuntimeError("failed")

        _handle_slash("/complete-lp test", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()


class TestInteractiveCompleteN:
    def test_complete_n_with_count(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.complete_n.return_value = [
            {"index": 0, "text": "one", "finish_reason": "stop"},
            {"index": 1, "text": "two", "finish_reason": "stop"},
        ]

        _handle_slash("/complete-n 2 Hello world", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "one" in output
        assert "two" in output
        backend.complete_n.assert_called_once_with("Hello world", n=2)

    def test_complete_n_default(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.complete_n.return_value = [
            {"index": 0, "text": "x", "finish_reason": "stop"},
        ]

        _handle_slash("/complete-n Hello world", [], backend, {}, Mode.THINK, Path("/tmp"))

        backend.complete_n.assert_called_once_with("Hello world", n=3)

    def test_complete_n_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/complete-n", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_complete_n_number_only(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/complete-n 5", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_complete_n_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/complete-n test", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()
