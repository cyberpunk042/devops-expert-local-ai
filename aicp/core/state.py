"""AICP runtime state — `.aicp/state.yaml` read/write helpers.

The state file holds: active_task (e.g. "T001"), active_stage (e.g. "implement"),
mode (think|edit|act), updated (ISO 8601). Read by `tools/hooks/pretool_safety.py`
for Layer B stage-gate enforcement; written by `aicp task switch` CLI subcommand
and by feature-* skills as they advance task stages.

See wiki/decisions/01_drafts/aicp-active-state-mechanism-for-hooks.md for the
design rationale.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = REPO_ROOT / ".aicp"
STATE_FILE = STATE_DIR / "state.yaml"
TASKS_DIR = REPO_ROOT / "wiki" / "backlog" / "tasks"

VALID_MODES = {"think", "edit", "act"}
VALID_STAGES = {"document", "design", "scaffold", "implement", "test", "done"}
TASK_ID_RE = re.compile(r"^T\d+$")


def read_state() -> dict[str, Any] | None:
    """Read .aicp/state.yaml; returns dict or None if missing/unreadable."""
    if not STATE_FILE.exists():
        return None
    try:
        return yaml.safe_load(STATE_FILE.read_text(encoding="utf-8")) or None
    except (yaml.YAMLError, OSError):
        return None


def write_state(active_task: str, active_stage: str, mode: str = "edit") -> Path:
    """Write .aicp/state.yaml with validation. Returns the file path written."""
    if not TASK_ID_RE.match(active_task):
        raise ValueError(f"active_task must match T<NNN> (got: {active_task!r})")
    if active_stage not in VALID_STAGES:
        raise ValueError(f"active_stage must be one of {sorted(VALID_STAGES)} (got: {active_stage!r})")
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)} (got: {mode!r})")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "active_task": active_task,
        "active_stage": active_stage,
        "mode": mode,
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    STATE_FILE.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return STATE_FILE


def find_task_file(task_id: str) -> Path | None:
    """Find wiki/backlog/tasks/<task_id>-*.md; returns the path or None."""
    if not TASKS_DIR.exists():
        return None
    matches = list(TASKS_DIR.glob(f"{task_id}-*.md"))
    return matches[0] if matches else None


def read_task_stage(task_id: str) -> str | None:
    """Read current_stage from a task file's frontmatter."""
    task_file = find_task_file(task_id)
    if not task_file:
        return None
    text = task_file.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm_match:
        return None
    try:
        meta = yaml.safe_load(fm_match.group(1)) or {}
        return meta.get("current_stage")
    except yaml.YAMLError:
        return None


def list_tasks() -> list[dict[str, str]]:
    """List all tasks in wiki/backlog/tasks/, returning [{id, slug, stage, status, file}]."""
    if not TASKS_DIR.exists():
        return []
    out = []
    for path in sorted(TASKS_DIR.glob("T*-*.md")):
        match = re.match(r"^(T\d+)-(.+)\.md$", path.name)
        if not match:
            continue
        task_id, slug = match.group(1), match.group(2)
        stage = read_task_stage(task_id) or "?"
        # Read status too
        text = path.read_text(encoding="utf-8")
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        status = "?"
        if fm_match:
            try:
                meta = yaml.safe_load(fm_match.group(1)) or {}
                status = meta.get("status", "?")
            except yaml.YAMLError:
                pass
        out.append({
            "id": task_id,
            "slug": slug,
            "stage": stage,
            "status": status,
            "file": str(path.relative_to(REPO_ROOT)),
        })
    return out


def clear_state() -> bool:
    """Remove .aicp/state.yaml. Returns True if removed, False if absent."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        return True
    return False
