"""Project context builder — gives AI backends awareness of the project."""

from __future__ import annotations

from pathlib import Path
from typing import List

# Files to read for project context (in priority order)
_CONTEXT_FILES = ["README.md", "CLAUDE.md", "pyproject.toml", "package.json", "Cargo.toml"]

# Dirs to skip in tree
_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", "models", "backends"}


def build_project_context(project_path: Path, max_chars: int = 2000) -> str:
    """Build a text summary of the project: structure + key files.

    Args:
        project_path: Root of the project.
        max_chars: Max total characters for the context string.
    """
    sections = []
    total = 0

    # Directory tree (depth 2)
    tree = _dir_tree(project_path, max_depth=2)
    if tree:
        section = f"Project structure:\n{tree}"
        sections.append(section)
        total += len(section)

    # Key files content
    for filename in _CONTEXT_FILES:
        if total >= max_chars:
            break
        filepath = project_path / filename
        if filepath.is_file():
            try:
                content = filepath.read_text(errors="replace")
                remaining = max_chars - total
                if len(content) > remaining:
                    content = content[:remaining] + "\n... (truncated)"
                section = f"Contents of {filename}:\n{content}"
                sections.append(section)
                total += len(section)
            except OSError:
                pass

    return "\n\n".join(sections)


def _dir_tree(path: Path, max_depth: int = 2, prefix: str = "") -> str:
    """Build a simple directory tree string."""
    if max_depth < 0:
        return ""
    lines = []  # type: List[str]
    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    except OSError:
        return ""

    entries = [e for e in entries if e.name not in _SKIP_DIRS]

    for i, entry in enumerate(entries[:30]):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir() and max_depth > 0:
            extension = "    " if is_last else "│   "
            subtree = _dir_tree(entry, max_depth - 1, prefix + extension)
            if subtree:
                lines.append(subtree)

    return "\n".join(lines)
