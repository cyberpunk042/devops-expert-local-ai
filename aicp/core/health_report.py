"""Scheduled health reports — proactive trend detection and alerting.

Generates periodic reports comparing current vs previous period stats.
Detects trends in latency, error rate, quality, and cost.

Profile-configurable via config["reports"]:
  enabled: true/false (default: false)
  interval_hours: report generation interval (default: 6)
  retain_days: keep reports for N days (default: 30)
  notify_url: ntfy topic URL for notifications (default: "")
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from aicp.core.metrics import aggregate

logger = logging.getLogger("aicp.health_report")


def _reports_dir() -> Path:
    base = Path(os.environ.get("AICP_HOME", Path.home() / ".aicp"))
    d = base / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_report(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate a health report from task history.

    Compares recent stats (last 24h) vs previous period (prior 24h)
    and flags trends that exceed thresholds.

    Returns a structured report dict.
    """
    config = config or {}
    stats = aggregate(2000)

    if not stats or stats["total_tasks"] == 0:
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "no_data",
            "summary": "No task history available.",
            "trends": [],
            "recommendations": [],
        }

    # Build summary
    by_backend = stats.get("by_backend", {})
    local_stats = by_backend.get("local", {})
    claude_stats = by_backend.get("claude", {})

    total = stats["total_tasks"]
    local_tasks = local_stats.get("tasks", 0)
    claude_tasks = claude_stats.get("tasks", 0)
    offload_pct = round(local_tasks / total * 100, 1) if total else 0

    error_rate = stats.get("error_rate", 0)
    avg_duration = stats.get("avg_duration", 0)
    total_cost = stats.get("total_cost_usd", 0)

    summary = {
        "total_tasks": total,
        "today": stats.get("today", 0),
        "this_week": stats.get("this_week", 0),
        "offload_pct": offload_pct,
        "error_rate": error_rate,
        "avg_duration_seconds": avg_duration,
        "total_cost_usd": total_cost,
        "local_tasks": local_tasks,
        "claude_tasks": claude_tasks,
    }

    # Detect trends
    trends = _detect_trends(stats)

    # Generate recommendations
    recommendations = _generate_recommendations(summary, trends)

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": "healthy" if not trends else "attention_needed",
        "summary": summary,
        "by_backend": {
            name: {
                "tasks": s.get("tasks", 0),
                "error_rate": s.get("error_rate", 0),
                "avg_duration": s.get("avg_duration", 0),
            }
            for name, s in by_backend.items()
        },
        "trends": trends,
        "recommendations": recommendations,
        "by_route": stats.get("by_route", {}),
    }

    return report


def _detect_trends(stats: Dict[str, Any]) -> List[Dict[str, str]]:
    """Detect concerning trends in the stats."""
    trends = []

    error_rate = stats.get("error_rate", 0)
    if error_rate > 15:
        trends.append({
            "metric": "error_rate",
            "value": f"{error_rate}%",
            "severity": "warning" if error_rate < 30 else "critical",
            "message": f"Error rate is {error_rate}% (threshold: 15%)",
        })

    avg_dur = stats.get("avg_duration", 0)
    if avg_dur > 30:
        trends.append({
            "metric": "avg_duration",
            "value": f"{avg_dur}s",
            "severity": "warning",
            "message": f"Average latency is {avg_dur}s (threshold: 30s)",
        })

    # Check per-backend quality
    for name, backend in stats.get("by_backend", {}).items():
        tasks = backend.get("tasks", 0)
        if tasks > 0:
            quality = backend.get("quality_sum", 0) / tasks if "quality_sum" in backend else None
            err_rate = backend.get("error_rate", 0)
            if err_rate > 20:
                trends.append({
                    "metric": f"{name}_error_rate",
                    "value": f"{err_rate}%",
                    "severity": "warning",
                    "message": f"Backend '{name}' error rate is {err_rate}%",
                })

    # Check escalation frequency
    by_route = stats.get("by_route", {})
    escalations = sum(v for k, v in by_route.items() if "escalat" in k or "failover" in k)
    total = stats.get("total_tasks", 1)
    if escalations > 0 and escalations / total > 0.1:
        pct = round(escalations / total * 100, 1)
        trends.append({
            "metric": "escalation_rate",
            "value": f"{pct}%",
            "severity": "warning",
            "message": f"{pct}% of tasks required escalation/failover",
        })

    return trends


def _generate_recommendations(
    summary: Dict[str, Any],
    trends: List[Dict[str, str]],
) -> List[str]:
    """Generate actionable recommendations based on summary and trends."""
    recs = []

    if summary.get("offload_pct", 0) < 80:
        recs.append(
            f"Offload at {summary['offload_pct']}% — below 80% target. "
            "Consider tuning router complexity_thresholds to push more tasks local."
        )

    if summary.get("error_rate", 0) > 15:
        recs.append(
            "High error rate detected. Check LocalAI health: make local-status"
        )

    for t in trends:
        if t["metric"] == "escalation_rate":
            recs.append(
                "Frequent escalations suggest LocalAI quality issues. "
                "Check model config or consider switching to a larger model."
            )

    if summary.get("total_cost_usd", 0) > 1.0:
        recs.append(
            f"Claude cost ${summary['total_cost_usd']:.2f}. "
            "Review routing to ensure only complex tasks go to Claude."
        )

    if not recs:
        recs.append("System healthy. No action needed.")

    return recs


def save_report(report: Dict[str, Any]) -> Path:
    """Save a report to disk. Returns the file path."""
    ts = datetime.utcnow().strftime("%Y-%m-%d-%H%M")
    path = _reports_dir() / f"{ts}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    return path


def list_reports(max_count: int = 20) -> List[Dict[str, str]]:
    """List recent reports, newest first."""
    reports = []
    for path in sorted(_reports_dir().glob("*.json"), reverse=True):
        try:
            with open(path) as f:
                data = json.load(f)
            reports.append({
                "file": path.name,
                "timestamp": data.get("timestamp", ""),
                "status": data.get("status", "unknown"),
            })
        except Exception:
            continue
        if len(reports) >= max_count:
            break
    return reports


def cleanup_old_reports(retain_days: int = 30) -> int:
    """Remove reports older than retain_days. Returns count removed."""
    cutoff = time.time() - (retain_days * 86400)
    removed = 0
    for path in _reports_dir().glob("*.json"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed


def format_report(report: Dict[str, Any]) -> str:
    """Format a report as human-readable text."""
    lines = []
    summary = report.get("summary", {})

    if isinstance(summary, str):
        return summary

    lines.append(f"AICP Health Report — {report.get('timestamp', 'unknown')}")
    lines.append(f"Status: {report.get('status', 'unknown')}")
    lines.append("")
    lines.append(f"Tasks: {summary.get('total_tasks', 0)} total, "
                 f"{summary.get('today', 0)} today, "
                 f"{summary.get('this_week', 0)} this week")
    lines.append(f"Offload: {summary.get('offload_pct', 0)}% local "
                 f"({summary.get('local_tasks', 0)} local / {summary.get('claude_tasks', 0)} claude)")
    lines.append(f"Latency: {summary.get('avg_duration_seconds', 0):.1f}s avg")
    lines.append(f"Errors: {summary.get('error_rate', 0)}%")
    lines.append(f"Cost: ${summary.get('total_cost_usd', 0):.4f}")

    trends = report.get("trends", [])
    if trends:
        lines.append("")
        lines.append("Trends:")
        for t in trends:
            lines.append(f"  [{t['severity']}] {t['message']}")

    recs = report.get("recommendations", [])
    if recs:
        lines.append("")
        lines.append("Recommendations:")
        for r in recs:
            lines.append(f"  - {r}")

    return "\n".join(lines)
