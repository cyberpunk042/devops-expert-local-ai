"""Tests for LocalAI backend — constructor, config wiring, cold-start logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode


def test_default_max_tokens():
    backend = LocalAIBackend()
    assert backend.max_tokens == 2048


def test_custom_max_tokens():
    backend = LocalAIBackend(max_tokens=4096)
    assert backend.max_tokens == 4096


def test_max_tokens_in_payload(tmp_path):
    """max_tokens value is forwarded in the API payload."""
    backend = LocalAIBackend(max_tokens=1024)
    captured = {}

    def fake_post(url, json, timeout, headers=None):
        captured["payload"] = json
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": "hello"}}],
            "usage": {},
        }
        return resp

    with patch("httpx.post", side_effect=fake_post):
        backend.execute("test", Mode.THINK, tmp_path)

    assert captured["payload"]["max_tokens"] == 1024


def test_is_model_loaded_true():
    backend = LocalAIBackend(model="hermes")
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": [{"id": "hermes"}]}

    with patch("httpx.get", return_value=resp):
        assert backend._is_model_loaded() is True


def test_is_model_loaded_false_model_missing():
    backend = LocalAIBackend(model="hermes")
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": [{"id": "other-model"}]}

    with patch("httpx.get", return_value=resp):
        assert backend._is_model_loaded() is False


def test_is_model_loaded_false_on_connect_error():
    import httpx
    backend = LocalAIBackend(model="hermes")

    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        assert backend._is_model_loaded() is False


def test_is_available_false_on_remote_protocol_error():
    """RemoteProtocolError (server disconnect during model load) returns False."""
    import httpx as _httpx
    backend = LocalAIBackend(model="hermes")

    with patch("httpx.get", side_effect=_httpx.RemoteProtocolError("Server disconnected")):
        assert backend.is_available() is False


def test_wait_for_model_succeeds_on_second_poll():
    """_wait_for_model returns True when model appears after one failed poll."""
    backend = LocalAIBackend(model="hermes")
    call_count = {"n": 0}

    def fake_is_loaded():
        call_count["n"] += 1
        return call_count["n"] >= 2  # fail first, succeed second

    backend._is_model_loaded = fake_is_loaded

    with patch("time.sleep"):  # don't actually sleep in tests
        result = backend._wait_for_model(timeout=20.0, interval=5.0)

    assert result is True
    assert call_count["n"] == 2


def test_wait_for_model_times_out():
    """_wait_for_model returns False if model never appears within timeout."""
    backend = LocalAIBackend(model="hermes")
    backend._is_model_loaded = lambda: False

    with patch("time.sleep"):
        result = backend._wait_for_model(timeout=10.0, interval=5.0)

    assert result is False


def test_connect_error_message_mentions_make_local_up():
    backend = LocalAIBackend()
    with patch("subprocess.run", side_effect=Exception("no docker")):
        msg = backend._connect_error_message()
    assert "make local-up" in msg or "make local-status" in msg


def test_connect_error_message_detects_stopped_container():
    backend = LocalAIBackend()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"Name":"localai","Status":"exited","State":"exited"}'

    with patch("subprocess.run", return_value=mock_result):
        msg = backend._connect_error_message()
    assert "stopped" in msg.lower() or "exited" in msg.lower()


def test_cpu_fallback_on_primary_failure(tmp_path):
    """When primary model fails 3 times, fallback to phi-2 (CPU)."""
    backend = LocalAIBackend(model="hermes")
    call_count = {"n": 0}

    def fake_post(url, json, timeout, headers=None):
        call_count["n"] += 1
        resp = MagicMock()
        if json.get("model") == "phi-2":
            # Fallback model succeeds
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": "fallback response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "model": "phi-2",
            }
        else:
            # Primary model returns 500 (OOM/load failure)
            resp.status_code = 500
            resp.json.return_value = {"error": {"message": "OOM"}}
        return resp

    # Mock _wait_for_model to avoid sleeps
    backend._wait_for_model = lambda **kw: False

    with patch("httpx.post", side_effect=fake_post):
        result = backend.execute("test prompt", Mode.THINK, tmp_path)

    assert result == "fallback response"
    assert call_count["n"] == 4  # 3 retries with hermes + 1 fallback with phi-2


def test_no_fallback_when_already_using_fallback_model(tmp_path):
    """When already using the fallback model, don't try fallback again."""
    backend = LocalAIBackend(model="phi-2")  # already using fallback

    def fake_post(url, json, timeout, headers=None):
        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {"error": {"message": "OOM"}}
        return resp

    backend._wait_for_model = lambda **kw: False

    with patch("httpx.post", side_effect=fake_post):
        with pytest.raises(RuntimeError, match="LocalAI failed"):
            backend.execute("test", Mode.THINK, tmp_path)


# ---------------------------------------------------------------------------
# Profile-driven timeouts and retries
# ---------------------------------------------------------------------------


def test_default_timeouts():
    """Default timeout/retry values match module constants."""
    backend = LocalAIBackend()
    assert backend.request_timeout == 120.0
    assert backend.cold_start_timeout == 60.0
    assert backend.cold_start_interval == 5.0
    assert backend.max_retries == 3


def test_custom_timeouts():
    """Constructor accepts custom timeout/retry values."""
    backend = LocalAIBackend(
        request_timeout=60.0,
        cold_start_timeout=30.0,
        cold_start_interval=2.0,
        max_retries=5,
    )
    assert backend.request_timeout == 60.0
    assert backend.cold_start_timeout == 30.0
    assert backend.cold_start_interval == 2.0
    assert backend.max_retries == 5


def test_request_timeout_in_payload(tmp_path):
    """request_timeout is passed to httpx.post()."""
    backend = LocalAIBackend(request_timeout=42.0)
    captured = {}

    def fake_post(url, json, timeout, headers=None):
        captured["timeout"] = timeout
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }
        return resp

    with patch("httpx.post", side_effect=fake_post):
        backend.execute("test", Mode.THINK, tmp_path)

    assert captured["timeout"] == 42.0


def test_max_retries_controls_attempts(tmp_path):
    """max_retries controls how many times execute retries on 5xx."""
    backend = LocalAIBackend(max_retries=2)
    backend._wait_for_model = lambda **kw: False
    call_count = {"n": 0}

    def fake_post(url, json, timeout, headers=None):
        call_count["n"] += 1
        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {"error": {"message": "server error"}}
        return resp

    with patch("httpx.post", side_effect=fake_post):
        with pytest.raises(RuntimeError, match="LocalAI failed"):
            backend.execute("test", Mode.THINK, tmp_path)

    # 2 retries with main model + 1 fallback attempt = 3 total
    assert call_count["n"] == 3
