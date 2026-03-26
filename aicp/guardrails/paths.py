"""Path-based guardrails — protect sensitive files and directories."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional


# Patterns that should never be read or modified
FORBIDDEN_PATTERNS = [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*credentials*",
    "*secret*",
    ".ssh/",
    ".gnupg/",
]


def is_path_allowed(path: Path, project_root: Path, allowed_paths: Optional[List[Path]] = None) -> bool:
    """Check if a path is safe to access.

    Returns False for forbidden patterns and paths outside the project root.
    """
    # Must be within project root
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return False

    # Check forbidden patterns
    name = path.name.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.startswith("*") and name.endswith(pattern[1:]):
            return False
        if pattern.endswith("*") and name.startswith(pattern[:-1]):
            return False
        if name == pattern or name == pattern.rstrip("/"):
            return False

    # If allowed_paths specified, path must be within one of them
    if allowed_paths is not None:
        resolved = path.resolve()

        def _is_relative_to(p: Path, base: Path) -> bool:
            try:
                p.relative_to(base)
                return True
            except ValueError:
                return False

        return any(
            resolved == ap.resolve() or _is_relative_to(resolved, ap.resolve())
            for ap in allowed_paths
        )

    return True
