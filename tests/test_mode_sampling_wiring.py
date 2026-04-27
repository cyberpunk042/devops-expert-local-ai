"""Tests verifying mode-aware sampling is wired into all execution paths (M73)."""

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


def _mock_chat_response(content="ok"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {},
    }
    return resp


def _extract_payload(mock_post):
    """Extract the JSON payload from the mock call."""
    return mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")


# ── execute() uses mode-aware sampling ──────────────────────────────────────

class TestExecuteModeAware:
    def test_think_mode_temperature(self):
        backend = _make_backend()  # no explicit temperature
        with patch("httpx.post", return_value=_mock_chat_response()) as mock_post:
            backend.execute("test", Mode.THINK, Path("/tmp"))

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.7

    def test_edit_mode_temperature(self):
        backend = _make_backend()
        with patch("httpx.post", return_value=_mock_chat_response()) as mock_post:
            backend.execute("test", Mode.EDIT, Path("/tmp"))

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.4

    def test_act_mode_temperature(self):
        backend = _make_backend()
        with patch("httpx.post", return_value=_mock_chat_response()) as mock_post:
            backend.execute("test", Mode.ACT, Path("/tmp"))

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.1

    def test_explicit_overrides_mode(self):
        backend = _make_backend(temperature=0.9)
        with patch("httpx.post", return_value=_mock_chat_response()) as mock_post:
            backend.execute("test", Mode.ACT, Path("/tmp"))

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.9  # not 0.1


# ── execute_stream() uses mode-aware sampling ───────────────────────────────

class TestExecuteStreamModeAware:
    def test_think_mode_in_stream(self):
        backend = _make_backend()

        class FakeStream:
            status_code = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def iter_lines(self):
                yield "data: [DONE]"

        with patch("httpx.stream", return_value=FakeStream()) as mock_stream:
            list(backend.execute_stream("test", Mode.THINK, Path("/tmp")))

        payload = mock_stream.call_args.kwargs.get("json") or mock_stream.call_args[1].get("json")
        assert payload["temperature"] == 0.7


# ── execute_json() uses mode-aware sampling ─────────────────────────────────

class TestExecuteJsonModeAware:
    def test_edit_mode_in_json(self):
        backend = _make_backend()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": '{"key": "value"}'}}]}

        with patch("httpx.post", return_value=resp) as mock_post:
            backend.execute_json("test", Mode.EDIT, Path("/tmp"))

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.4


# ── execute_grammar() uses mode-aware sampling ──────────────────────────────

class TestExecuteGrammarModeAware:
    def test_act_mode_in_grammar(self):
        backend = _make_backend()
        with patch("httpx.post", return_value=_mock_chat_response("yes")) as mock_post:
            backend.execute_grammar("test", 'root ::= ("yes" | "no")', Mode.ACT, Path("/tmp"))

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.1
        assert payload["grammar"] == 'root ::= ("yes" | "no")'


# ── execute_with_tools() uses mode-aware sampling ───────────────────────────

class TestExecuteWithToolsModeAware:
    def test_think_mode_in_tools(self):
        backend = _make_backend()
        with patch("httpx.post", return_value=_mock_chat_response("no tools needed")) as mock_post:
            backend.execute_with_tools("test", Mode.THINK, Path("/tmp"), tools=[])

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.7


# ── execute_with_native_tools() uses mode-aware sampling + grammar ──────────

class TestExecuteWithNativeToolsModeAware:
    def test_edit_mode_in_native_tools(self):
        backend = _make_backend()
        with patch("httpx.post", return_value=_mock_chat_response("done")) as mock_post:
            backend.execute_with_native_tools("test", Mode.EDIT, Path("/tmp"), tools=[])

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.4

    def test_grammar_param_in_native_tools(self):
        backend = _make_backend()
        with patch("httpx.post", return_value=_mock_chat_response("yes")) as mock_post:
            backend.execute_with_native_tools(
                "test", Mode.ACT, Path("/tmp"), tools=[],
                grammar='root ::= ("yes" | "no")',
            )

        payload = _extract_payload(mock_post)
        assert payload["grammar"] == 'root ::= ("yes" | "no")'
        assert payload["temperature"] == 0.1

    def test_no_grammar_key_when_none(self):
        backend = _make_backend()
        with patch("httpx.post", return_value=_mock_chat_response("ok")) as mock_post:
            backend.execute_with_native_tools("test", Mode.THINK, Path("/tmp"), tools=[])

        payload = _extract_payload(mock_post)
        assert "grammar" not in payload


# ── execute_vision() uses mode-aware sampling ───────────────────────────────

class TestExecuteVisionModeAware:
    def test_think_mode_in_vision(self):
        backend = _make_backend()
        with patch("httpx.post", return_value=_mock_chat_response("I see an image")) as mock_post:
            backend.execute_vision("describe this", "base64data", Mode.THINK, Path("/tmp"))

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.7


# ── Utility methods still use _sampling_params (no mode) ────────────────────

class TestUtilityMethodsUnchanged:
    """edit(), complete(), complete_stream() don't have mode — use _sampling_params."""

    def test_edit_uses_base_params(self):
        backend = _make_backend(temperature=0.3)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"text": "fixed"}]}

        with patch("httpx.post", return_value=resp) as mock_post:
            backend.edit("text", "fix")

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.3

    def test_complete_uses_base_params(self):
        backend = _make_backend(temperature=0.5)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"text": "hello"}], "usage": {}}

        with patch("httpx.post", return_value=resp) as mock_post:
            backend.complete("test")

        payload = _extract_payload(mock_post)
        assert payload["temperature"] == 0.5

    def test_no_mode_default_in_complete(self):
        """complete() should NOT get mode defaults — only explicit config."""
        backend = _make_backend()  # no explicit temperature
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"text": "ok"}], "usage": {}}

        with patch("httpx.post", return_value=resp) as mock_post:
            backend.complete("test")

        payload = _extract_payload(mock_post)
        assert "temperature" not in payload
