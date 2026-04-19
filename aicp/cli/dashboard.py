"""Live dashboard for AICP system status."""

from __future__ import annotations

import subprocess
import time
from datetime import datetime
from typing import Dict, List

import httpx
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from aicp.core.metrics import aggregate
from aicp.core.observability import scrape_prometheus


def run_dashboard(local_url: str) -> int:
    """Run a live-updating dashboard. Refreshes every 5 seconds. Ctrl+C to exit."""
    console = Console()

    try:
        with Live(console=console, refresh_per_second=4, screen=True) as live:
            while True:
                panel = _build_dashboard(local_url)
                live.update(panel)
                time.sleep(5)
    except KeyboardInterrupt:
        # Per Gateway Output Contract Rule 5 — closing NEXT-move
        # See wiki/decisions/00_inbox/aicp-cli-mcp-outputs-adopt-gateway-output-contract.md
        print("NEXT: `aicp --metrics` for a static snapshot, or `aicp --check` for backend validation")
        return 0


def _build_dashboard(local_url: str) -> Layout:
    now = datetime.now().strftime("%H:%M:%S")

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )
    layout["header"].update(Panel(
        f"[bold blue]AICP Dashboard[/]  [dim]Last refresh: {now}  |  Ctrl+C to exit[/]",
        style="blue",
    ))

    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    layout["left"].split_column(
        Layout(_gpu_panel(), name="gpu"),
        Layout(_localai_panel(local_url), name="localai"),
    )

    layout["right"].split_column(
        Layout(_metrics_panel(), name="metrics"),
        Layout(_recent_tasks_panel(), name="recent"),
    )

    return layout


def _gpu_panel() -> Panel:
    """GPU status from nvidia-smi."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
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
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                idx, name, used, total, util, temp = parts[:6]
                try:
                    pct = int(float(used)) / int(float(total)) * 100 if float(total) > 0 else 0
                except (ValueError, ZeroDivisionError):
                    pct = 0
                color = "green" if pct < 70 else "yellow" if pct < 90 else "red"
                table.add_row(
                    f"[bold]{idx}[/] {name}",
                    f"[{color}]{used}/{total} MiB ({pct:.0f}%)[/]",
                    f"{util}%",
                    f"{temp}°C",
                )

        return Panel(table, title="GPU Status")
    except FileNotFoundError:
        return Panel("[dim]nvidia-smi not available[/]", title="GPU")
    except subprocess.TimeoutExpired:
        return Panel("[yellow]nvidia-smi timed out[/]", title="GPU")


def _localai_panel(local_url: str) -> Panel:
    """LocalAI status — online/offline, loaded models, request count from history."""
    try:
        resp = httpx.get(f"{local_url}/v1/models", timeout=3.0)
        if resp.status_code != 200:
            return Panel(f"[red]HTTP {resp.status_code}[/]", title="LocalAI")

        data = resp.json()
        models = [m.get("id", "?") for m in data.get("data", [])]
        model_list = ", ".join(models) if models else "[dim]none loaded[/]"

        # Pull request count from task history (no live request rate — LocalAI
        # doesn't expose one without Prometheus integration)
        m = aggregate(1000)
        local_stats = m.get("by_backend", {}).get("local", {})
        total_req = local_stats.get("tasks", 0)
        today_req = 0
        # Approximate today's local requests
        from aicp.core.history import list_tasks
        from datetime import datetime
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        for t in list_tasks(200):
            if t.get("backend") == "local" and (t.get("timestamp") or "").startswith(today_str):
                today_req += 1

        table = Table(show_header=False, expand=True, pad_edge=False)
        table.add_column("Key", style="bold")
        table.add_column("Val")
        table.add_row("[green]ONLINE[/]", "")
        table.add_row("URL", local_url)
        table.add_row("Models", model_list)
        table.add_row("Requests today", str(today_req))
        table.add_row("Requests total", str(total_req))

        # Live Prometheus metrics from LocalAI /metrics
        prom = scrape_prometheus(local_url, timeout=2.0)
        if prom.get("available"):
            goroutines = prom.get("go_goroutines")
            alloc = prom.get("go_memstats_alloc_bytes")
            if goroutines is not None:
                table.add_row("Goroutines", str(int(goroutines)))
            if alloc is not None:
                table.add_row("Memory", f"{alloc / (1024*1024):.1f} MiB")
            api = prom.get("api_calls", {})
            for method, stats in api.items():
                if stats.get("count", 0) > 0:
                    table.add_row(
                        f"API {method}",
                        f"{stats['count']} calls, avg {stats['avg_ms']:.0f}ms",
                    )

        return Panel(table, title="LocalAI")

    except (httpx.ConnectError, httpx.TimeoutException):
        return Panel(
            f"[red]OFFLINE[/]\n{local_url}\n[dim]Start with: make local-up[/]",
            title="LocalAI",
        )
    except Exception as e:
        return Panel(f"[red]Error:[/] {e}", title="LocalAI")


def _metrics_panel() -> Panel:
    """Aggregated task metrics — summary + per-backend breakdown."""
    m = aggregate(500)

    table = Table(show_header=False, expand=True, pad_edge=False)
    table.add_column("Key", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Tasks today", str(m["today"]))
    table.add_row("Tasks this week", str(m["this_week"]))
    table.add_row("Tasks total", str(m["total_tasks"]))
    table.add_row("", "")
    table.add_row("Avg latency", f"{m['avg_duration']:.1f}s")
    table.add_row("Error rate", f"{m['error_rate']:.1f}%")
    table.add_row("", "")
    table.add_row("Total tokens", f"{m['total_tokens']:,}")
    table.add_row("Est. cost", f"${m['total_cost_usd']:.4f}")

    by_backend = m.get("by_backend", {})
    if by_backend:
        table.add_row("", "")
        for name, b in by_backend.items():
            color = "cyan" if name == "local" else "magenta"
            table.add_row(f"[{color}]{name}[/]", "")
            table.add_row("  Tasks", str(b["tasks"]))
            table.add_row("  Avg latency", f"{b['avg_duration']:.1f}s")
            table.add_row("  Errors", f"{b['error_rate']:.1f}%")
            table.add_row("  Tokens", f"{b['prompt_tokens'] + b['completion_tokens']:,}")

    return Panel(table, title="Metrics")


def _recent_tasks_panel() -> Panel:
    """Last 5 tasks — timestamp, mode, backend, duration, status."""
    from aicp.core.history import list_tasks

    records = list_tasks(5)
    if not records:
        return Panel("[dim]No tasks yet[/]", title="Recent Tasks")

    table = Table(show_header=True, expand=True, pad_edge=False)
    table.add_column("Time", style="dim", width=8)
    table.add_column("Mode", width=6)
    table.add_column("Backend", width=7)
    table.add_column("Dur", justify="right", width=6)
    table.add_column("Prompt")

    for r in records:
        status_color = "green" if not r.get("error") else "red"
        ts = (r.get("timestamp") or "")[11:19]  # HH:MM:SS
        mode = r.get("mode", "?")
        backend = r.get("backend", "?")
        dur = f"{r.get('duration_seconds', 0):.1f}s"
        prompt = (r.get("prompt") or "")[:35]
        table.add_row(
            f"[{status_color}]{ts}[/]",
            f"[cyan]{mode}[/]",
            f"[magenta]{backend}[/]",
            dur,
            prompt,
        )

    return Panel(table, title="Recent Tasks")
