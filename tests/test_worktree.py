"""Tests for git worktree isolation."""

import subprocess
from pathlib import Path

import pytest

from aicp.core.worktree import create_worktree, remove_worktree, worktree_diff


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), capture_output=True)
    (path / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), capture_output=True)


def test_create_worktree(tmp_path):
    _init_git_repo(tmp_path)
    wt = create_worktree(tmp_path, "test-wt")
    assert wt.exists()
    assert (wt / "file.txt").exists()
    # Clean up
    remove_worktree(tmp_path, wt)
    assert not wt.exists()


def test_create_worktree_not_git_repo(tmp_path):
    with pytest.raises(ValueError, match="Not a git repo"):
        create_worktree(tmp_path)


def test_worktree_diff(tmp_path):
    _init_git_repo(tmp_path)
    wt = create_worktree(tmp_path, "diff-test")
    (wt / "new_file.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=str(wt), capture_output=True)
    diff = worktree_diff(tmp_path, wt)
    assert "new_file.txt" in diff or "new content" in diff
    remove_worktree(tmp_path, wt)
