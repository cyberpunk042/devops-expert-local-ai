"""Tests for path guardrails."""

from pathlib import Path

from aicp.guardrails.paths import is_path_allowed


def test_blocks_env_files():
    root = Path("/project")
    assert is_path_allowed(Path("/project/.env"), root) is False
    assert is_path_allowed(Path("/project/.env.local"), root) is False


def test_blocks_key_files():
    root = Path("/project")
    assert is_path_allowed(Path("/project/server.key"), root) is False
    assert is_path_allowed(Path("/project/cert.pem"), root) is False


def test_blocks_paths_outside_project():
    root = Path("/project")
    assert is_path_allowed(Path("/etc/passwd"), root) is False


def test_allows_normal_files():
    root = Path("/tmp/testproject")
    root.mkdir(parents=True, exist_ok=True)
    f = root / "main.py"
    f.touch()
    assert is_path_allowed(f, root) is True
