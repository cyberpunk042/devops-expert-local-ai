"""Tests for cluster management."""

from aicp.core.cluster import load_cluster_config, NodeInfo, find_best_node


def test_load_cluster_config_empty():
    nodes = load_cluster_config({})
    assert nodes == []


def test_load_cluster_config():
    config = {
        "cluster": {
            "config_file": "/nonexistent/fleet.yaml",
            "token": "secret123",
            "nodes": [
                {"name": "machine-a", "host": "192.168.1.10", "port": 9100},
                {"name": "machine-b", "host": "192.168.1.11"},
            ],
        }
    }
    nodes = load_cluster_config(config)
    assert len(nodes) == 2
    assert nodes[0].name == "machine-a"
    assert nodes[0].port == 9100
    assert nodes[0].token == "secret123"
    assert nodes[1].port == 9100  # default


def test_find_best_node_none_online():
    nodes = [NodeInfo("a", "host", 9100, online=False)]
    assert find_best_node(nodes) is None


def test_find_best_node_by_vram():
    a = NodeInfo("a", "host-a", 9100, online=True, gpus=[{"vram_free_mb": 2000}])
    b = NodeInfo("b", "host-b", 9100, online=True, gpus=[{"vram_free_mb": 6000}])
    best = find_best_node([a, b])
    assert best.name == "b"  # more free VRAM


def test_find_best_node_by_model():
    a = NodeInfo("a", "host-a", 9100, online=True,
                 gpus=[{"vram_free_mb": 2000}],
                 models=[{"name": "hermes"}])
    b = NodeInfo("b", "host-b", 9100, online=True,
                 gpus=[{"vram_free_mb": 6000}],
                 models=[{"name": "phi-2"}])
    best = find_best_node([a, b], model_name="hermes")
    assert best.name == "a"  # has the requested model
