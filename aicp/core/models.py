"""Model management — list, inspect, download, activate, and benchmark."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

from aicp.core.gpu import calculate_optimal_config, detect_gpus

MODELS_DIR = Path(__file__).parent.parent.parent / "models"

# Common HuggingFace GGUF URL pattern
_HF_URL_RE = re.compile(r"^https?://huggingface\.co/")


@dataclass
class ModelInfo:
    """Information about a local model."""
    name: str
    gguf_file: str
    gguf_size_mb: int
    backend: str
    context_size: int
    gpu_layers: int
    config_path: Path


def list_models(models_dir: Path | None = None) -> list[ModelInfo]:
    """List all configured models in the models directory."""
    d = models_dir or MODELS_DIR
    if not d.exists():
        return []

    models = []
    for yaml_file in sorted(d.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                cfg = yaml.safe_load(f)
            if not isinstance(cfg, dict) or "name" not in cfg:
                continue

            gguf = cfg.get("parameters", {}).get("model", "")
            gguf_path = d / gguf
            size_mb = int(gguf_path.stat().st_size / (1024 * 1024)) if gguf_path.exists() else 0

            models.append(ModelInfo(
                name=cfg["name"],
                gguf_file=gguf,
                gguf_size_mb=size_mb,
                backend=cfg.get("backend", "unknown"),
                context_size=cfg.get("context_size", 0),
                gpu_layers=cfg.get("gpu_layers", 0),
                config_path=yaml_file,
            ))
        except (yaml.YAMLError, OSError):
            continue

    return models


def get_model_info(name: str, models_dir: Path | None = None) -> ModelInfo | None:
    """Get info for a specific model by name."""
    for m in list_models(models_dir):
        if m.name == name:
            return m
    return None


def get_model_config(name: str, models_dir: Path | None = None) -> dict | None:
    """Get the full YAML config for a model."""
    d = models_dir or MODELS_DIR
    for yaml_file in d.glob("*.yaml"):
        try:
            with open(yaml_file) as f:
                cfg = yaml.safe_load(f)
            if isinstance(cfg, dict) and cfg.get("name") == name:
                return cfg
        except (yaml.YAMLError, OSError):
            continue
    return None


def download_model(
    url: str,
    models_dir: Path | None = None,
    name: str | None = None,
    progress_callback=None,
) -> Path:
    """Download a GGUF model file and generate a config.

    Args:
        url: Direct URL to a .gguf file (e.g., HuggingFace)
        models_dir: Target directory (default: models/)
        name: Model name for config (derived from filename if not given)
        progress_callback: Called with (downloaded_bytes, total_bytes)

    Returns: Path to the downloaded GGUF file.
    """
    d = models_dir or MODELS_DIR
    d.mkdir(parents=True, exist_ok=True)

    # Derive filename from URL
    filename = url.split("/")[-1].split("?")[0]
    if not filename.endswith(".gguf"):
        filename += ".gguf"

    dest = d / filename
    if dest.exists():
        raise FileExistsError(f"Model already exists: {dest}")

    # Stream download
    with httpx.stream("GET", url, follow_redirects=True, timeout=600.0) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total)

    # Generate config
    if name is None:
        name = filename.replace(".gguf", "").lower()
        name = re.sub(r"[^a-z0-9-]", "-", name)
        name = re.sub(r"-+", "-", name).strip("-")

    gpus = detect_gpus()
    optimal = calculate_optimal_config(dest, gpus)

    cfg = {
        "name": name,
        "backend": "cuda12-llama-cpp",
        "parameters": {
            "model": filename,
            "temperature": 0.7,
            "top_p": 0.9,
        },
        "context_size": optimal["context_size"],
        "threads": optimal["threads"],
        "gpu_layers": optimal["gpu_layers"],
    }
    if "tensor_split" in optimal:
        cfg["parameters"]["tensor_split"] = optimal["tensor_split"]

    config_path = d / f"{name}.yaml"
    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

    return dest


def activate_model(name: str, config: dict[str, Any], models_dir: Path | None = None) -> None:
    """Set a model as the active local model in the AICP config."""
    config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"
    with open(config_path) as f:
        full_config = yaml.safe_load(f)

    full_config["backends"]["local"]["model"] = name

    with open(config_path, "w") as f:
        yaml.dump(full_config, f, default_flow_style=False, sort_keys=False)


def benchmark_model(
    name: str,
    base_url: str = "http://localhost:8090",
    prompt: str = "Explain what a linked list is in 2 sentences.",
) -> dict[str, Any]:
    """Run a simple benchmark against a model.

    Returns: dict with tokens_per_second, latency, prompt_tokens, completion_tokens.
    """
    start = time.time()
    response = httpx.post(
        f"{base_url}/v1/chat/completions",
        json={
            "model": name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 128,
        },
        timeout=120.0,
    )
    elapsed = time.time() - start
    response.raise_for_status()

    try:
        data = response.json()
        usage = data.get("usage", {})
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
        preview = data["choices"][0]["message"]["content"][:100]
    except (KeyError, IndexError, TypeError, ValueError):
        pt, ct, preview = 0, 0, response.text[:100]

    return {
        "model": name,
        "latency_seconds": round(elapsed, 2),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "tokens_per_second": round(ct / elapsed, 1) if elapsed > 0 else 0,
        "response_preview": preview,
    }
