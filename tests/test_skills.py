"""Tests for skill system."""

from pathlib import Path

import yaml

from aicp.core.skills import (
    Skill,
    SkillParam,
    apply_params,
    create_skill,
    discover_skills,
    get_skill,
    resolve_params,
)


def _create_skill_yaml(path, name, desc="", params=None, steps=None):
    data = {
        "name": name,
        "description": desc,
        "parameters": params or [],
        "steps": steps or [{"prompt": "test", "mode": "think"}],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data))


def test_discover_global_skills(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    skill_dir = tmp_path / "skills"
    _create_skill_yaml(skill_dir / "my-skill.yaml", "my-skill", "A test skill")

    skills = discover_skills()
    assert len(skills) == 1
    assert skills[0].name == "my-skill"
    assert skills[0].source == "global"


def test_discover_project_skills(tmp_path):
    skill_dir = tmp_path / ".aicp" / "skills"
    _create_skill_yaml(skill_dir / "proj-skill.yaml", "proj-skill")

    skills = discover_skills(tmp_path)
    assert any(s.name == "proj-skill" and s.source == "project" for s in skills)


def test_discover_claude_skills(tmp_path):
    skill_dir = tmp_path / ".claude" / "skills" / "my-cmd"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: my-cmd\ndescription: Does stuff\n---\n\nDo stuff.")

    skills = discover_skills(tmp_path)
    assert any(s.name == "my-cmd" and s.source == "claude-project" for s in skills)


def test_get_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    skill_dir = tmp_path / "skills"
    _create_skill_yaml(skill_dir / "find-me.yaml", "find-me", "Found it")

    skill = get_skill("find-me")
    assert skill is not None
    assert skill.description == "Found it"


def test_get_skill_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    assert get_skill("nonexistent") is None


def test_resolve_params():
    skill = Skill(
        name="test", description="", source="global", path=Path("."),
        parameters=[
            SkillParam(name="name", required=True),
            SkillParam(name="desc", required=False, default="none"),
        ],
    )
    resolved = resolve_params(skill, {"name": "foo"})
    assert resolved == {"name": "foo", "desc": "none"}


def test_resolve_params_missing_required():
    skill = Skill(
        name="test", description="", source="global", path=Path("."),
        parameters=[SkillParam(name="required_param", required=True)],
    )
    import pytest
    with pytest.raises(ValueError, match="required_param"):
        resolve_params(skill, {})


def test_apply_params():
    steps = [
        {"prompt": "Create {name}: {desc}", "mode": "edit"},
        {"prompt": "Test {name}", "mode": "think"},
    ]
    result = apply_params(steps, {"name": "foo", "desc": "bar"})
    assert result[0]["prompt"] == "Create foo: bar"
    assert result[1]["prompt"] == "Test foo"


def test_create_skill(tmp_path):
    path = create_skill(
        "new-skill", "Does things",
        [{"name": "target", "required": True}],
        [{"prompt": "Do {target}", "mode": "think"}],
        tmp_path,
    )
    assert path.exists()
    with open(path) as f:
        data = yaml.safe_load(f)
    assert data["name"] == "new-skill"
    assert len(data["steps"]) == 1


def test_generate_claude_skill(tmp_path):
    from aicp.core.skills import generate_claude_skill
    skill = Skill(
        name="test-cmd", description="A test command", source="project",
        path=Path("."),
        parameters=[SkillParam(name="target", description="What to target")],
        steps=[{"prompt": "Do {target}", "mode": "think"}],
    )
    path = generate_claude_skill(skill, tmp_path)
    assert path.exists()
    content = path.read_text()
    assert "test-cmd" in content
    assert "target" in content
    assert (tmp_path / ".claude" / "skills" / "test-cmd" / "SKILL.md").exists()
