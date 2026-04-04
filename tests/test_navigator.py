"""Tests for Knowledge Map Navigator."""

from pathlib import Path
from unittest.mock import MagicMock

from aicp.core.modes import Mode
from aicp.core.navigator import Navigator


# Use the real project path so navigator loads actual YAML files
_PROJECT_PATH = Path(__file__).parent.parent


def test_navigator_loads_config():
    nav = Navigator(_PROJECT_PATH)
    stats = nav.stats()
    assert stats["profiles_loaded"] is True
    assert stats["intent_map_loaded"] is True
    assert stats["profile_count"] >= 4  # opus, sonnet, localai, heartbeat
    assert stats["intent_count"] >= 5


def test_select_profile_opus():
    nav = Navigator(_PROJECT_PATH)
    assert nav.select_profile("opus", context_window=1_000_000) == "opus-1m"
    assert nav.select_profile("claude-opus-4-6", context_window=1_000_000) == "opus-1m"


def test_select_profile_sonnet():
    nav = Navigator(_PROJECT_PATH)
    assert nav.select_profile("sonnet", context_window=200_000) == "sonnet-200k"


def test_select_profile_localai():
    nav = Navigator(_PROJECT_PATH)
    assert nav.select_profile("qwen3-8b", context_window=8192) == "localai-8k"
    assert nav.select_profile("qwen3-4b") == "localai-8k"
    assert nav.select_profile("hermes") == "localai-8k"


def test_select_profile_heartbeat():
    nav = Navigator(_PROJECT_PATH)
    assert nav.select_profile("qwen3-8b-fast") == "heartbeat"


def test_match_intent_code():
    nav = Navigator(_PROJECT_PATH)
    intent = nav.match_intent("implement a new function for parsing", Mode.THINK)
    assert intent == "code_task"


def test_match_intent_fleet():
    nav = Navigator(_PROJECT_PATH)
    intent = nav.match_intent("heartbeat check", Mode.THINK)
    assert intent == "fleet_ops"


def test_match_intent_model():
    nav = Navigator(_PROJECT_PATH)
    intent = nav.match_intent("download qwen3-8b model", Mode.THINK)
    assert intent == "model_mgmt"


def test_match_intent_rag():
    nav = Navigator(_PROJECT_PATH)
    intent = nav.match_intent("search the knowledge base for routing docs", Mode.THINK)
    assert intent == "rag_ops"


def test_match_intent_simple_qa():
    """Low-complexity prompts without specific keywords match simple_qa."""
    nav = Navigator(_PROJECT_PATH)
    intent = nav.match_intent("what's the weather like", Mode.THINK)
    assert intent == "simple_qa"


def test_match_intent_default():
    """Ambiguous prompts that don't match keywords or complexity thresholds."""
    nav = Navigator(_PROJECT_PATH)
    # ACT mode bumps complexity above 0.3, but no keywords match
    intent = nav.match_intent("do the thing now please", Mode.ACT)
    assert intent == "default"


def test_injection_spec():
    nav = Navigator(_PROJECT_PATH)
    spec = nav.get_injection_spec(
        "implement a parser", Mode.THINK,
        model="qwen3-8b", context_window=8192,
    )
    assert spec["profile"] == "localai-8k"
    assert spec["intent"] == "code_task"
    assert spec["model_hint"] == "qwen3-8b"


def test_injection_spec_heartbeat():
    nav = Navigator(_PROJECT_PATH)
    spec = nav.get_injection_spec(
        "heartbeat", Mode.THINK,
        model="qwen3-8b-fast",
    )
    assert spec["profile"] == "heartbeat"
    assert spec["budget_tokens"] == 0


def test_assemble_context_heartbeat():
    """Heartbeat profile returns prompt unchanged."""
    nav = Navigator(_PROJECT_PATH)
    result = nav.assemble_context(
        "heartbeat", Mode.THINK,
        model="qwen3-8b-fast",
    )
    assert result == "heartbeat"


def test_assemble_context_with_collection(monkeypatch):
    """When collection has content, context is augmented."""
    nav = Navigator(_PROJECT_PATH)
    # Mock the collection search to return results
    monkeypatch.setattr(nav, "_search_collection", lambda q, top_k=3: [
        {"content": "The router selects backends based on complexity"},
    ])
    result = nav.assemble_context(
        "how does routing work", Mode.THINK,
        model="qwen3-8b", context_window=8192,
    )
    assert "Context:" in result
    assert "router selects backends" in result
    assert "how does routing work" in result


def test_assemble_context_empty_collection(monkeypatch):
    """When collection is empty, returns original prompt."""
    nav = Navigator(_PROJECT_PATH)
    monkeypatch.setattr(nav, "_search_collection", lambda q, top_k=3: [])
    result = nav.assemble_context(
        "explain the system", Mode.THINK,
        model="qwen3-8b",
    )
    assert result == "explain the system"
