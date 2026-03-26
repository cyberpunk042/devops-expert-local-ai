"""Live dashboard for AICP system status."""

from __future__ import annotations

import subprocess
import time
from typing import Dict, List

import httpx
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from aicp.core.metrics import aggregate


def run_dashboard(local_url: str) -> int:
    """Run a live-updating dashboard."""
    console = Console()

    try:
        with Live(console=console, refresh_per_second=0.2, screen=True) as live:
            while True:
                panel = _build_dashboard(local_url)
                live.update(panel)
                time.sleep(5)
    except KeyboardInterrupt:
        return 0


def _build_dashboard(local_url: str) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )
    layout["header"].update(Panel("[bold blue]AICP Dashboard[/] — Ctrl+C to exit", style="blue"))

    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    layout["left"].split_column(
        Layout(_gpu_panel(), name="gpu"),
        Layout(_localai_panel(local_url), name="localai"),
    )
    layout["right"].update(_metrics_panel())

    return layout


def _gpu_panel() -> Panel:
    """GPU status from nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return Panel("[red]nvidia-smi failed[/]", title="GPU")

        table = Table(show_header=True, expand=True)
        table.add_column("GPU")
        table.add_column("VRAM", justify="right")
        table.add_column("Util", justify="right")
        table.add_column("Temp", justify="right")

        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                idx, name, used, total, util, temp = parts[:6]
                pct = int(float(used)) / int(float(total)) * 100 if float(total) > 0 else 0
                color = "green" if pct < 70 else "yellow" if pct < 90 else "red"
                table.add_row(
                    f"[bold]{idx}[/] {name}",
                    f"[{color}]{used}/{total} MiB ({pct:.0f}%)[/]",
                    f"{util}%",
                    f"{temp}C",
                )

        return Panel(table, title="GPU Status")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return Panel("[dim]nvidia-smi not available[/]", title="GPU")


def _localai_panel(local_url: str) -> Panel:
    """LocalAI status."""
    try:
        resp = httpx.get(f"{local_url}/v1/models", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("id", "?") for m in data.get("data", [])]
            model_list = ", ".join(models) if models else "none"

            system = httpx.get(f"{local_url}/system", timeout=3.0).json()
            backends = system.get("backends", [])
            loaded = system.get("loaded_models", [])

            info = f"URL: {local_url}\n"
            info += f"Models: {model_list}\n"
            info += f"Backends: {', '.join(backends) if backends else 'none'}\n"
            info += f"Loaded: {len(loaded)}"
            return Panel(f"[green]ONLINE[/]\n{info}", title="LocalAI")
        return Panel(f"[red]HTTP {resp.status_code}[/]", title="LocalAI")
    except (httpx.ConnectError, httpx.TimeoutException):
        return Panel(f"[red]OFFLINE[/] — {local_url}", title="LocalAI")
    except Exception as e:
        return Panel(f"[red]Error:[/] {e}", title="LocalAI")


def _metrics_panel() -> Panel:
    """Aggregated task metrics."""
    m = aggregate(500)

    table = Table(show_header=False, expand=True, pad_edge=False)
    table.add_column("Key", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Tasks today", str(m["today"]))
    table.add_row("Tasks this week", str(m["this_week"]))
    table.add_row("Tasks total", str(m["total_tasks"]))
    table.add_row("", "")
    table.add_row("Avg duration", f"{m['avg_duration']:.1f}s")
    table.add_row("Error rate", f"{m['error_rate']:.1f}%")
    table.add_row("", "")
    table.add_row("Prompt tokens", f"{m['total_prompt_tokens']:,}")
    table.add_row("Completion tokens", f"{m['total_completion_tokens']:,}")
    table.add_row("Total tokens", f"{m['total_tokens']:,}")
    table.add_row("", "")
    table.add_row("Est. cost", f"${m['total_cost_usd']:.4f}")

    # Per-backend breakdown
    for name, b in m.get("by_backend", {}).items():
        table.add_row("", "")
        table.add_row(f"[cyan]{name}[/]", "")
        table.add_row(f"  Tasks", str(b["tasks"]))
        table.add_row(f"  Avg time", f"{b['avg_duration']:.1f}s")
        table.add_row(f"  Errors", f"{b['error_rate']:.1f}%")
        table.add_row(f"  Tokens", f"{b['prompt_tokens'] + b['completion_tokens']:,}")

    return Panel(table, title="Metrics")
