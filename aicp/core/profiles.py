"""Profile system — named configuration bundles for AICP.

A profile is a named set of configuration overrides that sits between
config/default.yaml (base) and user/project overrides. It coordinates
settings across backends, router, RAG, budget, cache, and Docker with
a single switch.

Load order with profiles:
  1. config/default.yaml        — repo defaults (committed)
  2. config/profiles/<name>.yaml — profile overlay (selected)
  3. ~/.aicp/config.yaml        — user-level overrides
  4. <project>/.aicp/config.yaml — per-project overrides
  5. --config <path>            — explicit CLI override
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger("aicp")

# Default profiles directory (committed to repo)
PROFILES_DIR = Path(__file__).parent.parent.parent / "config" / "profiles"

# Every profile YAML must have these top-level keys
_REQUIRED_KEYS = {"name", "description"}

# Optional sections a profile may override (validated for correct types)
_SECTION_TYPES: Dict[str, type] = {
    "backends": dict,
    "router": dict,
    "mode_profiles": dict,
    "rag": dict,
    "budget": dict,
    "cache": dict,
    "quality": dict,
    "timeouts": dict,
    "docker": dict,
    "cluster": dict,
    "defaults": dict,
    "guardrails": dict,
    "stores": dict,
}


def list_profiles(profiles_dir: Path = PROFILES_DIR) -> List[Dict[str, str]]:
    """List all available profiles with name and description.

    Returns a list of dicts: [{"name": ..., "description": ..., "path": ...}]
    """
    if not profiles_dir.is_dir():
        return []

    profiles = []
    for path in sorted(profiles_dir.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and "name" in data:
                profiles.append({
                    "name": data["name"],
                    "description": data.get("description", ""),
                    "path": str(path),
                })
        except Exception:
            logger.warning("Failed to read profile: %s", path)
    return profiles


def load_profile(
    name: str,
    profiles_dir: Path = PROFILES_DIR,
) -> Dict[str, Any]:
    """Load a profile by name. Returns the parsed YAML dict.

    Raises FileNotFoundError if the profile doesn't exist.
    Raises ValueError if the profile is invalid.
    """
    path = profiles_dir / f"{name}.yaml"
    if not path.exists():
        available = [p["name"] for p in list_profiles(profiles_dir)]
        raise FileNotFoundError(
            f"Profile '{name}' not found in {profiles_dir}. "
            f"Available: {', '.join(available) or 'none'}"
        )

    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Profile '{name}' must be a YAML mapping, got {type(data).__name__}")

    errors = validate_profile(data)
    if errors:
        raise ValueError(f"Profile '{name}' is invalid:\n  " + "\n  ".join(errors))

    return data


def validate_profile(data: Dict[str, Any]) -> List[str]:
    """Validate a profile dict. Returns list of error strings (empty = valid)."""
    errors: List[str] = []

    # Required keys
    for key in _REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Missing required key: '{key}'")

    # Name must be a non-empty string
    name = data.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        errors.append("'name' must be a non-empty string")

    # Description must be a string
    desc = data.get("description")
    if desc is not None and not isinstance(desc, str):
        errors.append("'description' must be a string")

    # Extends must be a string if present
    extends = data.get("extends")
    if extends is not None and not isinstance(extends, str):
        errors.append("'extends' must be a string (profile name)")

    # Section type checks
    for section, expected_type in _SECTION_TYPES.items():
        val = data.get(section)
        if val is not None and not isinstance(val, expected_type):
            errors.append(
                f"Section '{section}' must be {expected_type.__name__}, "
                f"got {type(val).__name__}"
            )

    # Router-specific validation
    router = data.get("router", {})
    if isinstance(router, dict):
        thresholds = router.get("complexity_thresholds")
        if thresholds is not None:
            if not isinstance(thresholds, list) or len(thresholds) != 2:
                errors.append("router.complexity_thresholds must be a list of 2 floats")
            elif not all(isinstance(t, (int, float)) for t in thresholds):
                errors.append("router.complexity_thresholds values must be numbers")
            elif thresholds[0] >= thresholds[1]:
                errors.append(
                    "router.complexity_thresholds[0] must be less than [1] "
                    f"(got {thresholds[0]} >= {thresholds[1]})"
                )

        failover = router.get("failover_chain")
        if failover is not None:
            if not isinstance(failover, list):
                errors.append("router.failover_chain must be a list")
            elif not all(isinstance(b, str) for b in failover):
                errors.append("router.failover_chain entries must be strings")

    # Timeouts validation
    timeouts = data.get("timeouts", {})
    if isinstance(timeouts, dict):
        for key in ("request", "cold_start", "retries"):
            val = timeouts.get(key)
            if val is not None and not isinstance(val, (int, float)):
                errors.append(f"timeouts.{key} must be a number")
        retries = timeouts.get("retries")
        if isinstance(retries, (int, float)) and retries < 0:
            errors.append("timeouts.retries must be >= 0")

    # Quality validation
    quality = data.get("quality", {})
    if isinstance(quality, dict):
        threshold = quality.get("threshold")
        if threshold is not None:
            if not isinstance(threshold, (int, float)):
                errors.append("quality.threshold must be a number")
            elif not (0.0 <= threshold <= 1.0):
                errors.append(f"quality.threshold must be 0.0-1.0, got {threshold}")

    # Budget validation
    budget = data.get("budget", {})
    if isinstance(budget, dict):
        for key in ("max_cost_usd", "max_duration_seconds", "max_steps", "max_file_changes"):
            val = budget.get(key)
            if val is not None and not isinstance(val, (int, float)):
                errors.append(f"budget.{key} must be a number")

    # Mode profiles validation
    mode_profiles = data.get("mode_profiles", {})
    if isinstance(mode_profiles, dict):
        valid_modes = {"think", "edit", "act"}
        for mode_name, params in mode_profiles.items():
            if mode_name not in valid_modes:
                errors.append(
                    f"mode_profiles.{mode_name}: unknown mode "
                    f"(valid: {', '.join(sorted(valid_modes))})"
                )
            if not isinstance(params, dict):
                errors.append(f"mode_profiles.{mode_name} must be a dict")

    return errors


def profile_to_config_overlay(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the config-overlay portion of a profile.

    Strips profile-only metadata (name, description, extends) and returns
    only the keys that should be deep-merged into the AICP config.
    """
    metadata_keys = {"name", "description", "extends"}
    return {k: v for k, v in profile.items() if k not in metadata_keys}


def resolve_profile(
    name: str,
    profiles_dir: Path = PROFILES_DIR,
) -> Dict[str, Any]:
    """Load a profile and resolve its 'extends' chain.

    If profile A extends profile B, B's overlay is loaded first, then A's
    overlay is deep-merged on top. Circular extends are detected.
    """
    from aicp.config.loader import _deep_merge

    seen: List[str] = []
    overlays: List[Dict[str, Any]] = []

    current_name: Optional[str] = name
    while current_name:
        if current_name in seen:
            raise ValueError(
                f"Circular profile extends detected: "
                f"{' -> '.join(seen)} -> {current_name}"
            )
        seen.append(current_name)
        profile = load_profile(current_name, profiles_dir)
        overlays.append(profile_to_config_overlay(profile))
        current_name = profile.get("extends")

    # Merge from base to derived (last loaded = lowest priority)
    overlays.reverse()
    result: Dict[str, Any] = {}
    for overlay in overlays:
        result = _deep_merge(result, overlay)

    return result


def get_active_profile() -> Optional[str]:
    """Read the currently active profile name from .env or environment.

    Checks AICP_PROFILE environment variable first, then .env file.
    Returns None if no profile is set (uses default config).
    """
    import os

    # Env var takes precedence
    env_profile = os.environ.get("AICP_PROFILE")
    if env_profile:
        return env_profile

    # Check .env file
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("AICP_PROFILE=") and not line.startswith("#"):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value

    return None


def diff_profiles(
    name_a: str,
    name_b: str,
    profiles_dir: Path = PROFILES_DIR,
) -> Dict[str, Dict[str, Any]]:
    """Compare two profiles and return their differences.

    Returns a dict of {key: {"a": value_in_a, "b": value_in_b}} for keys
    that differ between the two resolved profiles.
    """
    overlay_a = resolve_profile(name_a, profiles_dir)
    overlay_b = resolve_profile(name_b, profiles_dir)

    all_keys = set(overlay_a) | set(overlay_b)
    diffs: Dict[str, Dict[str, Any]] = {}

    for key in sorted(all_keys):
        val_a = overlay_a.get(key)
        val_b = overlay_b.get(key)
        if val_a != val_b:
            diffs[key] = {"a": val_a, "b": val_b}

    return diffs
