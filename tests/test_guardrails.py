"""Tests for path guardrails and pre-execution checks."""

from pathlib import Path

import pytest

from aicp.core.modes import Mode
from aicp.guardrails.paths import is_path_allowed, get_forbidden_patterns
from aicp.guardrails.checks import check_project_path, check_mode_compatibility, run_preflight_checks


# --- Path guardrails ---

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


def test_blocks_credentials_anywhere_in_name():
    root = Path("/project")
    assert is_path_allowed(Path("/project/aws_credentials.json"), root) is False
    assert is_path_allowed(Path("/project/my_secret_file.txt"), root) is False


def test_custom_forbidden_patterns():
    root = Path("/tmp/testproject")
    root.mkdir(parents=True, exist_ok=True)
    f = root / "data.csv"
    f.touch()
    # Default patterns allow .csv
    assert is_path_allowed(f, root) is True
    # Custom pattern blocks it
    assert is_path_allowed(f, root, forbidden_patterns=["*.csv"]) is False


def test_get_forbidden_patterns_from_config():
    config = {"guardrails": {"forbidden_patterns": ["*.secret", ".env"]}}
    patterns = get_forbidden_patterns(config)
    assert patterns == ["*.secret", ".env"]


def test_get_forbidden_patterns_defaults_without_config():
    patterns = get_forbidden_patterns(None)
    assert ".env" in patterns
    assert "*.key" in patterns


# --- Pre-execution checks ---

def test_check_project_path_rejects_root():
    errors = check_project_path(Path("/"))
    assert len(errors) > 0
    assert "too broad" in errors[0].lower() or "refusing" in errors[0].lower()


def test_check_project_path_rejects_home():
    errors = check_project_path(Path.home())
    assert len(errors) > 0
    assert "home directory" in errors[0].lower()


def test_check_project_path_accepts_real_project(tmp_path):
    errors = check_project_path(tmp_path)
    assert errors == []


def test_check_project_path_rejects_nonexistent():
    errors = check_project_path(Path("/nonexistent/path/xyz"))
    assert len(errors) > 0
    assert "does not exist" in errors[0]


def test_mode_compatibility_warns_localai_edit():
    warnings = check_mode_compatibility(Mode.EDIT, "local")
    assert len(warnings) > 0
    assert "advisory" in warnings[0].lower()


def test_mode_compatibility_ok_for_claude_edit():
    warnings = check_mode_compatibility(Mode.EDIT, "claude")
    assert warnings == []


def test_mode_compatibility_ok_for_think():
    assert check_mode_compatibility(Mode.THINK, "local") == []
    assert check_mode_compatibility(Mode.THINK, "claude") == []


def test_preflight_blocks_dangerous_path():
    issues = run_preflight_checks(Path("/"), Mode.THINK, "local", {})
    errors = [i for i in issues if not i.startswith("WARNING:")]
    assert len(errors) > 0
