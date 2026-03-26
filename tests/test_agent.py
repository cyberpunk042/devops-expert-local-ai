"""Tests for the AICP agent client."""

from aicp.agent.client import AgentClient


def test_client_health_unreachable():
    client = AgentClient("127.0.0.1", 19999)
    assert client.health() is False


def test_client_status_unreachable():
    client = AgentClient("127.0.0.1", 19999)
    assert client.status() is None


def test_client_repr():
    client = AgentClient("10.0.0.1", 9100)
    assert "10.0.0.1:9100" in repr(client)
