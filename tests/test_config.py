"""Tests for configuration loading and validation."""

import pytest

from aicp.config.loader import load_config, validate_config, get_backend_config, DEFAULT_CONFIG_PATH


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
