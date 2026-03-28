"""Tests for aicp.core.chunking."""

import pytest
from pathlib import Path

from aicp.core.chunking import chunk_text, chunk_file


class TestChunkText:
    def test_empty_string(self):
        assert chunk_text("") == []

    def test_whitespace_only(self):
        assert chunk_text("   \n\n  ") == []

    def test_short_text_single_chunk(self):
        text = "Hello world"
        result = chunk_text(text, chunk_size=512)
        assert result == ["Hello world"]

    def test_text_at_exact_limit(self):
        text = "x" * 512
        result = chunk_text(text, chunk_size=512)
        assert len(result) == 1
        assert result[0] == text

    def test_splits_on_newline(self):
        lines = ["Line " + str(i) for i in range(50)]
        text = "\n".join(lines)
        result = chunk_text(text, chunk_size=100, chunk_overlap=0)
        assert len(result) > 1
        # Each chunk should be under the size limit (with some tolerance for last segment)
        for chunk in result:
            assert len(chunk) <= 120  # allow minor overrun from segment boundary

    def test_overlap_provides_context(self):
        """Adjacent chunks should share some text when overlap > 0."""
        lines = [f"Sentence number {i} provides some content." for i in range(30)]
        text = "\n".join(lines)
        result = chunk_text(text, chunk_size=200, chunk_overlap=50)
        assert len(result) >= 2
        # Check that there's overlap between consecutive chunks
        for i in range(len(result) - 1):
            # The end of chunk i should appear in the start of chunk i+1
            tail = result[i].split("\n")[-1]
            if tail.strip():
                assert tail in result[i + 1], f"Expected overlap at boundary {i}/{i+1}"

    def test_force_split_long_segment(self):
        """A single line longer than chunk_size gets force-split."""
        text = "x" * 2000
        result = chunk_text(text, chunk_size=500, chunk_overlap=50)
        assert len(result) >= 4
        for chunk in result:
            assert len(chunk) <= 500

    def test_no_empty_chunks(self):
        text = "\n\n\nHello\n\n\nWorld\n\n\n"
        result = chunk_text(text, chunk_size=512)
        for chunk in result:
            assert chunk.strip() != ""


class TestChunkFile:
    def test_chunk_file_returns_metadata(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Line 1\nLine 2\nLine 3\n")
        result = chunk_file(f, chunk_size=512)
        assert len(result) >= 1
        assert result[0]["source"] == str(f)
        assert result[0]["chunk_index"] == 0
        assert "Line 1" in result[0]["text"]

    def test_chunk_file_multiple_chunks(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("\n".join([f"Content line {i}" for i in range(100)]))
        result = chunk_file(f, chunk_size=100, chunk_overlap=20)
        assert len(result) > 1
        # All chunks should reference the same source
        for chunk in result:
            assert chunk["source"] == str(f)
        # Indices should be sequential
        indices = [c["chunk_index"] for c in result]
        assert indices == list(range(len(result)))
