"""Dead-Letter Queue — persist failed tasks for later retry.

Tasks that fail after exhausting the entire failover chain are written
to the DLQ with full context. They can be retried via CLI or MCP tool.

Storage: JSONL files in ~/.aicp/dlq/ (one file per day, matches history pattern).

Profile-configurable via config["dlq"]:
  enabled: true/false (default: true)
  max_retries: max retry attempts per entry (default: 3)
  retry_delay_seconds: minimum delay between retries (default: 300)
  max_entries: max DLQ entries before oldest are pruned (default: 1000)
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aicp.dlq")


def _dlq_dir() -> Path:
    base = Path(os.environ.get("AICP_HOME", Path.home() / ".aicp"))
    d = base / "dlq"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _today_file() -> Path:
    return _dlq_dir() / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"


def enqueue(
    prompt: str,
    mode: str,
    backend: str,
    project: str,
    error: str,
    failover_chain: List[str] = None,
    config: Dict[str, Any] = None,
) -> bool:
    """Write a failed task to the DLQ.

    Returns True if written, False if DLQ is disabled or full.
    """
    config = config or {}
    dlq_cfg = config.get("dlq", {})

    if not dlq_cfg.get("enabled", True):
        return False

    max_entries = dlq_cfg.get("max_entries", 1000)

    # Check current count
    current = count()
    if current >= max_entries:
        logger.warning("DLQ full (%d entries), dropping oldest", current)
        _prune_oldest(max_entries // 2)

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "enqueued_at": time.time(),
        "prompt": prompt,
        "mode": mode,
        "backend": backend,
        "project": project,
        "error": error,
        "failover_chain": failover_chain or [],
        "retry_count": 0,
        "status": "pending",
    }

    path = _today_file()
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    logger.info("DLQ: enqueued failed task (backend=%s, error=%s)", backend, error[:80])
    return True


def list_entries(max_count: int = 100) -> List[Dict[str, Any]]:
    """List DLQ entries, newest first."""
    entries: List[Dict[str, Any]] = []
    for path in sorted(_dlq_dir().glob("*.jsonl"), reverse=True):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        entry["_file"] = str(path)
                        entries.append(entry)
        except (json.JSONDecodeError, OSError):
            continue
        if len(entries) >= max_count:
            break
    return entries[:max_count]


def count() -> int:
    """Count total DLQ entries across all files."""
    total = 0
    for path in _dlq_dir().glob("*.jsonl"):
        try:
            with open(path) as f:
                total += sum(1 for line in f if line.strip())
        except OSError:
            continue
    return total


def retry_pending(
    controller,
    config: Dict[str, Any] = None,
    max_items: int = 10,
) -> Dict[str, Any]:
    """Retry pending DLQ entries through the controller.

    Returns dict with: retried, succeeded, failed counts.
    """
    config = config or {}
    dlq_cfg = config.get("dlq", {})
    max_retries = dlq_cfg.get("max_retries", 3)
    retry_delay = dlq_cfg.get("retry_delay_seconds", 300)

    from aicp.core.controller import Task
    from aicp.core.modes import Mode

    entries = list_entries(max_items * 2)
    pending = [
        e for e in entries
        if e.get("status") == "pending" and e.get("retry_count", 0) < max_retries
    ]

    # Filter by retry delay
    now = time.time()
    ready = []
    for e in pending:
        enqueued = e.get("enqueued_at", 0)
        if not enqueued:
            # Legacy: parse from timestamp string
            ts_str = e.get("timestamp", "")
            try:
                enqueued = datetime.fromisoformat(ts_str.rstrip("Z")).timestamp()
            except (ValueError, TypeError):
                enqueued = 0
        if now - enqueued >= retry_delay:
            ready.append(e)

    ready = ready[:max_items]
    results = {"retried": 0, "succeeded": 0, "failed": 0}

    for entry in ready:
        try:
            mode = Mode(entry.get("mode", "think"))
            task = Task(
                prompt=entry["prompt"],
                mode=mode,
                project_path=Path(entry.get("project", ".")).resolve(),
                backend_name=entry.get("backend", "local"),
            )
            controller.run(task)
            _mark_entry(entry, "succeeded")
            results["succeeded"] += 1
        except Exception as e:
            _mark_entry(entry, "pending", retry_count=entry.get("retry_count", 0) + 1)
            results["failed"] += 1
            logger.warning("DLQ retry failed: %s", e)
        results["retried"] += 1

    return results


def _mark_entry(entry: Dict, status: str, retry_count: int = None) -> None:
    """Update an entry's status in its file."""
    file_path = entry.get("_file")
    if not file_path or not Path(file_path).exists():
        return

    try:
        with open(file_path) as f:
            lines = f.readlines()

        updated = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if (e.get("timestamp") == entry.get("timestamp") and
                        e.get("prompt") == entry.get("prompt")):
                    e["status"] = status
                    if retry_count is not None:
                        e["retry_count"] = retry_count
                updated.append(json.dumps(e) + "\n")
            except json.JSONDecodeError:
                updated.append(line + "\n")

        with open(file_path, "w") as f:
            f.writelines(updated)
    except OSError:
        pass


def _prune_oldest(keep: int) -> None:
    """Remove oldest entries, keeping at most `keep` total."""
    files = sorted(_dlq_dir().glob("*.jsonl"))
    total = count()
    to_remove = total - keep
    if to_remove <= 0:
        return

    for path in files:
        if to_remove <= 0:
            break
        try:
            with open(path) as f:
                line_count = sum(1 for line in f if line.strip())
            if line_count <= to_remove:
                path.unlink()
                to_remove -= line_count
            else:
                # Partial prune: keep last N lines
                with open(path) as f:
                    lines = [l for l in f.readlines() if l.strip()]
                with open(path, "w") as f:
                    f.writelines(lines[to_remove:])
                to_remove = 0
        except OSError:
            continue


def status(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Return DLQ status summary."""
    config = config or {}
    dlq_cfg = config.get("dlq", {})
    entries = list_entries(1000)
    pending = sum(1 for e in entries if e.get("status") == "pending")
    succeeded = sum(1 for e in entries if e.get("status") == "succeeded")
    exhausted = sum(
        1 for e in entries
        if e.get("status") == "pending" and
        e.get("retry_count", 0) >= dlq_cfg.get("max_retries", 3)
    )

    return {
        "total": len(entries),
        "pending": pending,
        "succeeded": succeeded,
        "exhausted": exhausted,
        "enabled": dlq_cfg.get("enabled", True),
        "max_retries": dlq_cfg.get("max_retries", 3),
    }
