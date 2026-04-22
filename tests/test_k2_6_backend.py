"""Tests for the K2.6 OpenRouter backend (E011-m002, partial).

Verifies:
- OpenRouterBackend accepts a `name` parameter and reflects it in `.name`
- _build_backends registers `k2_6_openrouter` when OPENROUTER_API_KEY is set
- The two OpenRouter-class instances have distinct names + models

Brain authoritative spec: ~/devops-solutions-research-wiki/wiki/backlog/modules/
e011-m002-k2-6-openrouter-backend-adapter.md
"""
from __future__ import annotations

import os

from aicp.backends.openrouter import OpenRouterBackend


def test_openrouter_backend_default_name() -> None:
    backend = OpenRouterBackend(api_key="test-key", model="qwen/qwen3-8b:free")
    assert backend.name == "openrouter"


def test_openrouter_backend_custom_name_for_k2_6() -> None:
    backend = OpenRouterBackend(
        api_key="test-key",
        model="moonshotai/kimi-k2.6",
        max_tokens=8192,
        timeout=300,
        name="k2_6_openrouter",
    )
    assert backend.name == "k2_6_openrouter"
    assert backend.model == "moonshotai/kimi-k2.6"
    assert backend.max_tokens == 8192


def test_build_backends_registers_k2_6_when_openrouter_key_set(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-fake")

    from aicp.cli.main import _build_backends

    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
            "openrouter": {"max_tokens": 4096, "timeout": 120},
            "k2_6_openrouter": {
                "model": "moonshotai/kimi-k2.6",
                "max_tokens": 8192,
                "timeout": 300,
                "enabled": True,
            },
        }
    }

    backends = _build_backends(config)

    assert "openrouter" in backends
    assert "k2_6_openrouter" in backends
    assert backends["openrouter"].name == "openrouter"
    assert backends["k2_6_openrouter"].name == "k2_6_openrouter"
    assert backends["k2_6_openrouter"].model == "moonshotai/kimi-k2.6"
    assert backends["openrouter"].name != backends["k2_6_openrouter"].name


def test_build_backends_skips_k2_6_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-fake")

    from aicp.cli.main import _build_backends

    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
            "openrouter": {"max_tokens": 4096, "timeout": 120},
            "k2_6_openrouter": {
                "model": "moonshotai/kimi-k2.6",
                "enabled": False,
            },
        }
    }

    backends = _build_backends(config)

    assert "openrouter" in backends
    assert "k2_6_openrouter" not in backends


def test_build_backends_skips_k2_6_when_no_openrouter_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    from aicp.cli.main import _build_backends

    config = {
        "backends": {
            "local": {"base_url": "http://localhost:8090", "model": "qwen3-8b"},
            "claude": {"model": "opus", "max_turns": 10, "timeout": 300},
            "openrouter": {"max_tokens": 4096, "timeout": 120},
            "k2_6_openrouter": {
                "model": "moonshotai/kimi-k2.6",
                "enabled": True,
            },
        }
    }

    backends = _build_backends(config)

    assert "openrouter" not in backends
    assert "k2_6_openrouter" not in backends
