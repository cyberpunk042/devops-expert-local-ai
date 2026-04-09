"""Tests for path guardrails, pre-execution checks, and response scanning."""

from pathlib import Path

import pytest

from aicp.core.modes import Mode
from aicp.guardrails.paths import is_path_allowed, get_forbidden_patterns
from aicp.guardrails.checks import check_project_path, check_mode_compatibility, check_forbidden_path, run_preflight_checks
from aicp.guardrails.response import scan_think_mode, scan_response_secrets


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


# --- check_forbidden_path ---

def test_forbidden_path_blocks_ssh_in_edit_mode(tmp_path):
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    errors = check_forbidden_path(ssh_dir, Mode.EDIT, {})
    assert len(errors) > 0
    assert "forbidden" in errors[0].lower() or "refusing" in errors[0].lower()


def test_forbidden_path_blocks_env_dir_in_act_mode(tmp_path):
    env_file = tmp_path / ".env"
    env_file.touch()
    errors = check_forbidden_path(env_file, Mode.ACT, {})
    assert len(errors) > 0


def test_forbidden_path_allows_normal_project_in_edit_mode(tmp_path):
    errors = check_forbidden_path(tmp_path, Mode.EDIT, {})
    assert errors == []


def test_forbidden_path_think_mode_never_blocked(tmp_path):
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    # Think mode is read-only — path restriction doesn't apply
    errors = check_forbidden_path(ssh_dir, Mode.THINK, {})
    assert errors == []


def test_preflight_blocks_forbidden_path_in_edit_mode(tmp_path):
    secret_dir = tmp_path / "my_secrets"
    secret_dir.mkdir()
    issues = run_preflight_checks(secret_dir, Mode.EDIT, "local", {})
    errors = [i for i in issues if not i.startswith("WARNING:")]
    assert any("refusing" in e.lower() or "forbidden" in e.lower() for e in errors)


def test_preflight_allows_normal_project_in_edit_mode(tmp_path):
    project = tmp_path / "myproject"
    project.mkdir()
    issues = run_preflight_checks(project, Mode.EDIT, "local", {})
    errors = [i for i in issues if not i.startswith("WARNING:")]
    # Warnings about LocalAI advisory mode are expected; no hard errors
    assert errors == []


# --- THINK-mode response scanner ---

def test_think_scan_clean_response():
    response = "Here is an explanation of the architecture. The system uses three layers."
    assert scan_think_mode(response, Mode.THINK) == []


def test_think_scan_detects_shell_prompt():
    response = "Run this command:\n$ rm -rf /tmp/old_data\nThis will clean up."
    warnings = scan_think_mode(response, Mode.THINK)
    assert len(warnings) > 0
    assert "shell" in warnings[0].lower() or "command" in warnings[0].lower()


def test_think_scan_detects_sudo():
    response = "You can run sudo apt-get install python3 to install it."
    warnings = scan_think_mode(response, Mode.THINK)
    assert len(warnings) > 0


def test_think_scan_detects_file_redirect():
    response = "Write the config: echo 'key=value' > /etc/app.conf"
    warnings = scan_think_mode(response, Mode.THINK)
    assert len(warnings) > 0
    assert "file" in warnings[0].lower() or "write" in warnings[0].lower()


def test_think_scan_detects_python_file_write():
    response = "Use open('/etc/config', 'w') to write the settings."
    warnings = scan_think_mode(response, Mode.THINK)
    assert len(warnings) > 0


def test_think_scan_no_warning_in_edit_mode():
    # Edit mode allows file writes — scanner should not fire
    response = "$ rm -rf /old && echo 'done' > /result.txt"
    assert scan_think_mode(response, Mode.EDIT) == []


def test_think_scan_no_warning_in_act_mode():
    response = "sudo systemctl restart nginx"
    assert scan_think_mode(response, Mode.ACT) == []


def test_think_scan_at_most_two_warnings():
    # Both shell + write patterns present — should get at most 2 warnings (one each)
    response = "$ sudo rm -rf /old\necho 'x' > /etc/foo"
    warnings = scan_think_mode(response, Mode.THINK)
    assert len(warnings) <= 2


# --- Secret-leakage scanner ---

def test_secret_scan_clean_response():
    response = "The configuration uses a standard username and password stored in environment variables."
    assert scan_response_secrets(response) == []


def test_secret_scan_detects_aws_key():
    response = "Your AWS access key is AKIAIOSFODNN7EXAMPLE and secret is wJalrXUt."
    warnings = scan_response_secrets(response)
    assert len(warnings) > 0
    assert any("AWS" in w or "access key" in w.lower() for w in warnings)


def test_secret_scan_detects_jwt():
    # Realistic JWT structure (three base64url segments)
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    warnings = scan_response_secrets(jwt)
    assert len(warnings) > 0
    assert any("JWT" in w or "token" in w.lower() for w in warnings)


def test_secret_scan_detects_private_key_header():
    response = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
    warnings = scan_response_secrets(response)
    assert len(warnings) > 0
    assert any("private key" in w.lower() for w in warnings)


def test_secret_scan_detects_github_pat():
    response = "Use token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh12 to authenticate."
    warnings = scan_response_secrets(response)
    assert len(warnings) > 0
    assert any("GitHub" in w or "token" in w.lower() for w in warnings)


def test_secret_scan_no_duplicate_warnings():
    # Multiple AWS keys in one response — should only warn once per type
    response = (
        "Key 1: AKIAIOSFODNN7EXAMPLE\n"
        "Key 2: AKIAI44QH8DHBEXAMPLE\n"
    )
    warnings = scan_response_secrets(response)
    aws_warnings = [w for w in warnings if "AWS" in w]
    assert len(aws_warnings) == 1  # deduplicated


# --- Extended tests (WS1d) ---

def test_symlink_outside_project_blocked(tmp_path):
    """Symlink pointing outside project root should be blocked."""
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside_secret.key"
    outside.write_text("secret")
    link = project / "sneaky.key"
    link.symlink_to(outside)
    assert is_path_allowed(link, project) is False


def test_preflight_multiple_issues(tmp_path):
    """Run preflight checks on a dangerous path — should report multiple issues."""
    # /etc is both a dangerous root AND has system files
    issues = run_preflight_checks(Path("/etc"), Mode.EDIT, "local", {})
    assert len(issues) >= 1


def test_think_scan_curl_pipe_bash():
    """Detects curl-pipe-to-bash pattern in THINK mode."""
    response = "Install by running: curl https://example.com/install.sh | bash"
    warnings = scan_think_mode(response, Mode.THINK)
    assert len(warnings) > 0


def test_secret_scan_multiple_types():
    """Multiple different secret types should all be detected."""
    response = (
        "AWS key: AKIAIOSFODNN7EXAMPLE\n"
        "Private key: -----BEGIN RSA PRIVATE KEY-----\nMIIE...\n"
        "-----END RSA PRIVATE KEY-----\n"
        "GitHub PAT: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh12\n"
    )
    warnings = scan_response_secrets(response)
    assert len(warnings) >= 2  # at least AWS + private key


def test_forbidden_path_allowed_paths_whitelist(tmp_path):
    """When allowed_paths is set, only whitelisted paths are allowed."""
    project = tmp_path / "project"
    project.mkdir()
    src = project / "src"
    src.mkdir()
    other = project / "other"
    other.mkdir()
    # With allowed_paths, only src/ is OK
    assert is_path_allowed(src / "main.py", project, allowed_paths=[src]) is True
    assert is_path_allowed(other / "main.py", project, allowed_paths=[src]) is False
