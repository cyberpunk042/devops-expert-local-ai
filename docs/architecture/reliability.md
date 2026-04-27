# Reliability (Stage 4)

> Extracted from CLAUDE.md `## Reliability (Stage 4)` 2026-04-25. CLAUDE.md keeps a one-line pointer and routes here for the component table. (Note: there is also a related `docs/reliability.md` from prior milestone work — that file covers reliability *philosophy*; this file is the component map.)

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Circuit breaker | [aicp/core/circuit_breaker.py](../../aicp/core/circuit_breaker.py) | Per-backend state machine (CLOSED → OPEN → HALF_OPEN); failover in milliseconds |
| Startup warmup | [aicp/agent/server.py](../../aicp/agent/server.py) | Pre-loads models from `warmup.models` before accepting traffic |
| Deep health | `GET /health` | Returns `{status: ok|degraded|warming, backends: {...}}` |
| Dead-letter queue | [aicp/core/dlq.py](../../aicp/core/dlq.py) | Failed tasks → `~/.aicp/dlq/` JSONL; retry via `aicp --retry-dlq` |
| Persistent metrics | [aicp/core/prometheus.py](../../aicp/core/prometheus.py) | JSON snapshots; counters survive restarts |
| Health reports | [aicp/core/health_report.py](../../aicp/core/health_report.py) | Trend deltas; `aicp --health-report`; optional ntfy |
| Reliability profile | `make profile-use PROFILE=reliable` | Aggressive breaker (threshold=2), auto-warmup, DLQ retries=5, reports every 4h |

## Stage 4 status

- ✅ Circuit breakers + per-backend tuning (E011-m004 complete; pattern at `wiki/patterns/01_drafts/aicp-5-tier-fallback-chain.md`)
- ✅ DLQ + retry budget (pattern at `wiki/patterns/02_reviewed/per-day-jsonl-dlq-with-retry-budget.md`)
- ✅ Reliability profile shipped
- 🔲 Cluster peering (Alpha ↔ Bravo) — pending
- 🔲 Health reports cron / ntfy integration — partial
