# Observability System

## Minimal
Prometheus metrics, Grafana dashboards, structured logging, GPU monitoring. Tracks requests, tokens, cost, latency, quality, cache hits, model swaps per backend.

## Condensed

### Purpose
Monitor AICP health, performance, and cost across all backends. Alert on anomalies. Track model warm pool for swap optimization.

### Components
- **prometheus.py** — MetricsCollector, /metrics endpoint on :9101
- **observability.py** — scrape LocalAI /metrics, parse Prometheus text
- **metrics.py** — aggregate() from task history JSON
- **db.py** — SQLite metrics store (queryable index over history)
- **config/prometheus.yaml** — Prometheus scrape config
- **config/alerts.yaml** — 7 alerting rules

### Metrics Exposed (aicp_* namespace)
- `aicp_requests_total{backend}` — request count per backend
- `aicp_errors_total{backend}` — error count
- `aicp_tokens_input_total{backend}` / `aicp_tokens_output_total{backend}`
- `aicp_cost_usd_total{backend}` — cumulative cost
- `aicp_latency_ms_avg{backend}` — average latency
- `aicp_quality_avg{backend}` — average response quality score
- `aicp_cache_hits_total{backend}` — cache hit count
- `aicp_escalations_total{backend}` — quality escalation count
- `aicp_loaded_models` — GPU warm pool size
- `aicp_model_swaps_total` — model swap events

### Alerting Rules
ModelStuck, HighLatency, HighErrorRate, FrequentModelSwaps, LowQualityResponses, CostSpike, LocalAIHighMemory

### Stack
```
make monitoring-up    # Prometheus :9090 + Grafana :3000
```

### Key Config
```yaml
# .env
GRAFANA_USER=admin
GRAFANA_PASSWORD=aicp
```
