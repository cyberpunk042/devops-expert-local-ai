"""Tests for the profile system — loading, validation, merging, and config wiring."""

import pytest
import yaml
from pathlib import Path

from aicp.core.profiles import (
    PROFILES_DIR,
    diff_profiles,
    list_available_models,
    list_profiles,
    load_profile,
    profile_to_config_overlay,
    resolve_profile,
    validate_profile,
)
from aicp.config.loader import _deep_merge, load_config, DEFAULT_CONFIG_PATH


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _make_profile(**kwargs) -> dict:
    """Create a minimal valid profile dict with optional overrides."""
    base = {
        "name": "test-profile",
        "description": "A test profile",
    }
    base.update(kwargs)
    return base


def _write_profile(tmp_path: Path, name: str, data: dict) -> Path:
    """Write a profile YAML to a temp directory and return the path."""
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False))
    return path


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidateProfile:
    def test_minimal_valid(self):
        errors = validate_profile(_make_profile())
        assert errors == []

    def test_missing_name(self):
        errors = validate_profile({"description": "no name"})
        assert any("name" in e for e in errors)

    def test_missing_description(self):
        errors = validate_profile({"name": "x"})
        assert any("description" in e for e in errors)

    def test_empty_name(self):
        errors = validate_profile(_make_profile(name=""))
        assert any("non-empty" in e for e in errors)

    def test_name_wrong_type(self):
        errors = validate_profile(_make_profile(name=123))
        assert any("non-empty string" in e for e in errors)

    def test_extends_wrong_type(self):
        errors = validate_profile(_make_profile(extends=123))
        assert any("extends" in e for e in errors)

    def test_section_wrong_type(self):
        errors = validate_profile(_make_profile(backends="not-a-dict"))
        assert any("backends" in e and "dict" in e for e in errors)

    def test_router_thresholds_valid(self):
        profile = _make_profile(router={"complexity_thresholds": [0.3, 0.6]})
        errors = validate_profile(profile)
        assert errors == []

    def test_router_thresholds_wrong_count(self):
        profile = _make_profile(router={"complexity_thresholds": [0.5]})
        errors = validate_profile(profile)
        assert any("2 floats" in e for e in errors)

    def test_router_thresholds_not_ascending(self):
        profile = _make_profile(router={"complexity_thresholds": [0.8, 0.3]})
        errors = validate_profile(profile)
        assert any("less than" in e for e in errors)

    def test_router_failover_chain_valid(self):
        profile = _make_profile(router={"failover_chain": ["local", "claude"]})
        errors = validate_profile(profile)
        assert errors == []

    def test_router_failover_chain_wrong_type(self):
        profile = _make_profile(router={"failover_chain": "local"})
        errors = validate_profile(profile)
        assert any("failover_chain" in e for e in errors)

    def test_timeouts_valid(self):
        profile = _make_profile(timeouts={"request": 60, "retries": 2})
        errors = validate_profile(profile)
        assert errors == []

    def test_timeouts_negative_retries(self):
        profile = _make_profile(timeouts={"retries": -1})
        errors = validate_profile(profile)
        assert any("retries" in e for e in errors)

    def test_quality_threshold_out_of_range(self):
        profile = _make_profile(quality={"threshold": 1.5})
        errors = validate_profile(profile)
        assert any("0.0-1.0" in e for e in errors)

    def test_mode_profiles_valid(self):
        profile = _make_profile(mode_profiles={
            "think": {"temperature": 0.3},
            "edit": {"temperature": 0.2},
        })
        errors = validate_profile(profile)
        assert errors == []

    def test_mode_profiles_unknown_mode(self):
        profile = _make_profile(mode_profiles={"turbo": {"temperature": 0.1}})
        errors = validate_profile(profile)
        assert any("turbo" in e and "unknown mode" in e for e in errors)

    def test_budget_non_numeric(self):
        profile = _make_profile(budget={"max_cost_usd": "ten"})
        errors = validate_profile(profile)
        assert any("max_cost_usd" in e for e in errors)


# ---------------------------------------------------------------------------
# List profiles
# ---------------------------------------------------------------------------

class TestListProfiles:
    def test_list_committed_profiles(self):
        """Verify the committed config/profiles/ directory has profiles."""
        profiles = list_profiles(PROFILES_DIR)
        names = [p["name"] for p in profiles]
        assert "default" in names
        assert "fast" in names
        assert "offline" in names

    def test_list_empty_dir(self, tmp_path):
        assert list_profiles(tmp_path) == []

    def test_list_nonexistent_dir(self, tmp_path):
        assert list_profiles(tmp_path / "nope") == []

    def test_list_returns_description(self):
        profiles = list_profiles(PROFILES_DIR)
        for p in profiles:
            assert "description" in p
            assert "name" in p
            assert "path" in p


# ---------------------------------------------------------------------------
# Load profile
# ---------------------------------------------------------------------------

class TestLoadProfile:
    def test_load_default(self):
        profile = load_profile("default")
        assert profile["name"] == "default"
        assert "backends" in profile

    def test_load_fast(self):
        profile = load_profile("fast")
        assert profile["name"] == "fast"
        assert profile.get("extends") == "default"

    def test_load_offline(self):
        profile = load_profile("offline")
        assert profile["name"] == "offline"
        # Offline should not include claude in failover
        chain = profile.get("router", {}).get("failover_chain", [])
        assert "claude" not in chain

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_profile("does-not-exist")

    def test_load_invalid_profile(self, tmp_path):
        _write_profile(tmp_path, "bad", {"not": "valid"})
        with pytest.raises(ValueError, match="invalid"):
            load_profile("bad", profiles_dir=tmp_path)

    def test_load_from_custom_dir(self, tmp_path):
        data = _make_profile(name="custom", description="Custom profile")
        _write_profile(tmp_path, "custom", data)
        profile = load_profile("custom", profiles_dir=tmp_path)
        assert profile["name"] == "custom"


# ---------------------------------------------------------------------------
# Profile overlay extraction
# ---------------------------------------------------------------------------

class TestProfileToOverlay:
    def test_strips_metadata(self):
        profile = _make_profile(
            extends="default",
            backends={"local": {"model": "test"}},
        )
        overlay = profile_to_config_overlay(profile)
        assert "name" not in overlay
        assert "description" not in overlay
        assert "extends" not in overlay
        assert "backends" in overlay

    def test_preserves_all_sections(self):
        profile = _make_profile(
            backends={"local": {"model": "x"}},
            router={"complexity_thresholds": [0.4, 0.7]},
            rag={"top_k": 3},
        )
        overlay = profile_to_config_overlay(profile)
        assert "backends" in overlay
        assert "router" in overlay
        assert "rag" in overlay


# ---------------------------------------------------------------------------
# Resolve profile (extends chain)
# ---------------------------------------------------------------------------

class TestResolveProfile:
    def test_resolve_default_no_extends(self):
        overlay = resolve_profile("default")
        assert "backends" in overlay
        # No extends = no chain, just the profile's own overlay
        assert "name" not in overlay

    def test_resolve_fast_extends_default(self):
        overlay = resolve_profile("fast")
        # Fast extends default, so it should have default's settings
        # overridden by fast's settings
        assert overlay["backends"]["local"]["model"] == "gemma4-e2b"
        # Cache from fast (overrides default's 300)
        assert overlay["cache"]["ttl_seconds"] == 600

    def test_resolve_offline_extends_default(self):
        overlay = resolve_profile("offline")
        chain = overlay["router"]["failover_chain"]
        assert "claude" not in chain
        assert "local" in chain

    def test_circular_extends_detected(self, tmp_path):
        _write_profile(tmp_path, "a", _make_profile(name="a", extends="b"))
        _write_profile(tmp_path, "b", _make_profile(name="b", extends="a"))
        with pytest.raises(ValueError, match="Circular"):
            resolve_profile("a", profiles_dir=tmp_path)

    def test_multi_level_extends(self, tmp_path):
        _write_profile(tmp_path, "base", _make_profile(
            name="base",
            backends={"local": {"model": "base-model", "max_tokens": 1000}},
        ))
        _write_profile(tmp_path, "mid", _make_profile(
            name="mid",
            extends="base",
            backends={"local": {"max_tokens": 2000}},
        ))
        _write_profile(tmp_path, "top", _make_profile(
            name="top",
            extends="mid",
            backends={"local": {"max_tokens": 4000}},
        ))
        overlay = resolve_profile("top", profiles_dir=tmp_path)
        # top overrides mid overrides base
        assert overlay["backends"]["local"]["model"] == "base-model"
        assert overlay["backends"]["local"]["max_tokens"] == 4000


# ---------------------------------------------------------------------------
# Diff profiles
# ---------------------------------------------------------------------------

class TestDiffProfiles:
    def test_diff_same_profile(self):
        diffs = diff_profiles("default", "default")
        assert diffs == {}

    def test_diff_fast_vs_default(self):
        diffs = diff_profiles("fast", "default")
        # Should have differences in at least backends, router, rag
        assert len(diffs) > 0
        # Backends differ (fast uses qwen3-8b-fast as primary)
        assert "backends" in diffs

    def test_diff_returns_both_sides(self):
        diffs = diff_profiles("fast", "default")
        for key, sides in diffs.items():
            assert "a" in sides
            assert "b" in sides


# ---------------------------------------------------------------------------
# Config loader integration
# ---------------------------------------------------------------------------

class TestConfigLoaderIntegration:
    def test_load_config_without_profile(self):
        """Default load_config still works with no profile."""
        config = load_config(DEFAULT_CONFIG_PATH, profile=None)
        assert "backends" in config
        assert config["backends"]["local"]["model"] == "qwen3-8b"

    def test_load_config_with_fast_profile(self):
        """Profile overlay changes the primary model."""
        config = load_config(DEFAULT_CONFIG_PATH, profile="fast")
        assert config["backends"]["local"]["model"] == "gemma4-e2b"
        assert config.get("_active_profile") == "fast"

    def test_load_config_with_offline_profile(self):
        """Offline profile doesn't add claude to failover chain."""
        config = load_config(DEFAULT_CONFIG_PATH, profile="offline")
        # Router settings from profile are merged into config
        router = config.get("router", {})
        chain = router.get("failover_chain", [])
        assert "claude" not in chain

    def test_load_config_with_nonexistent_profile(self):
        with pytest.raises(FileNotFoundError):
            load_config(DEFAULT_CONFIG_PATH, profile="does-not-exist")

    def test_profile_does_not_break_required_keys(self):
        """All profiles produce valid config when merged with defaults."""
        from aicp.config.loader import validate_config
        for profile_name in ("default", "fast", "offline"):
            config = load_config(DEFAULT_CONFIG_PATH, profile=profile_name)
            errors = validate_config(config)
            assert errors == [], f"Profile '{profile_name}' produced invalid config: {errors}"

    def test_profile_overlay_preserves_unset_keys(self):
        """Profile shouldn't wipe keys it doesn't mention."""
        config = load_config(DEFAULT_CONFIG_PATH, profile="fast")
        # Fast doesn't override fleet_model, so it should still be there
        assert "fleet_model" in config["backends"]["local"]
        # Claude config should still exist (fast doesn't remove it)
        assert "claude" in config["backends"]


# ---------------------------------------------------------------------------
# Committed profiles are all valid
# ---------------------------------------------------------------------------

class TestCommittedProfiles:
    def test_all_committed_profiles_are_valid(self):
        """Every YAML in config/profiles/ must pass validation."""
        profiles = list_profiles(PROFILES_DIR)
        assert len(profiles) >= 3, "Expected at least default, fast, offline"
        for p in profiles:
            profile = load_profile(p["name"])
            errors = validate_profile(profile)
            assert errors == [], f"Profile '{p['name']}' has errors: {errors}"

    def test_all_committed_profiles_produce_valid_config(self):
        """Every profile, when merged with defaults, must pass config validation."""
        from aicp.config.loader import validate_config
        profiles = list_profiles(PROFILES_DIR)
        for p in profiles:
            config = load_config(DEFAULT_CONFIG_PATH, profile=p["name"])
            errors = validate_config(config)
            assert errors == [], (
                f"Profile '{p['name']}' + default.yaml produced invalid config: {errors}"
            )

    def test_all_extending_profiles_resolve(self):
        """Every profile with 'extends' must successfully resolve its chain."""
        profiles = list_profiles(PROFILES_DIR)
        for p in profiles:
            profile = load_profile(p["name"])
            if "extends" in profile:
                overlay = resolve_profile(p["name"])
                assert isinstance(overlay, dict)


# ---------------------------------------------------------------------------
# Deep merge with profile sections
# ---------------------------------------------------------------------------

class TestProfileMerge:
    def test_profile_overlays_deep_merge(self):
        """Profile should deep-merge, not replace, nested dicts."""
        base = {
            "backends": {
                "local": {"model": "base-model", "max_tokens": 4096, "fleet_model": "qwen3-4b"},
            }
        }
        profile_overlay = {
            "backends": {
                "local": {"model": "fast-model"},
            }
        }
        result = _deep_merge(base, profile_overlay)
        # Overridden
        assert result["backends"]["local"]["model"] == "fast-model"
        # Preserved
        assert result["backends"]["local"]["max_tokens"] == 4096
        assert result["backends"]["local"]["fleet_model"] == "qwen3-4b"

    def test_profile_adds_new_sections(self):
        """Profile can add sections that don't exist in base."""
        base = {"backends": {"local": {"model": "x"}}}
        overlay = {"router": {"complexity_thresholds": [0.5, 0.8]}}
        result = _deep_merge(base, overlay)
        assert result["router"]["complexity_thresholds"] == [0.5, 0.8]
        assert result["backends"]["local"]["model"] == "x"


# ---------------------------------------------------------------------------
# Model reference validation (WS3)
# ---------------------------------------------------------------------------


class TestModelValidation:
    """Validate that profile model references exist in the model catalog."""

    def test_unknown_model_rejected(self):
        profile = _make_profile(backends={"local": {"model": "nonexistent-model"}})
        errors = validate_profile(profile, available_models=["hermes", "qwen3-8b"])
        assert any("nonexistent-model" in e for e in errors)

    def test_valid_model_accepted(self):
        profile = _make_profile(backends={"local": {"model": "qwen3-8b"}})
        errors = validate_profile(profile, available_models=["hermes", "qwen3-8b"])
        model_errors = [e for e in errors if "unknown model" in e]
        assert model_errors == []

    def test_none_skips_model_check(self):
        """When available_models is None, model validation is skipped entirely."""
        profile = _make_profile(backends={"local": {"model": "any-model-name"}})
        errors = validate_profile(profile, available_models=None)
        model_errors = [e for e in errors if "unknown model" in e]
        assert model_errors == []

    def test_multiple_bad_models(self):
        profile = _make_profile(backends={"local": {
            "model": "bad1",
            "code_model": "bad2",
            "vision_model": "llava",
        }})
        errors = validate_profile(profile, available_models=["hermes", "llava"])
        bad_errors = [e for e in errors if "unknown model" in e]
        assert len(bad_errors) == 2  # bad1 and bad2
        assert any("bad1" in e for e in bad_errors)
        assert any("bad2" in e for e in bad_errors)

    def test_list_available_models(self, model_configs_dir):
        """list_available_models reads YAML file stems from a directory."""
        models = list_available_models(model_configs_dir)
        assert "hermes" in models
        assert "qwen3-8b" in models
        assert "phi-2" in models
        assert len(models) == 5
