"""Project lifecycle operations — create, plan, assess.

These use AI backends to analyze ideas, propose architecture,
and evaluate project state.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from rich.console import Console

from aicp.backends.base import Backend
from aicp.core.modes import Mode
from aicp.core.projects import (
    register_project, init_project_state, load_project_state,
    save_project_state, add_milestone,
)

console = Console(stderr=True)


def create_project(
    name: str,
    parent_dir: Path,
    backend: Backend,
    idea: str = "",
) -> Path:
    """Guided project creation from an idea document.

    1. Takes idea text (or asks for it)
    2. AI analyzes and proposes architecture
    3. User reviews
    4. Generates repo structure, README, CLAUDE.md
    5. Initializes git

    Returns path to the created project.
    """
    project_path = parent_dir / name
    if project_path.exists():
        raise FileExistsError(f"Directory already exists: {project_path}")

    # Step 1: Get idea
    if not idea:
        console.print("[bold]Describe your project idea[/] (paste text, then Ctrl+D):")
        try:
            lines = []
            while True:
                lines.append(input())
        except EOFError:
            pass
        idea = "\n".join(lines)

    if not idea.strip():
        raise ValueError("No idea provided.")

    console.print(f"\n[bold]Analyzing idea for '{name}'...[/]")

    # Step 2: AI proposes architecture
    arch_prompt = f"""Analyze this project idea and propose a concrete architecture.

Project name: {name}

Idea:
{idea}

Respond with:
1. One-line description
2. Key components/layers (3-7 items)
3. Suggested directory structure
4. Tech stack recommendations
5. First 3 milestones to build

Be specific and actionable. This will be used to scaffold the project."""

    architecture = backend.execute(arch_prompt, Mode.THINK, parent_dir)
    console.print("\n[bold]Proposed architecture:[/]")
    console.print(architecture)

    # Step 3: User review
    console.print("\n[yellow]Create project with this architecture?[/] [y/N/edit] ", end="")
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        raise ValueError("Cancelled.")

    if answer == "edit":
        console.print("Enter modifications (Ctrl+D to finish):")
        try:
            edits = []
            while True:
                edits.append(input())
        except EOFError:
            pass
        if edits:
            architecture = backend.execute(
                f"Revise this architecture based on feedback:\n\n"
                f"Original:\n{architecture}\n\nFeedback:\n" + "\n".join(edits),
                Mode.THINK, parent_dir,
            )
            console.print("\n[bold]Revised architecture:[/]")
            console.print(architecture)
    elif answer != "y":
        raise ValueError("Cancelled.")

    # Step 4: Generate project files
    console.print(f"\n[bold]Scaffolding {name}...[/]")

    gen_prompt = f"""Generate the initial files for this project.

Project: {name}
Architecture:
{architecture}

Generate ONLY these files (output each with its path and content):
1. README.md — project overview, architecture, setup instructions
2. CLAUDE.md — instructions for AI assistants working on this project

For each file, output:
--- FILE: <path> ---
<content>
--- END ---"""

    files_output = backend.execute(gen_prompt, Mode.THINK, parent_dir)

    # Create directory and write files
    project_path.mkdir(parents=True)
    _write_generated_files(project_path, files_output)

    # Ensure README and CLAUDE.md exist even if AI didn't generate them properly
    if not (project_path / "README.md").exists():
        (project_path / "README.md").write_text(f"# {name}\n\n{idea[:500]}\n")
    if not (project_path / "CLAUDE.md").exists():
        (project_path / "CLAUDE.md").write_text(
            f"# {name}\n\n## Architecture\n\n{architecture[:1000]}\n"
        )

    # Step 5: Git init
    subprocess.run(["git", "init"], cwd=str(project_path), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(project_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"Initial scaffold for {name}"],
        cwd=str(project_path), capture_output=True,
    )

    # Register with AICP
    register_project(project_path, name=name, description=idea[:200])

    # Initialize state with architecture reference
    state = load_project_state(project_path)
    if state:
        state["idea"] = idea[:2000]
        state["architecture"] = architecture[:3000]
        save_project_state(project_path, state)

    console.print(f"\n[green]Project created:[/] {project_path}")
    console.print(f"  [bold]cd {project_path}[/] to start working")
    return project_path


def plan_project(project_path: Path, backend: Backend) -> None:
    """Break a project's architecture into milestones."""
    state = load_project_state(project_path)
    if state is None:
        raise ValueError("No project state. Run --project-cmd register first.")

    # Build context
    arch = state.get("architecture", "")
    idea = state.get("idea", "")
    existing_milestones = state.get("milestones", [])

    # Read project files for context
    readme = ""
    claude_md = ""
    if (project_path / "README.md").exists():
        readme = (project_path / "README.md").read_text(errors="replace")[:2000]
    if (project_path / "CLAUDE.md").exists():
        claude_md = (project_path / "CLAUDE.md").read_text(errors="replace")[:2000]

    prompt = f"""Analyze this project and propose milestones.

Project: {state.get('name', project_path.name)}
Idea: {idea[:500]}
Architecture: {arch[:1000]}

README:
{readme[:500]}

CLAUDE.md:
{claude_md[:500]}

Existing milestones: {[m['name'] for m in existing_milestones] if existing_milestones else 'none'}

Propose 5-8 milestones that build on each other. For each:
- Name (short, like M1, M2)
- Description (one line)
- Dependencies (which milestones must be done first)

Be specific to THIS project, not generic."""

    console.print("[bold]Generating milestone plan...[/]")
    plan = backend.execute(prompt, Mode.THINK, project_path)
    console.print("\n[bold]Proposed milestones:[/]")
    console.print(plan)

    console.print("\n[yellow]Apply these milestones?[/] [y/N] ", end="")
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer == "y":
        # Parse milestones from AI output (best effort)
        _parse_and_add_milestones(project_path, plan)
        state = load_project_state(project_path)
        state["phase"] = "planned"
        save_project_state(project_path, state)
        console.print("[green]Milestones saved.[/]")


def assess_project(project_path: Path, backend: Backend) -> None:
    """Evaluate current project state against the plan."""
    state = load_project_state(project_path)
    if state is None:
        raise ValueError("No project state. Run --project-cmd register first.")

    milestones = state.get("milestones", [])

    # Get git log for recent activity
    git_log = ""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-20"],
            capture_output=True, text=True, cwd=str(project_path),
        )
        git_log = result.stdout
    except Exception:
        pass

    # Get file listing
    try:
        result = subprocess.run(
            ["find", ".", "-name", "*.py", "-not", "-path", "./.venv/*",
             "-not", "-path", "./__pycache__/*"],
            capture_output=True, text=True, cwd=str(project_path),
        )
        files = result.stdout
    except Exception:
        files = ""

    prompt = f"""Assess this project's current state.

Project: {state.get('name', project_path.name)}
Phase: {state.get('phase', '?')}

Milestones:
{_format_milestones(milestones)}

Recent git history:
{git_log[:500]}

Python files:
{files[:500]}

Provide:
1. What's been accomplished
2. Current state assessment
3. What should be done next (specific, actionable)
4. Any risks or blockers
5. Suggested milestone status updates"""

    console.print("[bold]Assessing project...[/]")
    assessment = backend.execute(prompt, Mode.THINK, project_path)
    console.print("\n[bold]Assessment:[/]")
    console.print(assessment)

    # Update session
    from aicp.core.projects import update_session
    update_session(project_path, f"Assessment completed")


def _write_generated_files(project_path: Path, output: str) -> None:
    """Parse AI-generated file output and write files."""
    import re
    pattern = r"---\s*FILE:\s*(.+?)\s*---\n(.*?)---\s*END\s*---"
    matches = re.findall(pattern, output, re.DOTALL)
    for filepath, content in matches:
        filepath = filepath.strip()
        target = project_path / filepath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.strip() + "\n")
        console.print(f"  Created: {filepath}")


def _parse_and_add_milestones(project_path: Path, plan: str) -> None:
    """Best-effort parse milestone names from AI output."""
    import re
    # Look for patterns like "M1:", "M1 -", "1.", "Milestone 1:"
    lines = plan.split("\n")
    for line in lines:
        line = line.strip()
        match = re.match(
            r"^(?:M(\d+)|(\d+)\.?|Milestone\s+(\d+))\s*[:\-–]\s*(.+)",
            line, re.IGNORECASE,
        )
        if match:
            num = match.group(1) or match.group(2) or match.group(3)
            desc = match.group(4).strip()
            name = f"M{num}"
            add_milestone(project_path, name, desc)


def _format_milestones(milestones: list) -> str:
    if not milestones:
        return "None defined"
    lines = []
    for m in milestones:
        lines.append(f"  [{m.get('status', 'pending')}] {m['name']}: {m.get('description', '')}")
    return "\n".join(lines)
