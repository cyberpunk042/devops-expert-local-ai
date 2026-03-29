"""Tests for Fleet Bootstrap & Multi-Machine (M95)."""

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from aicp.core.cluster import NodeInfo, load_fleet_config, load_cluster_config, check_cluster, find_best_node
from aicp.core.modes import Mode


# ── load_fleet_config() ──────────────────────────────────────────────────


class TestLoadFleetConfig:
    def test_loads_from_file(self, tmp_path):
        fleet_yaml = tmp_path / "fleet.yaml"
        fleet_yaml.write_text(yaml.dump({
            "fleet": {
                "token": "secret123",
                "port": 9100,
                "nodes": [
                    {"name": "mining-station", "host": "192.168.40.10", "port": 9100, "role": "primary"},
                    {"name": "node-250", "host": "192.168.40.250", "port": 9100, "role": "worker"},
                ],
            }
        }))

        nodes = load_fleet_config(fleet_yaml)

        assert len(nodes) == 2
        assert nodes[0].name == "mining-station"
        assert nodes[0].host == "192.168.40.10"
        assert nodes[0].token == "secret123"
        assert nodes[1].name == "node-250"
        assert nodes[1].host == "192.168.40.250"

    def test_empty_file(self, tmp_path):
        fleet_yaml = tmp_path / "fleet.yaml"
        fleet_yaml.write_text("")

        nodes = load_fleet_config(fleet_yaml)
        assert nodes == []

    def test_missing_file(self, tmp_path):
        nodes = load_fleet_config(tmp_path / "nonexistent.yaml")
        assert nodes == []

    def test_no_nodes(self, tmp_path):
        fleet_yaml = tmp_path / "fleet.yaml"
        fleet_yaml.write_text(yaml.dump({"fleet": {"token": "x"}}))

        nodes = load_fleet_config(fleet_yaml)
        assert nodes == []

    def test_token_shared_across_nodes(self, tmp_path):
        fleet_yaml = tmp_path / "fleet.yaml"
        fleet_yaml.write_text(yaml.dump({
            "fleet": {
                "token": "shared-secret",
                "nodes": [
                    {"name": "a", "host": "10.0.0.1"},
                    {"name": "b", "host": "10.0.0.2"},
                ],
            }
        }))

        nodes = load_fleet_config(fleet_yaml)
        assert all(n.token == "shared-secret" for n in nodes)

    def test_default_port(self, tmp_path):
        fleet_yaml = tmp_path / "fleet.yaml"
        fleet_yaml.write_text(yaml.dump({
            "fleet": {
                "token": "x",
                "port": 9200,
                "nodes": [{"name": "a", "host": "10.0.0.1"}],
            }
        }))

        nodes = load_fleet_config(fleet_yaml)
        assert nodes[0].port == 9200


class TestLoadClusterConfigWithFleet:
    def test_prefers_fleet_yaml(self, tmp_path):
        fleet_yaml = tmp_path / "fleet.yaml"
        fleet_yaml.write_text(yaml.dump({
            "fleet": {
                "token": "fleet-token",
                "nodes": [{"name": "fleet-node", "host": "10.0.0.1"}],
            }
        }))

        config = {"cluster": {"config_file": str(fleet_yaml)}}
        nodes = load_cluster_config(config)

        assert len(nodes) == 1
        assert nodes[0].name == "fleet-node"

    def test_falls_back_to_inline(self):
        config = {
            "cluster": {
                "token": "inline-token",
                "nodes": [{"name": "inline-node", "host": "10.0.0.2"}],
            }
        }
        # No fleet.yaml exists at default path
        with patch("aicp.core.cluster.load_fleet_config", return_value=[]):
            nodes = load_cluster_config(config)

        assert len(nodes) == 1
        assert nodes[0].name == "inline-node"

    def test_empty_config(self):
        nodes = load_cluster_config({})
        assert nodes == []


# ── check_cluster() ──────────────────────────────────────────────────────


class TestCheckCluster:
    def test_marks_online(self):
        nodes = [
            NodeInfo(name="a", host="10.0.0.1", port=9100, token="t"),
            NodeInfo(name="b", host="10.0.0.2", port=9100, token="t"),
        ]

        mock_client_a = MagicMock()
        mock_client_a.health.return_value = True
        mock_client_a.status.return_value = {
            "gpus": [{"name": "RTX 3060 Ti", "vram_total_mb": 8192, "vram_free_mb": 6000}],
            "models": [{"name": "hermes"}],
        }

        mock_client_b = MagicMock()
        mock_client_b.health.return_value = False

        with patch("aicp.core.cluster.AgentClient") as MockClient:
            MockClient.side_effect = [mock_client_a, mock_client_b]
            result = check_cluster(nodes)

        assert result[0].online is True
        assert result[0].gpus[0]["name"] == "RTX 3060 Ti"
        assert result[1].online is False

    def test_all_offline(self):
        nodes = [NodeInfo(name="a", host="10.0.0.1", port=9100)]

        mock_client = MagicMock()
        mock_client.health.return_value = False

        with patch("aicp.core.cluster.AgentClient", return_value=mock_client):
            result = check_cluster(nodes)

        assert result[0].online is False


# ── find_best_node() ─────────────────────────────────────────────────────


class TestFindBestNode:
    def test_picks_most_vram(self):
        nodes = [
            NodeInfo(name="small", host="10.0.0.1", port=9100, online=True,
                     gpus=[{"vram_free_mb": 2000}]),
            NodeInfo(name="big", host="10.0.0.2", port=9100, online=True,
                     gpus=[{"vram_free_mb": 6000}]),
        ]

        best = find_best_node(nodes)
        assert best.name == "big"

    def test_prefers_model_loaded(self):
        nodes = [
            NodeInfo(name="no-model", host="10.0.0.1", port=9100, online=True,
                     gpus=[{"vram_free_mb": 8000}], models=[]),
            NodeInfo(name="has-model", host="10.0.0.2", port=9100, online=True,
                     gpus=[{"vram_free_mb": 4000}], models=[{"name": "hermes"}]),
        ]

        best = find_best_node(nodes, model_name="hermes")
        assert best.name == "has-model"

    def test_none_online(self):
        nodes = [NodeInfo(name="a", host="10.0.0.1", port=9100, online=False)]
        assert find_best_node(nodes) is None


# ── Interactive /fleet ───────────────────────────────────────────────────


class TestInteractiveFleet:
    def test_fleet_status(self, capsys):
        from aicp.cli.interactive import _handle_slash

        mock_nodes = [
            NodeInfo(name="mining-station", host="192.168.40.10", port=9100, online=True,
                     gpus=[{"name": "RTX 3060 Ti", "vram_free_mb": 6000, "vram_total_mb": 8192}]),
            NodeInfo(name="node-250", host="192.168.40.250", port=9100, online=False),
        ]

        with patch("aicp.core.cluster.load_fleet_config", return_value=mock_nodes):
            with patch("aicp.core.cluster.check_cluster", return_value=mock_nodes):
                _handle_slash("/fleet", [], MagicMock(), {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "mining-station" in output
        assert "node-250" in output
        assert "2 node" in output

    def test_fleet_no_config(self, capsys):
        from aicp.cli.interactive import _handle_slash

        with patch("aicp.core.cluster.load_fleet_config", return_value=[]):
            _handle_slash("/fleet", [], MagicMock(), {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "fleet-init" in err

    def test_fleet_run_basic(self, capsys):
        from aicp.cli.interactive import _handle_slash

        mock_nodes = [
            NodeInfo(name="mining-station", host="192.168.40.10", port=9100, online=True,
                     gpus=[{"vram_free_mb": 6000}]),
        ]

        with patch("aicp.core.cluster.load_fleet_config", return_value=mock_nodes):
            with patch("aicp.core.cluster.check_cluster", return_value=mock_nodes):
                with patch("aicp.core.cluster.find_best_node", return_value=mock_nodes[0]):
                    with patch("aicp.core.cluster.execute_remote", return_value={
                        "result": "Hello from fleet!", "duration_seconds": 1.5,
                    }):
                        _handle_slash("/fleet-run What is 2+2?", [], MagicMock(), {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "Hello from fleet!" in output
        assert "mining-station" in output

    def test_fleet_run_no_arg(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/fleet-run", [], MagicMock(), {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "Usage" in err

    def test_fleet_run_no_nodes_online(self, capsys):
        from aicp.cli.interactive import _handle_slash

        mock_nodes = [
            NodeInfo(name="a", host="10.0.0.1", port=9100, online=False),
        ]

        with patch("aicp.core.cluster.load_fleet_config", return_value=mock_nodes):
            with patch("aicp.core.cluster.check_cluster", return_value=mock_nodes):
                with patch("aicp.core.cluster.find_best_node", return_value=None):
                    _handle_slash("/fleet-run test", [], MagicMock(), {}, Mode.THINK, Path("/tmp"))

        err = capsys.readouterr().err
        assert "online" in err.lower()


# ── MCP fleet tools ──────────────────────────────────────────────────────


class TestMcpFleetStatus:
    def test_returns_nodes(self):
        from aicp.mcp.server import aicp_fleet_status

        mock_nodes = [
            NodeInfo(name="a", host="10.0.0.1", port=9100, online=True,
                     gpus=[{"name": "RTX 3060 Ti"}], models=[{"name": "hermes"}]),
        ]

        with patch("aicp.core.cluster.load_fleet_config", return_value=mock_nodes):
            with patch("aicp.core.cluster.check_cluster", return_value=mock_nodes):
                result = aicp_fleet_status()

        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "a"
        assert parsed[0]["online"] is True

    def test_no_fleet(self):
        from aicp.mcp.server import aicp_fleet_status

        with patch("aicp.core.cluster.load_fleet_config", return_value=[]):
            result = aicp_fleet_status()

        parsed = json.loads(result)
        assert "error" in parsed


class TestMcpFleetRun:
    def test_routes_task(self):
        from aicp.mcp.server import aicp_fleet_run

        mock_nodes = [
            NodeInfo(name="big-gpu", host="10.0.0.1", port=9100, online=True,
                     gpus=[{"vram_free_mb": 8000}]),
        ]

        with patch("aicp.core.cluster.load_fleet_config", return_value=mock_nodes):
            with patch("aicp.core.cluster.check_cluster", return_value=mock_nodes):
                with patch("aicp.core.cluster.find_best_node", return_value=mock_nodes[0]):
                    with patch("aicp.core.cluster.execute_remote", return_value={
                        "result": "42", "duration_seconds": 0.5,
                    }):
                        result = aicp_fleet_run("What is 6*7?")

        parsed = json.loads(result)
        assert parsed["result"] == "42"
        assert parsed["node"] == "big-gpu"

    def test_no_nodes_online(self):
        from aicp.mcp.server import aicp_fleet_run

        with patch("aicp.core.cluster.load_fleet_config", return_value=[
            NodeInfo(name="a", host="10.0.0.1", port=9100, online=False),
        ]):
            with patch("aicp.core.cluster.check_cluster", return_value=[
                NodeInfo(name="a", host="10.0.0.1", port=9100, online=False),
            ]):
                with patch("aicp.core.cluster.find_best_node", return_value=None):
                    result = aicp_fleet_run("test")

        parsed = json.loads(result)
        assert "error" in parsed
