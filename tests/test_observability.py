"""Tests for aicp.core.observability."""

import pytest

from aicp.core.observability import (
    _parse_gauge,
    _parse_api_call_histogram,
    _bytes_to_mb,
    scrape_prometheus,
    get_gpu_status,
)


# ── Prometheus parsing ───────────────────────────────────────────────────────

SAMPLE_METRICS = """\
# HELP go_goroutines Number of goroutines that currently exist.
# TYPE go_goroutines gauge
go_goroutines 42
# HELP go_memstats_alloc_bytes Number of bytes allocated in heap and currently in use.
# TYPE go_memstats_alloc_bytes gauge
go_memstats_alloc_bytes 1.234567e+07
# HELP api_call api calls
# TYPE api_call histogram
api_call_bucket{method="GET",otel_scope_name="github.com/mudler/LocalAI",otel_scope_schema_url="",otel_scope_version="",path="",le="0"} 0
api_call_bucket{method="GET",otel_scope_name="github.com/mudler/LocalAI",otel_scope_schema_url="",otel_scope_version="",path="",le="5"} 3
api_call_bucket{method="GET",otel_scope_name="github.com/mudler/LocalAI",otel_scope_schema_url="",otel_scope_version="",path="",le="+Inf"} 5
api_call_sum{method="GET",otel_scope_name="github.com/mudler/LocalAI",otel_scope_schema_url="",otel_scope_version="",path=""} 150.5
api_call_count{method="GET",otel_scope_name="github.com/mudler/LocalAI",otel_scope_schema_url="",otel_scope_version="",path=""} 5
api_call_sum{method="POST",otel_scope_name="github.com/mudler/LocalAI",otel_scope_schema_url="",otel_scope_version="",path=""} 8500.2
api_call_count{method="POST",otel_scope_name="github.com/mudler/LocalAI",otel_scope_schema_url="",otel_scope_version="",path=""} 10
"""


class TestParseGauge:
    def test_parse_goroutines(self):
        assert _parse_gauge(SAMPLE_METRICS, "go_goroutines") == 42.0

    def test_parse_alloc_bytes(self):
        val = _parse_gauge(SAMPLE_METRICS, "go_memstats_alloc_bytes")
        assert val == pytest.approx(1.234567e+07)

    def test_missing_metric(self):
        assert _parse_gauge(SAMPLE_METRICS, "nonexistent_metric") is None

    def test_empty_text(self):
        assert _parse_gauge("", "go_goroutines") is None


class TestParseApiCallHistogram:
    def test_parses_methods(self):
        result = _parse_api_call_histogram(SAMPLE_METRICS)
        assert "GET" in result
        assert "POST" in result

    def test_get_counts(self):
        result = _parse_api_call_histogram(SAMPLE_METRICS)
        assert result["GET"]["count"] == 5
        assert result["GET"]["total_ms"] == pytest.approx(150.5)
        assert result["GET"]["avg_ms"] == pytest.approx(30.1)

    def test_post_counts(self):
        result = _parse_api_call_histogram(SAMPLE_METRICS)
        assert result["POST"]["count"] == 10
        assert result["POST"]["avg_ms"] == pytest.approx(850.02, rel=0.01)

    def test_empty_metrics(self):
        result = _parse_api_call_histogram("")
        assert result == {}


class TestBytesToMb:
    def test_normal(self):
        assert _bytes_to_mb(1048576) == 1.0

    def test_none(self):
        assert _bytes_to_mb(None) is None

    def test_zero(self):
        assert _bytes_to_mb(0) == 0.0


class TestGpuStatus:
    def test_returns_dict(self):
        """GPU status should return a dict with 'available' key."""
        result = get_gpu_status()
        assert isinstance(result, dict)
        assert "available" in result


class TestScrapePrometheus:
    def test_unreachable_returns_unavailable(self):
        result = scrape_prometheus("http://localhost:99999", timeout=0.5)
        assert result["available"] is False
        assert "error" in result
