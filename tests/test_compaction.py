"""Tests for context compaction."""

from aicp.core.compaction import (
    compact_messages,
    estimate_tokens,
    get_context_budget,
    should_compact,
)


def _make_messages(turns: int, chars_per_msg: int = 200) -> list:
    """Generate a conversation with N turn pairs."""
    msgs = [{"role": "system", "content": "You are a helpful assistant."}]
    for i in range(turns):
        msgs.append({"role": "user", "content": f"Question {i}: " + "x" * chars_per_msg})
        msgs.append({"role": "assistant", "content": f"Answer {i}: " + "y" * chars_per_msg})
    return msgs


def test_estimate_tokens():
    msgs = [{"role": "user", "content": "Hello world"}]  # 11 chars
    tokens = estimate_tokens(msgs)
    assert tokens == 2  # 11 // 4


def test_compact_short_history():
    """Short history should pass through unchanged."""
    msgs = _make_messages(2, 50)
    result = compact_messages(msgs, max_tokens=5000)
    assert len(result) == len(msgs)


def test_compact_long_history():
    """Long history should be compacted."""
    msgs = _make_messages(20, 200)  # ~20 turns × 400 chars = ~8000 chars ≈ 2000 tokens
    result = compact_messages(msgs, max_tokens=500, keep_recent_turns=2)
    assert len(result) < len(msgs)
    # Should have: system + summary + last 4 messages (2 turns)
    assert result[0]["role"] == "system"
    assert "summary" in result[1]["content"].lower()
    # Last messages preserved
    assert result[-1]["role"] == "assistant"
    assert "Answer 19" in result[-1]["content"]


def test_compact_keeps_system():
    msgs = _make_messages(10, 200)
    result = compact_messages(msgs, max_tokens=500, keep_recent_turns=2)
    system_msgs = [m for m in result if m["role"] == "system"]
    assert len(system_msgs) >= 1  # original system + summary


def test_compact_preserves_recent():
    msgs = _make_messages(10, 200)
    result = compact_messages(msgs, max_tokens=500, keep_recent_turns=3)
    # Last 6 messages (3 turns) should be preserved verbatim
    assert "Question 9" in result[-2]["content"]
    assert "Answer 9" in result[-1]["content"]


def test_should_compact_under_threshold():
    msgs = _make_messages(2, 50)  # small
    assert should_compact(msgs, context_window=8192) is False


def test_should_compact_over_threshold():
    msgs = _make_messages(50, 500)  # large
    assert should_compact(msgs, context_window=2048) is True


def test_get_context_budget():
    assert get_context_budget("qwen3-8b") == 8192
    assert get_context_budget("qwen3-4b") == 16384
    assert get_context_budget("opus") == 1_000_000
    assert get_context_budget("unknown-model") == 8192  # default


def test_compact_empty():
    result = compact_messages([], max_tokens=1000)
    assert result == []
