"""AICP command-line interface."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from aicp import __version__
from aicp.backends.base import Backend
from aicp.cli.display import (
    console, print_check_header, print_error, print_history_entry,
    print_response, print_status, print_warning, spinner,
)
from aicp.config.loader import load_config, validate_config, get_backend_config
from aicp.core.history import list_tasks, get_task
from aicp.core.modes import Mode
from aicp.core.controller import Controller, Task
from aicp.backends.localai import LocalAIBackend
from aicp.backends.claude_code import ClaudeCodeBackend


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aicp",
        description="AI Control Platform — orchestrate AI backends under your control.",
    )
    parser.add_argument("prompt", nargs="?", help="Task prompt")
    parser.add_argument(
        "--mode", "-m",
        choices=["think", "edit", "act"],
        default=os.environ.get("AICP_DEFAULT_MODE", "think"),
        help="Permission mode (default: think, env: AICP_DEFAULT_MODE)",
    )
    parser.add_argument(
        "--backend", "-b",
        choices=["local", "claude"],
        default=os.environ.get("AICP_DEFAULT_BACKEND", "local"),
        help="AI backend (default: local, env: AICP_DEFAULT_BACKEND)",
    )
    parser.add_argument(
        "--project", "-d",
        type=Path,
        default=Path(os.environ.get("AICP_PROJECT_PATH", ".")),
        help="Project directory (default: cwd, env: AICP_PROJECT_PATH)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Config file path (default: config/default.yaml)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check config validity and backend availability, then exit",
    )
    parser.add_argument(
        "--history",
        nargs="?",
        const=20,
        type=int,
        metavar="N",
        help="Show recent task history (default: last 20)",
    )
    parser.add_argument(
        "--replay",
        metavar="ID",
        help="Replay full output from a previous task by ID",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show aggregated task metrics (tokens, cost, latency)",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Live dashboard: GPU status, LocalAI, metrics (Ctrl+C to exit)",
    )
    parser.add_argument(
        "--auto-config",
        action="store_true",
        help="Auto-detect GPUs and generate optimal model configs",
    )
    parser.add_argument(
        "--models",
        nargs="?",
        const="list",
        metavar="COMMAND",
        help="Model management: list (default), info <name>",
    )
    parser.add_argument(
        "--models-arg",
        metavar="NAME",
        help="Model name for --models info",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Start interactive chat session (LocalAI only)",
    )
    parser.add_argument(
        "--continue-session", "-c",
        action="store_true",
        help="Continue most recent Claude Code session in this directory",
    )
    parser.add_argument("--version", "-v", action="version", version=f"aicp {__version__}")
    return parser


def _build_backends(config: Dict) -> Dict[str, Backend]:
    """Instantiate backends from config."""
    local_cfg = get_backend_config(config, "local")
    claude_cfg = get_backend_config(config, "claude")
    return {
        "local": LocalAIBackend(
            base_url=local_cfg.get("base_url", "http://localhost:8090"),
            model=local_cfg.get("model", "default"),
        ),
        "claude": ClaudeCodeBackend(
            model=claude_cfg.get("model", "opus"),
            max_turns=claude_cfg.get("max_turns", 10),
            max_budget_usd=claude_cfg.get("max_budget_usd"),
            timeout=claude_cfg.get("timeout", 300),
        ),
    }


def _run_check(config: Dict, backends: Dict[str, Backend]) -> int:
    """Validate config and check backend availability."""
    from aicp.core.gpu import detect_gpus

    print_check_header()

    errors = validate_config(config)
    if errors:
        console.print("  Config: [bold red]INVALID[/]")
        for err in errors:
            console.print(f"    - {err}")
        return 1
    else:
        console.print("  Config: [bold green]OK[/]")

    # GPU status
    gpus = detect_gpus()
    console.print()
    if gpus:
        for g in gpus:
            pct = g.vram_used_mb / g.vram_total_mb * 100 if g.vram_total_mb > 0 else 0
            color = "green" if pct < 70 else "yellow" if pct < 90 else "red"
            console.print(
                f"  [bold]GPU {g.index}[/] {g.name}: "
                f"[{color}]{g.vram_free_mb}/{g.vram_total_mb} MiB free[/] "
                f"(driver {g.driver_version})"
            )
    else:
        console.print("  [yellow]No GPUs detected[/]")

    console.print()
    all_ok = True
    for name, backend in backends.items():
        detail = backend.status_detail()
        ok = backend.is_available()
        print_status(name, detail, ok)
        if not ok:
            all_ok = False

    console.print()
    if all_ok:
        console.print("  [bold green]All systems ready.[/]")
    else:
        console.print("  [yellow]Some backends are unavailable.[/]")

    return 0


def _run_stats() -> int:
    """Show aggregated metrics."""
    from aicp.core.metrics import aggregate
    from rich.table import Table

    m = aggregate(1000)

    if m["total_tasks"] == 0:
        console.print("[dim]No history yet.[/]")
        return 0

    table = Table(title="AICP Metrics", show_header=True, expand=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Tasks today", str(m["today"]))
    table.add_row("Tasks this week", str(m["this_week"]))
    table.add_row("Tasks total", str(m["total_tasks"]))
    table.add_row("Avg duration", f"{m['avg_duration']:.1f}s")
    table.add_row("Error rate", f"{m['error_rate']:.1f}%")
    table.add_row("Prompt tokens", f"{m['total_prompt_tokens']:,}")
    table.add_row("Completion tokens", f"{m['total_completion_tokens']:,}")
    table.add_row("Total tokens", f"{m['total_tokens']:,}")
    table.add_row("Est. cost", f"${m['total_cost_usd']:.4f}")

    console.print(table)

    for name, b in m.get("by_backend", {}).items():
        bt = Table(title=f"Backend: {name}", show_header=True, expand=False)
        bt.add_column("Metric", style="bold")
        bt.add_column("Value", justify="right")
        bt.add_row("Tasks", str(b["tasks"]))
        bt.add_row("Avg duration", f"{b['avg_duration']:.1f}s")
        bt.add_row("Error rate", f"{b['error_rate']:.1f}%")
        bt.add_row("Tokens", f"{b['prompt_tokens'] + b['completion_tokens']:,}")
        bt.add_row("Cost", f"${b['cost']:.4f}")
        console.print(bt)

    return 0


def _run_auto_config() -> int:
    """Auto-detect GPUs and generate optimal model configs."""
    from aicp.core.gpu import detect_gpus, calculate_optimal_config, estimate_model_vram_mb
    from aicp.core.models import list_models, MODELS_DIR
    from rich.table import Table

    gpus = detect_gpus()
    if not gpus:
        console.print("[yellow]No NVIDIA GPUs detected. Models will run on CPU.[/]")
    else:
        table = Table(title="Detected GPUs", show_header=True)
        table.add_column("GPU")
        table.add_column("VRAM Total", justify="right")
        table.add_column("VRAM Free", justify="right")
        table.add_column("Driver")
        for g in gpus:
            table.add_row(
                f"[bold]{g.index}[/] {g.name}",
                f"{g.vram_total_mb} MiB",
                f"[green]{g.vram_free_mb} MiB[/]",
                g.driver_version,
            )
        console.print(table)
        console.print()

    models = list_models()
    if not models:
        console.print("[dim]No models found in models/ directory.[/]")
        return 0

    for m in models:
        gguf_path = MODELS_DIR / m.gguf_file
        if not gguf_path.exists():
            console.print(f"[yellow]{m.name}: GGUF file not found ({m.gguf_file})[/]")
            continue

        est_vram = estimate_model_vram_mb(gguf_path)
        optimal = calculate_optimal_config(gguf_path, gpus)

        console.print(f"[bold]{m.name}[/] ({m.gguf_file}, {m.gguf_size_mb} MiB, est. VRAM: {est_vram} MiB)")
        console.print(f"  Current:  gpu_layers={m.gpu_layers}, context_size={m.context_size}")
        console.print(f"  Optimal:  gpu_layers={optimal['gpu_layers']}, context_size={optimal['context_size']}, threads={optimal['threads']}")

        if "tensor_split" in optimal:
            console.print(f"  Multi-GPU: tensor_split={optimal['tensor_split']}, main_gpu={optimal['main_gpu']}")

        if optimal["gpu_layers"] != m.gpu_layers or optimal["context_size"] != m.context_size:
            console.print("  [yellow]Config differs from optimal.[/] Update? ", end="")
            try:
                answer = input("[y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print()
                continue
            if answer == "y":
                _apply_optimal_config(m.config_path, optimal)
                console.print("  [green]Updated.[/] Restart LocalAI to apply: make local-up")
        else:
            console.print("  [green]Already optimal.[/]")
        console.print()

    return 0


def _apply_optimal_config(config_path: Path, optimal: dict) -> None:
    """Update a model YAML with optimal settings."""
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    cfg["gpu_layers"] = optimal["gpu_layers"]
    cfg["context_size"] = optimal["context_size"]
    cfg["threads"] = optimal["threads"]

    if "tensor_split" in optimal:
        if "parameters" not in cfg:
            cfg["parameters"] = {}
        cfg["parameters"]["tensor_split"] = optimal["tensor_split"]
        cfg["parameters"]["main_gpu"] = optimal["main_gpu"]

    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def _run_models(command: str, model_name: str = None) -> int:
    """Model management commands."""
    from aicp.core.models import list_models, get_model_config
    from rich.table import Table

    if command == "list":
        models = list_models()
        if not models:
            console.print("[dim]No models found.[/]")
            return 0

        table = Table(title="Local Models", show_header=True)
        table.add_column("Name", style="bold")
        table.add_column("File")
        table.add_column("Size", justify="right")
        table.add_column("Backend")
        table.add_column("GPU Layers", justify="right")
        table.add_column("Context", justify="right")

        for m in models:
            table.add_row(
                m.name, m.gguf_file, f"{m.gguf_size_mb} MiB",
                m.backend, str(m.gpu_layers), str(m.context_size),
            )
        console.print(table)
        return 0

    elif command == "info" and model_name:
        cfg = get_model_config(model_name)
        if cfg is None:
            print_error(f"Model not found: {model_name}")
            return 1
        import yaml
        console.print(f"[bold]{model_name}[/] configuration:")
        console.print(yaml.dump(cfg, default_flow_style=False))
        return 0

    else:
        print_error("Usage: --models list | --models info --models-arg <name>")
        return 1


def _run_history(count: int) -> int:
    """Show recent task history."""
    records = list_tasks(count)
    if not records:
        console.print("[dim]No history yet.[/]")
        return 0

    for r in records:
        print_history_entry(
            status="ERR" if r.get("error") else "OK",
            timestamp=r.get("timestamp", "?")[:19],
            mode=r.get("mode", "?"),
            backend=r.get("backend", "?"),
            duration=r.get("duration_seconds", 0),
            prompt=r.get("prompt", ""),
            record_id=r.get("id", "?"),
        )

    return 0


def _run_replay(record_id: str) -> int:
    """Replay a previous task's full output."""
    record = get_task(record_id)
    if record is None:
        print_error(f"Task not found: {record_id}")
        return 1

    console.print(f"[bold]--- Task: {record.get('id', '?')} ---[/]")
    console.print(f"  Time:     {record.get('timestamp', '?')}")
    console.print(f"  Mode:     [cyan]{record.get('mode', '?')}[/]")
    console.print(f"  Backend:  [magenta]{record.get('backend', '?')}[/]")
    console.print(f"  Project:  {record.get('project', '?')}")
    console.print(f"  Duration: {record.get('duration_seconds', 0):.1f}s")
    console.print(f"  Prompt:   {record.get('prompt', '')}")
    console.print()

    error = record.get("error")
    if error:
        print_error(error)
    else:
        print_response(record.get("response", ""))

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --auto-config (no config needed)
    if args.auto_config:
        return _run_auto_config()

    # --models (no config needed)
    if args.models is not None:
        return _run_models(args.models, args.models_arg)

    # --stats mode (no config needed)
    if args.stats:
        return _run_stats()

    # --history mode (no config needed)
    if args.history is not None:
        return _run_history(args.history)

    # --replay mode (no config needed)
    if args.replay:
        return _run_replay(args.replay)

    # Load config
    try:
        config = load_config(args.config) if args.config else load_config()
    except (FileNotFoundError, ValueError) as e:
        print_error(f"Config: {e}")
        return 1

    backends = _build_backends(config)

    # --check mode
    if args.check:
        return _run_check(config, backends)

    # --dashboard mode
    if args.dashboard:
        from aicp.cli.dashboard import run_dashboard
        local_cfg = get_backend_config(config, "local")
        return run_dashboard(local_cfg.get("base_url", "http://localhost:8090"))

    # --interactive mode (LocalAI REPL)
    if args.interactive:
        from aicp.cli.interactive import run_interactive
        local_cfg = get_backend_config(config, "local")
        return run_interactive(
            base_url=local_cfg.get("base_url", "http://localhost:8090"),
            model=local_cfg.get("model", "default"),
            mode=Mode(args.mode),
            project_path=args.project.resolve(),
        )

    # --continue-session (resume Claude Code session)
    if args.continue_session:
        import subprocess
        cmd = ["claude", "-c"]
        if args.prompt:
            cmd.extend(["-p", args.prompt])
        try:
            result = subprocess.run(cmd, cwd=str(args.project.resolve()))
            return result.returncode
        except FileNotFoundError:
            print_error("claude CLI not found on PATH.")
            return 1

    # Normal mode: need a prompt
    if not args.prompt:
        parser.print_help()
        return 1

    controller = Controller(backends, config=config)
    task = Task(
        prompt=args.prompt,
        mode=Mode(args.mode),
        project_path=args.project.resolve(),
        backend_name=args.backend,
    )

    try:
        with spinner(f"Asking {args.backend}..."):
            result = controller.run(task)
        print_response(result)
        return 0
    except Exception as e:
        error_msg = str(e)
        print_error(error_msg)
        # Suggest alternative backend on failure
        alt = "claude" if args.backend == "local" else "local"
        alt_backend = backends.get(alt)
        if alt_backend and alt_backend.is_available():
            print_warning(f"Try with --backend {alt} instead?")
        return 1


if __name__ == "__main__":
    sys.exit(main())
