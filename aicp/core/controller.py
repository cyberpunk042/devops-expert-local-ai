"""Main controller — routes tasks to backends with mode enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from aicp.core.modes import Mode
from aicp.backends.base import Backend


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
        backend = self.backends.get(task.backend_name)
        if backend is None:
            raise ValueError(f"Unknown backend: {task.backend_name}")

        return backend.execute(task.prompt, task.mode, task.project_path)
