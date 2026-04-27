"""GPU detection and auto-configuration for LocalAI models."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class GpuInfo:
    """Information about a single GPU."""
    index: int
    name: str
    vram_total_mb: int
    vram_used_mb: int
    vram_free_mb: int
    driver_version: str
    compute_cap: str


def detect_gpus() -> list[GpuInfo]:
    """Detect available NVIDIA GPUs via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.total,memory.used,memory.free,driver_version,compute_cap",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    gpus = []
    for line in result.stdout.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 7:
            gpus.append(GpuInfo(
                index=int(parts[0]),
                name=parts[1],
                vram_total_mb=int(float(parts[2])),
                vram_used_mb=int(float(parts[3])),
                vram_free_mb=int(float(parts[4])),
                driver_version=parts[5],
                compute_cap=parts[6],
            ))
    return gpus


def estimate_model_vram_mb(gguf_path: Path) -> int:
    """Estimate VRAM needed for a GGUF model weights only (file size ≈ VRAM for quantized)."""
    size_bytes = gguf_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return int(size_mb * 1.05)  # 5% overhead for metadata — Q4_K_M doesn't expand much


def estimate_kv_cache_mb(context_size: int, n_layers: int = 32, kv_quantized: bool = True) -> int:
    """Estimate KV cache VRAM for a given context size.

    With q4_0 KV cache quantization (our default), VRAM is ~4x less than f16.
    Formula: 2 * n_layers * n_kv_heads * head_dim * context_size * bytes_per_element
    For 7-8B models: ~32 layers, 8 KV heads, 128 head_dim
    """
    bytes_per_element = 0.5 if kv_quantized else 2.0  # q4_0 vs f16
    # Simplified: ~0.5MB per 1K context with q4_0, ~2MB with f16
    per_1k = 0.5 if kv_quantized else 2.0
    return int(context_size / 1000 * per_1k * (n_layers / 32))


# VRAM reserve for system, driver, CUDA overhead, display
SYSTEM_VRAM_RESERVE_MB = 800


def calculate_optimal_config(
    gguf_path: Path,
    gpus: list[GpuInfo],
    target_gpu_indices: list[int] | None = None,
) -> dict:
    """Calculate optimal LocalAI model config based on available hardware.

    Uses TOTAL VRAM (not free) with a fixed system reserve.
    Accounts for KV cache quantization (q4_0 — our default via optimize-models.sh).
    Never downgrades below the model's designed config from config/models/.

    Returns a dict suitable for writing to a model YAML file.
    """
    model_vram = estimate_model_vram_mb(gguf_path)
    cpu_count = os.cpu_count() or 4

    if not gpus:
        return {
            "gpu_layers": 0,
            "context_size": 2048,
            "threads": max(1, cpu_count - 1),
        }

    if target_gpu_indices is not None:
        available = [g for g in gpus if g.index in target_gpu_indices]
    else:
        available = gpus

    if not available:
        return {"gpu_layers": 0, "context_size": 2048, "threads": max(1, cpu_count - 1)}

    # Use TOTAL VRAM minus system reserve — not FREE (which varies by moment)
    total_vram = sum(g.vram_total_mb for g in available)
    usable_vram = total_vram - SYSTEM_VRAM_RESERVE_MB

    # Check existing model YAML for KV cache quantization
    model_yaml = gguf_path.parent / (gguf_path.stem.split(".")[0] + ".yaml")
    kv_quantized = True  # assume yes — optimize-models.sh sets this for all models
    existing_context = 0
    existing_gpu_layers = 0
    if model_yaml.exists():
        try:
            with open(model_yaml) as f:
                data = yaml.safe_load(f) or {}
            kv_quantized = data.get("cache_type_k", "f16") != "f16"
            existing_context = data.get("context_size", 0)
            existing_gpu_layers = data.get("gpu_layers", 0)
        except Exception:
            pass

    if model_vram < usable_vram:
        # Model fits fully in GPU
        gpu_layers = 99
        remaining = usable_vram - model_vram
        # Calculate max context that fits in remaining VRAM
        # With q4_0 KV cache: ~0.5MB per 1K context per 32 layers
        per_1k = 0.5 if kv_quantized else 2.0
        max_context = int(remaining / per_1k * 1000) if per_1k > 0 else 8192
        # Round down to nearest standard size
        for size in [16384, 8192, 4096, 2048, 1024]:
            if max_context >= size:
                context_size = size
                break
        else:
            context_size = 512
    else:
        # Model needs partial offload — shouldn't happen for Q4 7-8B on 8GB
        fit_ratio = usable_vram / model_vram
        gpu_layers = max(1, int(fit_ratio * 33))  # typical 7-8B has ~33 layers
        context_size = 4096  # conservative but usable, not 2048

    # Never downgrade below existing config values (from config/models/ source of truth)
    if existing_gpu_layers > gpu_layers:
        gpu_layers = existing_gpu_layers
    if existing_context > context_size:
        context_size = existing_context

    config = {
        "gpu_layers": gpu_layers,
        "context_size": context_size,
        "threads": max(1, cpu_count // 2),  # half CPU cores — GPU does most work
    }

    if len(available) > 1 and gpu_layers > 0:
        total = sum(g.vram_total_mb for g in available)
        splits = [round(g.vram_total_mb / total, 2) for g in available]
        config["tensor_split"] = ",".join(str(s) for s in splits)
        config["main_gpu"] = available[0].index

    return config


def generate_model_yaml(
    model_name: str,
    gguf_filename: str,
    optimal_config: dict,
    backend: str = "cuda12-llama-cpp",
) -> str:
    """Generate a model YAML config string."""
    cfg = {
        "name": model_name,
        "backend": backend,
        "parameters": {
            "model": gguf_filename,
            "temperature": 0.7,
            "top_p": 0.9,
        },
        "context_size": optimal_config["context_size"],
        "threads": optimal_config["threads"],
        "gpu_layers": optimal_config["gpu_layers"],
    }

    if "tensor_split" in optimal_config:
        cfg["parameters"]["tensor_split"] = optimal_config["tensor_split"]
    if "main_gpu" in optimal_config:
        cfg["parameters"]["main_gpu"] = optimal_config["main_gpu"]

    return yaml.dump(cfg, default_flow_style=False, sort_keys=False)
