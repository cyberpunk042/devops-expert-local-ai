"""Shared test fixtures for AICP test suite."""

from unittest.mock import MagicMock

import pytest

from aicp.backends.localai import LocalAIBackend
from aicp.core.controller import Controller


@pytest.fixture
def mock_localai_backend():
    """A MagicMock spec'd against LocalAIBackend with sane defaults."""
    backend = MagicMock(spec=LocalAIBackend)
    backend.base_url = "http://localhost:8090"
    backend.model = "hermes"
    backend.embedding_model = "nomic-embed"
    backend.vision_model = "llava"
    backend.whisper_model = "whisper-1"
    backend.tts_model = "piper-tts"
    backend.image_model = "stablediffusion"
    backend.reranker_model = "bge-reranker-v2-m3"
    backend.name = "local"
    backend.last_usage = {}
    backend.execute.return_value = "mock response"
    backend.is_available.return_value = True
    return backend


@pytest.fixture
def mock_config():
    """Minimal valid AICP config dict."""
    return {
        "backends": {
            "local": {
                "base_url": "http://localhost:8090",
                "model": "hermes",
                "whisper_model": "whisper-1",
                "tts_model": "piper-tts",
            },
            "claude": {
                "model": "opus",
            },
        },
        "cluster": {"auto_route": False},
    }


@pytest.fixture
def mock_controller(mock_localai_backend, mock_config):
    """Controller with a single mock local backend."""
    return Controller(
        backends={"local": mock_localai_backend},
        config=mock_config,
    )


@pytest.fixture
def config_yaml(tmp_path):
    """Write a minimal valid YAML config file and return its path."""
    content = """\
backends:
  local:
    base_url: http://localhost:8090
    model: hermes
  claude:
    model: opus
cluster:
  auto_route: false
"""
    path = tmp_path / "config.yaml"
    path.write_text(content)
    return path


@pytest.fixture
def model_configs_dir(tmp_path):
    """Create a temp directory with sample model YAML config files."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    for name in ("hermes", "qwen3-8b", "nomic-embed", "phi-2", "llava"):
        cfg = models_dir / f"{name}.yaml"
        cfg.write_text(f"name: {name}\nbackend: llama-cpp\nparameters:\n  model: {name}.gguf\n")

    return models_dir
