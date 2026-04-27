"""Tests for task pipelines."""


import pytest
import yaml

from aicp.core.pipeline import load_pipeline, run_pipeline


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


def _write_pipeline(tmp_path, steps, **kwargs):
    data = {"steps": steps}
    data.update(kwargs)
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.dump(data))
    return path


def test_load_pipeline(tmp_path):
    path = _write_pipeline(tmp_path, [
        {"prompt": "step 1", "mode": "think"},
        {"prompt": "step 2", "mode": "edit"},
    ])
    data = load_pipeline(path)
    assert len(data["steps"]) == 2


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


def test_run_pipeline_with_budget(tmp_path):
    backends = {"local": _MockBackend("local")}
    data = {
        "steps": [
            {"prompt": "step 1", "mode": "think", "backend": "local"},
            {"prompt": "step 2", "mode": "think", "backend": "local"},
        ],
        "budget": {"max_steps": 1},
    }
    results = run_pipeline(data, backends, tmp_path)
    # First step completes, second blocked by budget
    assert len(results) == 2
    assert results[0]["error"] is None
    assert "Budget limit" in results[1]["error"]


def test_run_pipeline_with_agents(tmp_path):
    backends = {"local": _MockBackend("local")}
    data = {
        "steps": [
            {"prompt": "review code", "mode": "think", "backend": "local", "agent": "reviewer"},
        ],
        "agents": {
            "reviewer": {"system_prompt": "You are a code reviewer."},
        },
    }
    results = run_pipeline(data, backends, tmp_path)
    assert len(results) == 1
    assert results[0]["error"] is None
    assert results[0].get("agent") == "reviewer"


def test_run_pipeline_with_retry(tmp_path):
    call_count = [0]

    class _FlakeyBackend(_MockBackend):
        def execute(self, prompt, mode, project_path):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise RuntimeError("transient failure")
            return "success after retry"

    backends = {"local": _FlakeyBackend("local")}
    steps = [
        {"prompt": "do thing", "mode": "think", "backend": "local", "retry": 2},
    ]
    results = run_pipeline(steps, backends, tmp_path)
    assert len(results) == 1
    assert results[0]["error"] is None
    assert "success" in results[0]["result"]
    assert call_count[0] == 2
