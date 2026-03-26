"""Control plane — project-level operational visibility."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from aicp.core.history import list_tasks
from aicp.core.projects import list_projects, load_project_state

console = Console()


def run_control(project_name: Optional[str] = None) -> int:
    """Display the control plane — overview or deep dive."""
    if project_name:
        return _project_deep_dive(project_name)
    return _overview()


def _overview() -> int:
    """Cross-project overview: all managed projects + recent activity."""
    projects = list_projects()

    if not projects:
        console.print(Panel(
            "[dim]No projects registered.\n"
            "Use [bold]aicp --project-cmd register[/] to add a project.[/]",
            title="AICP Control Plane",
            border_style="blue",
        ))
        return 0

    # Projects table
    proj_table = Table(show_header=True, expand=True, title="Managed Projects")
    proj_table.add_column("Project", style="bold")
    proj_table.add_column("Phase")
    proj_table.add_column("Progress")
    proj_table.add_column("Last Activity")
    proj_table.add_column("Open Decisions")

    for p in projects:
        path = Path(p["path"])
        state = load_project_state(path)
        if not state:
            proj_table.add_row(p["name"], "[dim]no state[/]", "-", "-", "-")
            continue

        phase = state.get("phase", "?")
        phase_color = {
            "init": "dim", "planned": "yellow", "building": "cyan",
            "done": "green",
        }.get(phase, "white")

        milestones = state.get("milestones", [])
        done = sum(1 for m in milestones if m.get("status") == "done")
        total = len(milestones)
        if total:
            pct = done / total * 100
            bar = _progress_bar(pct)
            progress = f"{bar} {done}/{total}"
        else:
            progress = "[dim]-[/]"

        last = ""
        if state.get("last_session"):
            last = state["last_session"].get("timestamp", "")[:10]

        decisions = state.get("decisions", [])
        open_count = len(decisions)

        proj_table.add_row(
            p["name"],
            f"[{phase_color}]{phase}[/]",
            progress,
            last or "[dim]-[/]",
            str(open_count) if open_count else "[dim]-[/]",
        )

    console.print(Panel(proj_table, title="AICP Control Plane", border_style="blue"))

    # Recent activity across all projects
    recent = list_tasks(10)
    if recent:
        console.print()
        act_table = Table(title="Recent Activity", show_header=True, expand=True)
        act_table.add_column("Time", style="dim")
        act_table.add_column("Mode")
        act_table.add_column("Backend")
        act_table.add_column("Prompt")
        act_table.add_column("Status")

        for r in recent[:8]:
            status = "[green]OK[/]" if not r.get("error") else "[red]ERR[/]"
            ts = r.get("timestamp", "")[:16]
            prompt = r.get("prompt", "")[:50]
            act_table.add_row(
                ts,
                f"[cyan]{r.get('mode', '?')}[/]",
                f"[magenta]{r.get('backend', '?')}[/]",
                prompt,
                status,
            )
        console.print(act_table)

    return 0


def _project_deep_dive(project_name: str) -> int:
    """Detailed view of a single project."""
    projects = list_projects()
    project = None
    for p in projects:
        if p["name"] == project_name:
            project = p
            break

    if not project:
        console.print(f"[red]Project not found:[/] {project_name}")
        return 1

    path = Path(project["path"])
    state = load_project_state(path)
    if not state:
        console.print(f"[red]No state for project:[/] {project_name}")
        return 1

    # Header
    console.print(Panel(
        f"[bold]{state.get('name', project_name)}[/]\n"
        f"{state.get('description', '')}\n"
        f"Phase: [cyan]{state.get('phase', '?')}[/] | "
        f"Path: {project['path']}",
        title=f"Project: {project_name}",
        border_style="blue",
    ))

    # Architecture
    arch = state.get("architecture", "")
    if arch:
        console.print(Panel(
            arch[:1000] + ("..." if len(arch) > 1000 else ""),
            title="Architecture",
            border_style="dim",
        ))

    # Milestones
    milestones = state.get("milestones", [])
    if milestones:
        ms_table = Table(title="Milestones", show_header=True, expand=True)
        ms_table.add_column("Status", width=12)
        ms_table.add_column("Name", style="bold")
        ms_table.add_column("Description")

        for m in milestones:
            status = m.get("status", "pending")
            color = {"done": "green", "in_progress": "yellow", "pending": "dim"}.get(status, "white")
            icon = {"done": "v", "in_progress": ">", "pending": " "}.get(status, "?")
            ms_table.add_row(
                f"[{color}][{icon}] {status}[/]",
                m["name"],
                m.get("description", ""),
            )
        console.print(ms_table)

    # Decision log
    decisions = state.get("decisions", [])
    if decisions:
        dec_table = Table(title="Decision Log", show_header=True, expand=True)
        dec_table.add_column("Date", width=12, style="dim")
        dec_table.add_column("Decision")
        dec_table.add_column("Context")

        for d in decisions[-10:]:
            dec_table.add_row(
                d.get("timestamp", "")[:10],
                d["decision"],
                d.get("context", "")[:60],
            )
        console.print(dec_table)

    # Recent tasks for this project
    all_tasks = list_tasks(50)
    proj_tasks = [t for t in all_tasks if t.get("project", "").endswith(project_name)]
    if proj_tasks:
        task_table = Table(title="Recent Tasks", show_header=True, expand=True)
        task_table.add_column("Time", style="dim")
        task_table.add_column("Mode")
        task_table.add_column("Backend")
        task_table.add_column("Duration", justify="right")
        task_table.add_column("Tokens", justify="right")
        task_table.add_column("Prompt")

        for t in proj_tasks[:10]:
            tokens = t.get("total_tokens") or 0
            task_table.add_row(
                t.get("timestamp", "")[:16],
                t.get("mode", "?"),
                t.get("backend", "?"),
                f"{t.get('duration_seconds', 0):.1f}s",
                str(tokens) if tokens else "-",
                t.get("prompt", "")[:40],
            )
        console.print(task_table)

    # Last session
    last = state.get("last_session")
    if last:
        console.print(f"\n[dim]Last session: {last.get('timestamp', '')[:19]}[/]")
        if last.get("summary"):
            console.print(f"[dim]Summary: {last['summary']}[/]")

    return 0


def _progress_bar(pct: float, width: int = 10) -> str:
    """Simple text progress bar."""
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if pct >= 80 else "yellow" if pct >= 40 else "red"
    return f"[{color}]{bar}[/]"
