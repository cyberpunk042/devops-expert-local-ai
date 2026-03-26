"""Base backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from aicp.core.modes import Mode


class Backend(ABC):
    """Abstract base for all AI backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""

    @abstractmethod
    def execute(self, prompt: str, mode: Mode, project_path: Path) -> str:
        """Execute a prompt under the given mode constraints.

        Returns the backend's response as text.
        """
