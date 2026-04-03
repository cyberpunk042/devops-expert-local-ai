"""Tests for AICP Prometheus metrics collector."""

from aicp.core.prometheus import MetricsCollector


def test_empty_metrics():
    c = MetricsCollector()
    output = c.format_prometheus()
    assert "aicp_uptime_seconds" in output
    assert "aicp_loaded_models 0" in output


def test_record_request():
    c = MetricsCollector()
    c.record_request("local", model="qwen3-8b", total_tokens=100, latency_ms=500)
    output = c.format_prometheus()
    assert 'aicp_requests_total{backend="local"} 1' in output
    assert 'aicp_model_requests_total{model="qwen3-8b"} 1' in output


def test_record_error():
    c = MetricsCollector()
    c.record_request("local", error=True)
    output = c.format_prometheus()
    assert 'aicp_errors_total{backend="local"} 1' in output


def test_cache_hit():
    c = MetricsCollector()
    c.record_cache_hit("local")
    output = c.format_prometheus()
    assert 'aicp_cache_hits_total{backend="local"} 1' in output


def test_escalation():
    c = MetricsCollector()
    c.record_escalation("local")
    output = c.format_prometheus()
    assert 'aicp_escalations_total{backend="local"} 1' in output


def test_model_swap_tracking():
    c = MetricsCollector()
    c.record_model_load("qwen3-8b")
    assert c.model_swaps == 1
    assert "qwen3-8b" in c.loaded_models

    # Loading same model again = no new swap
    c.record_model_load("qwen3-8b")
    assert c.model_swaps == 1

    # Loading different model = new swap
    c.record_model_load("qwen3-4b")
    assert c.model_swaps == 2

    output = c.format_prometheus()
    assert "aicp_loaded_models 2" in output
    assert "aicp_model_swaps_total 2" in output


def test_model_unload():
    c = MetricsCollector()
    c.record_model_load("qwen3-8b")
    c.record_model_unload("qwen3-8b")
    assert "qwen3-8b" not in c.loaded_models
    output = c.format_prometheus()
    assert "aicp_loaded_models 0" in output


def test_cost_tracking():
    c = MetricsCollector()
    c.record_request("claude", cost_usd=0.015)
    c.record_request("claude", cost_usd=0.025)
    output = c.format_prometheus()
    assert 'aicp_cost_usd_total{backend="claude"} 0.040000' in output


def test_route_tracking():
    c = MetricsCollector()
    c.record_request("local", route="local")
    c.record_request("local", route="cache")
    c.record_request("local", route="cache")
    output = c.format_prometheus()
    assert 'aicp_route_total{route="cache"} 2' in output


def test_quality_average():
    c = MetricsCollector()
    c.record_request("local", quality=0.8)
    c.record_request("local", quality=0.6)
    output = c.format_prometheus()
    assert 'aicp_quality_avg{backend="local"} 0.700' in output


def test_multiple_backends():
    c = MetricsCollector()
    c.record_request("local", total_tokens=100)
    c.record_request("openrouter", total_tokens=200)
    c.record_request("claude", total_tokens=300)
    output = c.format_prometheus()
    assert 'aicp_requests_total{backend="local"} 1' in output
    assert 'aicp_requests_total{backend="openrouter"} 1' in output
    assert 'aicp_requests_total{backend="claude"} 1' in output
