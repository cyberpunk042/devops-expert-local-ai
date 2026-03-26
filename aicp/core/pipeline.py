"""Task pipelines — sequential multi-step workflows from YAML."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from aicp.backends.base import Backend
from aicp.core.modes import Mode
from aicp.core.router import classify_task


def load_pipeline(path: Path) -> List[Dict[str, Any]]:
    """Load a pipeline definition from a YAML file.

    Pipeline format:
    ```yaml
    steps:
      - prompt: "Analyze the codebase for bugs"
        mode: think
        backend: auto  # or local, claude
      - prompt: "Fix the bugs found in step 1"
        mode: edit
        backend: claude
        approval: true  # pause for approval before executing
    ```
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "steps" not in data:
        raise ValueError(f"Pipeline must have a 'steps' key: {path}")

    steps = data["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"Pipeline must have at least one step: {path}")

    return steps


def run_pipeline(
    steps: List[Dict[str, Any]],
    backends: Dict[str, Backend],
    project_path: Path,
    config: Dict[str, Any] = None,
) -> List[Dict[str, Any]]:
    """Execute a pipeline, returning results for each step.

    Each step result dict has: step_index, prompt, mode, backend, result, error.
    Previous step results are available as {step_N} in prompt templates.
    """
    results = []  # type: List[Dict[str, Any]]

    for i, step in enumerate(steps):
        prompt = step.get("prompt", "")
        mode_str = step.get("mode", "think")
        backend_name = step.get("backend", "auto")
        needs_approval = step.get("approval", False)

        # Template substitution: {step_0}, {step_1}, etc.
        for j, prev in enumerate(results):
            if prev.get("result"):
                prompt = prompt.replace(f"{{step_{j}}}", prev["result"])

        mode = Mode(mode_str)

        # Resolve backend
        if backend_name == "auto":
            backend_name = classify_task(prompt, mode, backends, config)

        backend = backends.get(backend_name)
        if backend is None:
            results.append({
                "step_index": i, "prompt": prompt, "mode": mode_str,
                "backend": backend_name, "result": None,
                "error": f"Unknown backend: {backend_name}",
            })
            break

        # Approval gate
        if needs_approval:
            print(f"\n--- Step {i + 1}/{len(steps)} ---", file=sys.stderr)
            print(f"Mode: {mode_str} | Backend: {backend_name}", file=sys.stderr)
            print(f"Prompt: {prompt[:200]}", file=sys.stderr)
            print("Execute? [y/N] ", end="", file=sys.stderr)
            try:
                answer = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "n"
            if answer != "y":
                results.append({
                    "step_index": i, "prompt": prompt, "mode": mode_str,
                    "backend": backend_name, "result": None,
                    "error": "Skipped by user",
                })
                break

        # Execute
        print(f"[Step {i + 1}/{len(steps)}] {mode_str}/{backend_name}: {prompt[:80]}...", file=sys.stderr)
        try:
            result = backend.execute(prompt, mode, project_path)
            results.append({
                "step_index": i, "prompt": prompt, "mode": mode_str,
                "backend": backend_name, "result": result, "error": None,
            })
        except Exception as e:
            results.append({
                "step_index": i, "prompt": prompt, "mode": mode_str,
                "backend": backend_name, "result": None, "error": str(e),
            })
            break  # Stop pipeline on error

    return results
