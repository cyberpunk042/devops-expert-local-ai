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


def check_forbidden_path(
    project_path: Path,
    mode: Mode,
    config: Dict[str, Any],
) -> List[str]:
    """Block Edit/Act tasks targeting forbidden or out-of-scope paths.

    Checks two things:
    1. Forbidden patterns — blocks .env, .ssh, *.key, *secret*, etc.
    2. allowed_paths — if configured, the project must be within one of them.
    """
    if mode == Mode.THINK:
        return []  # read-only mode: no restriction needed

    from aicp.guardrails.paths import get_forbidden_patterns, is_path_allowed

    forbidden_patterns = get_forbidden_patterns(config)

    # Resolve allowed_paths from config (optional — restricts scope of Edit/Act)
    raw_allowed = config.get("guardrails", {}).get("allowed_paths")
    allowed_paths = [Path(p) for p in raw_allowed] if raw_allowed else None

    if not is_path_allowed(
        project_path,
        project_path.parent,
        allowed_paths=allowed_paths,
        forbidden_patterns=forbidden_patterns,
    ):
        if allowed_paths and not any(
            project_path.resolve() == ap.resolve()
            or str(project_path.resolve()).startswith(str(ap.resolve()))
            for ap in allowed_paths
        ):
            return [
                f"Refusing to run {mode.value} mode on '{project_path}' — "
                "not in guardrails.allowed_paths. "
                "Add the path to allowed_paths in config or ~/.aicp/config.yaml."
            ]
        return [
            f"Refusing to run {mode.value} mode on '{project_path}' — "
            "it matches a forbidden pattern (secrets/credentials)."
        ]
    return []


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
    results.extend(check_forbidden_path(project_path, mode, config))

    return results
