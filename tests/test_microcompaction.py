"""Tests for microcompaction and time-based clearing in aicp.core.compaction."""

import time
import pytest

from aicp.core.compaction import (
    microcompact,
    time_based_clear,
    strip_images,
    should_microcompact,
    _COMPACTABLE_TOOLS,
    _CLEARED_MARKER,
    _MICROCOMPACT_KEEP_RECENT,
    _TIME_GAP_THRESHOLD,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tool_msg(name: str, content: str = "result") -> dict:
    return {"role": "tool", "name": name, "content": content}


def _user_msg(content: str = "question") -> dict:
    return {"role": "user", "content": content}


def _assistant_msg(content: str = "answer", ts: float = 0.0) -> dict:
    msg = {"role": "assistant", "content": content}
    if ts:
        msg["_timestamp"] = ts
    return msg


def _system_msg(content: str = "system prompt") -> dict:
    return {"role": "system", "content": content}


# ── Microcompaction tests ────────────────────────────────────────────────────

class TestMicrocompact:
    def test_no_tool_results(self):
        msgs = [_user_msg(), _assistant_msg()]
        result, cleared = microcompact(msgs)
        assert cleared == 0
        assert result == msgs

    def test_few_tool_results_not_cleared(self):
        """When there are fewer tool results than keep_recent, nothing is cleared."""
        msgs = [_tool_msg("file_read", f"content {i}") for i in range(3)]
        result, cleared = microcompact(msgs, keep_recent=5)
        assert cleared == 0

    def test_old_results_cleared(self):
        msgs = [
            _tool_msg("file_read", f"old content {i}") for i in range(8)
        ] + [
            _tool_msg("file_read", f"recent content {i}") for i in range(2)
        ]
        result, cleared = microcompact(msgs, keep_recent=2)
        assert cleared == 8
        # Old results should be markers
        for i in range(8):
            assert result[i]["content"] == _CLEARED_MARKER
        # Recent results should be preserved
        assert result[8]["content"] == "recent content 0"
        assert result[9]["content"] == "recent content 1"

    def test_non_compactable_tools_preserved(self):
        """Tools not in _COMPACTABLE_TOOLS should never be cleared."""
        msgs = [
            _tool_msg("file_read", "cleared"),
            _tool_msg("image_analyze", "keep me"),  # not compactable
            _tool_msg("file_read", "cleared too"),
            _tool_msg("file_read", "recent"),
        ]
        result, cleared = microcompact(msgs, keep_recent=1)
        assert cleared == 2
        # image_analyze should be untouched
        assert result[1]["content"] == "keep me"
        # Last file_read should be preserved
        assert result[3]["content"] == "recent"

    def test_mixed_message_types(self):
        msgs = [
            _system_msg(),
            _user_msg("q1"),
            _tool_msg("grep", "old grep result"),
            _assistant_msg("a1"),
            _user_msg("q2"),
            _tool_msg("file_read", "old read result"),
            _assistant_msg("a2"),
            _user_msg("q3"),
            _tool_msg("shell", "old shell result"),
            _tool_msg("file_read", "recent read"),
            _assistant_msg("a3"),
        ]
        result, cleared = microcompact(msgs, keep_recent=1)
        assert cleared == 3  # grep + old read + shell
        # Non-tool messages should be untouched
        assert result[0]["content"] == "system prompt"
        assert result[1]["content"] == "q1"
        assert result[3]["content"] == "a1"
        # Most recent tool result preserved
        assert result[9]["content"] == "recent read"

    def test_message_structure_preserved(self):
        """Cleared messages should keep role, name, and other fields."""
        msgs = [
            {"role": "tool", "name": "file_read", "content": "data", "tool_call_id": "abc123"},
            {"role": "tool", "name": "file_read", "content": "recent", "tool_call_id": "def456"},
        ]
        result, cleared = microcompact(msgs, keep_recent=1)
        assert cleared == 1
        assert result[0]["role"] == "tool"
        assert result[0]["name"] == "file_read"
        assert result[0]["tool_call_id"] == "abc123"
        assert result[0]["content"] == _CLEARED_MARKER

    def test_custom_compactable_tools(self):
        msgs = [
            _tool_msg("custom_tool", "old"),
            _tool_msg("custom_tool", "recent"),
        ]
        result, cleared = microcompact(msgs, keep_recent=1, compactable_tools=frozenset({"custom_tool"}))
        assert cleared == 1
        assert result[0]["content"] == _CLEARED_MARKER

    def test_all_compactable_tools(self):
        """Verify all expected tools are in _COMPACTABLE_TOOLS."""
        expected = {"file_read", "file_list", "grep", "shell", "kb_search", "store_recall", "system_info"}
        assert _COMPACTABLE_TOOLS == expected

    def test_empty_messages(self):
        result, cleared = microcompact([])
        assert result == []
        assert cleared == 0

    def test_keep_recent_zero(self):
        """keep_recent=0 should clear ALL compactable tool results."""
        msgs = [_tool_msg("file_read", f"content {i}") for i in range(5)]
        result, cleared = microcompact(msgs, keep_recent=0)
        assert cleared == 5
        for msg in result:
            assert msg["content"] == _CLEARED_MARKER


# ── Time-based clearing tests ────────────────────────────────────────────────

class TestTimeBasedClear:
    def test_no_time_gap(self):
        now = time.time()
        msgs = [
            _assistant_msg("a1", ts=now - 10),
            _tool_msg("file_read", "data"),
            _assistant_msg("a2", ts=now),
        ]
        result, cleared = time_based_clear(msgs, gap_threshold=60)
        assert cleared == 0

    def test_large_time_gap_triggers_clearing(self):
        now = time.time()
        msgs = [
            _assistant_msg("a1", ts=now - 7200),  # 2 hours ago
            _tool_msg("file_read", "old data"),
            _tool_msg("grep", "old grep"),
            _tool_msg("file_read", "old data 2"),
            _tool_msg("file_read", "recent"),
            _assistant_msg("a2", ts=now),
        ]
        result, cleared = time_based_clear(msgs, gap_threshold=3600, keep_recent=1)
        assert cleared == 3  # 3 old tool results cleared

    def test_no_timestamps(self):
        msgs = [
            _assistant_msg("a1"),
            _tool_msg("file_read", "data"),
            _assistant_msg("a2"),
        ]
        result, cleared = time_based_clear(msgs)
        assert cleared == 0

    def test_single_assistant_message(self):
        msgs = [_assistant_msg("only one", ts=time.time())]
        result, cleared = time_based_clear(msgs)
        assert cleared == 0

    def test_exact_threshold(self):
        """Gap exactly at threshold should NOT trigger clearing."""
        now = time.time()
        msgs = [
            _assistant_msg("a1", ts=now - 3600),
            _tool_msg("file_read", "data"),
            _assistant_msg("a2", ts=now),
        ]
        # gap == threshold, should NOT clear (< not <=)
        result, cleared = time_based_clear(msgs, gap_threshold=3600)
        assert cleared == 0


# ── Image stripping tests ────────────────────────────────────────────────────

class TestStripImages:
    def test_no_images(self):
        msgs = [_user_msg("text only")]
        assert strip_images(msgs) == msgs

    def test_image_url_block(self):
        msgs = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "What is this?"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ],
        }]
        result = strip_images(msgs)
        assert len(result[0]["content"]) == 2
        assert result[0]["content"][1] == {"type": "text", "text": "[image]"}

    def test_image_block(self):
        msgs = [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"data": "abc"}},
            ],
        }]
        result = strip_images(msgs)
        assert result[0]["content"][0] == {"type": "text", "text": "[image]"}

    def test_preserves_text_blocks(self):
        msgs = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "image_url", "image_url": {"url": "..."}},
                {"type": "text", "text": "Describe it"},
            ],
        }]
        result = strip_images(msgs)
        assert result[0]["content"][0] == {"type": "text", "text": "Hello"}
        assert result[0]["content"][2] == {"type": "text", "text": "Describe it"}

    def test_string_content_unchanged(self):
        msgs = [_user_msg("just text")]
        result = strip_images(msgs)
        assert result[0]["content"] == "just text"


# ── should_microcompact tests ────────────────────────────────────────────────

class TestShouldMicrocompact:
    def test_below_threshold(self):
        msgs = [_tool_msg("file_read") for _ in range(5)]
        assert should_microcompact(msgs, tool_result_threshold=10) is False

    def test_above_threshold(self):
        msgs = [_tool_msg("file_read") for _ in range(15)]
        assert should_microcompact(msgs, tool_result_threshold=10) is True

    def test_non_compactable_not_counted(self):
        msgs = [_tool_msg("image_analyze") for _ in range(15)]
        assert should_microcompact(msgs, tool_result_threshold=10) is False

    def test_empty_messages(self):
        assert should_microcompact([], tool_result_threshold=0) is False
