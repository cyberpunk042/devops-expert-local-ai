"""Tests for batch inference & concurrent execution (M79)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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


# ── execute_batch ───────────────────────────────────────────────────────────


class TestExecuteBatch:
    def test_returns_ordered_results(self):
        backend = _make_backend()
        prompts = ["Say hello", "Say goodbye", "Say thanks"]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "response"}}],
            "usage": {},
        }

        with patch("httpx.post", return_value=mock_resp):
            results = backend.execute_batch(prompts, Mode.THINK, Path("/tmp"))

        assert len(results) == 3
        # Results should be in order
        assert results[0]["index"] == 0
        assert results[1]["index"] == 1
        assert results[2]["index"] == 2
        # All should have responses
        for r in results:
            assert r["response"] == "response"
            assert r["error"] is None
            assert r["duration_ms"] >= 0

    def test_preserves_prompts(self):
        backend = _make_backend()
        prompts = ["first", "second"]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }

        with patch("httpx.post", return_value=mock_resp):
            results = backend.execute_batch(prompts, Mode.THINK, Path("/tmp"))

        assert results[0]["prompt"] == "first"
        assert results[1]["prompt"] == "second"

    def test_handles_partial_failure(self):
        backend = _make_backend()
        prompts = ["good prompt", "bad prompt"]

        call_count = [0]

        def mock_post(url, json=None, **kw):
            call_count[0] += 1
            resp = MagicMock()
            # First call succeeds, second fails
            if "good" in (json or {}).get("messages", [{}])[-1].get("content", ""):
                resp.status_code = 200
                resp.json.return_value = {
                    "choices": [{"message": {"content": "success"}}],
                    "usage": {},
                }
            else:
                resp.status_code = 500
                resp.text = "internal error"
                resp.json.return_value = {"error": {"message": "fail"}}
            return resp

        with patch("httpx.post", side_effect=mock_post):
            results = backend.execute_batch(prompts, Mode.THINK, Path("/tmp"))

        assert len(results) == 2
        # One should succeed, one should fail
        good = results[0]
        bad = results[1]
        assert good["response"] is not None or bad["response"] is not None

    def test_max_workers_respected(self):
        """Verify max_workers parameter is passed to ThreadPoolExecutor."""
        backend = _make_backend()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }

        captured_workers = {}

        original_pool = __import__("concurrent.futures", fromlist=["ThreadPoolExecutor"]).ThreadPoolExecutor

        class MockPool(original_pool):
            def __init__(self, max_workers=None, **kwargs):
                captured_workers["max_workers"] = max_workers
                super().__init__(max_workers=max_workers, **kwargs)

        with patch("httpx.post", return_value=mock_resp):
            with patch("concurrent.futures.ThreadPoolExecutor", MockPool):
                backend.execute_batch(["a", "b"], Mode.THINK, Path("/tmp"), max_workers=2)

        assert captured_workers["max_workers"] == 2

    def test_stop_sequences_passed(self):
        backend = _make_backend()

        captured_payloads = []

        def capture_post(url, json=None, **kw):
            captured_payloads.append(json or {})
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {},
            }
            return resp

        with patch("httpx.post", side_effect=capture_post):
            backend.execute_batch(["test"], Mode.THINK, Path("/tmp"), stop=["###"])

        assert any(p.get("stop") == ["###"] for p in captured_payloads)

    def test_empty_prompts(self):
        backend = _make_backend()
        results = backend.execute_batch([], Mode.THINK, Path("/tmp"))
        assert results == []

    def test_single_prompt(self):
        backend = _make_backend()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "solo"}}],
            "usage": {},
        }

        with patch("httpx.post", return_value=mock_resp):
            results = backend.execute_batch(["one"], Mode.THINK, Path("/tmp"))

        assert len(results) == 1
        assert results[0]["response"] == "solo"


# ── embed_batch_concurrent ──────────────────────────────────────────────────


class TestEmbedBatchConcurrent:
    def test_returns_ordered_embeddings(self):
        backend = _make_backend()

        def mock_embed(text):
            # Return different embeddings based on text
            return [hash(text) % 100 / 100.0] * 10

        with patch.object(backend, "embed", side_effect=mock_embed):
            results = backend.embed_batch_concurrent(["a", "b", "c"])

        assert len(results) == 3
        # Each should be a list of floats
        for r in results:
            assert len(r) == 10
        # Order preserved
        assert results[0] != results[1]  # different texts = different embeddings

    def test_empty_texts(self):
        backend = _make_backend()
        results = backend.embed_batch_concurrent([])
        assert results == []

    def test_single_text(self):
        backend = _make_backend()

        with patch.object(backend, "embed", return_value=[0.1] * 5):
            results = backend.embed_batch_concurrent(["hello"])

        assert len(results) == 1
        assert results[0] == [0.1] * 5


# ── MCP: aicp_batch ────────────────────────────────────────────────────────


class TestMcpBatch:
    def test_returns_json_results(self):
        from aicp.mcp.server import aicp_batch

        mock_backend = MagicMock()
        mock_backend.execute_batch.return_value = [
            {"index": 0, "prompt": "hi", "response": "hello", "error": None, "duration_ms": 100},
            {"index": 1, "prompt": "bye", "response": "goodbye", "error": None, "duration_ms": 150},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_batch('["hi", "bye"]')

        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["response"] == "hello"
        assert parsed[1]["response"] == "goodbye"

    def test_mode_passed(self):
        from aicp.mcp.server import aicp_batch

        mock_backend = MagicMock()
        mock_backend.execute_batch.return_value = []

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_batch('["test"]', mode="act")

        call_args = mock_backend.execute_batch.call_args
        assert call_args[0][1] == Mode.ACT

    def test_max_workers_passed(self):
        from aicp.mcp.server import aicp_batch

        mock_backend = MagicMock()
        mock_backend.execute_batch.return_value = []

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_batch('["test"]', max_workers=2)

        call_args = mock_backend.execute_batch.call_args
        assert call_args[1]["max_workers"] == 2


# ── Interactive: /batch ─────────────────────────────────────────────────────


class TestInteractiveBatch:
    def test_batch_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_batch.return_value = [
            {"index": 0, "prompt": "hello", "response": "hi there", "error": None, "duration_ms": 50},
            {"index": 1, "prompt": "goodbye", "response": "see ya", "error": None, "duration_ms": 60},
        ]

        _handle_slash("/batch hello | goodbye", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "hi there" in output
        assert "see ya" in output

    def test_batch_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/batch", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_batch_single_prompt_rejected(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/batch just one prompt", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "at least 2" in err

    def test_batch_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/batch a | b", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_batch_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_batch.side_effect = RuntimeError("connection failed")

        _handle_slash("/batch a | b", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_batch_partial_error_display(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.execute_batch.return_value = [
            {"index": 0, "prompt": "good", "response": "ok", "error": None, "duration_ms": 50},
            {"index": 1, "prompt": "bad", "response": None, "error": "timeout", "duration_ms": 5000},
        ]

        _handle_slash("/batch good | bad", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "ok" in output
        assert "ERROR" in output
