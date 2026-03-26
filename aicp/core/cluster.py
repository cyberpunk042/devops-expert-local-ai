"""Cluster management — coordinate multiple AICP nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from aicp.agent.client import AgentClient


@dataclass
class NodeInfo:
    """Information about a cluster node."""
    name: str
    host: str
    port: int
    token: str = ""
    online: bool = False
    gpus: List[Dict] = None
    models: List[Dict] = None

    def __post_init__(self):
        if self.gpus is None:
            self.gpus = []
        if self.models is None:
            self.models = []


def load_cluster_config(config: Dict[str, Any]) -> List[NodeInfo]:
    """Load cluster nodes from config.

    Config format:
    ```yaml
    cluster:
      token: "shared-secret"
      nodes:
        - name: machine-a
          host: 192.168.1.10
          port: 9100
        - name: machine-b
          host: 192.168.1.11
          port: 9100
    ```
    """
    cluster = config.get("cluster", {})
    if not cluster:
        return []

    default_token = cluster.get("token", "")
    nodes = []

    for node_cfg in cluster.get("nodes", []):
        nodes.append(NodeInfo(
            name=node_cfg.get("name", node_cfg.get("host", "unknown")),
            host=node_cfg["host"],
            port=node_cfg.get("port", 9100),
            token=node_cfg.get("token", default_token),
        ))

    return nodes


def check_cluster(nodes: List[NodeInfo]) -> List[NodeInfo]:
    """Check health and status of all cluster nodes."""
    for node in nodes:
        client = AgentClient(node.host, node.port, node.token)
        node.online = client.health()
        if node.online:
            status = client.status()
            if status:
                node.gpus = status.get("gpus", [])
                node.models = status.get("models", [])

    return nodes


def find_best_node(
    nodes: List[NodeInfo],
    model_name: Optional[str] = None,
) -> Optional[NodeInfo]:
    """Find the best node for a task based on availability and capacity.

    Prefers nodes with: the requested model loaded, most free VRAM, online status.
    """
    online = [n for n in nodes if n.online]
    if not online:
        return None

    # If a specific model is requested, prefer nodes that have it
    if model_name:
        with_model = [
            n for n in online
            if any(m.get("name") == model_name for m in n.models)
        ]
        if with_model:
            online = with_model

    # Sort by total free VRAM (descending)
    def free_vram(node: NodeInfo) -> int:
        return sum(g.get("vram_free_mb", 0) for g in node.gpus)

    online.sort(key=free_vram, reverse=True)
    return online[0]


def execute_remote(
    node: NodeInfo,
    prompt: str,
    mode: str = "think",
    backend: str = "local",
    project: str = ".",
) -> Dict[str, Any]:
    """Execute a task on a remote node."""
    client = AgentClient(node.host, node.port, node.token)
    return client.execute_task(prompt, mode, backend, project)
