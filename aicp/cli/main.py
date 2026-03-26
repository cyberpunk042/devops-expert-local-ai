"""AICP command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from aicp import __version__
from aicp.config.loader import load_config, get_backend_config
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
        "--config", "-c",
        type=Path,
        default=None,
        help="Config file path (default: config/default.yaml)",
    )
    parser.add_argument("--version", "-v", action="version", version=f"aicp {__version__}")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.prompt:
        parser.print_help()
        return 1

    config = load_config(args.config) if args.config else load_config()

    local_cfg = get_backend_config(config, "local")
    claude_cfg = get_backend_config(config, "claude")

    backends = {
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

    controller = Controller(backends)
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
