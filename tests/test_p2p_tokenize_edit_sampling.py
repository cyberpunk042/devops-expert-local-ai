"""Tests for P2P, tokenize, edits, and advanced sampling (M69)."""

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


# ── Advanced Sampling ────────────────────────────────────────────────────────

class TestAdvancedSampling:
    def test_mirostat_in_params(self):
        backend = _make_backend(mirostat=2, mirostat_tau=3.0, mirostat_eta=0.2)
        params = backend._sampling_params()
        assert params["mirostat"] == 2
        assert params["mirostat_tau"] == 3.0
        assert params["mirostat_eta"] == 0.2

    def test_typical_p_in_params(self):
        backend = _make_backend(typical_p=0.9)
        params = backend._sampling_params()
        assert params["typical_p"] == 0.9

    def test_frequency_presence_penalty(self):
        backend = _make_backend(frequency_penalty=0.5, presence_penalty=0.3)
        params = backend._sampling_params()
        assert params["frequency_penalty"] == 0.5
        assert params["presence_penalty"] == 0.3

    def test_defaults_omit_none(self):
        backend = _make_backend()
        params = backend._sampling_params()
        assert "mirostat" not in params
        assert "mirostat_tau" not in params
        assert "typical_p" not in params
        assert "frequency_penalty" not in params

    def test_advanced_params_in_payload(self):
        backend = _make_backend(mirostat=1, frequency_penalty=0.8)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.execute("test", Mode.THINK, Path("/tmp"))

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["mirostat"] == 1
        assert payload["frequency_penalty"] == 0.8

    def test_config_wiring(self):
        """Advanced sampling params are wired through _build_backends."""
        from aicp.cli.main import _build_backends
        config = {
            "backends": {
                "local": {
                    "base_url": "http://localhost:8090",
                    "model": "hermes",
                    "mirostat": 2,
                    "mirostat_tau": 4.0,
                    "typical_p": 0.95,
                    "frequency_penalty": 0.3,
                    "presence_penalty": 0.1,
                },
                "claude": {},
            }
        }
        backends = _build_backends(config)
        local = backends["local"]
        assert local.mirostat == 2
        assert local.mirostat_tau == 4.0
        assert local.typical_p == 0.95
        assert local.frequency_penalty == 0.3


# ── P2P Cluster ──────────────────────────────────────────────────────────────

class TestP2P:
    def test_p2p_stats_returns_data(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "online_workers": 3,
            "total_workers": 5,
            "online_federated": 2,
        }

        with patch("httpx.get", return_value=mock_resp):
            result = backend.p2p_stats()

        assert result["enabled"] is True
        assert result["online_workers"] == 3

    def test_p2p_stats_not_enabled(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("httpx.get", return_value=mock_resp):
            result = backend.p2p_stats()

        assert result["enabled"] is False

    def test_p2p_stats_connection_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            result = backend.p2p_stats()

        assert result["enabled"] is False

    def test_p2p_workers_returns_list(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"name": "worker-1", "online": True},
            {"name": "worker-2", "online": False},
        ]

        with patch("httpx.get", return_value=mock_resp):
            result = backend.p2p_workers()

        assert len(result) == 2
        assert result[0]["name"] == "worker-1"

    def test_p2p_workers_empty(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            result = backend.p2p_workers()

        assert result == []


# ── Tokenization ─────────────────────────────────────────────────────────────

class TestTokenize:
    def test_returns_tokens_and_count(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tokens": [1, 2, 3, 4, 5],
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = backend.tokenize("Hello world")

        assert result["tokens"] == [1, 2, 3, 4, 5]
        assert result["count"] == 5
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["content"] == "Hello world"
        assert payload["model"] == "hermes"

    def test_custom_model(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"tokens": [1, 2]}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.tokenize("test", model="codellama")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["model"] == "codellama"

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.tokenize("test")

    def test_connect_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.tokenize("test")


# ── Text Edits ───────────────────────────────────────────────────────────────

class TestEdit:
    def test_returns_edited_text(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "They're going to the store."}],
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = backend.edit("Their going to the store", "fix grammar")

        assert result == "They're going to the store."
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["input"] == "Their going to the store"
        assert payload["instruction"] == "fix grammar"
        assert "/v1/edits" in str(mock_post.call_args)

    def test_custom_model(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "edited"}]}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.edit("text", "edit it", model="codellama")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["model"] == "codellama"

    def test_includes_sampling_params(self):
        backend = _make_backend(temperature=0.3)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"text": "edited"}]}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            backend.edit("text", "edit it")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["temperature"] == 0.3

    def test_http_error(self):
        backend = _make_backend()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                backend.edit("text", "fix")

    def test_connect_error(self):
        import httpx
        backend = _make_backend()

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                backend.edit("text", "fix")


# ── MCP Tools ────────────────────────────────────────────────────────────────

class TestMcpNewTools:
    def test_aicp_tokenize(self):
        from aicp.mcp.server import aicp_tokenize

        mock_backend = MagicMock()
        mock_backend.tokenize.return_value = {"tokens": [1, 2, 3], "count": 3}

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_tokenize("Hello world")

        parsed = json.loads(result)
        assert parsed["count"] == 3

    def test_aicp_edit(self):
        from aicp.mcp.server import aicp_edit

        mock_backend = MagicMock()
        mock_backend.edit.return_value = "Fixed text."

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_edit("Broken text", "fix grammar")

        mock_backend.edit.assert_called_once_with("Broken text", "fix grammar")
        assert result == "Fixed text."

    def test_aicp_p2p_status(self):
        from aicp.mcp.server import aicp_p2p_status

        mock_backend = MagicMock()
        mock_backend.p2p_stats.return_value = {"enabled": True, "online_workers": 2}
        mock_backend.p2p_workers.return_value = [{"name": "w1", "online": True}]

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_p2p_status()

        parsed = json.loads(result)
        assert parsed["stats"]["online_workers"] == 2
        assert len(parsed["workers"]) == 1


# ── Interactive Slash Commands ───────────────────────────────────────────────

class TestInteractiveNewCommands:
    def test_edit_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.edit.return_value = "Fixed."

        _handle_slash(
            "/edit fix grammar | Their going there",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        backend.edit.assert_called_once_with("Their going there", "fix grammar")
        assert "Fixed." in capsys.readouterr().out

    def test_edit_no_pipe(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/edit fix this text", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "Usage" in capsys.readouterr().err

    def test_edit_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.edit.side_effect = RuntimeError("fail")
        _handle_slash("/edit fix | text", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "error" in capsys.readouterr().err.lower()

    def test_tokenize_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tokenize.return_value = {"tokens": [1, 2, 3], "count": 3}

        _handle_slash(
            "/tokenize Hello world test",
            [], backend, {}, Mode.THINK, Path("/tmp"),
        )

        output = capsys.readouterr().out
        assert "3" in output

    def test_tokenize_shows_ids_for_short(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tokenize.return_value = {"tokens": [42, 99], "count": 2}

        _handle_slash("/tokenize hi", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "42" in output

    def test_tokenize_no_text(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        _handle_slash("/tokenize", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "Usage" in capsys.readouterr().err

    def test_tokenize_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.tokenize.side_effect = RuntimeError("broken")
        _handle_slash("/tokenize test", [], backend, {}, Mode.THINK, Path("/tmp"))
        assert "error" in capsys.readouterr().err.lower()
