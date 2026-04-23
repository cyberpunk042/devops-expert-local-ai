"""Load and validate AICP configuration from YAML files.

Load order (each layer overrides the previous via deep merge):
  1. config/default.yaml             — repo defaults (committed)
  2. config/profiles/<name>.yaml     — profile overlay (selected via --profile or AICP_PROFILE)
  3. ~/.aicp/config.yaml             — user-level overrides (machine-specific)
  4. <project>/.aicp/config.yaml     — per-project overrides
  5. --config <path>                 — explicit CLI override (replaces layer 1 entirely)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "default.yaml"
USER_CONFIG_PATH = Path(os.environ.get("AICP_HOME", Path.home() / ".aicp")) / "config.yaml"
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DOTENV_PATH = PROJECT_ROOT / ".env"


def load_dotenv(path: Path | None = None) -> int:
    """Populate os.environ from a KEY=VALUE .env file at the AICP project root.

    Shell `source .env` does NOT export these because the repo's .env file uses
    bare KEY=VALUE (no `export`). This helper bridges the gap so Python code —
    which reads env via os.environ — sees the operator's keys (OPENROUTER_API_KEY,
    HUGGINGFACE_API_KEY, AICP_* overrides, etc.) without requiring shell magic.

    Call once at CLI entry (before backends are built). Existing os.environ values
    win over .env — the env a user explicitly exports is always authoritative.

    Format (one KEY=VALUE per line):
      - `#` lines and blank lines are skipped
      - surrounding single/double quotes on VALUE are stripped
      - no variable interpolation (not a bash script)

    Returns the count of keys actually set (i.e., those not already in os.environ).
    Missing / unreadable file → 0, never raises.
    """
    target = path or DEFAULT_DOTENV_PATH
    if not target.exists():
        return 0
    try:
        content = target.read_text()
    except OSError:
        return 0

    set_count = 0
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if not key or not key.replace("_", "").replace("-", "").isalnum():
            continue  # skip junk keys
        # Strip one layer of matching surrounding quotes
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        # Existing os.environ wins
        if key in os.environ:
            continue
        os.environ[key] = val
        set_count += 1
    return set_count

# Required config structure: (dotted_key, expected_type, description)
_REQUIRED_KEYS = [
    ("backends.local.base_url", str, "LocalAI base URL"),
    ("backends.local.model", str, "LocalAI model name"),
    ("backends.claude.model", str, "Claude Code model name"),
]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
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
    project_path: Path | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Load configuration, merging override layers on top of defaults.

    Load order (each layer overrides the previous):
      1. config/default.yaml             — repo defaults (committed)
      2. config/profiles/<name>.yaml     — profile overlay (if selected)
      3. ~/.aicp/config.yaml             — user-level overrides (machine-specific)
      4. <project>/.aicp/config.yaml     — per-project overrides
      5. --config <path>                 — explicit CLI override (replaces layer 1)

    The profile can be specified via:
      - ``profile`` parameter (CLI --profile flag)
      - ``AICP_PROFILE`` environment variable
      - ``AICP_PROFILE=`` line in .env file
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a YAML mapping, got {type(config).__name__}")

    # Layer 2: profile overlay (only when loading default config, not --config override)
    if path == DEFAULT_CONFIG_PATH:
        profile_name = profile
        if profile_name is None:
            # Auto-detect from environment / .env
            from aicp.core.profiles import get_active_profile
            profile_name = get_active_profile()
        if profile_name is not None:
            from aicp.core.profiles import resolve_profile
            overlay = resolve_profile(profile_name)
            config = _deep_merge(config, overlay)

    # Layer 3: user-level overrides (only when loading the default config)
    if path == DEFAULT_CONFIG_PATH and USER_CONFIG_PATH.exists():
        with open(USER_CONFIG_PATH) as f:
            user_cfg = yaml.safe_load(f)
        if isinstance(user_cfg, dict):
            config = _deep_merge(config, user_cfg)

    # Layer 4: per-project overrides from <project>/.aicp/config.yaml
    if project_path is not None:
        project_cfg_path = Path(project_path) / ".aicp" / "config.yaml"
        if project_cfg_path.exists():
            with open(project_cfg_path) as f:
                project_cfg = yaml.safe_load(f)
            if isinstance(project_cfg, dict):
                config = _deep_merge(config, project_cfg)

    # Store active profile name in config for introspection
    if profile is not None or (path == DEFAULT_CONFIG_PATH):
        from aicp.core.profiles import get_active_profile
        active = profile or get_active_profile()
        if active:
            config["_active_profile"] = active

    return config


def validate_config(config: dict[str, Any]) -> list[str]:
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


def get_backend_config(config: dict[str, Any], backend_name: str) -> dict[str, Any]:
    """Extract backend-specific configuration."""
    backends = config.get("backends", {})
    if backend_name not in backends:
        raise ValueError(f"No config for backend: {backend_name}")
    return backends[backend_name]


def get_rag_config(config: dict[str, Any]) -> dict[str, Any]:
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
