"""AICP command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

from aicp import __version__
from aicp.backends.base import Backend
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
        default="think",
        help="Permission mode (default: think)",
    )
    parser.add_argument(
        "--backend", "-b",
        choices=["local", "claude"],
        default="local",
        help="AI backend (default: local)",
    )
    parser.add_argument(
        "--project", "-d",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: current directory)",
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
    print(f"AICP v{__version__} — system check\n")

    errors = validate_config(config)
    if errors:
        print("Config: INVALID")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("Config: OK")

    print()
    all_ok = True
    for name, backend in backends.items():
        detail = backend.status_detail()
        ok = backend.is_available()
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("All systems ready.")
    else:
        print("Some backends are unavailable. AICP will work with the available ones.")

    return 0


def _run_history(count: int) -> int:
    """Show recent task history."""
    records = list_tasks(count)
    if not records:
        print("No history yet.")
        return 0

    for r in records:
        ts = r.get("timestamp", "?")[:19]
        mode = r.get("mode", "?")
        backend = r.get("backend", "?")
        prompt = r.get("prompt", "")
        error = r.get("error")
        duration = r.get("duration_seconds", 0)
        rid = r.get("id", "?")

        prompt_preview = prompt[:60] + "..." if len(prompt) > 60 else prompt
        status = "ERR" if error else "OK"
        print(f"[{status}] {ts}  {mode:5s}  {backend:6s}  {duration:5.1f}s  {prompt_preview}")
        print(f"       ID: {rid}")

    return 0


def _run_replay(record_id: str) -> int:
    """Replay a previous task's full output."""
    record = get_task(record_id)
    if record is None:
        print(f"Task not found: {record_id}", file=sys.stderr)
        return 1

    print(f"--- Task: {record.get('id', '?')} ---")
    print(f"Time:    {record.get('timestamp', '?')}")
    print(f"Mode:    {record.get('mode', '?')}")
    print(f"Backend: {record.get('backend', '?')}")
    print(f"Project: {record.get('project', '?')}")
    print(f"Duration: {record.get('duration_seconds', 0):.1f}s")
    print(f"Prompt:  {record.get('prompt', '')}")
    print()

    error = record.get("error")
    if error:
        print(f"Error: {error}")
    else:
        print(record.get("response", ""))

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

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
        print(f"Config error: {e}", file=sys.stderr)
        return 1

    backends = _build_backends(config)

    # --check mode
    if args.check:
        return _run_check(config, backends)

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
        result = controller.run(task)
        print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
