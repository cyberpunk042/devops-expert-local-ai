"""Tests for the K2.6 local backend (E011-m003).

Verifies:
- K26LocalBackend construction + defaults
- is_available / status_detail probe behavior (mocked httpx)
- execute() request shape + response parsing (mocked httpx)
- _build_backends registration behavior (enabled flag gating)

Brain authoritative spec: ~/devops-solutions-research-wiki/wiki/backlog/modules/
e011-m003-k2-6-local-backend-adapter.md
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from aicp.backends.k2_6_local import DEFAULT_BASE_URL, DEFAULT_MODEL, K26LocalBackend
from aicp.core.modes import Mode

# ---------------------------------------------------------------------------
# Construction / defaults
# ---------------------------------------------------------------------------


def test_k2_6_local_defaults():
    b = K26LocalBackend()
    assert b.name == "k2_6_local"
    assert b.base_url == DEFAULT_BASE_URL
    assert b.model == DEFAULT_MODEL
    assert b.max_tokens == 8192
    assert b.timeout == 600.0


def test_k2_6_local_custom_params():
    b = K26LocalBackend(
        base_url="http://host:9000/",
        model="custom-model",
        max_tokens=16384,
        timeout=900,
        name="k2_6_local_custom",
    )
    assert b.base_url == "http://host:9000"  # trailing slash stripped
    assert b.model == "custom-model"
    assert b.max_tokens == 16384
    assert b.timeout == 900
    assert b.name == "k2_6_local_custom"


# ---------------------------------------------------------------------------
# Availability probe
# ---------------------------------------------------------------------------


def test_is_available_true_when_endpoint_responds():
    b = K26LocalBackend()
    resp = MagicMock(status_code=200)
    with patch("httpx.get", return_value=resp):
        assert b.is_available() is True


def test_is_available_false_on_connection_error():
    b = K26LocalBackend()
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        assert b.is_available() is False


def test_is_available_false_on_timeout():
    b = K26LocalBackend()
    with patch("httpx.get", side_effect=httpx.TimeoutException("slow")):
        assert b.is_available() is False


def test_status_detail_returns_model_list_when_ok():
    b = K26LocalBackend()
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"data": [{"id": "kimi-k2.6-q2"}]}
    with patch("httpx.get", return_value=resp):
        status = b.status_detail()
    assert "OK" in status
    assert "kimi-k2.6-q2" in status


def test_status_detail_flags_server_down():
    b = K26LocalBackend()
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        status = b.status_detail()
    assert "UNAVAILABLE" in status
    assert "kt server" in status.lower() or "8091" in status


# ---------------------------------------------------------------------------
# execute() contract
# ---------------------------------------------------------------------------


def _mock_chat_response(content: str = "hello back", usage: dict | None = None) -> MagicMock:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "id": "chatcmpl-123",
        "model": "kimi-k2.6-q2",
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": usage or {"prompt_tokens": 12, "completion_tokens": 7},
    }
    return resp


def test_execute_sends_openai_compat_payload(tmp_path):
    b = K26LocalBackend(model="kimi-k2.6-q2")
    mock_post = MagicMock(return_value=_mock_chat_response("hi"))
    with patch("httpx.post", mock_post):
        result = b.execute("hello", Mode.THINK, tmp_path)
    assert result == "hi"
    assert mock_post.call_count == 1
    _, kwargs = mock_post.call_args
    payload = kwargs["json"]
    assert payload["model"] == "kimi-k2.6-q2"
    assert any(m["role"] == "user" and m["content"] == "hello" for m in payload["messages"])
    assert payload["max_tokens"] == 8192


def test_execute_records_usage_and_zero_cost(tmp_path):
    b = K26LocalBackend()
    with patch("httpx.post", return_value=_mock_chat_response("hi")):
        b.execute("p", Mode.THINK, tmp_path)
    assert b.last_usage["backend"] == "k2_6_local"
    assert b.last_usage["prompt_tokens"] == 12
    assert b.last_usage["completion_tokens"] == 7
    assert b.last_usage["estimated_cost_usd"] == 0.0


def test_execute_raises_on_connection_error(tmp_path):
    b = K26LocalBackend()
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        try:
            b.execute("p", Mode.THINK, tmp_path)
        except RuntimeError as exc:
            assert "local endpoint" in str(exc).lower()
            assert "kt run" in str(exc).lower()
            return
    raise AssertionError("expected RuntimeError")


def test_execute_raises_on_timeout(tmp_path):
    b = K26LocalBackend(timeout=120)
    with patch("httpx.post", side_effect=httpx.TimeoutException("slow")):
        try:
            b.execute("p", Mode.THINK, tmp_path)
        except RuntimeError as exc:
            assert "timed out" in str(exc).lower()
            assert "120" in str(exc)
            return
    raise AssertionError("expected RuntimeError")


def test_execute_raises_on_server_error(tmp_path):
    b = K26LocalBackend()
    resp = MagicMock(status_code=500)
    resp.text = "internal server error"
    with patch("httpx.post", return_value=resp):
        try:
            b.execute("p", Mode.THINK, tmp_path)
        except RuntimeError as exc:
            assert "500" in str(exc)
            return
    raise AssertionError("expected RuntimeError")


def test_execute_extracts_reasoning_when_content_empty(tmp_path):
    b = K26LocalBackend()
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "model": "kimi-k2.6-q2",
        "choices": [{"message": {"reasoning": "thought-trace", "content": ""}}],
        "usage": {},
    }
    with patch("httpx.post", return_value=resp):
        result = b.execute("p", Mode.THINK, tmp_path)
    assert result == "thought-trace"


# ---------------------------------------------------------------------------
# _build_backends registration
# ---------------------------------------------------------------------------


def test_build_backends_skips_k2_6_local_when_disabled(monkeypatch):
    from aicp.cli.main import _build_backends
    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
            "k2_6_local": {
                "base_url": "http://localhost:8091",
                "model": "kimi-k2.6-q2",
                "enabled": False,  # ← gated off
            },
        }
    }
    backends = _build_backends(config)
    assert "k2_6_local" not in backends


def test_build_backends_registers_k2_6_local_when_enabled(monkeypatch):
    from aicp.cli.main import _build_backends
    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
            "k2_6_local": {
                "base_url": "http://localhost:8091",
                "model": "kimi-k2.6-q2",
                "max_tokens": 8192,
                "timeout": 600,
                "enabled": True,
            },
        }
    }
    backends = _build_backends(config)
    assert "k2_6_local" in backends
    b = backends["k2_6_local"]
    assert b.name == "k2_6_local"
    assert b.base_url == "http://localhost:8091"
    assert b.model == "kimi-k2.6-q2"
    assert b.max_tokens == 8192
    assert b.timeout == 600


def test_build_backends_skips_k2_6_local_when_config_missing():
    """No k2_6_local stanza in config → don't register; don't crash."""
    from aicp.cli.main import _build_backends
    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
        }
    }
    backends = _build_backends(config)
    assert "k2_6_local" not in backends
