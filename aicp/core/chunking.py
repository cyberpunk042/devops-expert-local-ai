"""Text chunking strategies for RAG pipelines."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    separator: str = "\n",
) -> List[str]:
    """Split text into overlapping chunks.

    Uses a separator-aware strategy: splits on the separator first,
    then merges segments into chunks that respect the size limit.

    Args:
        text: The text to chunk.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap between consecutive chunks.
        separator: Preferred split boundary (newline by default).

    Returns:
        List of text chunks.
    """
    if not text or not text.strip():
        return []

    if len(text) <= chunk_size:
        return [text.strip()]

    # Split on separator, preserving segments
    segments = text.split(separator)
    segments = [s for s in segments if s.strip()]

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for segment in segments:
        seg_len = len(segment) + len(separator)

        # If a single segment exceeds chunk_size, force-split it
        if seg_len > chunk_size:
            # Flush current buffer first
            if current:
                chunks.append(separator.join(current).strip())
                current, current_len = _overlap_segments(
                    current, separator, chunk_overlap,
                )

            for sub in _force_split(segment, chunk_size, chunk_overlap):
                chunks.append(sub.strip())
            continue

        # Would adding this segment exceed the limit?
        if current_len + seg_len > chunk_size and current:
            chunks.append(separator.join(current).strip())
            current, current_len = _overlap_segments(
                current, separator, chunk_overlap,
            )

        current.append(segment)
        current_len += seg_len

    # Flush remaining
    if current:
        chunk = separator.join(current).strip()
        if chunk:
            chunks.append(chunk)

    return [c for c in chunks if c]


def chunk_file(
    path: Path,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> List[dict]:
    """Read a file and return chunks with metadata.

    Returns:
        List of dicts: {"text": str, "source": str, "chunk_index": int}
    """
    text = path.read_text(errors="replace")
    chunks = chunk_text(text, chunk_size, chunk_overlap)
    source = str(path)
    return [
        {"text": c, "source": source, "chunk_index": i}
        for i, c in enumerate(chunks)
    ]


def _overlap_segments(
    segments: List[str],
    separator: str,
    overlap: int,
) -> tuple[List[str], int]:
    """Return the tail segments that fit within the overlap budget."""
    if overlap <= 0:
        return [], 0

    result: List[str] = []
    total = 0
    for seg in reversed(segments):
        seg_len = len(seg) + len(separator)
        if total + seg_len > overlap:
            break
        result.insert(0, seg)
        total += seg_len

    return result, total


def _force_split(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split a single long segment into fixed-size pieces."""
    pieces: List[str] = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(text):
        pieces.append(text[start : start + chunk_size])
        start += step
    return pieces
