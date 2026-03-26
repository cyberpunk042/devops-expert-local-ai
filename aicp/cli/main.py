"""AICP command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

from aicp import __version__
from aicp.backends.base import Backend
from aicp.config.loader import load_config, validate_config, get_backend_config
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
    parser.add_argument("--version", "-v", action="version", version=f"aicp {__version__}")
    return parser


def _build_backends(config: Dict) -> Dict[str, Backend]:
    """Instantiate backends from config."""
    local_cfg = get_backend_config(config, "local")
    claude_cfg = get_backend_config(config, "claude")
    return {
        "local": LocalAIBackend(
            base_url=local_cfg.get("base_url", "http://localhost:8080"),
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

    # Config validation
    errors = validate_config(config)
    if errors:
        print("Config: INVALID")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("Config: OK")

    # Backend checks
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

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
