"""Tests for the Ollama Cloud backend adapter.

Mirrors test_k2_6_local_backend.py structure: construction/defaults, availability
probe, execute contract, registration gating.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from aicp.backends.ollama_cloud import DEFAULT_BASE_URL, DEFAULT_MODEL, OllamaCloudBackend
from aicp.core.modes import Mode


def test_defaults():
    b = OllamaCloudBackend(api_key="k")
    assert b.name == "ollama_cloud"
    assert b.base_url == DEFAULT_BASE_URL
    assert b.model == DEFAULT_MODEL
    assert b.max_tokens == 8192
    assert b.timeout == 300.0


def test_custom_params():
    b = OllamaCloudBackend(
        api_key="k",
        base_url="https://alt.ollama.example/v1/",
        model="qwen3.6",
        max_tokens=16384,
        timeout=600,
        name="oc_custom",
    )
    assert b.base_url == "https://alt.ollama.example/v1"
    assert b.model == "qwen3.6"
    assert b.max_tokens == 16384
    assert b.timeout == 600
    assert b.name == "oc_custom"


def test_is_available_false_without_key():
    b = OllamaCloudBackend(api_key="")
    assert b.is_available() is False


def test_is_available_true_when_endpoint_responds():
    b = OllamaCloudBackend(api_key="k")
    resp = MagicMock(status_code=200)
    with patch("httpx.get", return_value=resp):
        assert b.is_available() is True


def test_is_available_false_on_connection_error():
    b = OllamaCloudBackend(api_key="k")
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        assert b.is_available() is False


def test_status_detail_reports_no_key():
    b = OllamaCloudBackend(api_key="")
    status = b.status_detail()
    assert "UNAVAILABLE" in status
    assert "OLLAMA_API_KEY" in status


def test_status_detail_reports_model_count():
    b = OllamaCloudBackend(api_key="k")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"data": [{"id": "kimi-k2.6"}, {"id": "qwen3.6"}]}
    with patch("httpx.get", return_value=resp):
        status = b.status_detail()
    assert "OK" in status
    assert "2 models" in status


def test_status_detail_flags_invalid_key():
    b = OllamaCloudBackend(api_key="bad")
    resp = MagicMock(status_code=401)
    with patch("httpx.get", return_value=resp):
        status = b.status_detail()
    assert "UNAVAILABLE" in status
    assert "invalid" in status.lower()


def test_status_detail_flags_403():
    b = OllamaCloudBackend(api_key="k")
    resp = MagicMock(status_code=403)
    with patch("httpx.get", return_value=resp):
        status = b.status_detail()
    assert "UNAVAILABLE" in status
    assert "subscription" in status.lower()


def _mock_chat_response(content: str = "hello back", usage: dict | None = None) -> MagicMock:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "id": "chatcmpl-123",
        "model": "kimi-k2.6",
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": usage or {"prompt_tokens": 12, "completion_tokens": 7},
    }
    return resp


def test_execute_sends_openai_compat_payload(tmp_path):
    b = OllamaCloudBackend(api_key="k", model="kimi-k2.6")
    mock_post = MagicMock(return_value=_mock_chat_response("hi"))
    with patch("httpx.post", mock_post):
        result = b.execute("hello", Mode.THINK, tmp_path)
    assert result == "hi"
    _, kwargs = mock_post.call_args
    payload = kwargs["json"]
    assert payload["model"] == "kimi-k2.6"
    assert any(m["role"] == "user" and m["content"] == "hello" for m in payload["messages"])
    assert payload["max_tokens"] == 8192


def test_execute_sends_bearer_auth(tmp_path):
    b = OllamaCloudBackend(api_key="secret-token")
    mock_post = MagicMock(return_value=_mock_chat_response("hi"))
    with patch("httpx.post", mock_post):
        b.execute("hello", Mode.THINK, tmp_path)
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer secret-token"


def test_execute_raises_without_key(tmp_path):
    b = OllamaCloudBackend(api_key="")
    try:
        b.execute("p", Mode.THINK, tmp_path)
    except RuntimeError as exc:
        assert "API key" in str(exc)
        return
    raise AssertionError("expected RuntimeError")


def test_execute_records_usage_and_zero_cost(tmp_path):
    b = OllamaCloudBackend(api_key="k")
    with patch("httpx.post", return_value=_mock_chat_response("hi")):
        b.execute("p", Mode.THINK, tmp_path)
    assert b.last_usage["backend"] == "ollama_cloud"
    assert b.last_usage["prompt_tokens"] == 12
    assert b.last_usage["completion_tokens"] == 7
    assert b.last_usage["estimated_cost_usd"] == 0.0


def test_execute_raises_on_rate_limit(tmp_path):
    b = OllamaCloudBackend(api_key="k")
    resp = MagicMock(status_code=429)
    resp.text = "rate limit exceeded"
    with patch("httpx.post", return_value=resp):
        try:
            b.execute("p", Mode.THINK, tmp_path)
        except RuntimeError as exc:
            assert "cap" in str(exc).lower() or "rate" in str(exc).lower()
            return
    raise AssertionError("expected RuntimeError")


def test_execute_raises_on_invalid_key_401(tmp_path):
    b = OllamaCloudBackend(api_key="bad")
    resp = MagicMock(status_code=401)
    resp.text = "unauthorized"
    with patch("httpx.post", return_value=resp):
        try:
            b.execute("p", Mode.THINK, tmp_path)
        except RuntimeError as exc:
            assert "invalid api key" in str(exc).lower()
            return
    raise AssertionError("expected RuntimeError")


def test_execute_extracts_reasoning_when_content_empty(tmp_path):
    b = OllamaCloudBackend(api_key="k")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "model": "kimi-k2.6",
        "choices": [{"message": {"reasoning": "thought-trace", "content": ""}}],
        "usage": {},
    }
    with patch("httpx.post", return_value=resp):
        result = b.execute("p", Mode.THINK, tmp_path)
    assert result == "thought-trace"


def test_build_backends_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "k")
    from aicp.cli.main import _build_backends
    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
            "ollama_cloud": {"model": "kimi-k2.6", "enabled": False},
        }
    }
    backends = _build_backends(config)
    assert "ollama_cloud" not in backends


def test_build_backends_skips_when_no_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    from aicp.cli.main import _build_backends
    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
            "ollama_cloud": {"model": "kimi-k2.6", "enabled": True},
        }
    }
    backends = _build_backends(config)
    assert "ollama_cloud" not in backends


def test_build_backends_registers_when_enabled_and_key_present(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "k")
    from aicp.cli.main import _build_backends
    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
            "ollama_cloud": {
                "model": "kimi-k2.6",
                "max_tokens": 8192,
                "timeout": 300,
                "enabled": True,
            },
        }
    }
    backends = _build_backends(config)
    assert "ollama_cloud" in backends
    b = backends["ollama_cloud"]
    assert b.name == "ollama_cloud"
    assert b.model == "kimi-k2.6"
    assert b.max_tokens == 8192
    assert b.timeout == 300
    assert b.api_key == "k"


def test_build_backends_skips_when_config_missing(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "k")
    from aicp.cli.main import _build_backends
    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
        }
    }
    backends = _build_backends(config)
    assert "ollama_cloud" not in backends
