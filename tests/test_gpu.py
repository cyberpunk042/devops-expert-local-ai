"""Tests for GPU detection and auto-configuration."""

from pathlib import Path

from aicp.core.gpu import (
    GpuInfo, calculate_optimal_config, estimate_model_vram_mb, generate_model_yaml,
)


def _mock_gpu(vram_total=8192, vram_free=4000, index=0):
    return GpuInfo(
        index=index, name="Test GPU", vram_total_mb=vram_total,
        vram_used_mb=vram_total - vram_free, vram_free_mb=vram_free,
        driver_version="595.97", compute_cap="7.5",
    )


def test_estimate_model_vram(tmp_path):
    f = tmp_path / "test.gguf"
    f.write_bytes(b"\x00" * (2000 * 1024 * 1024))  # 2GB file
    est = estimate_model_vram_mb(f)
    assert 2300 < est < 2500  # 2000 * 1.2 = 2400


def test_optimal_config_model_fits_in_gpu(tmp_path):
    f = tmp_path / "small.gguf"
    f.write_bytes(b"\x00" * (1500 * 1024 * 1024))  # 1.5GB
    gpus = [_mock_gpu(vram_free=4000)]
    cfg = calculate_optimal_config(f, gpus)
    assert cfg["gpu_layers"] == 99  # all layers offloaded
    assert cfg["context_size"] >= 512


def test_optimal_config_no_gpu(tmp_path):
    f = tmp_path / "model.gguf"
    f.write_bytes(b"\x00" * (1024 * 1024))
    cfg = calculate_optimal_config(f, [])
    assert cfg["gpu_layers"] == 0
    assert cfg["context_size"] == 2048


def test_optimal_config_model_too_large(tmp_path):
    f = tmp_path / "huge.gguf"
    f.write_bytes(b"\x00" * (7000 * 1024 * 1024))  # 7GB, won't fit in 4GB free
    gpus = [_mock_gpu(vram_free=4000)]
    cfg = calculate_optimal_config(f, gpus)
    assert cfg["gpu_layers"] == 0  # can't fit


def test_optimal_config_multi_gpu(tmp_path):
    f = tmp_path / "model.gguf"
    f.write_bytes(b"\x00" * (1024 * 1024 * 1024))  # 1GB
    gpus = [_mock_gpu(index=0, vram_free=4000), _mock_gpu(index=1, vram_free=4000)]
    cfg = calculate_optimal_config(f, gpus)
    assert cfg["gpu_layers"] == 99
    assert "tensor_split" in cfg


def test_generate_model_yaml():
    yaml_str = generate_model_yaml("test-model", "test.gguf", {
        "gpu_layers": 99, "context_size": 4096, "threads": 3,
    })
    assert "test-model" in yaml_str
    assert "test.gguf" in yaml_str
    assert "gpu_layers: 99" in yaml_str
