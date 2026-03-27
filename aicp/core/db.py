"""Optional SQLite metrics store.

Activated by setting ``AICP_DB_FILE`` to a file path, e.g.:

    export AICP_DB_FILE=~/.aicp/metrics.db

When set, every completed task is also recorded in the database via
``record_task()``, which is called automatically from ``history.save_task()``.

The database is queryable with any SQLite client:

    sqlite3 ~/.aicp/metrics.db
    > SELECT backend, COUNT(*), AVG(duration_seconds) FROM tasks GROUP BY backend;
    > SELECT DATE(timestamp) AS day, SUM(total_tokens) FROM tasks GROUP BY day;

The history JSON files in ``~/.aicp/history/`` remain the source of truth —
the DB is an index for fast aggregation queries. If the DB is deleted it can
be rebuilt from history files using ``rebuild_db()``.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id                TEXT PRIMARY KEY,
    timestamp         TEXT NOT NULL,
    mode              TEXT,
    backend           TEXT,
    model             TEXT,
    project           TEXT,
    duration_seconds  REAL,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    estimated_cost_usd REAL,
    error             TEXT,
    prompt_preview    TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_timestamp ON tasks (timestamp);
CREATE INDEX IF NOT EXISTS idx_tasks_backend   ON tasks (backend);
CREATE INDEX IF NOT EXISTS idx_tasks_project   ON tasks (project);
"""


def _db_path() -> Optional[str]:
    """Return the configured DB path, or None if not set."""
    raw = os.environ.get("AICP_DB_FILE", "").strip()
    if not raw:
        return None
    return str(Path(raw).expanduser())


def _connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def record_task(record: Dict[str, Any]) -> None:
    """Insert or replace a task record in the SQLite DB.

    Called automatically by ``history.save_task()`` when AICP_DB_FILE is set.
    No-ops silently on any error to never block the main flow.
    """
    path = _db_path()
    if not path:
        return

    try:
        conn = _connect(path)
        conn.execute(
            """
            INSERT OR REPLACE INTO tasks
                (id, timestamp, mode, backend, model, project,
                 duration_seconds, prompt_tokens, completion_tokens,
                 total_tokens, estimated_cost_usd, error, prompt_preview)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("id"),
                record.get("timestamp"),
                record.get("mode"),
                record.get("backend"),
                record.get("model"),
                record.get("project"),
                record.get("duration_seconds"),
                record.get("prompt_tokens"),
                record.get("completion_tokens"),
                record.get("total_tokens"),
                record.get("estimated_cost_usd"),
                record.get("error"),
                (record.get("prompt") or "")[:120],
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Never crash the main flow


def rebuild_db() -> int:
    """Rebuild the SQLite DB from all JSON history files.

    Returns the number of records imported. Useful after enabling AICP_DB_FILE
    on a machine that already has a populated history directory.
    """
    path = _db_path()
    if not path:
        raise RuntimeError("AICP_DB_FILE is not set. Set it before calling rebuild_db().")

    from aicp.core.history import list_tasks, _history_dir

    count = 0
    conn = _connect(path)
    history_dir = _history_dir()
    files = sorted(history_dir.glob("*.json"))

    for f in files:
        try:
            with open(f) as fh:
                record = json.load(fh)
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                    (id, timestamp, mode, backend, model, project,
                     duration_seconds, prompt_tokens, completion_tokens,
                     total_tokens, estimated_cost_usd, error, prompt_preview)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("id"),
                    record.get("timestamp"),
                    record.get("mode"),
                    record.get("backend"),
                    record.get("model"),
                    record.get("project"),
                    record.get("duration_seconds"),
                    record.get("prompt_tokens"),
                    record.get("completion_tokens"),
                    record.get("total_tokens"),
                    record.get("estimated_cost_usd"),
                    record.get("error"),
                    (record.get("prompt") or "")[:120],
                ),
            )
            count += 1
        except Exception:
            continue

    conn.commit()
    conn.close()
    return count


def query_tasks(
    backend: Optional[str] = None,
    since_days: Optional[int] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Query tasks from the DB with optional filters.

    Falls back gracefully to an empty list if AICP_DB_FILE is not set.
    """
    path = _db_path()
    if not path or not Path(path).exists():
        return []

    conditions = []
    params: List[Any] = []

    if backend:
        conditions.append("backend = ?")
        params.append(backend)

    if since_days is not None:
        conditions.append("timestamp >= datetime('now', ?)")
        params.append(f"-{since_days} days")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT * FROM tasks {where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    try:
        conn = _connect(path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
