"""Task history — log every task run to disk as JSON."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _history_dir() -> Path:
    """Get history directory, respecting AICP_HISTORY_DIR env var."""
    d = Path(os.environ.get("AICP_HISTORY_DIR", Path.home() / ".aicp" / "history"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_task(
    prompt: str,
    mode: str,
    backend: str,
    project: str,
    response: str,
    duration_seconds: float,
    error: Optional[str] = None,
) -> str:
    """Save a task record to disk. Returns the record ID (filename stem)."""
    now = datetime.utcnow()
    record_id = now.strftime("%Y%m%d_%H%M%S_%f") + f"_{backend}_{mode}"

    record = {
        "id": record_id,
        "timestamp": now.isoformat() + "Z",
        "prompt": prompt,
        "mode": mode,
        "backend": backend,
        "project": project,
        "response": response,
        "duration_seconds": round(duration_seconds, 2),
        "error": error,
    }

    path = _history_dir() / f"{record_id}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    return record_id


def list_tasks(count: int = 20) -> List[Dict[str, Any]]:
    """List recent task records, newest first."""
    d = _history_dir()
    files = sorted(d.glob("*.json"), reverse=True)

    records = []
    for f in files[:count]:
        try:
            with open(f) as fh:
                records.append(json.load(fh))
        except (json.JSONDecodeError, OSError):
            continue
    return records


def get_task(record_id: str) -> Optional[Dict[str, Any]]:
    """Load a single task record by ID."""
    path = _history_dir() / f"{record_id}.json"
    if not path.exists():
        # Try partial match
        matches = list(_history_dir().glob(f"*{record_id}*.json"))
        if len(matches) == 1:
            path = matches[0]
        elif len(matches) > 1:
            return None  # ambiguous
        else:
            return None

    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None