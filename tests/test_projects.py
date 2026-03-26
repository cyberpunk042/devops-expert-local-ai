"""Tests for project registry and state."""

from pathlib import Path

from aicp.core.projects import (
    register_project, unregister_project, list_projects,
    init_project_state, load_project_state, save_project_state,
    add_milestone, update_milestone, add_decision, update_session,
)


def test_register_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path / "aicp_home"))
    project = tmp_path / "my-project"
    project.mkdir()

    entry = register_project(project, name="test-project", description="A test")
    assert entry["name"] == "test-project"

    projects = list_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "test-project"


def test_unregister(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path / "aicp_home"))
    project = tmp_path / "proj"
    project.mkdir()

    register_project(project)
    assert len(list_projects()) == 1
    assert unregister_project(project) is True
    assert len(list_projects()) == 0


def test_project_state_init(tmp_path):
    state = init_project_state(tmp_path, "test", "desc")
    assert state["name"] == "test"
    assert state["phase"] == "init"
    assert (tmp_path / ".aicp" / "state.yaml").exists()


def test_project_state_load_save(tmp_path):
    init_project_state(tmp_path, "test", "desc")
    state = load_project_state(tmp_path)
    assert state is not None
    assert state["name"] == "test"

    state["phase"] = "building"
    save_project_state(tmp_path, state)

    reloaded = load_project_state(tmp_path)
    assert reloaded["phase"] == "building"


def test_milestones(tmp_path):
    init_project_state(tmp_path, "test")
    add_milestone(tmp_path, "M1", "First milestone")
    add_milestone(tmp_path, "M2", "Second milestone")

    state = load_project_state(tmp_path)
    assert len(state["milestones"]) == 2
    assert state["milestones"][0]["name"] == "M1"
    assert state["milestones"][0]["status"] == "pending"

    assert update_milestone(tmp_path, "M1", "done") is True
    state = load_project_state(tmp_path)
    assert state["milestones"][0]["status"] == "done"


def test_decisions(tmp_path):
    init_project_state(tmp_path, "test")
    add_decision(tmp_path, "Use Python 3.11", "Best compatibility")

    state = load_project_state(tmp_path)
    assert len(state["decisions"]) == 1
    assert state["decisions"][0]["decision"] == "Use Python 3.11"


def test_update_session(tmp_path):
    init_project_state(tmp_path, "test")
    update_session(tmp_path, "Completed M1, started M2")

    state = load_project_state(tmp_path)
    assert state["last_session"]["summary"] == "Completed M1, started M2"


def test_register_creates_state(tmp_path, monkeypatch):
    monkeypatch.setenv("AICP_HOME", str(tmp_path / "aicp_home"))
    project = tmp_path / "proj"
    project.mkdir()

    register_project(project, name="proj", description="Test project")
    assert (project / ".aicp" / "state.yaml").exists()
    state = load_project_state(project)
    assert state["name"] == "proj"
