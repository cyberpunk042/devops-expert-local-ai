"""Tests for configuration loading and validation."""

import pytest
from pathlib import Path

from aicp.config.loader import load_config, validate_config, get_backend_config, DEFAULT_CONFIG_PATH, _deep_merge


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
