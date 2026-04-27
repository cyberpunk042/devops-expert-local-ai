"""Auto-extraction of learnable facts from task history into memory files.

Inspired by Claude Code's extractMemories.ts. Scans recent task history
and extracts notable patterns, errors, and decisions into persistent
memory files for future conversations.

This runs as a periodic background job or on-demand via CLI.
Uses the local LLM (when warm) to decide what's worth remembering.
Falls back to heuristic extraction when no LLM is available.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("aicp.memory_extract")

# Maximum tasks to analyze per extraction run
MAX_TASKS_PER_RUN = 30

# Minimum task count before extraction runs
MIN_TASKS_THRESHOLD = 5

# Patterns that suggest extractable knowledge
_ERROR_PATTERNS = [
    r"(?i)fix(?:ed)?[:\s]",
    r"(?i)workaround[:\s]",
    r"(?i)solution[:\s]",
    r"(?i)resolved[:\s]",
    r"(?i)the (?:issue|problem|bug) (?:was|is)",
]

_DECISION_PATTERNS = [
    r"(?i)decided to",
    r"(?i)chose .+ over",
    r"(?i)switched (?:to|from)",
    r"(?i)replaced .+ with",
    r"(?i)upgraded? (?:to|from)",
    r"(?i)prefer(?:red|s)?",
]

_LEARNING_PATTERNS = [
    r"(?i)learned that",
    r"(?i)discovered that",
    r"(?i)found that",
    r"(?i)turns out",
    r"(?i)important(?:ly)?[:\s]",
    r"(?i)note[:\s]",
    r"(?i)key (?:finding|insight|takeaway)",
]


@dataclass
class ExtractedFact:
    """A fact extracted from task history."""
    content: str
    source_task_id: str
    memory_type: str  # user, feedback, project, reference
    confidence: float  # 0.0 - 1.0
    category: str  # error_fix, decision, learning, pattern


def _classify_fact(text: str) -> tuple[str, str, float]:
    """Classify extracted text into memory type and category.

    Returns (memory_type, category, confidence).
    """
    text_lower = text.lower()

    # Check for error/fix patterns -> project memory
    for pattern in _ERROR_PATTERNS:
        if re.search(pattern, text):
            return "project", "error_fix", 0.7

    # Check for decision patterns -> project or feedback
    for pattern in _DECISION_PATTERNS:
        if re.search(pattern, text):
            if any(w in text_lower for w in ("user", "prefer", "style", "convention")):
                return "feedback", "decision", 0.6
            return "project", "decision", 0.6

    # Check for learning patterns -> project or reference
    for pattern in _LEARNING_PATTERNS:
        if re.search(pattern, text):
            if any(w in text_lower for w in ("url", "link", "docs", "wiki", "repo")):
                return "reference", "learning", 0.5
            return "project", "learning", 0.5

    return "project", "pattern", 0.3


def extract_facts_heuristic(tasks: list[dict[str, Any]]) -> list[ExtractedFact]:
    """Extract notable facts from task history using heuristics.

    This is the fallback extractor when no LLM is available.
    It scans prompts and responses for patterns that suggest
    learnable information.
    """
    facts = []
    seen_content = set()

    for task in tasks:
        task_id = task.get("id", "unknown")
        response = task.get("response", "")
        prompt = task.get("prompt", "")
        error = task.get("error")

        # Extract from errors (always interesting)
        if error:
            fact_text = f"Error encountered: {error[:200]}"
            if fact_text not in seen_content:
                seen_content.add(fact_text)
                facts.append(ExtractedFact(
                    content=fact_text,
                    source_task_id=task_id,
                    memory_type="project",
                    confidence=0.6,
                    category="error_fix",
                ))

        # Scan response for extractable patterns
        if response:
            sentences = _split_sentences(response)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20 or len(sentence) > 300:
                    continue

                mem_type, category, confidence = _classify_fact(sentence)
                if confidence >= 0.5:
                    if sentence not in seen_content:
                        seen_content.add(sentence)
                        facts.append(ExtractedFact(
                            content=sentence,
                            source_task_id=task_id,
                            memory_type=mem_type,
                            confidence=confidence,
                            category=category,
                        ))

    # Sort by confidence descending
    facts.sort(key=lambda f: f.confidence, reverse=True)
    return facts[:20]  # cap at 20 facts per run


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences (simple heuristic)."""
    # Split on period followed by space and capital, or newline
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])|(?:\n\s*\n)', text)
    return [p.strip() for p in parts if p.strip()]


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s_]+', '_', slug)
    return slug[:50].strip('_')


def save_extracted_fact(
    fact: ExtractedFact,
    memory_dir: Path,
    overwrite: bool = False,
) -> Path | None:
    """Save an extracted fact as a memory file.

    Returns the file path if saved, None if skipped (already exists).
    """
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename from category and content
    slug = _slugify(fact.content[:60])
    filename = f"{fact.memory_type}_{fact.category}_{slug}.md"
    filepath = memory_dir / filename

    if filepath.exists() and not overwrite:
        return None

    # Build memory file with frontmatter
    now = datetime.utcnow().strftime("%Y-%m-%d")
    name = fact.content[:80].replace("\n", " ")

    content = f"""---
name: "{name}"
description: "Auto-extracted from task {fact.source_task_id} ({fact.category})"
type: {fact.memory_type}
---

{fact.content}

**Extracted:** {now} (confidence: {fact.confidence:.1f}, source: {fact.source_task_id})
"""

    try:
        filepath.write_text(content)
        logger.info("Saved extracted memory: %s", filename)
        return filepath
    except OSError as e:
        logger.warning("Failed to save memory %s: %s", filename, e)
        return None


def run_extraction(
    memory_dir: Path,
    task_count: int = MAX_TASKS_PER_RUN,
    min_confidence: float = 0.5,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Run the extraction pipeline on recent task history.

    Args:
        memory_dir: Directory to save memory files.
        task_count: Number of recent tasks to analyze.
        min_confidence: Minimum confidence threshold for saving.
        dry_run: If True, don't write files, just return what would be extracted.

    Returns:
        List of dicts describing extracted/saved facts.
    """
    from aicp.core.history import list_tasks

    tasks = list_tasks(count=task_count)
    if len(tasks) < MIN_TASKS_THRESHOLD:
        logger.info("Not enough tasks (%d < %d) for extraction", len(tasks), MIN_TASKS_THRESHOLD)
        return []

    # Check existing memories to avoid duplicates
    from aicp.core.memory_relevance import scan_memory_files
    existing = scan_memory_files(memory_dir)
    existing_descriptions = {h.description for h in existing if h.description}

    facts = extract_facts_heuristic(tasks)
    results = []

    for fact in facts:
        if fact.confidence < min_confidence:
            continue

        # Skip if similar content already exists in memory
        desc_preview = f"Auto-extracted from task {fact.source_task_id} ({fact.category})"
        if desc_preview in existing_descriptions:
            continue

        result = {
            "content": fact.content[:200],
            "type": fact.memory_type,
            "category": fact.category,
            "confidence": fact.confidence,
            "source": fact.source_task_id,
        }

        if not dry_run:
            path = save_extracted_fact(fact, memory_dir)
            if path:
                result["saved_to"] = str(path)
            else:
                result["skipped"] = "already exists"
        else:
            result["dry_run"] = True

        results.append(result)

    logger.info("Extraction complete: %d facts from %d tasks", len(results), len(tasks))
    return results
