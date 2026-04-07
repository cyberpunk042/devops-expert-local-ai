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


# ---------------------------------------------------------------------------
# Zero-token intercept
# ---------------------------------------------------------------------------


class TestIntercept:
    """Test zero-token operation interception."""

    def test_heartbeat_bypasses_backend(self, tmp_path):
        """Heartbeat prompt should be intercepted without calling backend.execute()."""
        backend = MagicMock()
        backend.execute.return_value = "should not be called"
        backend.last_usage = {}

        ctrl = Controller(backends={"local": backend}, config={})
        task = Task(prompt="heartbeat", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        result = ctrl.run(task)

        assert "HEARTBEAT_OK" in result
        assert ctrl.last_route == "intercepted"
        backend.execute.assert_not_called()

    def test_ping_bypasses_backend(self, tmp_path):
        """Ping should be intercepted."""
        backend = MagicMock()
        backend.last_usage = {}

        ctrl = Controller(backends={"local": backend}, config={})
        task = Task(prompt="ping", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        result = ctrl.run(task)

        assert "HEARTBEAT_OK" in result
        backend.execute.assert_not_called()

    def test_normal_prompt_not_intercepted(self, tmp_path):
        """Normal prompts should go through to backend.execute()."""
        backend = MagicMock()
        backend.execute.return_value = "normal response"
        backend.last_usage = {}

        ctrl = Controller(backends={"local": backend}, config={})
        task = Task(prompt="what is Python?", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        result = ctrl.run(task)

        assert result == "normal response"
        assert ctrl.last_route == "local"
        backend.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Profile-driven configuration
# ---------------------------------------------------------------------------


class TestProfileConfig:
    """Test that profile settings are respected by the controller."""

    def test_failover_chain_from_config(self, tmp_path):
        """Failover chain should follow config order, not hardcoded order."""
        local_backend = MagicMock()
        local_backend.execute.side_effect = RuntimeError("LocalAI down")
        local_backend.last_usage = {}

        claude_backend = MagicMock()
        claude_backend.execute.return_value = "claude result"
        claude_backend.last_usage = {}

        openrouter_backend = MagicMock()
        openrouter_backend.execute.return_value = "openrouter result"
        openrouter_backend.last_usage = {}

        # Config says failover order is local → claude (skip openrouter and fleet)
        ctrl = Controller(
            backends={"local": local_backend, "claude": claude_backend, "openrouter": openrouter_backend},
            config={
                "cluster": {"auto_route": True, "config_file": "/nonexistent"},
                "router": {"failover_chain": ["local", "claude"]},
            },
        )
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")
        result = ctrl.run(task)

        assert result == "claude result"
        assert ctrl.last_route == "failover:claude"
        # OpenRouter should NOT have been called (not in failover chain)
        openrouter_backend.execute.assert_not_called()

    def test_offline_profile_failover_chain(self, tmp_path):
        """Offline profile (local-only failover) should never try cloud backends."""
        local_backend = MagicMock()
        local_backend.execute.side_effect = RuntimeError("LocalAI down")
        local_backend.last_usage = {}

        claude_backend = MagicMock()
        claude_backend.last_usage = {}

        # Offline profile: failover only to fleet, no cloud
        ctrl = Controller(
            backends={"local": local_backend, "claude": claude_backend},
            config={
                "cluster": {"auto_route": True, "config_file": "/nonexistent"},
                "router": {"failover_chain": ["local", "fleet"]},
            },
        )
        task = Task(prompt="hello", mode=Mode.THINK, project_path=tmp_path, backend_name="local")

        # Should raise because no fleet peers and no cloud in chain
        with pytest.raises(RuntimeError, match="LocalAI down"):
            ctrl.run(task)
        claude_backend.execute.assert_not_called()

    def test_quality_threshold_from_profile(self):
        """Quality threshold should be read from quality.threshold config."""
        ctrl = Controller(
            backends={},
            config={"quality": {"threshold": 0.15}},
        )
        assert ctrl.quality_threshold == 0.15

    def test_quality_threshold_legacy_fallback(self):
        """Legacy flat quality_threshold key should still work."""
        ctrl = Controller(
            backends={},
            config={"quality_threshold": 0.30},
        )
        assert ctrl.quality_threshold == 0.30

    def test_quality_threshold_profile_overrides_legacy(self):
        """Profile quality.threshold should take precedence over legacy key."""
        ctrl = Controller(
            backends={},
            config={
                "quality": {"threshold": 0.10},
                "quality_threshold": 0.50,
            },
        )
        assert ctrl.quality_threshold == 0.10

    def test_default_failover_chain(self):
        """Without config, default failover chain is used."""
        ctrl = Controller(backends={}, config={})
        assert ctrl.failover_chain == ["local", "fleet", "openrouter", "claude"]

    def test_cache_from_config(self):
        """Cache settings should be read from config."""
        ctrl = Controller(
            backends={},
            config={"cache": {"enabled": False, "ttl_seconds": 600, "max_entries": 128}},
        )
        assert ctrl.cache_enabled is False
        assert ctrl._cache.ttl == 600
        assert ctrl._cache.max_entries == 128
