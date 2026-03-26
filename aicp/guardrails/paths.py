"""Path-based guardrails — protect sensitive files and directories."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


# Default patterns — used when config doesn't specify any
DEFAULT_FORBIDDEN_PATTERNS = [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*credentials*",
    "*secret*",
    ".ssh/",
    ".gnupg/",
]


def get_forbidden_patterns(config: Optional[Dict[str, Any]] = None) -> List[str]:
    """Get forbidden patterns from config, falling back to defaults."""
    if config is not None:
        patterns = config.get("guardrails", {}).get("forbidden_patterns")
        if patterns is not None:
            return patterns
    return DEFAULT_FORBIDDEN_PATTERNS


def is_path_allowed(
    path: Path,
    project_root: Path,
    allowed_paths: Optional[List[Path]] = None,
    forbidden_patterns: Optional[List[str]] = None,
) -> bool:
    """Check if a path is safe to access.

    Returns False for forbidden patterns and paths outside the project root.
    """
    if forbidden_patterns is None:
        forbidden_patterns = DEFAULT_FORBIDDEN_PATTERNS

    # Must be within project root
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return False

    # Check forbidden patterns
    name = path.name.lower()
    for pattern in forbidden_patterns:
        pattern = pattern.lower()
        if pattern.startswith("*") and pattern.endswith("*") and len(pattern) > 2:
            # *credentials* — match anywhere in name
            if pattern[1:-1] in name:
                return False
        elif pattern.startswith("*") and name.endswith(pattern[1:]):
            return False
        elif pattern.endswith("*") and name.startswith(pattern[:-1]):
            return False
        elif name == pattern or name == pattern.rstrip("/"):
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
