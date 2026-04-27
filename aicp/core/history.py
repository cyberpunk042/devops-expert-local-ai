"""Task history — log every task run to disk as JSON."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _append_event_log(record: dict[str, Any]) -> None:
    """Append a JSON-line entry to AICP_LOG_FILE if the env var is set.

    Each line is a self-contained JSON object (newline-delimited JSON / JSONL),
    making it easy to stream-process with jq or import into log aggregators.
    The full response body is excluded to keep the log compact — history files
    in ~/.aicp/history/ hold the full records.
    """
    log_path = os.environ.get("AICP_LOG_FILE")
    if not log_path:
        return

    entry = {
        "ts": record.get("timestamp"),
        "id": record.get("id"),
        "mode": record.get("mode"),
        "backend": record.get("backend"),
        "model": record.get("model"),
        "project": record.get("project"),
        "duration_s": record.get("duration_seconds"),
        "prompt_tokens": record.get("prompt_tokens"),
        "completion_tokens": record.get("completion_tokens"),
        "total_tokens": record.get("total_tokens"),
        "cost_usd": record.get("estimated_cost_usd"),
        "error": record.get("error"),
        # Truncated prompt for log correlation — full text is in the history file
        "prompt_preview": (record.get("prompt") or "")[:120],
    }

    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Never crash the main flow due to logging failure


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
    error: str | None = None,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    route: str | None = None,
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
        "model": model,
        "route": route,
        "project": project,
        "response": response,
        "duration_seconds": round(duration_seconds, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": (prompt_tokens or 0) + (completion_tokens or 0) if prompt_tokens or completion_tokens else None,
        "estimated_cost_usd": round(estimated_cost_usd, 6) if estimated_cost_usd else None,
        "error": error,
    }

    path = _history_dir() / f"{record_id}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    _append_event_log(record)

    # Optional SQLite store — activated by AICP_DB_FILE env var
    from aicp.core.db import record_task
    record_task(record)

    return record_id


def list_tasks(count: int = 20) -> list[dict[str, Any]]:
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


def get_task(record_id: str) -> dict[str, Any] | None:
    """Load a single task record by ID."""
    path = _history_dir() / f"{record_id}.json"
    if not path.exists():
        matches = list(_history_dir().glob(f"*{record_id}*.json"))
        if len(matches) == 1:
            path = matches[0]
        elif len(matches) > 1:
            return None
        else:
            return None

    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
