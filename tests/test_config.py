"""Tests for configuration loading and validation."""

import os

import pytest
from pathlib import Path

from aicp.config.loader import (
    DEFAULT_CONFIG_PATH,
    _deep_merge,
    get_backend_config,
    load_config,
    load_dotenv,
    validate_config,
)


def test_load_default_config():
    config = load_config(DEFAULT_CONFIG_PATH)
    assert "backends" in config
    assert "local" in config["backends"]
    assert "claude" in config["backends"]


def test_get_backend_config():
    config = load_config(DEFAULT_CONFIG_PATH)
    local = get_backend_config(config, "local")
    assert "base_url" in local
    assert "model" in local


def test_validate_default_config_is_valid():
    config = load_config(DEFAULT_CONFIG_PATH)
    errors = validate_config(config)
    assert errors == [], f"Default config should be valid, got: {errors}"


def test_validate_missing_backend_key():
    config = {"backends": {"local": {"base_url": "http://localhost", "model": "x"}}}
    errors = validate_config(config)
    assert any("backends.claude.model" in e for e in errors)


def test_validate_wrong_type():
    config = {
        "backends": {
            "local": {"base_url": "http://localhost", "model": "x"},
            "claude": {"model": 123},  # should be str
        }
    }
    errors = validate_config(config)
    assert any("should be str" in e for e in errors)


def test_validate_bad_max_turns():
    config = {
        "backends": {
            "local": {"base_url": "http://localhost", "model": "x"},
            "claude": {"model": "opus", "max_turns": "five"},
        }
    }
    errors = validate_config(config)
    assert any("max_turns" in e for e in errors)


def test_validate_empty_config():
    errors = validate_config({})
    assert len(errors) > 0, "Empty config should have errors"


def test_validate_bad_max_tokens():
    config = {
        "backends": {
            "local": {"base_url": "http://localhost", "model": "x", "max_tokens": "big"},
            "claude": {"model": "opus"},
        }
    }
    errors = validate_config(config)
    assert any("max_tokens" in e for e in errors)


def test_validate_zero_max_tokens():
    config = {
        "backends": {
            "local": {"base_url": "http://localhost", "model": "x", "max_tokens": 0},
            "claude": {"model": "opus"},
        }
    }
    errors = validate_config(config)
    assert any("max_tokens" in e for e in errors)


def test_validate_valid_max_tokens():
    config = {
        "backends": {
            "local": {"base_url": "http://localhost", "model": "x", "max_tokens": 2048},
            "claude": {"model": "opus"},
        }
    }
    errors = validate_config(config)
    assert not any("max_tokens" in e for e in errors)


# ── _deep_merge tests ─────────────────────────────────────────────────────────

def test_deep_merge_simple_override():
    base = {"a": 1, "b": 2}
    override = {"b": 99, "c": 3}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": 99, "c": 3}


def test_deep_merge_nested():
    base = {"backends": {"local": {"model": "hermes", "max_tokens": 512}}}
    override = {"backends": {"local": {"max_tokens": 4096}}}
    result = _deep_merge(base, override)
    assert result["backends"]["local"]["model"] == "hermes"
    assert result["backends"]["local"]["max_tokens"] == 4096


def test_deep_merge_does_not_mutate_base():
    base = {"backends": {"local": {"model": "hermes"}}}
    override = {"backends": {"local": {"model": "phi3"}}}
    _deep_merge(base, override)
    assert base["backends"]["local"]["model"] == "hermes"


def test_deep_merge_empty_override():
    base = {"a": 1}
    result = _deep_merge(base, {})
    assert result == {"a": 1}


def test_load_config_applies_user_override(tmp_path, monkeypatch):
    import yaml

    user_cfg = tmp_path / "config.yaml"
    user_cfg.write_text(yaml.dump({"backends": {"local": {"max_tokens": 9999}}}))

    monkeypatch.setenv("AICP_HOME", str(tmp_path))
    # Re-import to pick up the patched env (USER_CONFIG_PATH is computed at import time)
    import importlib
    import aicp.config.loader as loader_module
    importlib.reload(loader_module)

    config = loader_module.load_config(loader_module.DEFAULT_CONFIG_PATH)
    assert config["backends"]["local"]["max_tokens"] == 9999

    # Restore
    importlib.reload(loader_module)


def test_load_config_applies_project_override(tmp_path):
    import yaml

    project_dir = tmp_path / "myproject"
    aicp_dir = project_dir / ".aicp"
    aicp_dir.mkdir(parents=True)
    (aicp_dir / "config.yaml").write_text(
        yaml.dump({"backends": {"local": {"model": "project-specific-model"}}})
    )

    import importlib
    import aicp.config.loader as loader_module
    importlib.reload(loader_module)

    config = loader_module.load_config(
        loader_module.DEFAULT_CONFIG_PATH,
        project_path=project_dir,
    )
    assert config["backends"]["local"]["model"] == "project-specific-model"

    importlib.reload(loader_module)


def test_load_config_project_override_does_not_affect_other_keys(tmp_path):
    import yaml

    project_dir = tmp_path / "myproject"
    aicp_dir = project_dir / ".aicp"
    aicp_dir.mkdir(parents=True)
    (aicp_dir / "config.yaml").write_text(
        yaml.dump({"backends": {"local": {"max_tokens": 512}}})
    )

    import importlib
    import aicp.config.loader as loader_module
    importlib.reload(loader_module)

    config = loader_module.load_config(
        loader_module.DEFAULT_CONFIG_PATH,
        project_path=project_dir,
    )
    # max_tokens overridden, but model still comes from default
    assert config["backends"]["local"]["max_tokens"] == 512
    assert "model" in config["backends"]["local"]  # default key preserved

    importlib.reload(loader_module)


def test_load_config_no_project_override_when_file_missing(tmp_path):
    import importlib
    import aicp.config.loader as loader_module
    importlib.reload(loader_module)

    # Project dir exists but has no .aicp/config.yaml
    project_dir = tmp_path / "clean_project"
    project_dir.mkdir()

    config = loader_module.load_config(
        loader_module.DEFAULT_CONFIG_PATH,
        project_path=project_dir,
    )
    # Should load fine without error
    assert "backends" in config

    importlib.reload(loader_module)


# ── Extended tests (WS1d) ────────────────────────────────────────────────────

def test_load_config_nonexistent_path_raises():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


def test_load_config_invalid_yaml(tmp_path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("{{invalid yaml: [")
    with pytest.raises(Exception):
        load_config(bad_yaml)


def test_deep_merge_override_wins_at_all_levels():
    """Layer 4 override should beat layer 1-3 values."""
    base = {"a": {"b": {"c": 1, "d": 2}}, "x": 10}
    override = {"a": {"b": {"c": 99}}, "x": 20}
    result = _deep_merge(base, override)
    assert result["a"]["b"]["c"] == 99
    assert result["a"]["b"]["d"] == 2  # preserved from base
    assert result["x"] == 20


def test_validate_config_multiple_errors():
    """Empty config should report multiple missing required keys."""
    errors = validate_config({})
    assert len(errors) >= 3  # at least 3 required keys missing


def test_get_backend_config_missing_backend():
    config = {"backends": {"local": {"model": "x"}}}
    with pytest.raises(ValueError, match="No config for backend"):
        get_backend_config(config, "nonexistent")


# ---------------------------------------------------------------------------
# .env loader (bridge KEY=VALUE → os.environ)
# ---------------------------------------------------------------------------


class TestLoadDotenv:
    def test_missing_file_is_silent(self, tmp_path):
        assert load_dotenv(tmp_path / "nope.env") == 0

    def test_simple_keys(self, tmp_path, monkeypatch):
        envfile = tmp_path / ".env"
        envfile.write_text("FOO=bar\nBAZ=qux\n")
        monkeypatch.delenv("FOO", raising=False)
        monkeypatch.delenv("BAZ", raising=False)

        n = load_dotenv(envfile)
        assert n == 2
        assert os.environ["FOO"] == "bar"
        assert os.environ["BAZ"] == "qux"

    def test_comments_and_blank_lines_skipped(self, tmp_path, monkeypatch):
        envfile = tmp_path / ".env"
        envfile.write_text(
            "# header comment\n"
            "\n"
            "REAL_KEY=value\n"
            "  # indented comment\n"
            "\n"
        )
        monkeypatch.delenv("REAL_KEY", raising=False)
        assert load_dotenv(envfile) == 1
        assert os.environ["REAL_KEY"] == "value"

    def test_surrounding_quotes_stripped(self, tmp_path, monkeypatch):
        envfile = tmp_path / ".env"
        envfile.write_text(
            'DOUBLE="hello world"\n'
            "SINGLE='one two'\n"
            "BARE=plain\n"
        )
        for k in ("DOUBLE", "SINGLE", "BARE"):
            monkeypatch.delenv(k, raising=False)
        load_dotenv(envfile)
        assert os.environ["DOUBLE"] == "hello world"
        assert os.environ["SINGLE"] == "one two"
        assert os.environ["BARE"] == "plain"

    def test_existing_env_wins(self, tmp_path, monkeypatch):
        """User's exported env must override .env — protects against stale keys."""
        envfile = tmp_path / ".env"
        envfile.write_text("APIKEY=from-dotenv\n")
        monkeypatch.setenv("APIKEY", "from-shell")
        n = load_dotenv(envfile)
        assert n == 0                                # no new keys set
        assert os.environ["APIKEY"] == "from-shell"  # shell value preserved

    def test_export_prefix_tolerated(self, tmp_path, monkeypatch):
        """Supporting `export KEY=VAL` lets the same file be sourced OR loaded."""
        envfile = tmp_path / ".env"
        envfile.write_text("export FOO=ok\n")
        monkeypatch.delenv("FOO", raising=False)
        assert load_dotenv(envfile) == 1
        assert os.environ["FOO"] == "ok"

    def test_junk_keys_skipped(self, tmp_path, monkeypatch):
        """Malformed lines must not crash or pollute env."""
        envfile = tmp_path / ".env"
        envfile.write_text(
            "=no-key\n"
            "no-equals\n"
            "WITH SPACE=nope\n"        # space in key → skip
            "GOOD_KEY=good\n"
        )
        monkeypatch.delenv("GOOD_KEY", raising=False)
        n = load_dotenv(envfile)
        assert n == 1
        assert os.environ["GOOD_KEY"] == "good"

    def test_real_aicp_env_pattern(self, tmp_path, monkeypatch):
        """Smoke: the actual .env shape from the handoff round-trips cleanly."""
        envfile = tmp_path / ".env"
        envfile.write_text(
            "# ── AICP defaults ───────\n"
            "AICP_DEFAULT_MODE=think\n"
            "AICP_DEFAULT_BACKEND=local\n"
            "\n"
            "OPENROUTER_API_KEY=sk-or-v1-fakekey12345\n"
        )
        for k in ("AICP_DEFAULT_MODE", "AICP_DEFAULT_BACKEND", "OPENROUTER_API_KEY"):
            monkeypatch.delenv(k, raising=False)

        n = load_dotenv(envfile)
        assert n == 3
        assert os.environ["OPENROUTER_API_KEY"] == "sk-or-v1-fakekey12345"
        assert os.environ["AICP_DEFAULT_MODE"] == "think"
