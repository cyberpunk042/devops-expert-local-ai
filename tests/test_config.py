"""Tests for configuration loading."""

from aicp.config.loader import load_config, get_backend_config, DEFAULT_CONFIG_PATH


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
