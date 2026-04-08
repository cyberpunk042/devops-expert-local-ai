# AICP Reliability — Architecture & Operational Runbook

## Overview

AICP Stage 4 provides six reliability components that work together to keep
fleet agents running 24/7. This document covers how they interact, when they
trigger, and what to do when things go wrong.

## Architecture

```
Fleet Agent Request
       │
       ▼
┌─ Agent Daemon (/health → Deep Health Check) ─┐
│  Warmup: pre-load models at startup           │
│                                                │
│  ┌─ Controller.run() ────────────────────────┐ │
│  │  1. Cache check (skip if cached)          │ │
│  │  2. Intercept (heartbeats → 0 tokens)     │ │
│  │  3. Fleet routing (peer if available)     │ │
│  │  4. Circuit Breaker gate ◄── OPEN? skip   │ │
│  │  5. Backend.execute()                     │ │
│  │  6. Quality escalation (score < threshold)│ │
│  │  7. Failover chain (configurable)         │ │
│  │  8. DLQ write (if all fail)               │ │
│  └───────────────────────────────────────────┘ │
│                                                │
│  Prometheus metrics → snapshot persistence     │
│  Health reports → trend detection + ntfy       │
└────────────────────────────────────────────────┘
```

## Components

### 1. Circuit Breaker (`aicp/core/circuit_breaker.py`)

**What it does:** Prevents thundering herd when a backend is down. Per-backend
state machine: CLOSED (normal) → OPEN (fail fast) → HALF_OPEN (probe).

**When it triggers:**
- CLOSED → OPEN: after `failure_threshold` consecutive failures (default: 3)
- OPEN → HALF_OPEN: after `recovery_timeout` seconds (default: 30)
- HALF_OPEN → CLOSED: on successful probe
- HALF_OPEN → OPEN: on failed probe

**Prometheus metrics:**
- `aicp_circuit_breaker_state{backend="local"}` (0=closed, 1=half_open, 2=open)
- `aicp_circuit_breaker_trips_total{backend="local"}` (counter)

**Alert:** `CircuitBreakerOpen` fires when any breaker has been OPEN for >5 minutes.

**What to do when it trips:**
1. Check LocalAI: `make local-status`
2. Check logs: `docker logs devops-expert-local-ai-localai-1 --tail 50`
3. If OOM: restart container (`docker compose restart localai`)
4. If model corrupt: re-download (`make model-qwen3`)
5. Breaker auto-recovers — HALF_OPEN probe every 30s

### 2. Startup Warmup (`aicp/agent/server.py`)

**What it does:** Pre-loads models into GPU VRAM before accepting fleet traffic.

**When it triggers:** Agent daemon startup, if `warmup.enabled: true` in profile.

**Health endpoint during warmup:**
```json
{"status": "warming", "model": "qwen3-8b", "backends": {}}
```

**What to do if warmup fails:**
- Agent still starts (warmup failure is non-fatal)
- First request will cold-start the model (10-80s)
- Check LocalAI availability: `curl http://localhost:8090/v1/models`

### 3. Deep Health Endpoint (`GET /health`)

**What it does:** Reports actual backend availability, not just "agent is running".

**Responses:**
```json
{"status": "ok",       "backends": {"local": true},  "warming": false}
{"status": "degraded", "backends": {"local": false}, "warming": false}
{"status": "warming",  "model": "qwen3-8b",          "backends": {}}
```

**What to do when degraded:**
- LocalAI is unreachable from the agent
- Fleet should route to other nodes
- Check: `make local-status`, `docker compose ps`

### 4. Dead-Letter Queue (`aicp/core/dlq.py`)

**What it does:** Persists failed tasks (after full failover chain exhausted)
to `~/.aicp/dlq/` as JSONL. Supports manual or automatic retry.

**When it triggers:** Every time `Controller.run()` raises an exception.

**Commands:**
```bash
# Check DLQ status
python3 -c "from aicp.core.dlq import status; print(status())"

# Retry pending entries
aicp --retry-dlq
```

**What to do when DLQ fills up:**
1. Check why tasks are failing: read the DLQ entries
2. Fix the underlying issue (LocalAI down, model missing, etc.)
3. Retry: entries auto-retry after `retry_delay_seconds`
4. After `max_retries`, entries stay as "exhausted" — manual investigation needed

### 5. Persistent Metrics (`aicp/core/prometheus.py`)

**What it does:** Saves MetricsCollector counters to `~/.aicp/metrics_snapshot.json`
every 60 seconds. Restores on restart.

**What survives restarts:** Request counts, error counts, token totals, cost,
cache hits, escalations, model usage, route counts, breaker trips.

**What doesn't survive:** In-flight timing, warm pool state (re-detected at startup).

### 6. Health Reports (`aicp/core/health_report.py`)

**What it does:** Generates structured reports comparing current stats to detect trends.

**Trend detection:**
- Error rate > 15%
- Average latency > 30s
- Per-backend error rate > 20%
- Escalation/failover rate > 10%

**Recommendations generated for:**
- Offload below 80% target
- High error rate
- Frequent escalations
- High Claude cost

**Commands:**
```bash
aicp --health-report          # Generate and display report
```

**Reports stored at:** `~/.aicp/reports/YYYY-MM-DD-HHMM.json`

## Failure Mode Matrix

| Failure | Detection | Response | Recovery |
|---------|-----------|----------|----------|
| LocalAI container crash | Docker healthcheck (30s) | `restart: unless-stopped` | Auto-restart, warmup re-runs |
| Model OOM | Backend 500 error | Circuit breaker opens | Fallback to CPU model (phi-2), then failover chain |
| Cold start timeout | Request timeout (120s) | Failover to fleet peer or cloud | Warmup prevents on next startup |
| All backends down | Full failover chain exhausted | DLQ captures task | Manual investigation + retry |
| Slow degradation | Health report trend detection | Recommendation generated | Tune profile thresholds |
| Thundering herd | Circuit breaker trips counter | Fail fast, instant failover | Recovery probe after 30s |
| Fleet peer down | Deep health check (degraded) | Route to other peers | Auto-recovery when peer restarts |

## Profile Recommendations

| Scenario | Profile | Key settings |
|----------|---------|-------------|
| Development | `default` | Warmup off, breaker threshold=3 |
| Fleet node (production) | `reliable` | Warmup on, breaker threshold=2, DLQ 5 retries, reports on |
| Fleet heartbeat duty | `fleet-light` | Warmup on (gemma4-e2b), minimal everything |
| Air-gapped / offline | `offline` | No cloud failover, force_cloud_modes=[] |
| Benchmarking | `benchmark` | Deterministic, no cache, no failover |

## Monitoring Checklist

For production fleet nodes, verify these are running:

```bash
# 1. LocalAI healthy
make local-status

# 2. Agent daemon running
curl http://localhost:9100/health

# 3. Prometheus scraping (if monitoring profile active)
curl http://localhost:9101/metrics | head -5

# 4. Profiles valid
make profile-validate

# 5. Offload status
make offload

# 6. Health report
aicp --health-report
```
