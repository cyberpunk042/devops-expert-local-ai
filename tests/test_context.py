"""Tests for project context builder."""

from pathlib import Path

from aicp.core.context import build_project_context


def test_builds_context_from_real_project():
    project = Path(__file__).parent.parent
    ctx = build_project_context(project, max_chars=2000)
    assert "Project structure:" in ctx
    assert "aicp" in ctx


def test_includes_readme(tmp_path):
    (tmp_path / "README.md").write_text("# My Project\nThis is a test.")
    (tmp_path / "src").mkdir()
    ctx = build_project_context(tmp_path)
    assert "My Project" in ctx
    assert "README.md" in ctx


def test_respects_max_chars(tmp_path):
    (tmp_path / "README.md").write_text("x" * 5000)
    ctx = build_project_context(tmp_path, max_chars=500)
    assert len(ctx) < 600  # some overhead from headers


def test_empty_project(tmp_path):
    ctx = build_project_context(tmp_path)
    assert ctx == ""  # empty dir, no files
