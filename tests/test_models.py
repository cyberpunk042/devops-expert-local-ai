"""Tests for model management."""


import yaml

from aicp.core.models import get_model_config, get_model_info, list_models


def _create_model(models_dir, name, gguf_name, size_mb=100):
    """Helper to create a model config + fake GGUF file."""
    cfg = {
        "name": name,
        "backend": "cuda12-llama-cpp",
        "parameters": {"model": gguf_name},
        "context_size": 2048,
        "gpu_layers": 0,
    }
    (models_dir / f"{name}.yaml").write_text(yaml.dump(cfg))
    (models_dir / gguf_name).write_bytes(b"\x00" * (size_mb * 1024 * 1024))


def test_list_models(tmp_path):
    _create_model(tmp_path, "test-model", "test.gguf", 50)
    models = list_models(tmp_path)
    assert len(models) == 1
    assert models[0].name == "test-model"
    assert models[0].gguf_size_mb == 50


def test_get_model_info(tmp_path):
    _create_model(tmp_path, "alpha", "alpha.gguf")
    info = get_model_info("alpha", tmp_path)
    assert info is not None
    assert info.name == "alpha"


def test_get_model_info_not_found(tmp_path):
    assert get_model_info("nonexistent", tmp_path) is None


def test_get_model_config(tmp_path):
    _create_model(tmp_path, "beta", "beta.gguf")
    cfg = get_model_config("beta", tmp_path)
    assert cfg is not None
    assert cfg["name"] == "beta"
    assert cfg["parameters"]["model"] == "beta.gguf"


def test_list_multiple_models(tmp_path):
    _create_model(tmp_path, "aaa", "aaa.gguf", 100)
    _create_model(tmp_path, "bbb", "bbb.gguf", 200)
    models = list_models(tmp_path)
    assert len(models) == 2
    names = [m.name for m in models]
    assert "aaa" in names
    assert "bbb" in names
