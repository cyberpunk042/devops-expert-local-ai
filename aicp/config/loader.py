"""Load and validate AICP configuration from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "default.yaml"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def get_backend_config(config: Dict[str, Any], backend_name: str) -> Dict[str, Any]:
    """Extract backend-specific configuration."""
    backends = config.get("backends", {})
    if backend_name not in backends:
        raise ValueError(f"No config for backend: {backend_name}")
    return backends[backend_name]
