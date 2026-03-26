"""Git worktree isolation — run tasks in isolated branches."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Optional


def create_worktree(project_path: Path, name: Optional[str] = None) -> Path:
    """Create a git worktree for isolated task execution.

    Returns the path to the worktree directory.
    """
    if not (project_path / ".git").exists():
        raise ValueError(f"Not a git repo: {project_path}")

    if name is None:
        name = f"aicp-{uuid.uuid4().hex[:8]}"

    worktree_dir = project_path / ".aicp-worktrees" / name
    branch_name = f"aicp/{name}"

    # Create worktree with a new branch
    result = subprocess.run(
        ["git", "worktree", "add", "-b", branch_name, str(worktree_dir)],
        capture_output=True, text=True, cwd=str(project_path),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create worktree: {result.stderr.strip()}")

    return worktree_dir


def remove_worktree(project_path: Path, worktree_dir: Path) -> None:
    """Remove a worktree and its branch."""
    branch = _get_worktree_branch(project_path, worktree_dir)

    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_dir)],
        capture_output=True, text=True, cwd=str(project_path),
    )

    if branch:
        subprocess.run(
            ["git", "branch", "-D", branch],
            capture_output=True, text=True, cwd=str(project_path),
        )


def merge_worktree(project_path: Path, worktree_dir: Path) -> str:
    """Merge a worktree branch back into the current branch.

    Returns the merge output.
    """
    branch = _get_worktree_branch(project_path, worktree_dir)
    if not branch:
        raise ValueError("Could not determine worktree branch")

    result = subprocess.run(
        ["git", "merge", "--no-ff", branch, "-m", f"Merge AICP worktree: {branch}"],
        capture_output=True, text=True, cwd=str(project_path),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Merge failed: {result.stderr.strip()}")

    # Clean up
    remove_worktree(project_path, worktree_dir)
    return result.stdout


def worktree_diff(project_path: Path, worktree_dir: Path) -> str:
    """Get the diff of changes made in a worktree."""
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        capture_output=True, text=True, cwd=str(worktree_dir),
    )
    return result.stdout


def _get_worktree_branch(project_path: Path, worktree_dir: Path) -> Optional[str]:
    """Get the branch name for a worktree."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, cwd=str(project_path),
    )
    worktree_str = str(worktree_dir.resolve())
    lines = result.stdout.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("worktree ") and line[9:] == worktree_str:
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].startswith("branch refs/heads/"):
                    return lines[j].replace("branch refs/heads/", "")
    return None
