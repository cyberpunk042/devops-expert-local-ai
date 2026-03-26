"""AICP command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aicp import __version__
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
    parser.add_argument("--version", "-v", action="version", version=f"aicp {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.prompt:
        parser.print_help()
        return 1

    backends = {
        "local": LocalAIBackend(),
        "claude": ClaudeCodeBackend(),
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
