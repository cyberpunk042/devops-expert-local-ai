"""Budget and time limits for autonomous workflows."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BudgetLimits:
    """Hard limits for autonomous pipeline execution."""
    max_cost_usd: float = 10.0
    max_duration_seconds: float = 600.0  # 10 minutes
    max_steps: int = 20
    max_file_changes: int = 50

    # Runtime tracking
    spent_cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
    completed_steps: int = 0
    file_changes: int = 0
    _start_time: Optional[float] = field(default=None, repr=False)

    def start(self) -> None:
        """Start tracking time."""
        self._start_time = time.time()

    def update(
        self,
        cost: float = 0,
        steps: int = 0,
        files: int = 0,
    ) -> None:
        """Update budget tracking."""
        self.spent_cost_usd += cost
        self.completed_steps += steps
        self.file_changes += files
        if self._start_time:
            self.elapsed_seconds = time.time() - self._start_time

    def check(self) -> Optional[str]:
        """Check if any limit is exceeded. Returns reason string or None."""
        if self._start_time:
            self.elapsed_seconds = time.time() - self._start_time

        if self.spent_cost_usd >= self.max_cost_usd:
            return f"Cost limit exceeded: ${self.spent_cost_usd:.4f} >= ${self.max_cost_usd:.2f}"

        if self.elapsed_seconds >= self.max_duration_seconds:
            return f"Time limit exceeded: {self.elapsed_seconds:.0f}s >= {self.max_duration_seconds:.0f}s"

        if self.completed_steps >= self.max_steps:
            return f"Step limit exceeded: {self.completed_steps} >= {self.max_steps}"

        if self.file_changes >= self.max_file_changes:
            return f"File change limit exceeded: {self.file_changes} >= {self.max_file_changes}"

        return None

    def summary(self) -> str:
        """Return a human-readable budget summary."""
        lines = [
            f"Cost:    ${self.spent_cost_usd:.4f} / ${self.max_cost_usd:.2f}",
            f"Time:    {self.elapsed_seconds:.0f}s / {self.max_duration_seconds:.0f}s",
            f"Steps:   {self.completed_steps} / {self.max_steps}",
            f"Files:   {self.file_changes} / {self.max_file_changes}",
        ]
        return "\n".join(lines)


def load_budget_from_config(pipeline_config: dict) -> BudgetLimits:
    """Load budget limits from pipeline YAML config.

    Format:
    ```yaml
    budget:
      max_cost_usd: 5.0
      max_duration_seconds: 300
      max_steps: 10
      max_file_changes: 20
    ```
    """
    budget = pipeline_config.get("budget", {})
    return BudgetLimits(
        max_cost_usd=budget.get("max_cost_usd", 10.0),
        max_duration_seconds=budget.get("max_duration_seconds", 600.0),
        max_steps=budget.get("max_steps", 20),
        max_file_changes=budget.get("max_file_changes", 50),
    )
