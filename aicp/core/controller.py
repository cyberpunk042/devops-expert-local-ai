"""Main controller — routes tasks to backends with mode enforcement."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from aicp.core.modes import Mode
from aicp.backends.base import Backend

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

    def __init__(self, backends: Dict[str, Backend]) -> None:
        self.backends = backends

    def run(self, task: Task) -> str:
        """Run a task through the selected backend with mode enforcement."""
        # Validate project path before doing anything
        if not task.project_path.exists():
            raise ValueError(f"Project path does not exist: {task.project_path}")
        if not task.project_path.is_dir():
            raise ValueError(f"Project path is not a directory: {task.project_path}")

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
