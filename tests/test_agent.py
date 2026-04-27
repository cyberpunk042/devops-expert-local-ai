"""Tests for the AICP agent client."""

from unittest.mock import MagicMock, patch

import pytest

from aicp.agent.client import AgentClient

# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------

def test_client_health_unreachable():
    client = AgentClient("127.0.0.1", 19999)
    assert client.health() is False


def test_client_status_unreachable():
    client = AgentClient("127.0.0.1", 19999)
    assert client.status() is None


def test_client_repr():
    client = AgentClient("10.0.0.1", 9100)
    assert "10.0.0.1:9100" in repr(client)


# ---------------------------------------------------------------------------
# Health success paths
# ---------------------------------------------------------------------------

def test_health_returns_true_on_200():
    client = AgentClient("10.0.0.1", 9100)
    resp = MagicMock()
    resp.status_code = 200
    with patch("httpx.get", return_value=resp):
        assert client.health() is True


def test_health_returns_false_on_500():
    client = AgentClient("10.0.0.1", 9100)
    resp = MagicMock()
    resp.status_code = 500
    with patch("httpx.get", return_value=resp):
        assert client.health() is False


# ---------------------------------------------------------------------------
# Status success paths
# ---------------------------------------------------------------------------

def test_status_returns_dict_on_200():
    client = AgentClient("10.0.0.1", 9100)
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"gpus": [], "models": []}
    with patch("httpx.get", return_value=resp):
        result = client.status()
    assert result == {"gpus": [], "models": []}


def test_status_returns_none_on_500():
    client = AgentClient("10.0.0.1", 9100)
    resp = MagicMock()
    resp.status_code = 500
    with patch("httpx.get", return_value=resp):
        assert client.status() is None


# ---------------------------------------------------------------------------
# Execute task
# ---------------------------------------------------------------------------

def test_execute_task_success():
    client = AgentClient("10.0.0.1", 9100, token="secret")
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"result": "hello", "task_id": "t1"}
    resp.raise_for_status = MagicMock()
    with patch("httpx.post", return_value=resp):
        result = client.execute_task("test prompt")
    assert result["result"] == "hello"


def test_execute_task_sends_correct_payload():
    client = AgentClient("10.0.0.1", 9100)
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["json"] = json
        captured["url"] = url
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"result": "ok"}
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.post", side_effect=fake_post):
        client.execute_task("test", mode="edit", backend="claude", project="/myproject")

    assert captured["json"]["prompt"] == "test"
    assert captured["json"]["mode"] == "edit"
    assert captured["json"]["backend"] == "claude"
    assert captured["json"]["project"] == "/myproject"
    assert captured["json"]["remote"] is True


def test_execute_task_includes_auth_header():
    client = AgentClient("10.0.0.1", 9100, token="mytoken")
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"result": "ok"}
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.post", side_effect=fake_post):
        client.execute_task("test")

    assert captured["headers"]["Authorization"] == "Bearer mytoken"


def test_execute_task_no_auth_header_without_token():
    client = AgentClient("10.0.0.1", 9100)
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"result": "ok"}
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.post", side_effect=fake_post):
        client.execute_task("test")

    assert "Authorization" not in captured["headers"]


def test_execute_task_raises_on_http_error():
    import httpx
    client = AgentClient("10.0.0.1", 9100)
    resp = MagicMock()
    resp.status_code = 500
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=resp
    )
    with patch("httpx.post", return_value=resp):
        with pytest.raises(httpx.HTTPStatusError):
            client.execute_task("test")
