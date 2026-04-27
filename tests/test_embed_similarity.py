"""Tests for Embedding Dimensions & Similarity Utilities (M91)."""

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


def _embed_response(vec):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"embedding": vec}],
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }
    return mock_resp


# ── embed_dims() ─────────────────────────────────────────────────────────


class TestEmbedDims:
    def test_basic(self):
        backend = _make_backend()
        vec = [0.1] * 128

        with patch("httpx.post", return_value=_embed_response(vec)):
            result = backend.embed_dims("hello", 128)

        assert result == vec
        assert len(result) == 128

    def test_sends_dimensions_param(self):
        backend = _make_backend()
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _embed_response([0.1] * 256)

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_dims("hello", 256)

        assert captured["dimensions"] == 256

    def test_uses_embeddings_endpoint(self):
        backend = _make_backend()
        captured_url = {}

        def capture_post(url, **kw):
            captured_url["url"] = url
            return _embed_response([0.1] * 64)

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_dims("hello", 64)

        assert "/v1/embeddings" in captured_url["url"]

    def test_custom_model(self):
        backend = _make_backend(embedding_model="bge-base")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _embed_response([0.1] * 64)

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_dims("hello", 64, model="nomic-embed")

        assert captured["model"] == "nomic-embed"

    def test_default_embedding_model(self):
        backend = _make_backend(embedding_model="bge-base")
        captured = {}

        def capture_post(url, json=None, **kw):
            captured.update(json or {})
            return _embed_response([0.1] * 64)

        with patch("httpx.post", side_effect=capture_post):
            backend.embed_dims("hello", 64)

        assert captured["model"] == "bge-base"

    def test_tracks_usage(self):
        backend = _make_backend()

        with patch("httpx.post", return_value=_embed_response([0.1] * 128)):
            backend.embed_dims("hello", 128)

        assert backend.last_usage["embedding_dims"] is True
        assert backend.last_usage["dimensions"] == 128

    def test_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.embed_dims("hello", 128)

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="400"):
                backend.embed_dims("hello", 128)


# ── cosine_similarity() ──────────────────────────────────────────────────


class TestCosineSimilarity:
    def test_identical_vectors(self):
        score = LocalAIBackend.cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        assert score == pytest.approx(1.0)

    def test_opposite_vectors(self):
        score = LocalAIBackend.cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert score == pytest.approx(-1.0)

    def test_orthogonal_vectors(self):
        score = LocalAIBackend.cosine_similarity([1.0, 0.0], [0.0, 1.0])
        assert score == pytest.approx(0.0)

    def test_similar_vectors(self):
        score = LocalAIBackend.cosine_similarity([1.0, 1.0], [1.0, 0.8])
        assert 0.9 < score < 1.0

    def test_zero_vector(self):
        score = LocalAIBackend.cosine_similarity([0.0, 0.0], [1.0, 1.0])
        assert score == 0.0

    def test_dimension_mismatch(self):
        with pytest.raises(ValueError, match="dimensions must match"):
            LocalAIBackend.cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_single_dimension(self):
        score = LocalAIBackend.cosine_similarity([5.0], [3.0])
        assert score == pytest.approx(1.0)

    def test_negative_values(self):
        score = LocalAIBackend.cosine_similarity([-1.0, -1.0], [-1.0, -1.0])
        assert score == pytest.approx(1.0)


# ── nearest_neighbors() ──────────────────────────────────────────────────


class TestNearestNeighbors:
    def _mock_embed(self, text):
        """Deterministic fake embeddings based on text."""
        h = hash(text) % 1000
        return [h / 1000.0, (h + 100) / 1000.0, (h + 200) / 1000.0]

    def _mock_embed_batch(self, texts):
        return [self._mock_embed(t) for t in texts]

    def test_basic_ranking(self):
        backend = _make_backend()
        docs = ["cat", "dog", "fish"]

        with patch.object(backend, "embed", self._mock_embed):
            with patch.object(backend, "embed_batch", self._mock_embed_batch):
                results = backend.nearest_neighbors("cat", docs)

        assert len(results) == 3
        # First result should be "cat" itself (highest similarity)
        assert results[0]["text"] == "cat"
        assert results[0]["score"] == pytest.approx(1.0, abs=0.01)
        assert results[0]["index"] == 0

    def test_top_k(self):
        backend = _make_backend()
        docs = ["a", "b", "c", "d", "e"]

        with patch.object(backend, "embed", self._mock_embed):
            with patch.object(backend, "embed_batch", self._mock_embed_batch):
                results = backend.nearest_neighbors("a", docs, top_k=2)

        assert len(results) == 2

    def test_empty_docs(self):
        backend = _make_backend()

        with patch.object(backend, "embed", self._mock_embed):
            results = backend.nearest_neighbors("query", [])

        assert results == []

    def test_result_structure(self):
        backend = _make_backend()
        docs = ["hello"]

        with patch.object(backend, "embed", self._mock_embed):
            with patch.object(backend, "embed_batch", self._mock_embed_batch):
                results = backend.nearest_neighbors("hello", docs)

        assert len(results) == 1
        r = results[0]
        assert "index" in r
        assert "text" in r
        assert "score" in r
        assert isinstance(r["score"], float)

    def test_sorted_descending(self):
        backend = _make_backend()
        docs = ["x", "y", "z"]

        with patch.object(backend, "embed", self._mock_embed):
            with patch.object(backend, "embed_batch", self._mock_embed_batch):
                results = backend.nearest_neighbors("x", docs)

        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_score_rounded(self):
        backend = _make_backend()
        docs = ["hello"]

        with patch.object(backend, "embed", lambda self_text: [0.123456789, 0.9, 0.5]):
            with patch.object(backend, "embed_batch", lambda self_texts: [[0.2, 0.8, 0.6]]):
                results = backend.nearest_neighbors("q", docs)

        score_str = str(results[0]["score"])
        # Should be rounded to 4 decimal places
        decimal_part = score_str.split(".")[-1] if "." in score_str else ""
        assert len(decimal_part) <= 4


# ── MCP: aicp_embed_dims ─────────────────────────────────────────────────


class TestMcpEmbedDims:
    def test_returns_json(self):
        from aicp.mcp.server import aicp_embed_dims

        mock_backend = MagicMock()
        mock_backend.embed_dims.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_embed_dims("hello", 128)

        parsed = json.loads(result)
        assert parsed["requested_dimensions"] == 128
        assert parsed["actual_dimensions"] == 5

    def test_passes_model(self):
        from aicp.mcp.server import aicp_embed_dims

        mock_backend = MagicMock()
        mock_backend.embed_dims.return_value = [0.1] * 10

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_embed_dims("hello", 64, model="nomic")

        mock_backend.embed_dims.assert_called_once_with("hello", 64, model="nomic")

    def test_empty_model_passes_none(self):
        from aicp.mcp.server import aicp_embed_dims

        mock_backend = MagicMock()
        mock_backend.embed_dims.return_value = [0.1] * 10

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_embed_dims("hello", 64, model="")

        mock_backend.embed_dims.assert_called_once_with("hello", 64, model=None)

    def test_truncates_preview(self):
        from aicp.mcp.server import aicp_embed_dims

        mock_backend = MagicMock()
        mock_backend.embed_dims.return_value = [float(i) for i in range(20)]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_embed_dims("hello", 20)

        parsed = json.loads(result)
        assert len(parsed["embedding"]) == 10  # only first 10


# ── MCP: aicp_similarity ─────────────────────────────────────────────────


class TestMcpSimilarity:
    def test_returns_score(self):
        from aicp.mcp.server import aicp_similarity

        mock_backend = MagicMock()
        mock_backend.embed.side_effect = [[1.0, 0.0], [1.0, 0.0]]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_similarity("cat", "cat")

        parsed = json.loads(result)
        assert parsed["similarity"] == pytest.approx(1.0)

    def test_calls_embed_twice(self):
        from aicp.mcp.server import aicp_similarity

        mock_backend = MagicMock()
        mock_backend.embed.side_effect = [[1.0, 0.0], [0.0, 1.0]]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_similarity("a", "b")

        assert mock_backend.embed.call_count == 2


# ── MCP: aicp_nearest_neighbors ──────────────────────────────────────────


class TestMcpNearestNeighbors:
    def test_returns_json_array(self):
        from aicp.mcp.server import aicp_nearest_neighbors

        mock_backend = MagicMock()
        mock_backend.nearest_neighbors.return_value = [
            {"index": 0, "text": "cat", "score": 0.95},
            {"index": 1, "text": "dog", "score": 0.80},
        ]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_nearest_neighbors("cat", '["cat", "dog"]', top_k=2)

        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["score"] == 0.95

    def test_passes_top_k(self):
        from aicp.mcp.server import aicp_nearest_neighbors

        mock_backend = MagicMock()
        mock_backend.nearest_neighbors.return_value = []

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_nearest_neighbors("q", '["a"]', top_k=3)

        call_kwargs = mock_backend.nearest_neighbors.call_args
        assert call_kwargs.kwargs["top_k"] == 3

    def test_parses_documents_json(self):
        from aicp.mcp.server import aicp_nearest_neighbors

        mock_backend = MagicMock()
        mock_backend.nearest_neighbors.return_value = []

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            aicp_nearest_neighbors("q", '["hello", "world"]')

        call_args = mock_backend.nearest_neighbors.call_args
        assert call_args.args[1] == ["hello", "world"]


# ── Interactive /similarity ──────────────────────────────────────────────


class TestInteractiveSimilarity:
    def test_basic(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.embed.side_effect = [[1.0, 0.0], [1.0, 0.0]]
        backend.cosine_similarity = LocalAIBackend.cosine_similarity

        _handle_slash("/similarity cat | cat", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "1.0000" in output

    def test_no_pipe(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/similarity hello world", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/similarity", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_empty_text(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/similarity |", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "required" in err.lower() or "Usage" in err

    def test_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/similarity cat | dog", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.embed.side_effect = RuntimeError("connection failed")

        _handle_slash("/similarity cat | dog", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()


# ── Interactive /neighbors ───────────────────────────────────────────────


class TestInteractiveNeighbors:
    def test_basic(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.nearest_neighbors.return_value = [
            {"index": 0, "text": "cat", "score": 0.95},
            {"index": 1, "text": "dog", "score": 0.80},
        ]

        _handle_slash("/neighbors cat | cat | dog", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "cat" in output
        assert "0.95" in output

    def test_no_pipe(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/neighbors hello world", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/neighbors", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/neighbors cat | dog", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "backend" in err.lower()

    def test_error_handling(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.nearest_neighbors.side_effect = RuntimeError("embed failed")

        _handle_slash("/neighbors cat | dog", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_query_only_no_docs(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/neighbors query |", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Need" in err or "Usage" in err or "error" in err.lower()
