"""Load and validate AICP configuration from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "default.yaml"

# Required config structure: (dotted_key, expected_type, description)
_REQUIRED_KEYS = [
    ("backends.local.base_url", str, "LocalAI base URL"),
    ("backends.local.model", str, "LocalAI model name"),
    ("backends.claude.model", str, "Claude Code model name"),
]


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a YAML mapping, got {type(config).__name__}")
    return config


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate config structure. Returns list of error strings (empty = valid)."""
    errors = []

    for dotted_key, expected_type, description in _REQUIRED_KEYS:
        parts = dotted_key.split(".")
        value = config
        for part in parts:
            if not isinstance(value, dict) or part not in value:
                errors.append(f"Missing required key '{dotted_key}' ({description})")
                value = None
                break
            value = value[part]
        if value is not None and not isinstance(value, expected_type):
            errors.append(
                f"Key '{dotted_key}' should be {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )

    # Validate optional numeric fields
    claude = config.get("backends", {}).get("claude", {})
    for key in ("max_turns", "timeout"):
        val = claude.get(key)
        if val is not None and not isinstance(val, int):
            errors.append(f"backends.claude.{key} should be int, got {type(val).__name__}")

    budget = claude.get("max_budget_usd")
    if budget is not None and not isinstance(budget, (int, float)):
        errors.append(
            f"backends.claude.max_budget_usd should be a number, got {type(budget).__name__}"
        )

    return errors


def get_backend_config(config: Dict[str, Any], backend_name: str) -> Dict[str, Any]:
    """Extract backend-specific configuration."""
    backends = config.get("backends", {})
    if backend_name not in backends:
        raise ValueError(f"No config for backend: {backend_name}")
    return backends[backend_name]
