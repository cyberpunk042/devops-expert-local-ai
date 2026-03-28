"""Tests for streaming completions, batch ops, and mode-aware sampling (M72)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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


# ── Streaming Completions ────────────────────────────────────────────────────

class TestCompleteStream:
    def test_yields_chunks(self):
        backend = _make_backend()

        class FakeStream:
            status_code = 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def iter_lines(self):
                yield 'data: {"choices": [{"text": "Hello"}]}'
                yield 'data: {"choices": [{"text": " world"}]}'
                yield "data: [DONE]"

        with patch("httpx.stream", return_value=FakeStream()):
            chunks = list(backend.complete_stream("Once upon"))

        assert chunks == ["Hello", " world"]

    def test_empty_chunks_skipped(self):
        backend = _make_backend()

        class FakeStream:
            status_code = 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def iter_lines(self):
                yield 'data: {"choices": [{"text": ""}]}'
                yield 'data: {"choices": [{"text": "ok"}]}'
                yield "data: [DONE]"

        with patch("httpx.stream", return_value=FakeStream()):
            chunks = list(backend.complete_stream("test"))

        assert chunks == ["ok"]

    def test_includes_sampling_params(self):
        backend = _make_backend(temperature=0.5)

        class FakeStream:
            status_code = 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def iter_lines(self):
                yield "data: [DONE]"

        with patch("httpx.stream", return_value=FakeStream()) as mock_stream:
            list(backend.complete_stream("test"))

        call_kwargs = mock_stream.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["stream"] is True
        assert payload["temperature"] == 0.5

    def test_stop_sequences(self):
        backend = _make_backend()

        class FakeStream:
            status_code = 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def iter_lines(self):
                yield "data: [DONE]"

        with patch("httpx.stream", return_value=FakeStream()) as mock_stream:
            list(backend.complete_stream("test", stop=["###"]))

        call_kwargs = mock_stream.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["stop"] == ["###"]

    def test_http_error(self):
        backend = _make_backend()

        class FakeStream:
            status_code = 500
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def read(self):
                return b"internal error"

        with patch("httpx.stream", return_value=FakeStream()):
            with pytest.raises(RuntimeError, match="500"):
                list(backend.complete_stream("test"))

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.stream", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                list(backend.complete_stream("test"))


# ── Batch Tokenization ──────────────────────────────────────────────────────

class TestTokenizeBatch:
    def test_returns_list(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        # Different token counts for each call
        responses = [
            {"tokens": [1, 2, 3]},
            {"tokens": [4, 5]},
        ]
        call_count = [0]

        def _mock_post(url, **kw):
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = responses[call_count[0]]
            call_count[0] += 1
            return r

        with patch("httpx.post", side_effect=_mock_post):
            results = backend.tokenize_batch(["Hello world", "Hi"])

        assert len(results) == 2
        assert results[0]["count"] == 3
        assert results[1]["count"] == 2

    def test_empty_list(self):
        backend = _make_backend()
        results = backend.tokenize_batch([])
        assert results == []

    def test_single_item(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"tokens": [1]}

        with patch("httpx.post", return_value=mock_resp):
            results = backend.tokenize_batch(["test"])

        assert len(results) == 1
        assert results[0]["count"] == 1


# ── Mode-Aware Sampling ─────────────────────────────────────────────────────

class TestModeAwareSampling:
    def test_think_mode_defaults(self):
        backend = _make_backend()
        params = backend.sampling_params_for_mode(Mode.THINK)
        assert params["temperature"] == 0.7

    def test_edit_mode_defaults(self):
        backend = _make_backend()
        params = backend.sampling_params_for_mode(Mode.EDIT)
        assert params["temperature"] == 0.4

    def test_act_mode_defaults(self):
        backend = _make_backend()
        params = backend.sampling_params_for_mode(Mode.ACT)
        assert params["temperature"] == 0.1

    def test_explicit_overrides_mode_default(self):
        """User-configured temperature takes precedence over mode default."""
        backend = _make_backend(temperature=0.9)
        params = backend.sampling_params_for_mode(Mode.THINK)
        assert params["temperature"] == 0.9  # not 0.7

    def test_other_params_preserved(self):
        backend = _make_backend(mirostat=2, top_p=0.95)
        params = backend.sampling_params_for_mode(Mode.THINK)
        assert params["mirostat"] == 2
        assert params["top_p"] == 0.95
        assert params["temperature"] == 0.7  # mode default since not explicit

    def test_no_mode_defaults_when_explicit(self):
        """When all sampling params are set explicitly, mode adds nothing."""
        backend = _make_backend(temperature=0.5, top_p=0.9)
        params = backend.sampling_params_for_mode(Mode.ACT)
        assert params["temperature"] == 0.5
        assert params["top_p"] == 0.9


# ── MCP Batch Tokenize Tool ─────────────────────────────────────────────────

class TestMcpBatchTokenize:
    def test_aicp_tokenize_batch(self):
        from aicp.mcp.server import aicp_tokenize_batch

        mock_backend = MagicMock()
        mock_backend.tokenize_batch.return_value = [
            {"tokens": [1, 2], "count": 2},
            {"tokens": [3], "count": 1},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_tokenize_batch("Hello world\nHi")

        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["count"] == 2

    def test_empty_lines_filtered(self):
        from aicp.mcp.server import aicp_tokenize_batch

        mock_backend = MagicMock()
        mock_backend.tokenize_batch.return_value = [{"tokens": [1], "count": 1}]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_tokenize_batch("Hello\n\n\n")

        mock_backend.tokenize_batch.assert_called_once_with(["Hello"])


# ── Interactive Streaming ────────────────────────────────────────────────────

class TestInteractiveStreaming:
    def test_complete_streams_in_repl(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.complete_stream.return_value = iter(["Hello", " world"])

        _handle_slash(
            "/complete Once upon a time",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        output = capsys.readouterr().out
        assert "Hello" in output
        assert "world" in output

    def test_complete_error_handled(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.complete_stream.side_effect = RuntimeError("timeout")

        _handle_slash(
            "/complete test",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        err = capsys.readouterr().err
        assert "error" in err.lower()
