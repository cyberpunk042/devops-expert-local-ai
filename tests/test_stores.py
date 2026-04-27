"""Tests for LocalAI Stores API integration (M66)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.core.stores import EmbeddingStore, LocalAIStore

# ── LocalAIStore low-level tests ─────────────────────────────────────────────

class TestLocalAIStore:
    def test_set_sends_correct_payload(self):
        store = LocalAIStore("http://localhost:8090", store_name="test")
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            store.set([[1.0, 2.0]], ["hello"])

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["store"] == "test"
        assert payload["keys"] == [[1.0, 2.0]]
        assert payload["values"] == ["hello"]
        assert "/stores/set" in str(call_kwargs)

    def test_set_validates_length_mismatch(self):
        store = LocalAIStore("http://localhost:8090")
        with pytest.raises(ValueError, match="same length"):
            store.set([[1.0]], ["a", "b"])

    def test_get_returns_values(self):
        store = LocalAIStore("http://localhost:8090", store_name="test")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "keys": [[1.0, 2.0]],
            "values": ["hello"],
        }

        with patch("httpx.post", return_value=mock_resp):
            result = store.get([[1.0, 2.0]])

        assert result["values"] == ["hello"]

    def test_delete_sends_keys(self):
        store = LocalAIStore("http://localhost:8090")
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            store.delete([[1.0, 2.0]])

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["keys"] == [[1.0, 2.0]]
        assert "/stores/delete" in str(mock_post.call_args)

    def test_find_returns_structured_results(self):
        store = LocalAIStore("http://localhost:8090", store_name="test")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "keys": [[1.0, 2.0], [3.0, 4.0]],
            "values": ["hello", "world"],
            "similarities": [0.98, 0.75],
        }

        with patch("httpx.post", return_value=mock_resp):
            results = store.find([1.0, 2.0], top_k=2)

        assert len(results) == 2
        assert results[0]["value"] == "hello"
        assert results[0]["similarity"] == 0.98
        assert results[1]["value"] == "world"

    def test_find_sends_singular_key(self):
        """find uses 'key' (singular) not 'keys' (plural)."""
        store = LocalAIStore("http://localhost:8090")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"keys": [], "values": [], "similarities": []}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            store.find([1.0, 2.0], top_k=3)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "key" in payload  # singular
        assert "keys" not in payload
        assert payload["topk"] == 3

    def test_set_http_error(self):
        store = LocalAIStore("http://localhost:8090")
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                store.set([[1.0]], ["test"])

    def test_find_http_error(self):
        store = LocalAIStore("http://localhost:8090")
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                store.find([1.0], top_k=1)

    def test_api_key_in_headers(self):
        store = LocalAIStore("http://localhost:8090", api_key="secret")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"keys": [], "values": [], "similarities": []}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            store.find([1.0], top_k=1)

        headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args[1].get("headers")
        assert headers["Authorization"] == "Bearer secret"


# ── EmbeddingStore high-level tests ──────────────────────────────────────────

class TestEmbeddingStore:
    def _make_store(self):
        backend = MagicMock()
        backend.embed.return_value = [1.0, 2.0, 3.0]
        backend.embed_batch.return_value = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        return EmbeddingStore(backend, "http://localhost:8090", store_name="test")

    def test_remember_embeds_and_stores(self):
        es = self._make_store()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.post", return_value=mock_resp):
            es.remember("Python is great")

        es.backend.embed.assert_called_once_with("Python is great")

    def test_remember_with_metadata(self):
        es = self._make_store()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            es.remember("Python is great", metadata="lang")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["values"] == ["lang: Python is great"]

    def test_remember_batch(self):
        es = self._make_store()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.post", return_value=mock_resp):
            es.remember_batch(["hello", "world"])

        es.backend.embed_batch.assert_called_once_with(["hello", "world"])

    def test_recall_returns_results(self):
        es = self._make_store()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "keys": [[1.0, 2.0, 3.0]],
            "values": ["Python is great"],
            "similarities": [0.95],
        }

        with patch("httpx.post", return_value=mock_resp):
            results = es.recall("programming languages")

        assert len(results) == 1
        assert results[0]["value"] == "Python is great"
        assert results[0]["similarity"] == 0.95
        # No 'key' field in high-level results
        assert "key" not in results[0]

    def test_forget_embeds_and_deletes(self):
        es = self._make_store()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.post", return_value=mock_resp):
            es.forget("Python is great")

        es.backend.embed.assert_called_with("Python is great")


# ── Backend store methods ────────────────────────────────────────────────────

class TestBackendStoreMethods:
    def _make_backend(self):
        from aicp.backends.localai import LocalAIBackend
        return LocalAIBackend(
            base_url="http://localhost:8090",
            model="hermes",
            max_tokens=256,
            api_key="",
        )

    def test_store_set_embeds_and_stores(self):
        backend = self._make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"embedding": [1.0, 2.0]}],
        }

        with patch("httpx.post", return_value=mock_resp):
            count = backend.store_set(["hello"], store_name="test")

        assert count == 1

    def test_store_find_returns_results(self):
        backend = self._make_backend()

        # First call: embed query, second call: store find
        embed_resp = MagicMock()
        embed_resp.status_code = 200
        embed_resp.json.return_value = {
            "data": [{"embedding": [1.0, 2.0]}],
        }

        find_resp = MagicMock()
        find_resp.status_code = 200
        find_resp.json.return_value = {
            "keys": [[1.0, 2.0]],
            "values": ["hello"],
            "similarities": [0.99],
        }

        with patch("httpx.post", side_effect=[embed_resp, find_resp]):
            results = backend.store_find("test query", store_name="test", top_k=3)

        assert len(results) == 1
        assert results[0]["value"] == "hello"
        assert results[0]["similarity"] == 0.99

    def test_store_delete_embeds_and_deletes(self):
        backend = self._make_backend()

        embed_resp = MagicMock()
        embed_resp.status_code = 200
        embed_resp.json.return_value = {
            "data": [{"embedding": [1.0, 2.0]}],
        }

        delete_resp = MagicMock()
        delete_resp.status_code = 200

        with patch("httpx.post", side_effect=[embed_resp, delete_resp]):
            backend.store_delete(["hello"], store_name="test")


# ── Tool implementations ─────────────────────────────────────────────────────

class TestStoreTools:
    def test_store_remember_tool(self):
        from aicp.core.tools import execute_tool
        mock_backend = MagicMock()
        mock_backend.store_set.return_value = 1

        result = execute_tool(
            "store_remember",
            json.dumps({"text": "Python is interpreted"}),
            Path("/tmp"),
            backend=mock_backend,
        )

        mock_backend.store_set.assert_called_once_with(["Python is interpreted"], store_name="memory")
        assert "Stored" in result

    def test_store_recall_tool(self):
        from aicp.core.tools import execute_tool
        mock_backend = MagicMock()
        mock_backend.store_find.return_value = [
            {"value": "Python is interpreted", "similarity": 0.95},
        ]

        result = execute_tool(
            "store_recall",
            json.dumps({"query": "programming", "top_k": 3}),
            Path("/tmp"),
            backend=mock_backend,
        )

        mock_backend.store_find.assert_called_once_with("programming", store_name="memory", top_k=3)
        parsed = json.loads(result)
        assert parsed[0]["value"] == "Python is interpreted"

    def test_store_remember_no_backend(self):
        from aicp.core.tools import execute_tool
        result = execute_tool("store_remember", '{"text": "test"}', Path("/tmp"))
        assert "Error" in result

    def test_store_recall_no_backend(self):
        from aicp.core.tools import execute_tool
        result = execute_tool("store_recall", '{"query": "test"}', Path("/tmp"))
        assert "Error" in result

    def test_store_tools_in_tool_sets(self):
        from aicp.core.tools import ALL_TOOLS, EDIT_TOOLS, THINK_TOOLS
        names = lambda tools: [t["function"]["name"] for t in tools]
        # recall is read-only → in think
        assert "store_recall" in names(THINK_TOOLS)
        # remember is write → in edit and act
        assert "store_remember" in names(EDIT_TOOLS)
        assert "store_remember" in names(ALL_TOOLS)
        # recall also in edit and act
        assert "store_recall" in names(EDIT_TOOLS)
        assert "store_recall" in names(ALL_TOOLS)


# ── MCP tools ────────────────────────────────────────────────────────────────

class TestMcpStore:
    def test_aicp_store_set(self):
        from aicp.mcp.server import aicp_store_set
        mock_backend = MagicMock()

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_store_set("remember this", store="notes")

        mock_backend.store_set.assert_called_once_with(["remember this"], store_name="notes")
        assert "Stored" in result

    def test_aicp_store_find(self):
        from aicp.mcp.server import aicp_store_find
        mock_backend = MagicMock()
        mock_backend.store_find.return_value = [
            {"value": "remembered thing", "similarity": 0.9},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_store_find("what did I remember?", top_k=3, store="notes")

        mock_backend.store_find.assert_called_once_with("what did I remember?", store_name="notes", top_k=3)
        parsed = json.loads(result)
        assert parsed[0]["value"] == "remembered thing"


# ── Interactive /store command ───────────────────────────────────────────────

class TestInteractiveStoreCommand:
    def test_store_set_command(self, capsys):
        from aicp.cli.interactive import _handle_slash
        from aicp.core.modes import Mode

        backend = MagicMock()
        result = _handle_slash(
            "/store set The sky is blue",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        assert result is None
        backend.store_set.assert_called_once_with(["The sky is blue"], store_name="memory")
        assert "stored" in capsys.readouterr().out.lower()

    def test_store_find_command(self, capsys):
        from aicp.cli.interactive import _handle_slash
        from aicp.core.modes import Mode

        backend = MagicMock()
        backend.store_find.return_value = [
            {"value": "The sky is blue", "similarity": 0.95},
        ]

        result = _handle_slash(
            "/store find sky color",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        assert result is None
        output = capsys.readouterr().out
        assert "sky is blue" in output.lower()
        assert "0.950" in output

    def test_store_find_no_results(self, capsys):
        from aicp.cli.interactive import _handle_slash
        from aicp.core.modes import Mode

        backend = MagicMock()
        backend.store_find.return_value = []

        _handle_slash(
            "/store find nothing",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        assert "no results" in capsys.readouterr().out.lower()

    def test_store_invalid_subcommand(self, capsys):
        from aicp.cli.interactive import _handle_slash
        from aicp.core.modes import Mode

        backend = MagicMock()
        _handle_slash("/store", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "Usage" in capsys.readouterr().err
