"""Skill system — reusable parameterized workflows at three layers.

Layer 1: AICP global skills (~/.aicp/skills/)
Layer 2: Project skills (<project>/.aicp/skills/)
Layer 3: Claude Code slash commands (<project>/.claude/commands/)

Skills are YAML pipeline files with parameter support.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class SkillParam:
    """A parameter for a skill."""
    name: str
    required: bool = True
    default: str = ""
    description: str = ""


@dataclass
class Skill:
    """A reusable, parameterized workflow."""
    name: str
    description: str
    source: str  # "global", "project", or "claude-command"
    path: Path
    parameters: List[SkillParam] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)


def _global_skills_dir() -> Path:
    return Path(os.environ.get("AICP_HOME", Path.home() / ".aicp")) / "skills"


def _project_skills_dir(project_path: Path) -> Path:
    return project_path / ".aicp" / "skills"


def _claude_commands_dir(project_path: Path) -> Path:
    return project_path / ".claude" / "commands"


def discover_skills(project_path: Optional[Path] = None) -> List[Skill]:
    """Discover skills from all three layers."""
    skills = []

    # Layer 1: Global
    gdir = _global_skills_dir()
    if gdir.exists():
        for f in sorted(gdir.glob("*.yaml")):
            skill = _load_skill(f, "global")
            if skill:
                skills.append(skill)

    # Layer 2: Project
    if project_path:
        pdir = _project_skills_dir(project_path)
        if pdir.exists():
            for f in sorted(pdir.glob("*.yaml")):
                skill = _load_skill(f, "project")
                if skill:
                    skills.append(skill)

    # Layer 3: Claude Code commands (read-only discovery)
    if project_path:
        cdir = _claude_commands_dir(project_path)
        if cdir.exists():
            for f in sorted(cdir.glob("*.md")):
                skills.append(Skill(
                    name=f.stem,
                    description=f"Claude Code command: /{f.stem}",
                    source="claude-command",
                    path=f,
                ))

    return skills


def get_skill(name: str, project_path: Optional[Path] = None) -> Optional[Skill]:
    """Find a skill by name across all layers."""
    for skill in discover_skills(project_path):
        if skill.name == name:
            return skill
    return None


def resolve_params(skill: Skill, provided: Dict[str, str]) -> Dict[str, str]:
    """Resolve skill parameters, applying defaults and checking required ones."""
    resolved = {}
    for param in skill.parameters:
        if param.name in provided:
            resolved[param.name] = provided[param.name]
        elif not param.required and param.default:
            resolved[param.name] = param.default
        elif param.required:
            raise ValueError(f"Missing required parameter: {param.name}")
    return resolved


def apply_params(steps: List[Dict[str, Any]], params: Dict[str, str]) -> List[Dict[str, Any]]:
    """Substitute {param_name} in step prompts."""
    result = []
    for step in steps:
        new_step = dict(step)
        prompt = new_step.get("prompt", "")
        for key, value in params.items():
            prompt = prompt.replace(f"{{{key}}}", value)
        new_step["prompt"] = prompt
        result.append(new_step)
    return result


def create_skill(
    name: str,
    description: str,
    parameters: List[Dict[str, Any]],
    steps: List[Dict[str, Any]],
    target_dir: Path,
) -> Path:
    """Create a new skill YAML file."""
    target_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "steps": steps,
    }

    path = target_dir / f"{name}.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return path


def generate_claude_command(skill: Skill, project_path: Path) -> Path:
    """Generate a Claude Code slash command (.md) from an AICP skill.

    Claude Code commands are markdown files in .claude/commands/ that
    describe what the command does. Claude Code reads them as custom
    slash commands.
    """
    cdir = _claude_commands_dir(project_path)
    cdir.mkdir(parents=True, exist_ok=True)

    params_doc = ""
    if skill.parameters:
        params_doc = "\n\nParameters:\n"
        for p in skill.parameters:
            req = "(required)" if p.required else f"(default: {p.default})"
            params_doc += f"- {p.name}: {p.description or p.name} {req}\n"

    steps_doc = "\n\nSteps:\n"
    for i, step in enumerate(skill.steps):
        steps_doc += f"{i + 1}. [{step.get('mode', 'think')}] {step.get('prompt', '')[:100]}\n"

    content = f"""# /{skill.name}

{skill.description}
{params_doc}{steps_doc}
---
This command was generated from AICP skill: {skill.name}
Run via AICP: `aicp skill run {skill.name}`
"""

    path = cdir / f"{skill.name}.md"
    with open(path, "w") as f:
        f.write(content)

    return path


def _load_skill(path: Path, source: str) -> Optional[Skill]:
    """Load a skill from a YAML file."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict) or "name" not in data:
            return None

        params = []
        for p in data.get("parameters", []):
            if isinstance(p, dict):
                params.append(SkillParam(
                    name=p.get("name", ""),
                    required=p.get("required", True),
                    default=str(p.get("default", "")),
                    description=p.get("description", ""),
                ))

        return Skill(
            name=data["name"],
            description=data.get("description", ""),
            source=source,
            path=path,
            parameters=params,
            steps=data.get("steps", []),
        )
    except (yaml.YAMLError, OSError):
        return None
