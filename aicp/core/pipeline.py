"""Task pipelines — sequential multi-step workflows from YAML.

Pipeline format:
```yaml
budget:
  max_cost_usd: 5.0
  max_duration_seconds: 300
  max_steps: 10

agents:
  reviewer:
    system_prompt: "You are a code reviewer. Be thorough."
  coder:
    system_prompt: "You are a senior developer. Write clean code."

steps:
  - prompt: "Analyze the codebase for bugs"
    mode: think
    backend: auto
    agent: reviewer
  - prompt: "Fix the bugs found: {step_0}"
    mode: edit
    backend: claude
    agent: coder
    approval: true
  - prompt: "Run tests and verify fixes"
    mode: act
    backend: claude
    condition: "no error in {step_1}"
    retry: 2
```
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from aicp.backends.base import Backend
from aicp.core.budget import BudgetLimits, load_budget_from_config
from aicp.core.modes import Mode
from aicp.core.router import classify_task


def load_pipeline(path: Path) -> Dict[str, Any]:
    """Load a full pipeline definition from a YAML file.

    Returns the full pipeline dict (steps, budget, agents).
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "steps" not in data:
        raise ValueError(f"Pipeline must have a 'steps' key: {path}")

    steps = data["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"Pipeline must have at least one step: {path}")

    return data


def run_pipeline(
    steps_or_data,
    backends: Dict[str, Backend],
    project_path: Path,
    config: Dict[str, Any] = None,
) -> List[Dict[str, Any]]:
    """Execute a pipeline, returning results for each step.

    Accepts either a list of steps (backward compat) or a full pipeline dict.
    """
    if isinstance(steps_or_data, dict):
        pipeline_data = steps_or_data
        steps = pipeline_data["steps"]
        budget = load_budget_from_config(pipeline_data)
        agents = pipeline_data.get("agents", {})
    else:
        steps = steps_or_data
        budget = BudgetLimits()
        agents = {}

    budget.start()
    results = []  # type: List[Dict[str, Any]]

    for i, step in enumerate(steps):
        # Check budget before each step
        limit_hit = budget.check()
        if limit_hit:
            print(f"[Budget] {limit_hit}", file=sys.stderr)
            print(f"[Budget] Pipeline paused. {budget.summary()}", file=sys.stderr)
            results.append({
                "step_index": i, "prompt": "", "mode": "",
                "backend": "", "result": None,
                "error": f"Budget limit: {limit_hit}",
            })
            break

        prompt = step.get("prompt", "")
        mode_str = step.get("mode", "think")
        backend_name = step.get("backend", "auto")
        needs_approval = step.get("approval", False)
        agent_name = step.get("agent")
        condition = step.get("condition")
        max_retries = step.get("retry", 0)

        # Template substitution: {step_0}, {step_1}, etc.
        for j, prev in enumerate(results):
            if prev.get("result"):
                prompt = prompt.replace(f"{{step_{j}}}", prev["result"])

        # Condition check
        if condition and results:
            cond_text = condition
            for j, prev in enumerate(results):
                cond_text = cond_text.replace(f"{{step_{j}}}", prev.get("result", "") or "")
            # Simple condition: "no error in ..."
            if "no error" in condition.lower():
                last = results[-1]
                if last.get("error"):
                    results.append({
                        "step_index": i, "prompt": prompt, "mode": mode_str,
                        "backend": backend_name, "result": None,
                        "error": f"Condition not met: {condition}",
                    })
                    continue

        # Agent system prompt injection
        if agent_name and agent_name in agents:
            agent_cfg = agents[agent_name]
            sys_prompt = agent_cfg.get("system_prompt", "")
            if sys_prompt:
                prompt = f"[System: {sys_prompt}]\n\n{prompt}"

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
            if agent_name:
                print(f"Agent: {agent_name}", file=sys.stderr)
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

        # Execute with retry
        print(f"[Step {i + 1}/{len(steps)}] {mode_str}/{backend_name}: {prompt[:80]}...", file=sys.stderr)
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = backend.execute(prompt, mode, project_path)
                usage = getattr(backend, "last_usage", {})
                budget.update(
                    cost=usage.get("estimated_cost_usd") or 0,
                    steps=1,
                )
                results.append({
                    "step_index": i, "prompt": prompt, "mode": mode_str,
                    "backend": backend_name, "result": result, "error": None,
                    "agent": agent_name,
                })
                last_error = None
                break
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    print(f"  Retry {attempt + 1}/{max_retries}: {last_error}", file=sys.stderr)

        if last_error:
            results.append({
                "step_index": i, "prompt": prompt, "mode": mode_str,
                "backend": backend_name, "result": None, "error": last_error,
                "agent": agent_name,
            })
            break

    # Budget summary
    print(f"\n[Budget Summary]\n{budget.summary()}", file=sys.stderr)

    return results
