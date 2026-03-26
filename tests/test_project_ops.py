"""Tests for project lifecycle operations."""

from pathlib import Path
from unittest.mock import MagicMock

from aicp.cli.project_ops import _write_generated_files, _parse_and_add_milestones
from aicp.core.projects import init_project_state, load_project_state


def test_write_generated_files(tmp_path):
    output = """Here are the files:

--- FILE: README.md ---
# My Project
This is a test.
--- END ---

--- FILE: src/main.py ---
print("hello")
--- END ---
"""
    _write_generated_files(tmp_path, output)
    assert (tmp_path / "README.md").exists()
    assert "My Project" in (tmp_path / "README.md").read_text()
    assert (tmp_path / "src" / "main.py").exists()
    assert "hello" in (tmp_path / "src" / "main.py").read_text()


def test_write_generated_files_empty(tmp_path):
    _write_generated_files(tmp_path, "No files here.")
    # Should not crash, just no files written


def test_parse_milestones(tmp_path):
    init_project_state(tmp_path, "test")
    plan = """
M1: Set up project structure
M2: Build the intake layer
M3 - Implement data processing
4. Add reporting
Milestone 5: Deploy to production
"""
    _parse_and_add_milestones(tmp_path, plan)
    state = load_project_state(tmp_path)
    milestones = state["milestones"]
    assert len(milestones) >= 3  # Should catch at least M1, M2, M3
    names = [m["name"] for m in milestones]
    assert "M1" in names
    assert "M2" in names


def test_parse_milestones_empty(tmp_path):
    init_project_state(tmp_path, "test")
    _parse_and_add_milestones(tmp_path, "No milestones here, just text.")
    state = load_project_state(tmp_path)
    assert len(state["milestones"]) == 0
