"""Semi-auto approval workflow — plan first, execute on approval."""

from __future__ import annotations

import sys
from typing import Any, Dict

from aicp.backends.base import Backend
from aicp.core.modes import Mode
from pathlib import Path


def run_with_approval(
    prompt: str,
    mode: Mode,
    project_path: Path,
    backend: Backend,
) -> str:
    """Two-phase execution: plan first (think), then execute on approval.

    Phase 1: Run in THINK mode to produce a plan.
    Phase 2: Show the plan, ask for approval, then run in the requested mode.
    """
    # Phase 1: Plan
    print("Phase 1: Generating plan...", file=sys.stderr)
    plan = backend.execute(prompt, Mode.THINK, project_path)

    print("\n--- Proposed Plan ---", file=sys.stderr)
    print(plan, file=sys.stderr)
    print("--- End Plan ---\n", file=sys.stderr)

    # Ask for approval
    print(f"Execute this plan in {mode.value} mode? [y/N/edit] ", end="", file=sys.stderr)
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.", file=sys.stderr)
        return plan

    if answer == "y":
        # Phase 2: Execute
        print(f"\nExecuting in {mode.value} mode...", file=sys.stderr)
        result = backend.execute(
            f"Execute this plan:\n{plan}\n\nOriginal request: {prompt}",
            mode,
            project_path,
        )
        return result
    elif answer == "edit":
        print("Enter modified prompt (Ctrl+D to finish):", file=sys.stderr)
        try:
            lines = []
            while True:
                lines.append(input())
        except EOFError:
            pass
        modified = "\n".join(lines)
        if modified.strip():
            print(f"\nExecuting modified prompt in {mode.value} mode...", file=sys.stderr)
            return backend.execute(modified, mode, project_path)
        print("Empty prompt, aborting.", file=sys.stderr)
        return plan
    else:
        print("Aborted. Plan returned without execution.", file=sys.stderr)
        return plan
