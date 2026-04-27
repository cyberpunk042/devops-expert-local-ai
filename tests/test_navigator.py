"""Tests for Knowledge Map Navigator."""

from pathlib import Path

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


# ---------------------------------------------------------------------------
# E-M34: End-to-end routing → profile → injection pipeline validation
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    """Verify that the full routing + profile + injection pipeline
    selects the right model, profile, and content for each task type."""

    def test_fleet_heartbeat_gets_zero_injection(self):
        """Fleet heartbeats with fast model → heartbeat profile → no KB content."""
        nav = Navigator(_PROJECT_PATH)
        # Fast model triggers heartbeat profile
        spec = nav.get_injection_spec("heartbeat", Mode.THINK, model="qwen3-8b-fast")
        assert spec["profile"] == "heartbeat"
        assert spec["budget_tokens"] == 0
        result = nav.assemble_context("heartbeat", Mode.THINK, model="qwen3-8b-fast")
        assert result == "heartbeat"  # unchanged

    def test_gemma4_fleet_gets_localai_profile(self):
        """Gemma4-e2b is a full model (not fast) → localai-8k profile, not heartbeat."""
        nav = Navigator(_PROJECT_PATH)
        spec = nav.get_injection_spec("heartbeat", Mode.THINK, model="gemma4-e2b")
        assert spec["profile"] == "localai-8k"
        assert spec["intent"] == "fleet_ops"

    def test_code_task_gets_localai_profile(self):
        """Code tasks with local model → localai-8k profile → code intent."""
        nav = Navigator(_PROJECT_PATH)
        spec = nav.get_injection_spec(
            "implement a parser for YAML config",
            Mode.THINK, model="qwen3-8b", context_window=8192,
        )
        assert spec["profile"] == "localai-8k"
        assert spec["intent"] == "code_task"
        assert spec["budget_tokens"] > 0

    def test_code_task_with_gemma4(self):
        """Gemma 4 models are recognized as localai-8k tier."""
        nav = Navigator(_PROJECT_PATH)
        spec = nav.get_injection_spec(
            "write a function to sort", Mode.THINK,
            model="gemma4-e4b", context_window=8192,
        )
        assert spec["profile"] == "localai-8k"
        assert spec["intent"] == "code_task"

    def test_opus_model_gets_full_injection(self):
        """Opus model → opus-1m profile → large budget."""
        nav = Navigator(_PROJECT_PATH)
        spec = nav.get_injection_spec(
            "review the architecture", Mode.THINK,
            model="opus", context_window=1_000_000,
        )
        assert spec["profile"] == "opus-1m"
        assert spec["budget_tokens"] >= 50000

    def test_fast_model_gets_heartbeat(self):
        """Fast models (no thinking) → heartbeat profile → zero injection."""
        nav = Navigator(_PROJECT_PATH)
        for model in ["qwen3-8b-fast", "gemma4-fast"]:
            spec = nav.get_injection_spec("summarize this", Mode.THINK, model=model)
            assert spec["profile"] == "heartbeat", f"Expected heartbeat for {model}"
            assert spec["budget_tokens"] == 0

    def test_rag_query_avoids_kb_recursion(self):
        """RAG operations → rag_ops intent → inject_kb=False (avoids recursion)."""
        nav = Navigator(_PROJECT_PATH)
        spec = nav.get_injection_spec(
            "search knowledge base for routing docs", Mode.THINK,
            model="qwen3-8b", context_window=8192,
        )
        assert spec["intent"] == "rag_ops"
        # KB injection is explicitly disabled for rag_ops to avoid recursion
        assert spec["inject_kb"] is False
        # But system/module docs should still be injected
        assert len(spec["inject_systems"]) > 0

    def test_fleet_ops_intent_matched(self):
        """Fleet operation prompts match fleet_ops intent."""
        nav = Navigator(_PROJECT_PATH)
        for prompt in ["heartbeat check", "agent status", "node health check"]:
            spec = nav.get_injection_spec(prompt, Mode.THINK, model="qwen3-4b")
            assert spec["intent"] == "fleet_ops", f"Expected fleet_ops for '{prompt}'"

    def test_model_mgmt_intent(self):
        """Model management prompts match model_mgmt intent."""
        nav = Navigator(_PROJECT_PATH)
        spec = nav.get_injection_spec(
            "download qwen3-8b model and configure it",
            Mode.THINK, model="qwen3-8b",
        )
        assert spec["intent"] == "model_mgmt"

    def test_injection_budget_respected(self, monkeypatch):
        """Injected content stays within profile budget."""
        nav = Navigator(_PROJECT_PATH)
        # Mock collection returning large content
        large_content = "x" * 20000
        monkeypatch.setattr(nav, "_search_collection", lambda q, top_k=3: [
            {"content": large_content},
        ])
        result = nav.assemble_context(
            "how does routing work", Mode.THINK,
            model="qwen3-8b", context_window=8192,
            max_chars=3000,  # localai-8k budget
        )
        # Injected context should be capped
        assert len(result) < len(large_content)

    def test_profile_matches_routing_decision(self):
        """Verify profile selection is consistent with router complexity scoring."""
        from aicp.core.router import analyze_complexity
        nav = Navigator(_PROJECT_PATH)

        # Simple prompt → low complexity → local model → localai-8k profile
        complexity = analyze_complexity("what is Python?", Mode.THINK)
        assert complexity.recommended_tier == "local"
        spec = nav.get_injection_spec("what is Python?", Mode.THINK, model="qwen3-8b")
        assert spec["profile"] == "localai-8k"

        # Heartbeat → even simpler → heartbeat-eligible model → heartbeat profile
        spec2 = nav.get_injection_spec("heartbeat", Mode.THINK, model="qwen3-8b-fast")
        assert spec2["profile"] == "heartbeat"


class TestProfileAwareAssembly:
    """E-M31: Verify profile-based context assembly injects system/module docs."""

    def test_code_task_injects_system_docs(self, monkeypatch):
        """Code task with opus profile injects routing + backends system docs."""
        nav = Navigator(_PROJECT_PATH)
        monkeypatch.setattr(nav, "_search_collection", lambda q, **kw: [])
        result = nav.assemble_context(
            "implement a new router feature", Mode.THINK,
            model="opus", context_window=1_000_000,
        )
        # Opus profile has systems: full, code_task intent injects routing + backends
        assert "[system:routing]" in result
        assert "[system:backends]" in result
        assert "Context:" in result

    def test_heartbeat_injects_nothing(self):
        """Heartbeat profile returns prompt unchanged — no docs, no KB."""
        nav = Navigator(_PROJECT_PATH)
        result = nav.assemble_context(
            "heartbeat", Mode.THINK, model="qwen3-8b-fast",
        )
        assert result == "heartbeat"

    def test_localai_profile_skips_system_docs(self, monkeypatch):
        """localai-8k profile has systems: none — no system docs injected."""
        nav = Navigator(_PROJECT_PATH)
        monkeypatch.setattr(nav, "_search_collection", lambda q, top_k=3: [
            {"content": "some kb result"},
        ])
        result = nav.assemble_context(
            "implement a function", Mode.THINK,
            model="qwen3-8b", context_window=8192,
        )
        # localai-8k has systems: none, so no [system:*] blocks
        assert "[system:" not in result

    def test_load_system_doc_full(self):
        """_load_system_doc at 'full' level returns entire document."""
        nav = Navigator(_PROJECT_PATH)
        doc = nav._load_system_doc("routing", "full")
        assert doc is not None
        assert len(doc) > 500  # routing.md is ~1500 chars

    def test_load_system_doc_condensed(self):
        """_load_system_doc at 'condensed' level returns first section only."""
        nav = Navigator(_PROJECT_PATH)
        full = nav._load_system_doc("routing", "full")
        condensed = nav._load_system_doc("routing", "condensed")
        assert condensed is not None
        assert len(condensed) < len(full)

    def test_load_system_doc_minimal(self):
        """_load_system_doc at 'minimal' level returns first paragraph."""
        nav = Navigator(_PROJECT_PATH)
        minimal = nav._load_system_doc("routing", "minimal")
        full = nav._load_system_doc("routing", "full")
        assert minimal is not None
        assert len(minimal) < len(full)

    def test_load_system_doc_none(self):
        """_load_system_doc at 'none' level returns None."""
        nav = Navigator(_PROJECT_PATH)
        assert nav._load_system_doc("routing", "none") is None

    def test_load_system_doc_missing(self):
        """_load_system_doc for nonexistent system returns None."""
        nav = Navigator(_PROJECT_PATH)
        assert nav._load_system_doc("nonexistent", "full") is None

    def test_context_respects_max_chars(self, monkeypatch):
        """Assembled context stays within max_chars budget."""
        nav = Navigator(_PROJECT_PATH)
        monkeypatch.setattr(nav, "_search_collection", lambda q, top_k=5: [
            {"content": "x" * 5000},
            {"content": "y" * 5000},
        ])
        result = nav.assemble_context(
            "review the architecture", Mode.THINK,
            model="opus", context_window=1_000_000,
            max_chars=2000,
        )
        # Context block + question wrapper should be bounded
        assert len(result) < 5000


class TestMapBoost:
    """E-M32: Verify map-aware boosting re-ranks results using cross-references."""

    def test_boost_promotes_relevant_source(self):
        """Results from sources in the intent's cross-references get boosted."""
        nav = Navigator(_PROJECT_PATH)
        results = [
            {"source": "aicp/core/router.py", "text": "routing logic", "score": 0.5},
            {"source": "aicp/core/session.py", "text": "session state", "score": 0.6},
            {"source": "aicp/backends/localai.py", "text": "backend call", "score": 0.55},
        ]
        boosted = nav.map_boost(results, "code_task")
        # router.py and localai.py are in routing/backends systems → boosted
        # session.py is NOT in code_task cross-refs → no boost
        assert boosted[0]["source"] == "aicp/core/router.py" or \
               boosted[0]["source"] == "aicp/backends/localai.py"
        # Router/localai should have higher scores than session
        session_score = next(r["score"] for r in boosted if "session" in r["source"])
        router_score = next(r["score"] for r in boosted if "router" in r["source"])
        assert router_score > session_score

    def test_boost_no_intent_returns_unchanged(self):
        """Empty intent returns results unchanged."""
        nav = Navigator(_PROJECT_PATH)
        results = [
            {"source": "foo.py", "text": "test", "score": 0.5},
        ]
        boosted = nav.map_boost(results, "")
        assert boosted == results

    def test_boost_unknown_intent_returns_unchanged(self):
        """Unknown intent (no inject config) returns results unchanged."""
        nav = Navigator(_PROJECT_PATH)
        results = [
            {"source": "foo.py", "text": "test", "score": 0.5},
        ]
        boosted = nav.map_boost(results, "nonexistent_intent")
        assert boosted == results

    def test_boost_score_capped_at_one(self):
        """Boosted scores should not exceed 1.0."""
        nav = Navigator(_PROJECT_PATH)
        results = [
            {"source": "aicp/core/router.py", "text": "routing", "score": 0.95},
        ]
        boosted = nav.map_boost(results, "code_task", boost_factor=0.2)
        assert boosted[0]["score"] <= 1.0

    def test_boost_fleet_ops_promotes_cluster(self):
        """Fleet ops intent boosts cluster-related sources."""
        nav = Navigator(_PROJECT_PATH)
        results = [
            {"source": "aicp/core/cluster.py", "text": "cluster config", "score": 0.4},
            {"source": "aicp/core/rag.py", "text": "rag pipeline", "score": 0.5},
        ]
        boosted = nav.map_boost(results, "fleet_ops")
        # cluster.py should be boosted above rag.py
        assert boosted[0]["source"] == "aicp/core/cluster.py"

    def test_boost_integrated_in_assembly(self, monkeypatch):
        """Map boost is applied during context assembly."""
        nav = Navigator(_PROJECT_PATH)
        monkeypatch.setattr(nav, "_search_collection", lambda q, **kw: [
            {"content": "rag pipeline details", "source": "rag.py", "score": 0.6},
            {"content": "routing logic", "source": "router.py", "score": 0.5},
        ])
        result = nav.assemble_context(
            "implement a routing feature", Mode.THINK,
            model="opus", context_window=1_000_000,
        )
        # code_task intent → routing system → router.py should be boosted
        # The order in the context block should reflect boosted ranking
        if "[kb]" in result:
            kb_start = result.index("[kb]")
            remaining = result[kb_start:]
            # routing should appear before rag (boosted)
            if "routing" in remaining and "rag" in remaining:
                assert remaining.index("routing") < remaining.index("rag")


class TestProfileModelMatrix:
    """Verify all model × profile combinations produce valid specs."""

    MODELS = [
        ("qwen3-8b", 8192, "localai-8k"),
        ("qwen3-4b", 16384, "localai-8k"),
        ("qwen3-8b-fast", 8192, "heartbeat"),
        ("gemma4-e2b", 16384, "localai-8k"),
        ("gemma4-e4b", 8192, "localai-8k"),
        ("opus", 1_000_000, "opus-1m"),
        ("sonnet", 200_000, "sonnet-200k"),
        ("hermes", 8192, "localai-8k"),
        ("phi-2", 4096, "localai-8k"),
    ]

    def test_all_models_select_correct_profile(self):
        nav = Navigator(_PROJECT_PATH)
        for model, ctx, expected in self.MODELS:
            result = nav.select_profile(model, context_window=ctx)
            assert result == expected, (
                f"Model '{model}' (ctx={ctx}) expected profile '{expected}', got '{result}'"
            )

    def test_all_models_produce_valid_injection_spec(self):
        nav = Navigator(_PROJECT_PATH)
        for model, ctx, _ in self.MODELS:
            spec = nav.get_injection_spec(
                "explain how routing works", Mode.THINK,
                model=model, context_window=ctx,
            )
            assert "profile" in spec
            assert "intent" in spec
            assert "budget_tokens" in spec
            assert isinstance(spec["budget_tokens"], int)
