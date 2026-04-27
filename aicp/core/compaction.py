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
from typing import Any

logger = logging.getLogger("aicp.compaction")

# Approximate tokens per character (conservative estimate for English)
_CHARS_PER_TOKEN = 4


def estimate_tokens(messages: list[dict[str, str]]) -> int:
    """Estimate token count for a message list."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars // _CHARS_PER_TOKEN


def compact_messages(
    messages: list[dict[str, str]],
    max_tokens: int = 8192,
    keep_recent_turns: int = 4,
    summary_prefix: str = "Previous conversation summary",
) -> list[dict[str, str]]:
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


def _summarize_messages(messages: list[dict[str, str]]) -> str:
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
    messages: list[dict[str, str]],
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


# ── Microcompaction (inspired by Claude Code) ────────────────────────────────
# Surgical pruning of old tool results while keeping conversation structure.
# Much more efficient than full compaction for ongoing sessions.

# Tool names whose results can be cleared after they age out
_COMPACTABLE_TOOLS = frozenset({
    "file_read", "file_list", "grep", "shell",
    "kb_search", "store_recall", "system_info",
})

# Tool results newer than this many turns are kept
_MICROCOMPACT_KEEP_RECENT = 5

# Placeholder for cleared tool results
_CLEARED_MARKER = "[Tool result cleared — re-run if needed]"

# Time gap (seconds) after which old tool results are aggressively cleared
_TIME_GAP_THRESHOLD = 3600  # 60 minutes


def microcompact(
    messages: list[dict[str, Any]],
    keep_recent: int = _MICROCOMPACT_KEEP_RECENT,
    compactable_tools: frozenset | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Clear old tool results while keeping conversation structure.

    Unlike full compaction which summarizes, microcompaction replaces
    old tool result content with a short marker. This preserves:
    - The fact that a tool was called (for reasoning continuity)
    - Recent tool results (for active work context)
    - All non-tool messages (user, assistant, system)

    Args:
        messages: Full message history.
        keep_recent: Number of recent tool results to preserve.
        compactable_tools: Set of tool names that can be cleared.
                          Defaults to _COMPACTABLE_TOOLS.

    Returns:
        Tuple of (compacted messages, number of results cleared).
    """
    if compactable_tools is None:
        compactable_tools = _COMPACTABLE_TOOLS

    # Find all tool result messages with their indices
    tool_indices = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "tool" and msg.get("name") in compactable_tools:
            tool_indices.append(i)

    if len(tool_indices) <= keep_recent:
        return messages, 0  # nothing to compact

    # Indices to clear (all except the most recent keep_recent)
    clear_indices = set(tool_indices[:-keep_recent] if keep_recent > 0 else tool_indices)

    # Build new message list
    cleared_count = 0
    result = []
    for i, msg in enumerate(messages):
        if i in clear_indices:
            # Replace content but keep the message structure
            result.append({
                **msg,
                "content": _CLEARED_MARKER,
            })
            cleared_count += 1
        else:
            result.append(msg)

    if cleared_count > 0:
        logger.info("Microcompacted %d old tool results (kept %d recent)", cleared_count, keep_recent)

    return result, cleared_count


def time_based_clear(
    messages: list[dict[str, Any]],
    gap_threshold: float = _TIME_GAP_THRESHOLD,
    keep_recent: int = _MICROCOMPACT_KEEP_RECENT,
) -> tuple[list[dict[str, Any]], int]:
    """Clear old tool results when a time gap is detected.

    If the gap between the last two assistant messages exceeds the threshold,
    the server-side prompt cache has likely expired. Clear old tool results
    to reduce context size for the inevitable cache miss.

    Args:
        messages: Full message history. Messages may have a '_timestamp' field.
        gap_threshold: Seconds of inactivity before clearing (default: 60 min).
        keep_recent: Number of recent tool results to keep.

    Returns:
        Tuple of (messages, number cleared).
    """
    # Find timestamps of assistant messages
    assistant_timestamps = []
    for msg in messages:
        if msg.get("role") == "assistant" and "_timestamp" in msg:
            assistant_timestamps.append(msg["_timestamp"])

    if len(assistant_timestamps) < 2:
        return messages, 0

    # Check gap between last two assistant messages
    gap = assistant_timestamps[-1] - assistant_timestamps[-2]
    if gap < gap_threshold:
        return messages, 0

    logger.info("Time gap detected (%.0fs > %.0fs threshold) — clearing old tool results", gap, gap_threshold)
    return microcompact(messages, keep_recent=keep_recent)


def strip_images(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace image/document content with markers to reduce token usage.

    Handles both string content and list-of-blocks content format.
    """
    result = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            # Multi-block content (OpenAI vision format)
            new_blocks = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "image_url":
                        new_blocks.append({"type": "text", "text": "[image]"})
                    elif block.get("type") == "image":
                        new_blocks.append({"type": "text", "text": "[image]"})
                    else:
                        new_blocks.append(block)
                else:
                    new_blocks.append(block)
            result.append({**msg, "content": new_blocks})
        else:
            result.append(msg)
    return result


def should_microcompact(
    messages: list[dict[str, Any]],
    tool_result_threshold: int = 10,
) -> bool:
    """Check if microcompaction would be beneficial.

    Returns True if there are more tool results than the threshold.
    """
    tool_count = sum(
        1 for m in messages
        if m.get("role") == "tool" and m.get("name") in _COMPACTABLE_TOOLS
    )
    return tool_count > tool_result_threshold
