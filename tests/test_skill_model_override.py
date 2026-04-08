"""Tests for skill model override and new frontmatter fields."""

import pytest
from pathlib import Path

from aicp.core.skills import (
    Skill,
    SkillParam,
    _load_skill_md,
    _load_skill_yaml,
    _parse_allowed_tools,
    discover_skills,
    generate_claude_skill,
    get_skill,
)


class TestParseAllowedTools:
    def test_comma_separated_string(self):
        assert _parse_allowed_tools("Read, Write, Edit") == ["Read", "Write", "Edit"]

    def test_list(self):
        assert _parse_allowed_tools(["Read", "Write"]) == ["Read", "Write"]

    def test_empty_string(self):
        assert _parse_allowed_tools("") == []

    def test_none(self):
        assert _parse_allowed_tools(None) == []

    def test_single_tool(self):
        assert _parse_allowed_tools("Bash") == ["Bash"]

    def test_strips_whitespace(self):
        assert _parse_allowed_tools("  Read ,  Write  ") == ["Read", "Write"]

    def test_filters_empty_entries(self):
        assert _parse_allowed_tools("Read,,Write,") == ["Read", "Write"]


class TestSkillModelOverride:
    def test_skill_dataclass_defaults(self):
        s = Skill(name="test", description="test", source="global", path=Path("."))
        assert s.model == ""
        assert s.allowed_tools == []
        assert s.effort == ""
        assert s.context == "inline"
        assert s.paths == []

    def test_skill_with_model(self):
        s = Skill(
            name="heartbeat", description="Fleet heartbeat",
            source="project", path=Path("."),
            model="gemma4-e2b",
        )
        assert s.model == "gemma4-e2b"

    def test_load_md_with_model(self, tmp_path):
        skill_dir = tmp_path / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: test-skill\n"
            "description: Test with model override\n"
            "allowed-tools: Read, Bash, Grep\n"
            "model: gemma4-e2b\n"
            "effort: low\n"
            "context: fork\n"
            "---\n\nDo the thing.\n"
        )
        skill = _load_skill_md(skill_dir / "SKILL.md", "test")
        assert skill is not None
        assert skill.model == "gemma4-e2b"
        assert skill.allowed_tools == ["Read", "Bash", "Grep"]
        assert skill.effort == "low"
        assert skill.context == "fork"

    def test_load_md_without_model(self, tmp_path):
        skill_dir = tmp_path / "skills" / "plain"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: plain\ndescription: No model\n---\nJust text.\n"
        )
        skill = _load_skill_md(skill_dir / "SKILL.md", "test")
        assert skill is not None
        assert skill.model == ""
        assert skill.context == "inline"

    def test_load_md_with_paths(self, tmp_path):
        skill_dir = tmp_path / "skills" / "scoped"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: scoped\n"
            "description: Scoped skill\n"
            "paths:\n"
            "  - src/\n"
            "  - tests/\n"
            "---\nScoped work.\n"
        )
        skill = _load_skill_md(skill_dir / "SKILL.md", "test")
        assert skill is not None
        assert skill.paths == ["src/", "tests/"]

    def test_load_yaml_with_model(self, tmp_path):
        skill_file = tmp_path / "heartbeat.yaml"
        skill_file.write_text(
            "name: heartbeat\n"
            "description: Fleet heartbeat\n"
            "model: gemma4-e2b\n"
            "allowed-tools: Read\n"
            "effort: low\n"
            "context: inline\n"
            "paths:\n"
            "  - config/\n"
            "steps:\n"
            "  - prompt: Check status\n"
        )
        skill = _load_skill_yaml(skill_file, "global")
        assert skill is not None
        assert skill.model == "gemma4-e2b"
        assert skill.allowed_tools == ["Read"]
        assert skill.effort == "low"
        assert skill.paths == ["config/"]

    def test_load_yaml_without_new_fields(self, tmp_path):
        """Backward compatibility — old YAML skills without new fields."""
        skill_file = tmp_path / "old.yaml"
        skill_file.write_text(
            "name: old-skill\n"
            "description: Legacy skill\n"
            "steps:\n"
            "  - prompt: Do something\n"
        )
        skill = _load_skill_yaml(skill_file, "global")
        assert skill is not None
        assert skill.model == ""
        assert skill.allowed_tools == []
        assert skill.effort == ""
        assert skill.context == "inline"

    def test_generate_claude_skill_with_model(self, tmp_path):
        skill = Skill(
            name="fleet-heartbeat",
            description="Fleet agent heartbeat response",
            source="project",
            path=Path("."),
            model="gemma4-e2b",
            allowed_tools=["Read", "Grep"],
            effort="low",
            context="fork",
        )
        path = generate_claude_skill(skill, tmp_path)
        content = path.read_text()
        assert "model: gemma4-e2b" in content
        assert "allowed-tools: Read, Grep" in content
        assert "effort: low" in content
        assert "context: fork" in content

    def test_generate_claude_skill_default_effort(self, tmp_path):
        skill = Skill(
            name="basic",
            description="Basic skill",
            source="global",
            path=Path("."),
        )
        path = generate_claude_skill(skill, tmp_path)
        content = path.read_text()
        assert "effort: medium" in content  # default
        assert "model:" not in content  # empty model not included
        assert "context:" not in content  # inline is default, not included

    def test_load_md_invalid_model_type(self, tmp_path):
        """Non-string model field should be handled gracefully."""
        skill_dir = tmp_path / "skills" / "bad"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: bad\ndescription: Bad model\nmodel: 123\n---\nContent.\n"
        )
        skill = _load_skill_md(skill_dir / "SKILL.md", "test")
        assert skill is not None
        # Non-string model should be empty (fail-safe)
        assert skill.model == ""

    def test_load_md_invalid_context_type(self, tmp_path):
        skill_dir = tmp_path / "skills" / "bad2"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: bad2\ndescription: Bad context\ncontext: 42\n---\nContent.\n"
        )
        skill = _load_skill_md(skill_dir / "SKILL.md", "test")
        assert skill is not None
        assert skill.context == "inline"  # fallback to default

    def test_allowed_tools_as_list_in_yaml(self, tmp_path):
        skill_file = tmp_path / "list_tools.yaml"
        skill_file.write_text(
            "name: list-tools\n"
            "description: Tools as list\n"
            "allowed-tools:\n"
            "  - Read\n"
            "  - Write\n"
            "  - Bash\n"
            "steps: []\n"
        )
        skill = _load_skill_yaml(skill_file, "global")
        assert skill is not None
        assert skill.allowed_tools == ["Read", "Write", "Bash"]

    def test_discover_skills_includes_new_fields(self, tmp_path):
        """Skills discovered from .claude/skills/ should have new fields."""
        skill_dir = tmp_path / ".claude" / "skills" / "enhanced"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: enhanced\n"
            "description: Enhanced skill\n"
            "model: qwen3-8b\n"
            "allowed-tools: Read, Grep\n"
            "effort: high\n"
            "---\nEnhanced content.\n"
        )
        skills = discover_skills(tmp_path)
        assert len(skills) >= 1
        s = next(s for s in skills if s.name == "enhanced")
        assert s.model == "qwen3-8b"
        assert s.allowed_tools == ["Read", "Grep"]
        assert s.effort == "high"
