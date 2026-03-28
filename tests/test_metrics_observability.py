"""Tests for Prometheus metrics & observability integration (M78)."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from aicp.backends.localai import LocalAIBackend
from aicp.core.modes import Mode


def _make_backend(**kwargs) -> LocalAIBackend:
    defaults = dict(
        base_url="http://localhost:8090",
        model="hermes",
        max_tokens=256,
        api_key="",
    )
    defaults.update(kwargs)
    return LocalAIBackend(**defaults)


def _make_console():
    buf = StringIO()
    return Console(file=buf, force_terminal=False, no_color=True), buf


# ── Backend metrics() method ────────────────────────────────────────────────


class TestBackendMetrics:
    def test_returns_system_status(self):
        backend = _make_backend()
        mock_status = {
            "localai": {
                "available": True,
                "url": "http://localhost:8090",
                "goroutines": 42,
                "memory_alloc_mb": 128.5,
                "memory_sys_mb": 512.0,
                "models": ["hermes"],
                "loaded_models": ["hermes"],
                "backends": ["llama-cpp"],
                "api_calls": {"POST": {"count": 10, "total_ms": 5000, "avg_ms": 500}},
            },
            "gpu": {
                "available": True,
                "name": "RTX 3060 Ti",
                "memory_used_mb": 4000,
                "memory_total_mb": 8192,
                "memory_used_pct": 48.8,
                "utilization_pct": 35,
                "temperature_c": 55,
            },
        }

        with patch("aicp.core.observability.get_system_status", return_value=mock_status):
            result = backend.metrics()

        assert result["localai"]["available"] is True
        assert result["localai"]["goroutines"] == 42
        assert result["gpu"]["name"] == "RTX 3060 Ti"

    def test_uses_backend_base_url(self):
        backend = _make_backend(base_url="http://custom:9090")
        captured_url = {}

        def mock_get_status(url):
            captured_url["url"] = url
            return {"localai": {"available": True}, "gpu": {}}

        with patch("aicp.core.observability.get_system_status", side_effect=mock_get_status):
            backend.metrics()

        assert captured_url["url"] == "http://custom:9090"


# ── CLI --metrics ───────────────────────────────────────────────────────────


class TestCLIMetrics:
    def test_arg_exists(self):
        from aicp.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["--metrics"])
        assert args.metrics is True

    def test_arg_default_false(self):
        from aicp.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args([])
        assert getattr(args, "metrics", False) is False

    def test_metrics_output(self):
        test_console, buf = _make_console()
        mock_status = {
            "localai": {
                "available": True,
                "url": "http://localhost:8090",
                "goroutines": 42,
                "memory_alloc_mb": 128.5,
                "memory_sys_mb": 512.0,
                "models": ["hermes"],
                "loaded_models": ["hermes"],
                "backends": ["llama-cpp"],
                "api_calls": {"POST": {"count": 10, "total_ms": 5000, "avg_ms": 500}},
            },
            "gpu": {
                "available": True,
                "name": "RTX 3060 Ti",
                "memory_used_mb": 4000,
                "memory_total_mb": 8192,
                "memory_used_pct": 48.8,
                "utilization_pct": 35,
                "temperature_c": 55,
            },
        }

        with patch("aicp.cli.main.console", test_console):
            with patch("aicp.core.observability.get_system_status", return_value=mock_status):
                from aicp.cli.main import _run_metrics
                rc = _run_metrics()

        output = buf.getvalue()
        assert rc == 0
        assert "Live Metrics" in output
        assert "42" in output  # goroutines
        assert "128.5" in output  # memory
        assert "hermes" in output  # model
        assert "RTX 3060 Ti" in output  # GPU

    def test_metrics_unreachable(self):
        test_console, buf = _make_console()
        mock_status = {
            "localai": {"available": False},
            "gpu": {"available": False},
        }

        with patch("aicp.cli.main.console", test_console):
            with patch("aicp.core.observability.get_system_status", return_value=mock_status):
                from aicp.cli.main import _run_metrics
                rc = _run_metrics()

        assert rc == 1
        assert "not reachable" in buf.getvalue()


# ── Interactive /metrics ────────────────────────────────────────────────────


class TestInteractiveMetrics:
    def test_metrics_command(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.metrics.return_value = {
            "localai": {
                "available": True,
                "goroutines": 30,
                "memory_alloc_mb": 100.0,
                "memory_sys_mb": 400.0,
                "models": ["hermes"],
                "api_calls": {"POST": {"count": 5, "total_ms": 1000, "avg_ms": 200}},
            },
            "gpu": {
                "available": True,
                "name": "RTX 3060 Ti",
                "memory_used_mb": 3000,
                "memory_total_mb": 8192,
                "utilization_pct": 25,
                "temperature_c": 50,
            },
        }

        _handle_slash("/metrics", [], backend, {}, Mode.THINK, Path("/tmp"))

        output = capsys.readouterr().out
        assert "30" in output  # goroutines
        assert "100.0" in output  # memory
        assert "hermes" in output
        assert "RTX 3060 Ti" in output

    def test_metrics_no_backend(self, capsys):
        from aicp.cli.interactive import _handle_slash

        _handle_slash("/metrics", [], None, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "require" in err.lower() or "backend" in err.lower()

    def test_metrics_unavailable(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.metrics.return_value = {
            "localai": {"available": False},
            "gpu": {"available": False},
        }

        _handle_slash("/metrics", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "not reachable" in err.lower()

    def test_metrics_error(self, capsys):
        from aicp.cli.interactive import _handle_slash

        backend = MagicMock()
        backend.metrics.side_effect = RuntimeError("connection refused")

        _handle_slash("/metrics", [], backend, {}, Mode.THINK, Path("/tmp"))
        err = capsys.readouterr().err
        assert "error" in err.lower()


# ── MCP tool ────────────────────────────────────────────────────────────────


class TestMcpMetrics:
    def test_returns_json(self):
        from aicp.mcp.server import aicp_metrics

        mock_backend = MagicMock()
        mock_backend.metrics.return_value = {
            "localai": {"available": True, "goroutines": 20},
            "gpu": {"available": False},
        }

        with patch("aicp.mcp.server._get_backend", return_value=mock_backend):
            result = aicp_metrics()

        parsed = json.loads(result)
        assert parsed["localai"]["goroutines"] == 20
