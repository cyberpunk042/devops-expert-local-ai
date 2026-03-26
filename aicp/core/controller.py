"""Main controller — routes tasks to backends with mode enforcement."""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from aicp.core.modes import Mode
from aicp.backends.base import Backend
from aicp.guardrails.checks import run_preflight_checks

logger = logging.getLogger("aicp")


@dataclass
class Task:
    """A unit of work to send to a backend."""

    prompt: str
    mode: Mode
    project_path: Path
    backend_name: str = "local"


class Controller:
    """Orchestrates backend selection, mode enforcement, and task execution."""

    def __init__(
        self,
        backends: Dict[str, Backend],
        config: Dict[str, Any] = None,
    ) -> None:
        self.backends = backends
        self.config = config or {}

    def run(self, task: Task) -> str:
        """Run a task through the selected backend with mode enforcement."""
        # Run preflight guardrail checks
        issues = run_preflight_checks(
            task.project_path, task.mode, task.backend_name, self.config
        )

        errors = [i for i in issues if not i.startswith("WARNING:")]
        warnings = [i for i in issues if i.startswith("WARNING:")]

        if errors:
            raise ValueError("\n".join(errors))

        for warning in warnings:
            print(warning, file=sys.stderr)

        backend = self.backends.get(task.backend_name)
        if backend is None:
            raise ValueError(f"Unknown backend: {task.backend_name}")

        start = datetime.utcnow()

        logger.info(json.dumps({
            "event": "task_start",
            "mode": task.mode.value,
            "backend": task.backend_name,
            "project": str(task.project_path),
            "timestamp": start.isoformat(),
        }))

        result = backend.execute(task.prompt, task.mode, task.project_path)

        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.info(json.dumps({
            "event": "task_complete",
            "mode": task.mode.value,
            "backend": task.backend_name,
            "duration_seconds": elapsed,
            "response_length": len(result),
            "timestamp": datetime.utcnow().isoformat(),
        }))

        return result
