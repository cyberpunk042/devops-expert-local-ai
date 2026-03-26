"""GPU detection and auto-configuration for LocalAI models."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

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


def detect_gpus() -> List[GpuInfo]:
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
    """Estimate VRAM needed for a GGUF model (rough: file size + 20% overhead)."""
    size_bytes = gguf_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return int(size_mb * 1.2)  # 20% overhead for KV cache base allocation


def calculate_optimal_config(
    gguf_path: Path,
    gpus: List[GpuInfo],
    target_gpu_indices: Optional[List[int]] = None,
) -> dict:
    """Calculate optimal LocalAI model config based on available hardware.

    Returns a dict suitable for writing to a model YAML file.
    """
    model_vram = estimate_model_vram_mb(gguf_path)
    cpu_count = os.cpu_count() or 4

    if not gpus:
        # CPU-only fallback
        return {
            "gpu_layers": 0,
            "context_size": 2048,
            "threads": max(1, cpu_count - 1),
        }

    # Filter to target GPUs
    if target_gpu_indices is not None:
        available = [g for g in gpus if g.index in target_gpu_indices]
    else:
        available = gpus

    if not available:
        return {"gpu_layers": 0, "context_size": 2048, "threads": max(1, cpu_count - 1)}

    total_free = sum(g.vram_free_mb for g in available)

    if model_vram < total_free * 0.8:
        # Model fits in GPU with room for KV cache
        gpu_layers = 99  # offload all layers
        remaining_vram = total_free - model_vram
        # Rough: ~2MB per 1K context for a 3B model
        context_size = min(8192, max(512, (remaining_vram // 2) * 1000))
        # Round to nearest power of 2
        for size in [512, 1024, 2048, 4096, 8192]:
            if size >= context_size:
                context_size = size
                break
    elif model_vram < total_free * 1.5:
        # Partial offload
        fit_ratio = total_free * 0.7 / model_vram
        gpu_layers = max(1, int(fit_ratio * 40))  # assume ~40 layers for typical model
        context_size = 2048
    else:
        # Model too large for available VRAM
        gpu_layers = 0
        context_size = 2048

    config = {
        "gpu_layers": gpu_layers,
        "context_size": context_size,
        "threads": max(1, cpu_count - 1),
    }

    # Multi-GPU tensor split
    if len(available) > 1 and gpu_layers > 0:
        total_vram = sum(g.vram_total_mb for g in available)
        splits = [round(g.vram_total_mb / total_vram, 2) for g in available]
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
