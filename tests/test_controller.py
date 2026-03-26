"""Tests for the Controller."""

from pathlib import Path

import pytest

from aicp.core.controller import Controller, Task
from aicp.core.modes import Mode


def test_rejects_nonexistent_project_path():
    controller = Controller(backends={})
    task = Task(
        prompt="hello",
        mode=Mode.THINK,
        project_path=Path("/nonexistent/path/that/does/not/exist"),
        backend_name="local",
    )
    with pytest.raises(ValueError, match="does not exist"):
        controller.run(task)


def test_rejects_file_as_project_path(tmp_path):
    f = tmp_path / "not_a_dir.txt"
    f.write_text("hello")
    controller = Controller(backends={})
    task = Task(
        prompt="hello",
        mode=Mode.THINK,
        project_path=f,
        backend_name="local",
    )
    with pytest.raises(ValueError, match="not a directory"):
        controller.run(task)


def test_rejects_unknown_backend(tmp_path):
    controller = Controller(backends={})
    task = Task(
        prompt="hello",
        mode=Mode.THINK,
        project_path=tmp_path,
        backend_name="nonexistent",
    )
    with pytest.raises(ValueError, match="Unknown backend"):
        controller.run(task)
