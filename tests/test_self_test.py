"""Tests for --self-test CLI command (M70)."""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console


def _make_console():
    """Return a Rich Console writing to a capturable StringIO."""
    buf = StringIO()
    return Console(file=buf, force_terminal=False, no_color=True), buf


class TestSelfTestProbes:
    """Unit-test the _run_self_test function by mocking httpx calls."""

    def _run(self, mock_responses: dict, *, env_url: str = "http://localhost:8090"):
        """Run _run_self_test with mocked httpx and capture output."""
        import httpx

        test_console, buf = _make_console()

        def _mock_request(url, **kw):
            resp = MagicMock()
            for pattern, cfg in mock_responses.items():
                if pattern in url:
                    resp.status_code = cfg.get("status", 200)
                    resp.json.return_value = cfg.get("json", {})
                    resp.raise_for_status = MagicMock()
                    if cfg.get("status", 200) >= 400:
                        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                            "error", request=MagicMock(), response=resp,
                        )
                    return resp
            # Default: 404
            resp.status_code = 404
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "not found", request=MagicMock(), response=resp,
                )
            )
            return resp

        with patch.dict("os.environ", {"LOCALAI_BASE_URL": env_url}):
            with patch("aicp.cli.main.console", test_console):
                with patch("httpx.get", side_effect=_mock_request):
                    with patch("httpx.post", side_effect=_mock_request):
                        from aicp.cli.main import _run_self_test
                        rc = _run_self_test()

        return rc, buf.getvalue()

    def test_all_pass(self):
        """When all endpoints respond correctly, self-test returns 0."""
        responses = {
            "/healthz": {"json": {}},
            "/readyz": {"json": {}},
            "/v1/models": {"json": {"data": [{"id": "hermes"}]}},
            "/v1/chat/completions": {"json": {"choices": [{"message": {"content": "hi"}}]}},
            "/v1/completions": {"json": {"choices": [{"text": "hello"}]}},
            "/v1/embeddings": {"json": {"data": [{"embedding": [0.1] * 768}]}},
            "/v1/tokenize": {"json": {"tokens": [1, 2, 3]}},
            "/v1/edits": {"json": {"choices": [{"text": "fixed"}]}},
            "/models/available": {"json": [{"name": "model1"}]},
            "/backend/monitor": {"json": {"state": 2}},
            "/stores/set": {"json": {}},
            "/stores/delete": {"json": {}},
            "/stores/get": {"json": {}},
            "/api/p2p/stats": {"status": 404},
            "/v1/reranking": {"status": 404},
            "/api/backends": {"json": ["llama-cpp"]},
            "/v1/sound-generation": {"json": {}},
        }
        rc, output = self._run(responses)
        assert "PASS" in output
        assert rc == 0

    def test_api_unreachable_fails(self):
        """When LocalAI is down, self-test returns 1."""
        import httpx as _httpx

        test_console, buf = _make_console()

        def _raise(*a, **kw):
            raise _httpx.ConnectError("refused")

        with patch.dict("os.environ", {"LOCALAI_BASE_URL": "http://localhost:8090"}):
            with patch("aicp.cli.main.console", test_console):
                with patch("httpx.get", side_effect=_raise):
                    with patch("httpx.post", side_effect=_raise):
                        from aicp.cli.main import _run_self_test
                        rc = _run_self_test()

        output = buf.getvalue()
        assert "FAIL" in output
        assert rc == 1

    def test_partial_failure(self):
        """Some probes fail, some pass — returns 1."""
        responses = {
            "/v1/models": {"json": {"data": [{"id": "hermes"}]}},
            "/v1/chat/completions": {"status": 500},
            "/v1/completions": {"status": 500},
            "/v1/embeddings": {"status": 500},
            "/v1/tokenize": {"json": {"tokens": [1]}},
            "/v1/edits": {"status": 500},
            "/models/available": {"json": []},
            "/backend/monitor": {"status": 404},
            "/stores/set": {"status": 404},
            "/api/p2p/stats": {"status": 404},
            "/v1/reranking": {"status": 404},
        }
        rc, output = self._run(responses)
        assert "FAIL" in output
        assert "PASS" in output
        assert rc == 1

    def test_skipped_probes(self):
        """Optional features (P2P, reranking) return SKIP not FAIL."""
        responses = {
            "/healthz": {"json": {}},
            "/readyz": {"json": {}},
            "/v1/models": {"json": {"data": [{"id": "hermes"}]}},
            "/v1/chat/completions": {"json": {"choices": [{"message": {"content": "hi"}}]}},
            "/v1/completions": {"json": {"choices": [{"text": "ok"}]}},
            "/v1/embeddings": {"json": {"data": [{"embedding": [0.1] * 100}]}},
            "/v1/tokenize": {"json": {"tokens": [1, 2]}},
            "/v1/edits": {"json": {"choices": [{"text": "done"}]}},
            "/models/available": {"json": [{"name": "m1"}]},
            "/backend/monitor": {"status": 404},
            "/stores/set": {"status": 404},
            "/stores/delete": {"status": 404},
            "/stores/get": {"status": 404},
            "/api/p2p/stats": {"status": 404},
            "/v1/reranking": {"status": 404},
            "/api/backends": {"status": 404},
            "/v1/sound-generation": {"status": 404},
        }
        rc, output = self._run(responses)
        assert "SKIP" in output
        assert rc == 0

    def test_return_code_zero_when_no_failures(self):
        """Return code 0 even with skips as long as no failures."""
        responses = {
            "/healthz": {"json": {}},
            "/readyz": {"json": {}},
            "/v1/models": {"json": {"data": [{"id": "hermes"}]}},
            "/v1/chat/completions": {"json": {"choices": [{"message": {"content": "ok"}}]}},
            "/v1/completions": {"json": {"choices": [{"text": "ok"}]}},
            "/v1/embeddings": {"json": {"data": [{"embedding": [0.1] * 768}]}},
            "/v1/tokenize": {"json": {"tokens": [1, 2, 3]}},
            "/v1/edits": {"json": {"choices": [{"text": "ok"}]}},
            "/models/available": {"json": [{"name": "m"}]},
            "/backend/monitor": {"json": {"state": 2}},
            "/stores/set": {"json": {}},
            "/stores/delete": {"json": {}},
            "/stores/get": {"json": {}},
            "/api/p2p/stats": {"json": {"online_workers": 1}},
            "/v1/reranking": {"json": {"results": []}},
            "/api/backends": {"json": ["llama-cpp"]},
            "/v1/sound-generation": {"json": {}},
        }
        rc, output = self._run(responses)
        assert rc == 0


class TestSelfTestCLIArg:
    """Verify --self-test is wired as a CLI argument."""

    def test_arg_exists(self):
        from aicp.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["--self-test"])
        assert args.self_test is True

    def test_arg_default_false(self):
        from aicp.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args([])
        assert getattr(args, "self_test", False) is False


class TestConfigCompleteness:
    """Verify config/default.yaml has all expected keys."""

    def test_all_model_keys_present(self):
        from aicp.config.loader import load_config
        cfg = load_config()
        local_cfg = cfg.get("backends", {}).get("local", {})
        required = [
            "base_url", "model", "embedding_model", "code_model",
            "vision_model", "whisper_model", "tts_model", "image_model",
            "reranker_model", "sound_model",
        ]
        for key in required:
            assert key in local_cfg, f"Missing config key: {key}"

    def test_stores_section_exists(self):
        from aicp.config.loader import load_config
        cfg = load_config()
        assert "stores" in cfg, "Missing 'stores' section in config"
        assert "default_store" in cfg["stores"]

    def test_advanced_sampling_documented(self):
        """Advanced sampling options should be commented in the YAML."""
        from pathlib import Path
        text = Path("config/default.yaml").read_text()
        for param in ["mirostat", "mirostat_tau", "mirostat_eta",
                       "typical_p", "frequency_penalty", "presence_penalty"]:
            assert param in text, f"Missing documented param: {param}"
