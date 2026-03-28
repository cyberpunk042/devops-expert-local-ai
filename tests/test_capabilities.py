"""Tests for --capabilities CLI command (M75)."""

from io import StringIO
from unittest.mock import patch

from rich.console import Console


def _make_console():
    buf = StringIO()
    return Console(file=buf, force_terminal=False, no_color=True), buf


class TestCapabilitiesCLIArg:
    """Verify --capabilities is wired as a CLI argument."""

    def test_arg_exists(self):
        from aicp.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["--capabilities"])
        assert args.capabilities is True

    def test_arg_default_false(self):
        from aicp.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args([])
        assert getattr(args, "capabilities", False) is False


class TestCapabilitiesOutput:
    """Verify _run_capabilities produces expected output sections."""

    def _run(self):
        test_console, buf = _make_console()
        with patch("aicp.cli.main.console", test_console):
            from aicp.cli.main import _run_capabilities
            rc = _run_capabilities()
        return rc, buf.getvalue()

    def test_returns_zero(self):
        rc, _ = self._run()
        assert rc == 0

    def test_shows_title(self):
        _, output = self._run()
        assert "Capabilities Report" in output

    def test_lists_endpoints(self):
        _, output = self._run()
        assert "/v1/chat/completions" in output
        assert "/v1/completions" in output
        assert "/v1/embeddings" in output
        assert "/v1/audio/transcriptions" in output
        assert "/v1/audio/speech" in output
        assert "/v1/audio/vad" in output
        assert "/v1/detection" in output
        assert "/v1/sound-generation" in output
        assert "/healthz" in output
        assert "/readyz" in output

    def test_endpoint_count(self):
        _, output = self._run()
        assert "30" in output  # 30 endpoints integrated

    def test_lists_mcp_tools(self):
        _, output = self._run()
        assert "MCP Tools" in output
        assert "aicp_chat" in output
        assert "aicp_vad" in output
        assert "aicp_detect" in output

    def test_lists_slash_commands(self):
        _, output = self._run()
        assert "Slash Commands" in output
        assert "/vad" in output
        assert "/detect" in output
        assert "/health" in output

    def test_lists_execution_modes(self):
        _, output = self._run()
        assert "Execution Modes" in output
        assert "think" in output
        assert "edit" in output
        assert "act" in output

    def test_lists_mode_sampling(self):
        _, output = self._run()
        assert "Mode Sampling" in output
        assert "temperature" in output

    def test_lists_llm_tools(self):
        _, output = self._run()
        assert "LLM-Callable Tools" in output

    def test_lists_configured_models(self):
        _, output = self._run()
        assert "Configured Models" in output
        assert "model" in output
        assert "embedding_model" in output


class TestSelfTestVadDetectProbes:
    """Verify VAD and detection probes are in --self-test."""

    def _run(self, mock_responses):
        import httpx

        test_console, buf = _make_console()

        def _mock_request(url, **kw):
            from unittest.mock import MagicMock
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
            resp.status_code = 404
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "not found", request=MagicMock(), response=resp,
                )
            )
            return resp

        with patch.dict("os.environ", {"LOCALAI_BASE_URL": "http://localhost:8090"}):
            with patch("aicp.cli.main.console", test_console):
                with patch("httpx.get", side_effect=_mock_request):
                    with patch("httpx.post", side_effect=_mock_request):
                        from aicp.cli.main import _run_self_test
                        rc = _run_self_test()

        return rc, buf.getvalue()

    def _base_responses(self):
        return {
            "/healthz": {"json": {}},
            "/readyz": {"json": {}},
            "/v1/models": {"json": {"data": [{"id": "hermes"}]}},
            "/v1/chat/completions": {"json": {"choices": [{"message": {"content": "hi"}}]}},
            "/v1/completions": {"json": {"choices": [{"text": "ok"}]}},
            "/v1/embeddings": {"json": {"data": [{"embedding": [0.1] * 768}]}},
            "/v1/tokenize": {"json": {"tokens": [1, 2, 3]}},
            "/v1/edits": {"json": {"choices": [{"text": "done"}]}},
            "/models/available": {"json": [{"name": "m"}]},
            "/backend/monitor": {"json": {"state": 2}},
            "/stores/set": {"json": {}},
            "/stores/delete": {"json": {}},
            "/stores/get": {"json": {}},
            "/api/p2p/stats": {"status": 404},
            "/v1/reranking": {"status": 404},
            "/api/backends": {"json": ["llama-cpp"]},
            "/v1/sound-generation": {"json": {}},
            "/v1/audio/vad": {"json": {}},
            "/v1/detection": {"json": {}},
        }

    def test_vad_probe_pass(self):
        responses = self._base_responses()
        rc, output = self._run(responses)
        assert "Voice activity detection" in output
        assert rc == 0

    def test_detection_probe_pass(self):
        responses = self._base_responses()
        rc, output = self._run(responses)
        assert "Object detection" in output
        assert rc == 0

    def test_vad_probe_skip_on_404(self):
        responses = self._base_responses()
        responses["/v1/audio/vad"] = {"status": 404}
        rc, output = self._run(responses)
        assert "Voice activity detection" in output
        # Should be SKIP not FAIL
        lines = output.split("\n")
        vad_line = [l for l in lines if "Voice activity detection" in l][0]
        assert "SKIP" in vad_line

    def test_detection_probe_skip_on_404(self):
        responses = self._base_responses()
        responses["/v1/detection"] = {"status": 404}
        rc, output = self._run(responses)
        lines = output.split("\n")
        det_line = [l for l in lines if "Object detection" in l][0]
        assert "SKIP" in det_line
