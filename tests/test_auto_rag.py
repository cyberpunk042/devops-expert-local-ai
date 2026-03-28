"""Tests for auto-RAG: automatic KB context injection."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aicp.core.kb import KnowledgeBase


# ── KnowledgeBase augment_prompt is the core of auto-RAG ─────────────────────

class TestAutoRAGAugment:
    def test_augments_when_kb_has_content(self, tmp_path):
        cfg = {
            "rag": {
                "db_path": str(tmp_path / "kb.db"),
                "store_name": "test",
                "chunk_size": 256,
                "chunk_overlap": 32,
                "top_k": 3,
                "threshold": 0.0,
                "rerank": False,
            },
            "backends": {"local": {}},
        }
        backend = MagicMock()
        backend.embed_batch.return_value = [[1.0] * 768]
        backend.embed.return_value = [1.0] * 768

        kb = KnowledgeBase(backend, cfg)
        kb.ingest_text("Python is a programming language.", source="intro.md")

        result = kb.augment_prompt("What is Python?")
        assert "Context:" in result
        assert "Question: What is Python?" in result
        assert "Python is a programming language" in result

    def test_no_augment_when_kb_empty(self, tmp_path):
        cfg = {
            "rag": {"db_path": str(tmp_path / "kb.db")},
            "backends": {"local": {}},
        }
        backend = MagicMock()
        kb = KnowledgeBase(backend, cfg)
        result = kb.augment_prompt("What is Python?")
        assert result == "What is Python?"

    def test_stats_check_prevents_empty_kb_queries(self, tmp_path):
        cfg = {
            "rag": {"db_path": str(tmp_path / "kb.db")},
            "backends": {"local": {}},
        }
        backend = MagicMock()
        kb = KnowledgeBase(backend, cfg)
        stats = kb.stats()
        assert stats["total_chunks"] == 0
        # Auto-RAG should check this and skip augmentation


# ── CLI auto-RAG integration ────────────────────────────────────────────────

class TestAutoRAGFlow:
    def test_auto_rag_full_flow(self, tmp_path):
        """Simulate auto-RAG: check stats → augment if content exists."""
        cfg = {
            "rag": {
                "db_path": str(tmp_path / "kb.db"),
                "store_name": "default",
                "chunk_size": 256,
                "chunk_overlap": 32,
                "top_k": 3,
                "threshold": 0.0,
                "rerank": False,
                "max_context_chars": 1000,
                "enabled": True,
            },
            "backends": {"local": {}},
        }
        backend = MagicMock()
        backend.embed_batch.return_value = [[1.0] * 768]
        backend.embed.return_value = [1.0] * 768

        kb = KnowledgeBase(backend, cfg)
        kb.ingest_text("AICP is an AI control platform.", source="readme")

        # Auto-RAG check: stats > 0 → augment
        assert kb.stats()["total_chunks"] > 0
        augmented = kb.augment_prompt("What is AICP?", max_context_chars=1000)
        assert "Context:" in augmented
        assert "AICP is an AI control platform" in augmented
        assert "Question: What is AICP?" in augmented

    def test_auto_rag_skips_empty_kb(self, tmp_path):
        """Auto-RAG should skip when KB has no content."""
        cfg = {
            "rag": {
                "db_path": str(tmp_path / "kb.db"),
                "enabled": True,
            },
            "backends": {"local": {}},
        }
        backend = MagicMock()
        kb = KnowledgeBase(backend, cfg)
        assert kb.stats()["total_chunks"] == 0
        # Prompt should pass through unchanged
        result = kb.augment_prompt("test query")
        assert result == "test query"

    def test_auto_rag_disabled_config(self):
        """When rag.enabled=false, auto-RAG should not activate."""
        from aicp.config.loader import get_rag_config
        config = {"rag": {"enabled": False}}
        rag_cfg = get_rag_config(config)
        assert rag_cfg["enabled"] is False

    def test_auto_rag_default_disabled(self):
        """Auto-RAG should be off by default."""
        from aicp.config.loader import get_rag_config
        config = {}
        rag_cfg = get_rag_config(config)
        assert rag_cfg.get("enabled", False) is False
