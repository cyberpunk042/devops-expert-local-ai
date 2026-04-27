"""Skill system — reusable parameterized workflows at three layers.

Layer 1: AICP global skills (~/.aicp/skills/)
Layer 2: Project skills (<project>/.aicp/skills/)
Layer 3: Claude Code slash commands (<project>/.claude/commands/)

Skills are YAML pipeline files with parameter support.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    parameters: list[SkillParam] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    # New fields (inspired by Claude Code)
    model: str = ""              # Model override (e.g., "gemma4-e2b" for fleet skills)
    allowed_tools: list[str] = field(default_factory=list)  # Tool restriction
    effort: str = ""             # low, medium, high
    context: str = "inline"      # "inline" (expand in conversation) or "fork" (sub-agent)
    paths: list[str] = field(default_factory=list)  # Scope restriction


def _global_skills_dir() -> Path:
    return Path(os.environ.get("AICP_HOME", Path.home() / ".aicp")) / "skills"


def _project_skills_dir(project_path: Path) -> Path:
    return project_path / ".aicp" / "skills"


def _claude_skills_dir(project_path: Path) -> Path:
    return project_path / ".claude" / "skills"


def _global_claude_skills_dir() -> Path:
    return Path.home() / ".claude" / "skills"


def discover_skills(project_path: Path | None = None) -> list[Skill]:
    """Discover skills from all layers.

    Discovery order (later overrides earlier):
    1. AICP global skills (~/.aicp/skills/*.yaml)
    2. AICP project skills (<project>/.aicp/skills/*.yaml)
    3. Claude Code global skills (~/.claude/skills/*/SKILL.md)
    4. Claude Code project skills (<project>/.claude/skills/*/SKILL.md)
    """
    skills = []
    seen = set()  # type: set

    # Layer 1: AICP global YAML skills
    gdir = _global_skills_dir()
    if gdir.exists():
        for f in sorted(gdir.glob("*.yaml")):
            skill = _load_skill_yaml(f, "global")
            if skill and skill.name not in seen:
                skills.append(skill)
                seen.add(skill.name)

    # Layer 2: AICP project YAML skills
    if project_path:
        pdir = _project_skills_dir(project_path)
        if pdir.exists():
            for f in sorted(pdir.glob("*.yaml")):
                skill = _load_skill_yaml(f, "project")
                if skill:
                    # Override global if same name
                    skills = [s for s in skills if s.name != skill.name]
                    seen.discard(skill.name)
                    skills.append(skill)
                    seen.add(skill.name)

    # Layer 3: Claude Code global SKILL.md skills
    gcdir = _global_claude_skills_dir()
    if gcdir.exists():
        for skill_dir in sorted(gcdir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                skill = _load_skill_md(skill_md, "claude-global")
                if skill and skill.name not in seen:
                    skills.append(skill)
                    seen.add(skill.name)

    # Layer 4: Claude Code project SKILL.md skills
    if project_path:
        cdir = _claude_skills_dir(project_path)
        if cdir.exists():
            for skill_dir in sorted(cdir.iterdir()):
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    skill = _load_skill_md(skill_md, "claude-project")
                    if skill:
                        skills = [s for s in skills if s.name != skill.name]
                        skills.append(skill)
                        seen.add(skill.name)

    return skills


def get_skill(name: str, project_path: Path | None = None) -> Skill | None:
    """Find a skill by name across all layers."""
    for skill in discover_skills(project_path):
        if skill.name == name:
            return skill
    return None


def resolve_params(skill: Skill, provided: dict[str, str]) -> dict[str, str]:
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


def apply_params(steps: list[dict[str, Any]], params: dict[str, str]) -> list[dict[str, Any]]:
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
    parameters: list[dict[str, Any]],
    steps: list[dict[str, Any]],
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


def generate_claude_skill(skill: Skill, project_path: Path) -> Path:
    """Generate a Claude Code SKILL.md from an AICP skill.

    Creates .claude/skills/<name>/SKILL.md in the proper Claude Code format.
    """
    skill_dir = _claude_skills_dir(project_path) / skill.name
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Build argument hint from parameters
    arg_hint = ""
    if skill.parameters:
        hints = []
        for p in skill.parameters:
            if p.required:
                hints.append(f"<{p.name}>")
            else:
                hints.append(f"[{p.name}]")
        arg_hint = " ".join(hints)

    # Build frontmatter
    frontmatter = f"""---
name: {skill.name}
description: {skill.description}"""
    if arg_hint:
        frontmatter += f"\nargument-hint: {arg_hint}"
    if skill.allowed_tools:
        frontmatter += f"\nallowed-tools: {', '.join(skill.allowed_tools)}"
    if skill.model:
        frontmatter += f"\nmodel: {skill.model}"
    if skill.effort:
        frontmatter += f"\neffort: {skill.effort}"
    else:
        frontmatter += "\neffort: medium"
    if skill.context != "inline":
        frontmatter += f"\ncontext: {skill.context}"
    if skill.paths:
        frontmatter += f"\npaths: {skill.paths}"
    frontmatter += """
---"""

    # Build body
    body = f"\n\n# {skill.name}\n\n{skill.description}\n"

    if skill.parameters:
        body += "\n## Parameters\n\n"
        for p in skill.parameters:
            req = "(required)" if p.required else f"(default: {p.default})"
            body += f"- **{p.name}**: {p.description or p.name} {req}\n"

    if skill.steps:
        body += "\n## Steps\n\n"
        for i, step in enumerate(skill.steps):
            body += f"{i + 1}. [{step.get('mode', 'think')}] {step.get('prompt', '')}\n"

    body += f"\n---\nGenerated from AICP skill. Run via: `aicp --skill run --skill-name {skill.name}`\n"

    path = skill_dir / "SKILL.md"
    with open(path, "w") as f:
        f.write(frontmatter + body)

    return path

# Backward compat
generate_claude_command = generate_claude_skill


def _parse_allowed_tools(raw: Any) -> list[str]:
    """Parse allowed-tools from frontmatter (comma-separated string or list)."""
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if t]
    if isinstance(raw, str) and raw.strip():
        return [t.strip() for t in raw.split(",") if t.strip()]
    return []


def _load_skill_yaml(path: Path, source: str) -> Skill | None:
    """Load a skill from a YAML file (AICP format)."""
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
            model=data.get("model", ""),
            allowed_tools=_parse_allowed_tools(data.get("allowed-tools", "")),
            effort=data.get("effort", ""),
            context=data.get("context", "inline"),
            paths=data.get("paths", []),
        )
    except (yaml.YAMLError, OSError):
        return None

# Keep backward compat alias
_load_skill = _load_skill_yaml


def _load_skill_md(path: Path, source: str) -> Skill | None:
    """Load a skill from a SKILL.md file (Claude Code format).

    Parses YAML frontmatter between --- delimiters.
    """
    try:
        content = path.read_text(errors="replace")

        # Parse frontmatter
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        frontmatter = yaml.safe_load(parts[1])
        if not isinstance(frontmatter, dict):
            return None

        name = frontmatter.get("name", path.parent.name)
        description = frontmatter.get("description", "")
        argument_hint = frontmatter.get("argument-hint", "")
        if not isinstance(argument_hint, str):
            argument_hint = str(argument_hint) if argument_hint else ""

        model = frontmatter.get("model", "")
        allowed_tools = _parse_allowed_tools(frontmatter.get("allowed-tools", ""))
        effort = frontmatter.get("effort", "")
        context = frontmatter.get("context", "inline")
        paths_raw = frontmatter.get("paths", [])
        paths = paths_raw if isinstance(paths_raw, list) else []

        # Parse argument hints as parameters (best effort)
        params = []
        if argument_hint:
            import re
            # Parse patterns like <required> [optional] [optional: default]
            for match in re.finditer(r"[<\[]([^>\]]+)[>\]]", argument_hint):
                param_text = match.group(1)
                required = match.group(0).startswith("<")
                param_parts = param_text.split(":", 1)
                param_name = param_parts[0].strip()
                default = param_parts[1].strip() if len(param_parts) > 1 else ""
                params.append(SkillParam(
                    name=param_name,
                    required=required,
                    default=default,
                ))

        return Skill(
            name=name,
            description=description,
            source=source,
            path=path,
            parameters=params,
            # SKILL.md skills don't have pipeline steps — they're instructions for Claude
            steps=[],
            model=model if isinstance(model, str) else "",
            allowed_tools=allowed_tools,
            effort=effort if isinstance(effort, str) else "",
            context=context if isinstance(context, str) else "inline",
            paths=paths,
        )
    except (yaml.YAMLError, OSError):
        return None
