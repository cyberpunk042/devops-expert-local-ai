"""Project registry — track projects AICP manages across sessions."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def _global_registry_path() -> Path:
    """AICP-side project index."""
    return Path(os.environ.get("AICP_HOME", Path.home() / ".aicp")) / "projects.yaml"


def _project_state_dir(project_path: Path) -> Path:
    """Per-project .aicp/ directory."""
    d = project_path / ".aicp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _project_state_path(project_path: Path) -> Path:
    return _project_state_dir(project_path) / "state.yaml"


# --- Global registry (cross-project) ---

def register_project(
    project_path: Path,
    name: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    """Register a project in the AICP global registry."""
    project_path = project_path.resolve()
    if name is None:
        name = project_path.name

    registry = _load_registry()
    entry = {
        "name": name,
        "path": str(project_path),
        "description": description,
        "registered": datetime.utcnow().isoformat() + "Z",
    }

    # Update or add
    registry["projects"] = [
        p for p in registry.get("projects", [])
        if p.get("path") != str(project_path)
    ]
    registry["projects"].append(entry)
    _save_registry(registry)

    # Initialize project state if it doesn't exist
    state_path = _project_state_path(project_path)
    if not state_path.exists():
        init_project_state(project_path, name, description)

    return entry


def unregister_project(project_path: Path) -> bool:
    """Remove a project from the global registry."""
    project_path = project_path.resolve()
    registry = _load_registry()
    before = len(registry.get("projects", []))
    registry["projects"] = [
        p for p in registry.get("projects", [])
        if p.get("path") != str(project_path)
    ]
    _save_registry(registry)
    return len(registry.get("projects", [])) < before


def list_projects() -> List[Dict[str, Any]]:
    """List all registered projects."""
    registry = _load_registry()
    return registry.get("projects", [])


def _load_registry() -> Dict[str, Any]:
    path = _global_registry_path()
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {"projects": []}
    return {"projects": []}


def _save_registry(data: Dict[str, Any]) -> None:
    path = _global_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# --- Per-project state ---

def init_project_state(
    project_path: Path,
    name: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """Initialize .aicp/state.yaml for a project."""
    state = {
        "name": name or project_path.name,
        "description": description,
        "created": datetime.utcnow().isoformat() + "Z",
        "phase": "init",
        "milestones": [],
        "decisions": [],
        "last_session": None,
    }
    save_project_state(project_path, state)
    return state


def load_project_state(project_path: Path) -> Optional[Dict[str, Any]]:
    """Load a project's .aicp/state.yaml."""
    path = _project_state_path(project_path)
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def save_project_state(project_path: Path, state: Dict[str, Any]) -> None:
    """Save project state to .aicp/state.yaml."""
    path = _project_state_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=False)


def update_session(project_path: Path, summary: str = "") -> None:
    """Update the last session timestamp and summary."""
    state = load_project_state(project_path)
    if state is None:
        state = init_project_state(project_path)
    state["last_session"] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
    }
    save_project_state(project_path, state)


def add_milestone(
    project_path: Path,
    name: str,
    description: str = "",
    status: str = "pending",
) -> None:
    """Add a milestone to the project state."""
    state = load_project_state(project_path)
    if state is None:
        state = init_project_state(project_path)
    state["milestones"].append({
        "name": name,
        "description": description,
        "status": status,
        "created": datetime.utcnow().isoformat() + "Z",
    })
    save_project_state(project_path, state)


def update_milestone(project_path: Path, name: str, status: str) -> bool:
    """Update a milestone's status. Returns True if found."""
    state = load_project_state(project_path)
    if state is None:
        return False
    for m in state.get("milestones", []):
        if m["name"] == name:
            m["status"] = status
            m["updated"] = datetime.utcnow().isoformat() + "Z"
            save_project_state(project_path, state)
            return True
    return False


def add_decision(project_path: Path, decision: str, context: str = "") -> None:
    """Record a decision in the project state."""
    state = load_project_state(project_path)
    if state is None:
        state = init_project_state(project_path)
    state["decisions"].append({
        "decision": decision,
        "context": context,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })
    save_project_state(project_path, state)
