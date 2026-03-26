"""Model management — list, inspect, and configure local models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml


MODELS_DIR = Path(__file__).parent.parent.parent / "models"


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


def list_models(models_dir: Optional[Path] = None) -> List[ModelInfo]:
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


def get_model_info(name: str, models_dir: Optional[Path] = None) -> Optional[ModelInfo]:
    """Get info for a specific model by name."""
    for m in list_models(models_dir):
        if m.name == name:
            return m
    return None


def get_model_config(name: str, models_dir: Optional[Path] = None) -> Optional[dict]:
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
