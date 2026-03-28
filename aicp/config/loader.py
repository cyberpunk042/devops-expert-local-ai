"""Load and validate AICP configuration from YAML files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "default.yaml"
USER_CONFIG_PATH = Path(os.environ.get("AICP_HOME", Path.home() / ".aicp")) / "config.yaml"

# Required config structure: (dotted_key, expected_type, description)
_REQUIRED_KEYS = [
    ("backends.local.base_url", str, "LocalAI base URL"),
    ("backends.local.model", str, "LocalAI model name"),
    ("backends.claude.model", str, "Claude Code model name"),
]


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override into base, returning a new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(
    path: Path = DEFAULT_CONFIG_PATH,
    project_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load configuration, merging three override layers on top of defaults.

    Load order (each layer overrides the previous):
      1. config/default.yaml        — repo defaults (committed)
      2. ~/.aicp/config.yaml        — user-level overrides (machine-specific)
      3. <project>/.aicp/config.yaml — per-project overrides (e.g. different model)
      4. --config <path>            — explicit CLI override (replaces layer 1 entirely)
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a YAML mapping, got {type(config).__name__}")

    # Layer 2: user-level overrides (only when loading the default config, not a --config override)
    if path == DEFAULT_CONFIG_PATH and USER_CONFIG_PATH.exists():
        with open(USER_CONFIG_PATH) as f:
            user_cfg = yaml.safe_load(f)
        if isinstance(user_cfg, dict):
            config = _deep_merge(config, user_cfg)

    # Layer 3: per-project overrides from <project>/.aicp/config.yaml
    if project_path is not None:
        project_cfg_path = Path(project_path) / ".aicp" / "config.yaml"
        if project_cfg_path.exists():
            with open(project_cfg_path) as f:
                project_cfg = yaml.safe_load(f)
            if isinstance(project_cfg, dict):
                config = _deep_merge(config, project_cfg)

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

    # Validate optional numeric fields — local backend
    local = config.get("backends", {}).get("local", {})
    max_tokens = local.get("max_tokens")
    if max_tokens is not None:
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            errors.append("backends.local.max_tokens should be a positive int")

    # Validate optional numeric fields — claude backend
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


def get_rag_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract RAG configuration with defaults."""
    defaults = {
        "enabled": False,
        "db_path": ".aicp/rag.db",
        "store_name": "default",
        "chunk_size": 512,
        "chunk_overlap": 64,
        "top_k": 5,
        "threshold": 0.3,
        "max_context_chars": 3000,
    }
    rag = config.get("rag", {})
    if not isinstance(rag, dict):
        return defaults
    return {**defaults, **rag}
