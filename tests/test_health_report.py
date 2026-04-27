"""Tests for health reports and persistent metrics (Stage 4 Phases 5+6)."""

import time
from unittest.mock import patch

from aicp.core.prometheus import MetricsCollector

# ---------------------------------------------------------------------------
# Phase 5: Persistent Metrics
# ---------------------------------------------------------------------------


class TestMetricsSnapshot:
    def test_save_snapshot(self, tmp_path):
        path = str(tmp_path / "snapshot.json")
        collector = MetricsCollector(snapshot_path=path)
        collector.record_request("local", "qwen3-8b", 0.8, 100, 0.0, 500)
        assert collector.save_snapshot() is True
        assert (tmp_path / "snapshot.json").exists()

    def test_restore_snapshot(self, tmp_path):
        path = str(tmp_path / "snapshot.json")
        # First collector: record and save
        c1 = MetricsCollector(snapshot_path=path)
        c1.record_request("local", "qwen3-8b", 0.8, 100, 0.0, 500)
        c1.record_request("local", "qwen3-8b", 0.7, 200, 0.0, 600)
        c1.save_snapshot()

        # Second collector: should restore
        c2 = MetricsCollector(snapshot_path=path)
        assert c2._backends["local"].requests == 2
        assert c2._backends["local"].tokens_in == 0  # not tracked in record_request
        assert c2._models["qwen3-8b"] == 2

    def test_restore_missing_file(self, tmp_path):
        path = str(tmp_path / "does_not_exist.json")
        collector = MetricsCollector(snapshot_path=path)
        # Should start fresh, not crash
        assert collector._backends == {}

    def test_restore_corrupt_file(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("{invalid json")
        collector = MetricsCollector(snapshot_path=str(path))
        # Should start fresh, not crash
        assert collector._backends == {}

    def test_atomic_write(self, tmp_path):
        path = str(tmp_path / "snapshot.json")
        collector = MetricsCollector(snapshot_path=path)
        collector.record_request("local", model="test")
        collector.save_snapshot()
        # tmp file should not exist (renamed to final)
        assert not (tmp_path / "snapshot.tmp").exists()
        assert (tmp_path / "snapshot.json").exists()

    def test_no_snapshot_when_no_path(self):
        collector = MetricsCollector()  # no snapshot_path
        assert collector.save_snapshot() is False


# ---------------------------------------------------------------------------
# Phase 6: Health Reports
# ---------------------------------------------------------------------------


class TestHealthReport:
    def test_generate_empty(self):
        from aicp.core.health_report import generate_report
        with patch("aicp.core.health_report.aggregate", return_value={
            "total_tasks": 0, "by_backend": {}, "by_route": {},
        }):
            report = generate_report()
            assert report["status"] == "no_data"

    def test_generate_healthy(self):
        from aicp.core.health_report import generate_report
        with patch("aicp.core.health_report.aggregate", return_value={
            "total_tasks": 100,
            "today": 20,
            "this_week": 80,
            "error_rate": 2.0,
            "avg_duration": 1.5,
            "total_cost_usd": 0.0,
            "by_backend": {
                "local": {"tasks": 90, "error_rate": 1.0, "avg_duration": 1.0},
                "claude": {"tasks": 10, "error_rate": 0, "avg_duration": 5.0},
            },
            "by_route": {"local": 85, "intercepted": 5, "failover:claude": 10},
        }):
            report = generate_report()
            assert report["status"] == "healthy"
            assert report["summary"]["offload_pct"] == 90.0

    def test_detect_high_error_rate(self):
        from aicp.core.health_report import generate_report
        with patch("aicp.core.health_report.aggregate", return_value={
            "total_tasks": 100,
            "today": 10,
            "this_week": 50,
            "error_rate": 25.0,
            "avg_duration": 2.0,
            "total_cost_usd": 0.0,
            "by_backend": {"local": {"tasks": 100, "error_rate": 25.0}},
            "by_route": {},
        }):
            report = generate_report()
            assert report["status"] == "attention_needed"
            assert any(t["metric"] == "error_rate" for t in report["trends"])

    def test_recommendations_low_offload(self):
        from aicp.core.health_report import generate_report
        with patch("aicp.core.health_report.aggregate", return_value={
            "total_tasks": 100,
            "today": 10,
            "this_week": 50,
            "error_rate": 5.0,
            "avg_duration": 2.0,
            "total_cost_usd": 0.0,
            "by_backend": {
                "local": {"tasks": 60, "error_rate": 3.0},
                "claude": {"tasks": 40, "error_rate": 0},
            },
            "by_route": {},
        }):
            report = generate_report()
            assert any("offload" in r.lower() for r in report["recommendations"])

    def test_save_and_list(self, tmp_path, monkeypatch):
        from aicp.core.health_report import list_reports, save_report
        monkeypatch.setenv("AICP_HOME", str(tmp_path))
        report = {"timestamp": "2026-04-07", "status": "healthy", "summary": {}}
        path = save_report(report)
        assert path.exists()
        reports = list_reports()
        assert len(reports) == 1
        assert reports[0]["status"] == "healthy"

    def test_format_report(self):
        from aicp.core.health_report import format_report
        report = {
            "timestamp": "2026-04-07T12:00:00Z",
            "status": "healthy",
            "summary": {
                "total_tasks": 100, "today": 20, "this_week": 80,
                "offload_pct": 85.0, "local_tasks": 85, "claude_tasks": 15,
                "avg_duration_seconds": 1.5, "error_rate": 2.0,
                "total_cost_usd": 0.01,
            },
            "trends": [],
            "recommendations": ["System healthy. No action needed."],
        }
        text = format_report(report)
        assert "85.0% local" in text
        assert "100 total" in text

    def test_cleanup_old_reports(self, tmp_path, monkeypatch):
        from aicp.core.health_report import cleanup_old_reports, save_report
        monkeypatch.setenv("AICP_HOME", str(tmp_path))
        report = {"timestamp": "old", "status": "ok"}
        path = save_report(report)
        # Set mtime to 60 days ago
        import os
        old_time = time.time() - (60 * 86400)
        os.utime(path, (old_time, old_time))
        removed = cleanup_old_reports(retain_days=30)
        assert removed == 1
