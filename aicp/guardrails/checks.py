"""Pre-execution guardrail checks — validated before any backend call."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from aicp.core.modes import Mode
from aicp.guardrails.paths import is_path_allowed


# Paths that should never be used as project roots
_DANGEROUS_ROOTS = ["/", "/root", "/home", "/etc", "/var", "/usr", "/tmp"]


def check_project_path(project_path: Path) -> List[str]:
    """Validate the project path is safe to operate on."""
    errors = []

    if not project_path.exists():
        errors.append(f"Project path does not exist: {project_path}")
        return errors

    if not project_path.is_dir():
        errors.append(f"Project path is not a directory: {project_path}")
        return errors

    resolved = str(project_path.resolve())
    home = str(Path.home().resolve())

    for dangerous in _DANGEROUS_ROOTS:
        if resolved == dangerous:
            errors.append(
                f"Refusing to operate on '{resolved}' — too broad. "
                "Point AICP at a specific project directory."
            )
            break

    if resolved == home:
        errors.append(
            "Refusing to operate on your entire home directory. "
            "Point AICP at a specific project directory."
        )

    return errors


def check_mode_compatibility(mode: Mode, backend_name: str) -> List[str]:
    """Validate that the mode is compatible with the backend.

    Documents enforcement reality:
    - Claude Code: hard enforcement via CLI flags
    - LocalAI: advisory enforcement via system prompt only
    """
    warnings = []

    if backend_name == "local" and mode in (Mode.EDIT, Mode.ACT):
        warnings.append(
            f"WARNING: {mode.value} mode with LocalAI is advisory only. "
            "The local model may not respect mode constraints. "
            "For hard enforcement, use --backend claude."
        )

    return warnings


def run_preflight_checks(
    project_path: Path,
    mode: Mode,
    backend_name: str,
    config: Dict[str, Any],
) -> List[str]:
    """Run all pre-execution checks. Returns list of errors/warnings."""
    results = []

    results.extend(check_project_path(project_path))
    results.extend(check_mode_compatibility(mode, backend_name))

    return results
