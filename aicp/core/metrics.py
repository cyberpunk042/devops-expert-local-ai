"""Metrics aggregation from task history."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from aicp.core.history import list_tasks


def _default_snapshot_path() -> Path:
    """Where MetricsCollector persists / restores counters (incl. breaker trips).

    Honors AICP_METRICS_SNAPSHOT env var for custom paths.
    """
    override = os.environ.get("AICP_METRICS_SNAPSHOT")
    if override:
        return Path(override)
    return Path.home() / ".aicp" / "metrics_snapshot.json"


def _read_breaker_trips() -> dict[str, int]:
    """Read per-backend breaker trip counts from the persisted Prometheus snapshot.

    Returns an empty dict if no snapshot exists yet (e.g. fresh install, or
    AICP_METRICS_SNAPSHOT not wired in cli/main.py). Never raises — the column
    is informational, not critical.
    """
    path = _default_snapshot_path()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        trips = data.get("breaker_trips", {})
        return {k: int(v) for k, v in trips.items() if isinstance(v, (int, float))}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def aggregate(count: int = 1000) -> Dict[str, Any]:
    """Aggregate metrics from recent task history."""
    records = list_tasks(count)
    if not records:
        return _empty()

    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    total = len(records)
    today_count = 0
    week_count = 0
    errors = 0
    total_duration = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0

    by_backend = {}  # type: Dict[str, Dict[str, Any]]
    by_route = {}  # type: Dict[str, int]

    for r in records:
        ts_str = r.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.rstrip("Z"))
        except (ValueError, TypeError):
            ts = datetime(2000, 1, 1)

        if ts >= today:
            today_count += 1
        if ts >= week_ago:
            week_count += 1

        if r.get("error"):
            errors += 1

        duration = r.get("duration_seconds", 0) or 0
        total_duration += duration

        pt = r.get("prompt_tokens") or 0
        ct = r.get("completion_tokens") or 0
        cost = r.get("estimated_cost_usd") or 0
        total_prompt_tokens += pt
        total_completion_tokens += ct
        total_cost += cost

        route = r.get("route", "local")
        by_route[route] = by_route.get(route, 0) + 1

        backend = r.get("backend", "unknown")
        if backend not in by_backend:
            by_backend[backend] = {
                "tasks": 0, "errors": 0, "total_duration": 0.0,
                "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0,
            }
        b = by_backend[backend]
        b["tasks"] += 1
        if r.get("error"):
            b["errors"] += 1
        b["total_duration"] += duration
        b["prompt_tokens"] += pt
        b["completion_tokens"] += ct
        b["cost"] += cost

    # Compute averages
    for b in by_backend.values():
        b["avg_duration"] = round(b["total_duration"] / b["tasks"], 2) if b["tasks"] else 0
        b["error_rate"] = round(b["errors"] / b["tasks"] * 100, 1) if b["tasks"] else 0

    return {
        "total_tasks": total,
        "today": today_count,
        "this_week": week_count,
        "errors": errors,
        "error_rate": round(errors / total * 100, 1) if total else 0,
        "avg_duration": round(total_duration / total, 2) if total else 0,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "total_cost_usd": round(total_cost, 4),
        "by_backend": by_backend,
        "by_route": by_route,
    }


def offload_report(count: int = 1000) -> Dict[str, Any]:
    """Compute LocalAI offload metrics — how much work avoids Claude.

    Returns a dict with:
      - offload_pct: percentage of tasks handled by local backends
      - token_savings_pct: percentage of tokens NOT sent to Claude
      - cost_savings_usd: estimated cost saved by using local
      - by_backend: per-backend breakdown
      - goal_met: True if offload >= 80% (the mission target)
    """
    stats = aggregate(count)
    by_backend = stats["by_backend"]

    local_tasks = by_backend.get("local", {}).get("tasks", 0)
    claude_tasks = by_backend.get("claude", {}).get("tasks", 0)
    total_tasks = stats["total_tasks"]

    local_tokens = (
        by_backend.get("local", {}).get("prompt_tokens", 0)
        + by_backend.get("local", {}).get("completion_tokens", 0)
    )
    claude_tokens = (
        by_backend.get("claude", {}).get("prompt_tokens", 0)
        + by_backend.get("claude", {}).get("completion_tokens", 0)
    )
    total_tokens = local_tokens + claude_tokens

    claude_cost = by_backend.get("claude", {}).get("cost", 0.0)

    # Estimate what local tasks would have cost on Claude
    # Conservative estimate: $0.003 per 1K tokens (blended opus/sonnet rate)
    estimated_claude_rate = 0.003 / 1000
    estimated_savings = local_tokens * estimated_claude_rate

    offload_pct = round(local_tasks / total_tasks * 100, 1) if total_tasks else 0
    token_savings_pct = round(local_tokens / total_tokens * 100, 1) if total_tokens else 0

    # Count failover and fleet-routed tasks
    by_route = stats.get("by_route", {})
    fleet_tasks = sum(v for k, v in by_route.items() if k and "fleet:" in k)
    failover_tasks = sum(v for k, v in by_route.items() if k and "failover:" in k)

    return {
        "total_tasks": total_tasks,
        "local_tasks": local_tasks,
        "claude_tasks": claude_tasks,
        "fleet_tasks": fleet_tasks,
        "failover_tasks": failover_tasks,
        "offload_pct": offload_pct,
        "token_savings_pct": token_savings_pct,
        "local_tokens": local_tokens,
        "claude_tokens": claude_tokens,
        "claude_cost_usd": round(claude_cost, 4),
        "estimated_savings_usd": round(estimated_savings, 4),
        "avg_local_duration": by_backend.get("local", {}).get("avg_duration", 0),
        "avg_claude_duration": by_backend.get("claude", {}).get("avg_duration", 0),
        "goal_met": offload_pct >= 80,
        "today": stats["today"],
        "this_week": stats["this_week"],
    }


def _empty() -> Dict[str, Any]:
    return {
        "total_tasks": 0, "today": 0, "this_week": 0,
        "errors": 0, "error_rate": 0, "avg_duration": 0,
        "total_prompt_tokens": 0, "total_completion_tokens": 0,
        "total_tokens": 0, "total_cost_usd": 0, "by_backend": {}, "by_route": {},
    }


def _parse_window(window: str) -> timedelta:
    """Parse a human window string into a timedelta.

    Accepts: "Nd" (days), "Nh" (hours), "Nm" (minutes), or a bare int (days).
    Raises ValueError on unparseable input.
    """
    if not window:
        raise ValueError("window must be non-empty")
    s = window.strip().lower()
    if s[-1].isdigit():  # bare int → days
        return timedelta(days=int(s))
    unit = s[-1]
    try:
        n = int(s[:-1])
    except ValueError as exc:
        raise ValueError(f"unparseable window '{window}'") from exc
    if unit == "d":
        return timedelta(days=n)
    if unit == "h":
        return timedelta(hours=n)
    if unit == "m":
        return timedelta(minutes=n)
    raise ValueError(f"unknown window unit '{unit}' (expected d/h/m)")


def aggregate_window(window: str = "7d", max_records: int = 10000) -> dict[str, Any]:
    """Aggregate metrics over a time window (E011-m005).

    Same result shape as aggregate(count=N) but bounded by wall-clock time rather
    than record count. Intended for the weekly routing-review ritual.

    Args:
        window: human-readable duration, e.g. "7d", "24h", "30m". See _parse_window.
        max_records: upper bound on history records scanned (avoids unbounded IO).
    """
    delta = _parse_window(window)
    records = list_tasks(max_records)
    if not records:
        return {**_empty(), "window": window, "window_seconds": int(delta.total_seconds())}

    cutoff = datetime.utcnow() - delta

    by_backend: dict[str, dict[str, Any]] = {}
    by_route: dict[str, int] = {}
    total = 0
    errors = 0
    total_duration = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0

    for r in records:
        ts_str = r.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.rstrip("Z"))
        except (ValueError, TypeError):
            continue
        if ts < cutoff:
            continue

        total += 1
        if r.get("error"):
            errors += 1

        duration = r.get("duration_seconds", 0) or 0
        pt = r.get("prompt_tokens") or 0
        ct = r.get("completion_tokens") or 0
        cost = r.get("estimated_cost_usd") or 0
        total_duration += duration
        total_prompt_tokens += pt
        total_completion_tokens += ct
        total_cost += cost

        route = r.get("route", "local")
        by_route[route] = by_route.get(route, 0) + 1

        backend = r.get("backend", "unknown")
        if backend not in by_backend:
            by_backend[backend] = {
                "tasks": 0, "errors": 0, "total_duration": 0.0,
                "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0,
            }
        b = by_backend[backend]
        b["tasks"] += 1
        if r.get("error"):
            b["errors"] += 1
        b["total_duration"] += duration
        b["prompt_tokens"] += pt
        b["completion_tokens"] += ct
        b["cost"] += cost

    # Enrich with cumulative breaker-trip counts from persisted snapshot.
    # Snapshot is cumulative-since-install, not windowed — flagged in the report.
    trips = _read_breaker_trips()

    for name, b in by_backend.items():
        b["avg_duration"] = round(b["total_duration"] / b["tasks"], 2) if b["tasks"] else 0
        b["error_rate"] = round(b["errors"] / b["tasks"] * 100, 1) if b["tasks"] else 0
        b["share_pct"] = round(b["tasks"] / total * 100, 1) if total else 0
        b["tokens"] = b["prompt_tokens"] + b["completion_tokens"]
        b["breaker_opens"] = int(trips.get(name, 0))

    return {
        "window": window,
        "window_seconds": int(delta.total_seconds()),
        "total_tasks": total,
        "errors": errors,
        "error_rate": round(errors / total * 100, 1) if total else 0,
        "avg_duration": round(total_duration / total, 2) if total else 0,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "total_cost_usd": round(total_cost, 4),
        "by_backend": by_backend,
        "by_route": by_route,
        "snapshot_present": _default_snapshot_path().exists(),
    }
