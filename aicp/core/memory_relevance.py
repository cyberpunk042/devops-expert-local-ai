"""Memory relevance scoring and aging for AICP.

Inspired by Claude Code's memdir system. Uses local nomic-embed embeddings
for relevance scoring instead of their cloud Sonnet call — free, fast,
deterministic.

Key features:
  - Scan memory files and extract frontmatter metadata
  - Compute memory age and staleness warnings
  - Select top-K most relevant memories for a query using embeddings
  - Cache embeddings to avoid redundant computation
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger("aicp.memory")

# Maximum memory files to scan (prevents runaway on large dirs)
MAX_MEMORY_FILES = 200

# Maximum lines to read from each file for frontmatter extraction
MAX_FRONTMATTER_LINES = 30

# Default number of memories to surface per query
DEFAULT_TOP_K = 5

# Staleness threshold in seconds (1 day)
STALENESS_THRESHOLD_SECONDS = 86_400


@dataclass
class MemoryHeader:
    """Metadata extracted from a memory file's frontmatter."""
    filename: str          # relative path within memory dir
    filepath: str          # absolute path
    mtime: float           # modification time (epoch seconds)
    name: str = ""
    description: str = ""
    memory_type: str = ""  # user, feedback, project, reference


@dataclass
class ScoredMemory:
    """A memory file with relevance score."""
    header: MemoryHeader
    score: float
    content: str = ""
    age_text: str = ""
    staleness_warning: str = ""


# ── Memory aging ─────────────────────────────────────────────────────────────

def memory_age_days(mtime: float) -> int:
    """Return floor-rounded days since modification."""
    return max(0, int((time.time() - mtime) / 86_400))


def memory_age_text(mtime: float) -> str:
    """Return human-readable age string."""
    days = memory_age_days(mtime)
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


def memory_freshness_warning(mtime: float) -> str:
    """Return staleness warning for memories older than 1 day.

    Empty string if memory is fresh.
    """
    days = memory_age_days(mtime)
    if days <= 1:
        return ""
    return (
        f"This memory was last updated {memory_age_text(mtime)}. "
        "Claims about code behavior or file:line citations may be outdated — "
        "verify against current code before acting."
    )


# ── Memory scanning ──────────────────────────────────────────────────────────

def _parse_frontmatter(filepath: str, max_lines: int = MAX_FRONTMATTER_LINES) -> Dict[str, str]:
    """Extract YAML frontmatter from a markdown file.

    Reads only the first max_lines lines to avoid loading large files.
    Returns empty dict if no valid frontmatter found.
    """
    try:
        with open(filepath, "r", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line)

        text = "".join(lines)
        if not text.startswith("---"):
            return {}

        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}

        parsed = yaml.safe_load(parts[1])
        return parsed if isinstance(parsed, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}


def scan_memory_files(memory_dir: str | Path) -> List[MemoryHeader]:
    """Scan a memory directory for .md files with frontmatter.

    Excludes MEMORY.md (the index file). Returns headers sorted by
    mtime descending (newest first), capped at MAX_MEMORY_FILES.
    """
    memory_dir = Path(memory_dir)
    if not memory_dir.is_dir():
        return []

    headers = []
    for md_file in memory_dir.rglob("*.md"):
        if md_file.name == "MEMORY.md":
            continue
        if len(headers) >= MAX_MEMORY_FILES:
            break

        try:
            mtime = md_file.stat().st_mtime
        except OSError:
            continue

        frontmatter = _parse_frontmatter(str(md_file))
        headers.append(MemoryHeader(
            filename=str(md_file.relative_to(memory_dir)),
            filepath=str(md_file),
            mtime=mtime,
            name=frontmatter.get("name", ""),
            description=frontmatter.get("description", ""),
            memory_type=frontmatter.get("type", ""),
        ))

    # Sort by mtime descending (newest first)
    headers.sort(key=lambda h: h.mtime, reverse=True)
    return headers[:MAX_MEMORY_FILES]


def format_memory_manifest(headers: List[MemoryHeader]) -> str:
    """Format memory headers as a compact manifest string.

    Each line: - [type] filename (age): description
    """
    lines = []
    for h in headers:
        age = memory_age_text(h.mtime)
        type_tag = f"[{h.memory_type}] " if h.memory_type else ""
        desc = h.description or h.name or "(no description)"
        lines.append(f"- {type_tag}{h.filename} ({age}): {desc}")
    return "\n".join(lines)


# ── Embedding-based relevance scoring ────────────────────────────────────────

class MemoryRelevanceScorer:
    """Scores memory relevance using nomic-embed embeddings.

    Caches description embeddings to avoid redundant computation.
    The cache key is (filepath, mtime) — invalidated when file changes.
    """

    def __init__(self, embed_fn=None) -> None:
        """Initialize with an embedding function.

        embed_fn: Callable[[str], List[float]] — takes text, returns embedding vector.
                  If None, relevance scoring falls back to keyword matching.
        """
        self._embed_fn = embed_fn
        self._cache: Dict[Tuple[str, float], List[float]] = {}

    def _get_embedding(self, text: str, filepath: str = "", mtime: float = 0.0) -> Optional[List[float]]:
        """Get embedding for text, using cache if available."""
        if self._embed_fn is None:
            return None

        cache_key = (filepath, mtime) if filepath else None
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            embedding = self._embed_fn(text)
            if cache_key:
                self._cache[cache_key] = embedding
            return embedding
        except Exception as e:
            logger.warning("Embedding failed for '%s': %s", text[:50], e)
            return None

    def _keyword_score(self, query: str, header: MemoryHeader) -> float:
        """Fallback: simple keyword overlap score (0.0-1.0)."""
        query_words = set(query.lower().split())
        target_words = set()
        for text in [header.name, header.description, header.memory_type]:
            target_words.update(text.lower().split())

        if not query_words or not target_words:
            return 0.0

        overlap = len(query_words & target_words)
        return overlap / max(len(query_words), 1)

    def score(self, query: str, headers: List[MemoryHeader]) -> List[ScoredMemory]:
        """Score all memories against a query.

        Returns ScoredMemory list sorted by score descending.
        Uses embeddings if available, falls back to keyword matching.
        """
        query_embedding = self._get_embedding(query) if self._embed_fn else None
        results = []

        for header in headers:
            # Build searchable text from frontmatter
            search_text = " ".join(filter(None, [
                header.name, header.description, header.memory_type,
            ]))

            if query_embedding is not None:
                # Use embedding similarity
                desc_embedding = self._get_embedding(
                    search_text, header.filepath, header.mtime
                )
                if desc_embedding is not None:
                    score = _cosine_similarity(query_embedding, desc_embedding)
                else:
                    score = self._keyword_score(query, header)
            else:
                score = self._keyword_score(query, header)

            results.append(ScoredMemory(
                header=header,
                score=score,
                age_text=memory_age_text(header.mtime),
                staleness_warning=memory_freshness_warning(header.mtime),
            ))

        results.sort(key=lambda m: m.score, reverse=True)
        return results

    def select_relevant(
        self,
        query: str,
        headers: List[MemoryHeader],
        top_k: int = DEFAULT_TOP_K,
        threshold: float = 0.1,
    ) -> List[ScoredMemory]:
        """Select the top-K most relevant memories above threshold.

        Returns scored memories with content loaded from disk.
        """
        scored = self.score(query, headers)
        selected = [m for m in scored if m.score >= threshold][:top_k]

        # Load content for selected memories
        for memory in selected:
            try:
                content = Path(memory.header.filepath).read_text(errors="replace")
                memory.content = content
            except OSError:
                memory.content = "(failed to read)"

        return selected

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        return len(self._cache)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
