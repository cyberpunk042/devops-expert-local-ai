"""AICP Prometheus metrics exporter.

Exposes AICP-level metrics in Prometheus text format via a lightweight
HTTP server. This complements LocalAI's built-in /metrics endpoint
with higher-level routing, quality, cost, and cache metrics.

Usage:
    from aicp.core.prometheus import MetricsCollector, start_metrics_server

    collector = MetricsCollector()
    collector.record_request("local", "qwen3-8b", 0.8, 247, 0.0)
    start_metrics_server(collector, port=9101)

Scrape target: http://localhost:9101/metrics
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional


@dataclass
class _BackendStats:
    """Aggregated stats for one backend."""
    requests: int = 0
    errors: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_sum: float = 0.0
    cache_hits: int = 0
    escalations: int = 0
    quality_sum: float = 0.0


class MetricsCollector:
    """Thread-safe metrics collector for AICP operations.

    Supports optional snapshot persistence: saves counters to a JSON file
    periodically and restores on startup (Stage 4 Phase 5).
    """

    def __init__(self, snapshot_path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._backends: Dict[str, _BackendStats] = defaultdict(_BackendStats)
        self._models: Dict[str, int] = defaultdict(int)  # model → request count
        self._routes: Dict[str, int] = defaultdict(int)   # route → count
        self._start_time = time.time()
        # Warm pool tracking (E-M52)
        self._loaded_models: Dict[str, float] = {}  # model → last_used timestamp
        self._model_swaps: int = 0
        # Circuit breaker tracking (Stage 4)
        self._breaker_states: Dict[str, str] = {}   # backend → state
        self._breaker_trips: Dict[str, int] = defaultdict(int)  # backend → trip count
        # Snapshot persistence (Stage 4 Phase 5)
        self._snapshot_path = snapshot_path
        if snapshot_path:
            self._restore_snapshot()

    def record_request(
        self,
        backend: str,
        model: str = "",
        quality: float = 0.5,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
        latency_ms: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        route: str = "",
        error: bool = False,
    ) -> None:
        with self._lock:
            s = self._backends[backend]
            s.requests += 1
            if error:
                s.errors += 1
            s.tokens_in += prompt_tokens
            s.tokens_out += completion_tokens
            s.cost_usd += cost_usd
            s.latency_sum += latency_ms
            s.quality_sum += quality
            if model:
                self._models[model] += 1
            if route:
                self._routes[route] += 1

    def record_cache_hit(self, backend: str) -> None:
        with self._lock:
            self._backends[backend].cache_hits += 1

    def record_escalation(self, from_backend: str) -> None:
        with self._lock:
            self._backends[from_backend].escalations += 1

    def record_model_load(self, model: str) -> None:
        """Track a model being loaded into GPU (warm pool tracking)."""
        with self._lock:
            if model not in self._loaded_models:
                self._model_swaps += 1
            self._loaded_models[model] = time.time()

    def record_model_unload(self, model: str) -> None:
        with self._lock:
            self._loaded_models.pop(model, None)

    def record_breaker_state(self, backend: str, state: str) -> None:
        """Track circuit breaker state change."""
        with self._lock:
            self._breaker_states[backend] = state

    def record_breaker_trip(self, backend: str) -> None:
        """Track circuit breaker trip (CLOSED → OPEN)."""
        with self._lock:
            self._breaker_trips[backend] += 1

    @property
    def loaded_models(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._loaded_models)

    @property
    def model_swaps(self) -> int:
        with self._lock:
            return self._model_swaps

    def save_snapshot(self) -> bool:
        """Save current counters to disk. Returns True on success."""
        if not self._snapshot_path:
            return False
        try:
            import json
            from pathlib import Path
            data = {}
            with self._lock:
                for name, s in self._backends.items():
                    data[f"backend:{name}"] = {
                        "requests": s.requests, "errors": s.errors,
                        "tokens_in": s.tokens_in, "tokens_out": s.tokens_out,
                        "cost_usd": s.cost_usd, "latency_sum": s.latency_sum,
                        "cache_hits": s.cache_hits, "escalations": s.escalations,
                        "quality_sum": s.quality_sum,
                    }
                data["models"] = dict(self._models)
                data["routes"] = dict(self._routes)
                data["model_swaps"] = self._model_swaps
                data["breaker_trips"] = dict(self._breaker_trips)
            # Atomic write: tmp + rename
            path = Path(self._snapshot_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(data, f)
            tmp.rename(path)
            return True
        except Exception:
            return False

    def _restore_snapshot(self) -> bool:
        """Restore counters from disk. Returns True if restored."""
        if not self._snapshot_path:
            return False
        try:
            import json
            from pathlib import Path
            path = Path(self._snapshot_path)
            if not path.exists():
                return False
            with open(path) as f:
                data = json.load(f)
            with self._lock:
                for key, vals in data.items():
                    if key.startswith("backend:"):
                        name = key[len("backend:"):]
                        s = self._backends[name]
                        s.requests = vals.get("requests", 0)
                        s.errors = vals.get("errors", 0)
                        s.tokens_in = vals.get("tokens_in", 0)
                        s.tokens_out = vals.get("tokens_out", 0)
                        s.cost_usd = vals.get("cost_usd", 0.0)
                        s.latency_sum = vals.get("latency_sum", 0.0)
                        s.cache_hits = vals.get("cache_hits", 0)
                        s.escalations = vals.get("escalations", 0)
                        s.quality_sum = vals.get("quality_sum", 0.0)
                if "models" in data:
                    self._models.update(data["models"])
                if "routes" in data:
                    self._routes.update(data["routes"])
                self._model_swaps = data.get("model_swaps", 0)
                if "breaker_trips" in data:
                    self._breaker_trips.update(data["breaker_trips"])
            return True
        except Exception:
            return False

    def format_prometheus(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        lines = []
        now = time.time()
        uptime = now - self._start_time

        lines.append("# HELP aicp_uptime_seconds Time since AICP metrics collector started.")
        lines.append("# TYPE aicp_uptime_seconds gauge")
        lines.append(f"aicp_uptime_seconds {uptime:.1f}")

        with self._lock:
            # Per-backend metrics
            lines.append("")
            lines.append("# HELP aicp_requests_total Total requests per backend.")
            lines.append("# TYPE aicp_requests_total counter")
            for b, s in self._backends.items():
                lines.append(f'aicp_requests_total{{backend="{b}"}} {s.requests}')

            lines.append("")
            lines.append("# HELP aicp_errors_total Total errors per backend.")
            lines.append("# TYPE aicp_errors_total counter")
            for b, s in self._backends.items():
                lines.append(f'aicp_errors_total{{backend="{b}"}} {s.errors}')

            lines.append("")
            lines.append("# HELP aicp_tokens_input_total Total input tokens per backend.")
            lines.append("# TYPE aicp_tokens_input_total counter")
            for b, s in self._backends.items():
                lines.append(f'aicp_tokens_input_total{{backend="{b}"}} {s.tokens_in}')

            lines.append("")
            lines.append("# HELP aicp_tokens_output_total Total output tokens per backend.")
            lines.append("# TYPE aicp_tokens_output_total counter")
            for b, s in self._backends.items():
                lines.append(f'aicp_tokens_output_total{{backend="{b}"}} {s.tokens_out}')

            lines.append("")
            lines.append("# HELP aicp_cost_usd_total Total cost in USD per backend.")
            lines.append("# TYPE aicp_cost_usd_total counter")
            for b, s in self._backends.items():
                lines.append(f'aicp_cost_usd_total{{backend="{b}"}} {s.cost_usd:.6f}')

            lines.append("")
            lines.append("# HELP aicp_latency_ms_avg Average latency in ms per backend.")
            lines.append("# TYPE aicp_latency_ms_avg gauge")
            for b, s in self._backends.items():
                avg = s.latency_sum / s.requests if s.requests else 0
                lines.append(f'aicp_latency_ms_avg{{backend="{b}"}} {avg:.1f}')

            lines.append("")
            lines.append("# HELP aicp_quality_avg Average response quality per backend.")
            lines.append("# TYPE aicp_quality_avg gauge")
            for b, s in self._backends.items():
                avg = s.quality_sum / s.requests if s.requests else 0
                lines.append(f'aicp_quality_avg{{backend="{b}"}} {avg:.3f}')

            lines.append("")
            lines.append("# HELP aicp_cache_hits_total Cache hits per backend.")
            lines.append("# TYPE aicp_cache_hits_total counter")
            for b, s in self._backends.items():
                lines.append(f'aicp_cache_hits_total{{backend="{b}"}} {s.cache_hits}')

            lines.append("")
            lines.append("# HELP aicp_escalations_total Quality escalations from backend.")
            lines.append("# TYPE aicp_escalations_total counter")
            for b, s in self._backends.items():
                lines.append(f'aicp_escalations_total{{backend="{b}"}} {s.escalations}')

            # Model usage
            lines.append("")
            lines.append("# HELP aicp_model_requests_total Requests per model.")
            lines.append("# TYPE aicp_model_requests_total counter")
            for m, c in self._models.items():
                lines.append(f'aicp_model_requests_total{{model="{m}"}} {c}')

            # Route tracking
            lines.append("")
            lines.append("# HELP aicp_route_total Requests per route path.")
            lines.append("# TYPE aicp_route_total counter")
            for r, c in self._routes.items():
                lines.append(f'aicp_route_total{{route="{r}"}} {c}')

            # Warm pool (E-M52)
            lines.append("")
            lines.append("# HELP aicp_loaded_models Number of models currently in GPU memory.")
            lines.append("# TYPE aicp_loaded_models gauge")
            lines.append(f"aicp_loaded_models {len(self._loaded_models)}")

            lines.append("")
            lines.append("# HELP aicp_model_swaps_total Total model swap events.")
            lines.append("# TYPE aicp_model_swaps_total counter")
            lines.append(f"aicp_model_swaps_total {self._model_swaps}")

            # Circuit breaker (Stage 4)
            state_map = {"closed": 0, "half_open": 1, "open": 2}
            if self._breaker_states:
                lines.append("")
                lines.append("# HELP aicp_circuit_breaker_state Circuit breaker state (0=closed, 1=half_open, 2=open).")
                lines.append("# TYPE aicp_circuit_breaker_state gauge")
                for b, s in self._breaker_states.items():
                    lines.append(f'aicp_circuit_breaker_state{{backend="{b}"}} {state_map.get(s, 0)}')

            if self._breaker_trips:
                lines.append("")
                lines.append("# HELP aicp_circuit_breaker_trips_total Circuit breaker trip count per backend.")
                lines.append("# TYPE aicp_circuit_breaker_trips_total counter")
                for b, c in self._breaker_trips.items():
                    lines.append(f'aicp_circuit_breaker_trips_total{{backend="{b}"}} {c}')

        lines.append("")
        return "\n".join(lines) + "\n"


class _MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves Prometheus metrics."""

    collector: Optional[MetricsCollector] = None

    def do_GET(self) -> None:
        if self.path == "/metrics":
            body = self.collector.format_prometheus().encode() if self.collector else b""
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args) -> None:
        pass  # suppress HTTP access logs


def start_metrics_server(
    collector: MetricsCollector,
    port: int = 9101,
    host: str = "0.0.0.0",
) -> threading.Thread:
    """Start a background HTTP server serving /metrics.

    Returns the server thread. Server runs as a daemon thread and will
    stop when the main process exits.
    """
    _MetricsHandler.collector = collector
    server = HTTPServer((host, port), _MetricsHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread
