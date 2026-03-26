"""Tests for task pipelines."""

from pathlib import Path

import yaml
import pytest

from aicp.core.pipeline import load_pipeline, run_pipeline
from aicp.core.modes import Mode


class _MockBackend:
    def __init__(self, name):
        self._name = name
        self.last_usage = {}

    @property
    def name(self):
        return self._name

    def is_available(self):
        return True

    def execute(self, prompt, mode, project_path):
        return f"Response to: {prompt[:50]}"

    def status_detail(self):
        return "OK"


def _write_pipeline(tmp_path, steps):
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.dump({"steps": steps}))
    return path


def test_load_pipeline(tmp_path):
    path = _write_pipeline(tmp_path, [
        {"prompt": "step 1", "mode": "think"},
        {"prompt": "step 2", "mode": "edit"},
    ])
    steps = load_pipeline(path)
    assert len(steps) == 2


def test_load_pipeline_invalid(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("just a string")
    with pytest.raises(ValueError):
        load_pipeline(path)


def test_run_pipeline_basic(tmp_path):
    backends = {"local": _MockBackend("local"), "claude": _MockBackend("claude")}
    steps = [
        {"prompt": "analyze code", "mode": "think", "backend": "local"},
        {"prompt": "fix bugs from {step_0}", "mode": "edit", "backend": "claude"},
    ]
    results = run_pipeline(steps, backends, tmp_path)
    assert len(results) == 2
    assert results[0]["error"] is None
    assert results[1]["error"] is None
    # Step 1 result should be substituted into step 2 prompt
    assert "Response to:" in results[1]["result"]


def test_run_pipeline_stops_on_error(tmp_path):
    class _FailBackend(_MockBackend):
        def execute(self, prompt, mode, project_path):
            raise RuntimeError("intentional failure")

    backends = {"local": _FailBackend("local")}
    steps = [
        {"prompt": "step 1", "mode": "think", "backend": "local"},
        {"prompt": "step 2", "mode": "think", "backend": "local"},
    ]
    results = run_pipeline(steps, backends, tmp_path)
    assert len(results) == 1
    assert results[0]["error"] is not None


def test_run_pipeline_auto_backend(tmp_path):
    backends = {"local": _MockBackend("local"), "claude": _MockBackend("claude")}
    steps = [
        {"prompt": "what is python?", "mode": "think", "backend": "auto"},
    ]
    results = run_pipeline(steps, backends, tmp_path)
    assert len(results) == 1
    assert results[0]["error"] is None
    assert results[0]["backend"] in ("local", "claude")
