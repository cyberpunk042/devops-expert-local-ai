"""Context compaction — manage conversation history within token budgets.

When a session's message history grows beyond the model's context window,
this module decides what to keep, what to summarize, and what to drop.
Uses the knowledge map's injection profiles to determine budget per model tier.

Strategy:
  1. System message: always keep (essential identity/instructions)
  2. Last N user/assistant turns: always keep (recent context)
  3. Older turns: summarize into a single "context so far" message
  4. KB context: re-inject fresh (don't carry stale RAG results)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aicp.compaction")

# Approximate tokens per character (conservative estimate for English)
_CHARS_PER_TOKEN = 4


def estimate_tokens(messages: List[Dict[str, str]]) -> int:
    """Estimate token count for a message list."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars // _CHARS_PER_TOKEN


def compact_messages(
    messages: List[Dict[str, str]],
    max_tokens: int = 8192,
    keep_recent_turns: int = 4,
    summary_prefix: str = "Previous conversation summary",
) -> List[Dict[str, str]]:
    """Compact message history to fit within a token budget.

    Args:
        messages: Full message history (system + user/assistant pairs).
        max_tokens: Target token budget.
        keep_recent_turns: Number of recent user+assistant turn pairs to always keep.
        summary_prefix: Prefix for the summary message.

    Returns:
        Compacted message list that fits within max_tokens.
    """
    if not messages:
        return messages

    current_tokens = estimate_tokens(messages)
    if current_tokens <= max_tokens:
        return messages  # fits already

    # Separate system message from conversation
    system_msgs = [m for m in messages if m.get("role") == "system"]
    conv_msgs = [m for m in messages if m.get("role") != "system"]

    if not conv_msgs:
        return messages

    # Keep recent turns (user + assistant pairs)
    keep_count = keep_recent_turns * 2  # each turn = user + assistant
    if keep_count >= len(conv_msgs):
        return messages  # nothing to compact

    recent = conv_msgs[-keep_count:]
    old = conv_msgs[:-keep_count]

    # Summarize old messages into one condensed message
    summary = _summarize_messages(old)
    summary_msg = {
        "role": "system",
        "content": f"{summary_prefix}:\n{summary}",
    }

    # Assemble compacted history
    compacted = system_msgs + [summary_msg] + recent

    # If still too long, truncate summary
    while estimate_tokens(compacted) > max_tokens and len(summary_msg["content"]) > 200:
        summary_msg["content"] = summary_msg["content"][:len(summary_msg["content"]) // 2] + "\n... (truncated)"
        compacted = system_msgs + [summary_msg] + recent

    logger.info(
        "Compacted %d messages (%d tokens) → %d messages (%d tokens)",
        len(messages), current_tokens, len(compacted), estimate_tokens(compacted),
    )
    return compacted


def _summarize_messages(messages: List[Dict[str, str]]) -> str:
    """Create a text summary of older messages.

    This is a heuristic summarizer — extracts key points from each turn
    without requiring an LLM call. For LLM-based summarization, the
    caller should use the backend directly.
    """
    points = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "").strip()
        if not content:
            continue

        # Extract first sentence or first 150 chars
        first_line = content.split("\n")[0][:150]
        if role == "user":
            points.append(f"- User asked: {first_line}")
        elif role == "assistant":
            points.append(f"- Assistant: {first_line}")

    return "\n".join(points[-20:])  # keep last 20 points max


def should_compact(
    messages: List[Dict[str, str]],
    model: str = "",
    context_window: int = 8192,
    threshold: float = 0.75,
) -> bool:
    """Check if messages need compaction based on model's context window.

    Returns True if estimated tokens exceed threshold of context window.
    """
    tokens = estimate_tokens(messages)
    limit = int(context_window * threshold)
    return tokens > limit


def get_context_budget(model: str, profile: str = "") -> int:
    """Get the context window budget for a model.

    Uses injection profile hints to determine effective context.
    """
    # Known model context windows
    budgets = {
        "qwen3-8b": 8192,
        "qwen3-8b-fast": 8192,
        "qwen3-4b": 16384,
        "qwen3-30b-a3b": 8192,
        "gemma4-e2b": 16384,
        "gemma4-e4b": 8192,
        "gemma4-26b-a4b": 8192,
        "hermes": 16384,
        "hermes-3b": 16384,
        "opus": 1_000_000,
        "sonnet": 200_000,
    }

    model_lower = model.lower()
    for name, budget in budgets.items():
        if name in model_lower:
            return budget

    return 8192  # safe default
