"""Tests for the Controller."""

from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_rejects_dangerous_project_root():
    controller = Controller(backends={})
    task = Task(
        prompt="hello",
        mode=Mode.THINK,
        project_path=Path("/"),
        backend_name="local",
    )
    with pytest.raises(ValueError, match="[Rr]efusing"):
        controller.run(task)


def test_rejects_home_as_project():
    controller = Controller(backends={})
    task = Task(
        prompt="hello",
        mode=Mode.THINK,
        project_path=Path.home(),
        backend_name="local",
    )
    with pytest.raises(ValueError, match="home directory"):
        controller.run(task)


# ---------------------------------------------------------------------------
# Fleet-aware routing
# ---------------------------------------------------------------------------


class TestFleetRouting:
    """Test fleet-aware routing in the controller."""

    def _make_controller(self, auto_route: bool = True) -> Controller:
        backend = MagicMock()
        backend.execute.return_value = "local result"
        backend.last_usage = {}
        return Controller(
            backends={"local": backend},
            config={"cluster": {"auto_route": auto_route, "config_file": "config/fleet.yaml"}},
        )

    def test_fleet_disabled_uses_local(self, tmp_path):
        """When auto_route is false, fleet routing is skipped entirely."""
        ctrl = self._make_controller(auto_route=False)
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        result = ctrl.run(task)
        assert result == "local result"
        assert ctrl.last_route == "local"

    @patch("aicp.core.controller.find_best_node")
    @patch("aicp.core.controller.check_cluster")
    @patch("aicp.core.controller.load_cluster_config")
    def test_fleet_routes_to_remote(self, mock_load, mock_check, mock_best, tmp_path):
        """When best node is remote, task is delegated via execute_remote."""
        from aicp.core.cluster import NodeInfo

        remote = NodeInfo(name="workstation", host="192.168.40.250", port=9100, token="t", online=True)
        mock_load.return_value = [remote]
        mock_check.return_value = [remote]
        mock_best.return_value = remote

        ctrl = self._make_controller(auto_route=True)
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")

        with patch("aicp.core.controller.execute_remote", return_value={"response": "remote result"}) as mock_exec:
            result = ctrl.run(task)

        assert result == "remote result"
        assert "fleet:" in ctrl.last_route
        assert "workstation" in ctrl.last_route
        mock_exec.assert_called_once()

    @patch("aicp.core.controller.find_best_node")
    @patch("aicp.core.controller.check_cluster")
    @patch("aicp.core.controller.load_cluster_config")
    def test_fleet_falls_back_local_when_no_nodes(self, mock_load, mock_check, mock_best, tmp_path):
        """When no fleet nodes are online, falls back to local execution."""
        mock_load.return_value = []
        mock_check.return_value = []
        mock_best.return_value = None

        ctrl = self._make_controller(auto_route=True)
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        result = ctrl.run(task)
        assert result == "local result"
        assert ctrl.last_route == "local"

    @patch("aicp.core.controller._local_ips", return_value={"127.0.0.1", "::1", "localhost", "192.168.40.10"})
    @patch("aicp.core.controller.find_best_node")
    @patch("aicp.core.controller.check_cluster")
    @patch("aicp.core.controller.load_cluster_config")
    def test_fleet_self_node_uses_local(self, mock_load, mock_check, mock_best, mock_ips, tmp_path):
        """When best node is this machine, execute locally instead of remote."""
        from aicp.core.cluster import NodeInfo

        self_node = NodeInfo(name="mining-station", host="192.168.40.10", port=9100, token="t", online=True)
        mock_load.return_value = [self_node]
        mock_check.return_value = [self_node]
        mock_best.return_value = self_node

        ctrl = self._make_controller(auto_route=True)
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        result = ctrl.run(task)
        assert result == "local result"
        assert "local" in ctrl.last_route


# ---------------------------------------------------------------------------
# Failover chain
# ---------------------------------------------------------------------------


class TestFailoverChain:
    """Test failover: local → fleet peer → Claude."""

    def test_failover_to_claude_when_local_fails(self, tmp_path):
        """When local backend raises and Claude is available, failover to Claude."""
        local_backend = MagicMock()
        local_backend.execute.side_effect = RuntimeError("LocalAI down")
        local_backend.last_usage = {}

        claude_backend = MagicMock()
        claude_backend.execute.return_value = "claude fallback result"
        claude_backend.last_usage = {}

        ctrl = Controller(
            backends={"local": local_backend, "claude": claude_backend},
            config={"cluster": {"auto_route": True, "config_file": "/nonexistent"}},
        )
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        result = ctrl.run(task)
        assert result == "claude fallback result"
        assert ctrl.last_route == "failover:claude"
        claude_backend.execute.assert_called_once()

    def test_failover_disabled_raises_original_error(self, tmp_path):
        """When auto_route is off, local failure raises without trying failover."""
        local_backend = MagicMock()
        local_backend.execute.side_effect = RuntimeError("LocalAI down")
        local_backend.last_usage = {}

        claude_backend = MagicMock()
        claude_backend.last_usage = {}

        ctrl = Controller(
            backends={"local": local_backend, "claude": claude_backend},
            config={"cluster": {"auto_route": False}},
        )
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        with pytest.raises(RuntimeError, match="LocalAI down"):
            ctrl.run(task)
        claude_backend.execute.assert_not_called()

    @patch("aicp.core.controller._local_ips", return_value={"127.0.0.1", "::1", "localhost", "192.168.40.10"})
    @patch("aicp.core.controller.check_cluster")
    @patch("aicp.core.controller.load_cluster_config")
    def test_failover_to_fleet_peer(self, mock_load, mock_check, mock_ips, tmp_path):
        """When local fails, try fleet peer before Claude."""
        from aicp.core.cluster import NodeInfo

        local_backend = MagicMock()
        local_backend.execute.side_effect = RuntimeError("LocalAI down")
        local_backend.last_usage = {}

        claude_backend = MagicMock()
        claude_backend.last_usage = {}

        peer = NodeInfo(name="workstation", host="192.168.40.250", port=9100, token="t", online=True)
        mock_load.return_value = [peer]
        mock_check.return_value = [peer]

        ctrl = Controller(
            backends={"local": local_backend, "claude": claude_backend},
            config={"cluster": {"auto_route": True, "config_file": "config/fleet.yaml"}},
        )
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")

        with patch("aicp.core.controller.execute_remote", return_value={"result": "peer result"}) as mock_exec:
            # find_best_node returns self (192.168.40.10) so _try_fleet_route returns None,
            # then local fails, then _try_fleet_failover tries the peer
            with patch("aicp.core.controller.find_best_node", return_value=NodeInfo(
                name="mining-station", host="192.168.40.10", port=9100, token="t", online=True
            )):
                result = ctrl.run(task)

        assert result == "peer result"
        assert "failover:fleet:workstation" in ctrl.last_route
        claude_backend.execute.assert_not_called()

    def test_failover_all_fail_raises(self, tmp_path):
        """When local, fleet, and Claude all fail, raise the original error."""
        local_backend = MagicMock()
        local_backend.execute.side_effect = RuntimeError("LocalAI down")
        local_backend.last_usage = {}

        claude_backend = MagicMock()
        claude_backend.execute.side_effect = RuntimeError("Claude also down")
        claude_backend.last_usage = {}

        ctrl = Controller(
            backends={"local": local_backend, "claude": claude_backend},
            config={"cluster": {"auto_route": True, "config_file": "/nonexistent"}},
        )
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        with pytest.raises(RuntimeError, match="LocalAI down"):
            ctrl.run(task)
