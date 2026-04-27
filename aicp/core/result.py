"""Task result — structured return from backend execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenUsage:
    """Token consumption from a backend call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    estimated_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class TaskResult:
    """Structured result from a backend execution."""
    text: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
