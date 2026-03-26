"""Base backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Generator, Optional

from aicp.core.modes import Mode
from aicp.core.result import TaskResult


class Backend(ABC):
    """Abstract base for all AI backends."""

    # Populated by execute() for the controller to read
    last_usage = {}  # type: Dict

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""

    @abstractmethod
    def execute(self, prompt: str, mode: Mode, project_path: Path) -> str:
        """Execute a prompt under the given mode constraints.

        Returns the backend's response as text.
        Also populates self.last_usage with token/cost metadata.
        """

    def execute_result(self, prompt: str, mode: Mode, project_path: Path) -> TaskResult:
        """Execute and return a structured TaskResult.

        Default implementation wraps execute(). Backends can override
        for richer result data.
        """
        from aicp.core.result import TokenUsage
        text = self.execute(prompt, mode, project_path)
        usage = self.last_usage
        return TaskResult(
            text=text,
            usage=TokenUsage(
                prompt_tokens=usage.get("prompt_tokens") or 0,
                completion_tokens=usage.get("completion_tokens") or 0,
                model=usage.get("model", ""),
                estimated_cost_usd=usage.get("estimated_cost_usd") or 0,
            ),
            metadata=usage,
        )

    def execute_stream(
        self, prompt: str, mode: Mode, project_path: Path,
    ) -> Generator[str, None, None]:
        """Stream response chunks. Default: yield the full response at once."""
        yield self.execute(prompt, mode, project_path)

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is reachable and ready."""

    @abstractmethod
    def status_detail(self) -> str:
        """Return a human-readable status string for --check output."""
