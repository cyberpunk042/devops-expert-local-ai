"""Main controller — routes tasks to backends with mode enforcement."""

from __future__ import annotations

import json
import logging
import socket
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set

from aicp.core.modes import Mode
from aicp.backends.base import Backend
from aicp.core.cluster import (
    check_cluster,
    execute_remote,
    find_best_node,
    load_cluster_config,
)
from aicp.core.history import save_task
from aicp.guardrails.checks import run_preflight_checks

logger = logging.getLogger("aicp")


@dataclass
class Task:
    """A unit of work to send to a backend."""

    prompt: str
    mode: Mode
    project_path: Path
    backend_name: str = "local"


def _local_ips() -> Set[str]:
    """Return a set of IP addresses belonging to this machine."""
    ips = {"127.0.0.1", "::1", "localhost"}
    try:
        hostname = socket.gethostname()
        ips.add(hostname.lower())
        for info in socket.getaddrinfo(hostname, None):
            ips.add(info[4][0])
    except OSError:
        pass
    return ips


class Controller:
    """Orchestrates backend selection, mode enforcement, and task execution."""

    def __init__(
        self,
        backends: Dict[str, Backend],
        config: Dict[str, Any] = None,
    ) -> None:
        self.backends = backends
        self.config = config or {}
        self._fleet_checked = False
        self._fleet_nodes: list = []
        self.last_route: Optional[str] = None  # tracks where the last task ran

    def _check_fleet(self) -> None:
        """Load and health-check fleet nodes (cached per controller lifetime)."""
        if self._fleet_checked:
            return
        self._fleet_checked = True
        nodes = load_cluster_config(self.config)
        if nodes:
            self._fleet_nodes = check_cluster(nodes)
            online = [n for n in self._fleet_nodes if n.online]
            logger.info("Fleet: %d nodes loaded, %d online", len(nodes), len(online))

    def _try_fleet_route(self, task: Task) -> Optional[str]:
        """Attempt to route the task to the best fleet node.

        Returns the response string if routed remotely, None if we should
        execute locally.
        """
        cluster_cfg = self.config.get("cluster", {})
        if not cluster_cfg.get("auto_route", False):
            return None

        self._check_fleet()
        if not self._fleet_nodes:
            return None

        best = find_best_node(self._fleet_nodes, model_name=None)
        if best is None:
            logger.warning("Fleet: no online nodes, falling back to local")
            return None

        # If best node is this machine, execute locally
        if best.host in _local_ips() or best.name.lower() == socket.gethostname().lower():
            self.last_route = f"local ({best.name})"
            return None

        # Route to remote node
        logger.info("Fleet: routing to %s (%s:%d)", best.name, best.host, best.port)
        self.last_route = f"fleet:{best.name} ({best.host})"

        result_dict = execute_remote(
            best,
            prompt=task.prompt,
            mode=task.mode.value,
            backend=task.backend_name,
            project=str(task.project_path),
        )
        return result_dict.get("response", result_dict.get("result", str(result_dict)))

    def run(self, task: Task) -> str:
        """Run a task through the selected backend with mode enforcement."""
        issues = run_preflight_checks(
            task.project_path, task.mode, task.backend_name, self.config
        )

        errors = [i for i in issues if not i.startswith("WARNING:")]
        warnings = [i for i in issues if i.startswith("WARNING:")]

        if errors:
            raise ValueError("\n".join(errors))

        for warning in warnings:
            print(warning, file=sys.stderr)

        start = datetime.utcnow()

        logger.info(json.dumps({
            "event": "task_start",
            "mode": task.mode.value,
            "backend": task.backend_name,
            "project": str(task.project_path),
            "timestamp": start.isoformat(),
        }))

        error = None
        result = ""
        try:
            # Try fleet routing first (if auto_route is enabled)
            fleet_result = self._try_fleet_route(task)
            if fleet_result is not None:
                result = fleet_result
            else:
                # Execute locally
                self.last_route = "local"
                backend = self.backends.get(task.backend_name)
                if backend is None:
                    raise ValueError(f"Unknown backend: {task.backend_name}")
                result = backend.execute(task.prompt, task.mode, task.project_path)
        except Exception as e:
            error = str(e)
            raise
        finally:
            elapsed = (datetime.utcnow() - start).total_seconds()

            # Collect usage metadata from backend (populated by execute())
            backend_obj = self.backends.get(task.backend_name)
            usage = getattr(backend_obj, "last_usage", {}) if backend_obj else {}

            logger.info(json.dumps({
                "event": "task_complete",
                "mode": task.mode.value,
                "backend": task.backend_name,
                "route": self.last_route,
                "duration_seconds": elapsed,
                "response_length": len(result),
                "tokens": usage,
                "timestamp": datetime.utcnow().isoformat(),
            }))
            save_task(
                prompt=task.prompt,
                mode=task.mode.value,
                backend=task.backend_name,
                project=str(task.project_path),
                response=result,
                duration_seconds=elapsed,
                error=error,
                model=usage.get("model"),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                estimated_cost_usd=usage.get("estimated_cost_usd"),
            )

        return result
