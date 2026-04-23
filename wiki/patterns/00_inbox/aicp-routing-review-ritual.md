---
title: "AICP Routing Review Ritual (weekly)"
type: pattern
domain: backend-ai-platform-python
layer: 5
status: draft
confidence: medium
maturity: seed
derived_from:
  - "aicp-5-tier-fallback-chain"
  - "per-backend-circuit-breaker-with-failover-chain"
instances:
  - page: "AICP CLI (aicp/cli/main.py `_run_routing_report`)"
    context: "Implements the ritual's primary tool: `aicp --routing-report 7d` prints per-backend table (requests, share %, tokens, cost, latency, errors). `--json` emits same data for automation."
  - page: "AICP metrics (aicp/core/metrics.py `aggregate_window`)"
    context: "Time-windowed aggregation that powers the report. Parses 7d/24h/30m strings, filters history records by timestamp, dynamically discovers backend names from records."
created: 2026-04-22
updated: 2026-04-22
sources:
  - id: aicp-metrics
    type: file
    file: aicp/core/metrics.py
  - id: aicp-cli-main
    type: file
    file: aicp/cli/main.py
  - id: e011-m005-spec
    type: wiki
    file: wiki/backlog/modules/e011-m005-routing-metric-and-review-ritual.md
tags: [pattern, aicp, routing, ritual, weekly, review, observability, e011]
---

# AICP Routing Review Ritual

## Purpose

The 5-tier routing design (E011-m001) only pays off if the operator catches **tier drift** — when tasks start landing in the wrong tier due to scorer miscalibration, budget overruns, or reliability events. This ritual codifies the weekly check that keeps routing calibrated without requiring a full incident to flag problems.

## Cadence

**Every Monday**, at the start of the operator's weekly planning block. Duration: 10-15 minutes.

For solo operation: a self-review; the written ritual ensures it actually happens rather than drifting into "I'll check later."

## Inputs

Run these in order:

```bash
# Primary — routing report over the last 7 days
aicp --routing-report 7d

# Same data for archival / diff vs prior week
aicp --routing-report 7d --json > /tmp/routing-$(date +%Y%m%d).json

# Circuit breaker opens (persisted across restarts via prometheus snapshot)
curl -s http://localhost:9101/metrics | grep '^aicp_circuit_breaker_trips_total'

# OpenRouter cost dashboard — external, visual confirmation
# https://openrouter.ai/activity
```

## Review checklist

1. **Does `k2_6_openrouter` carry the expected share?**
   - Target: 40-70% of non-local traffic (agentic + mid-complexity coding)
   - If < 40%: scorer is under-routing to K2.6; consider widening band via `router.complexity_thresholds`
   - If > 70%: may be under-utilizing `local` for simpler tasks

2. **Is any tier capturing < 5% that was expected to carry real load?**
   - Typical: `openrouter` (classic tier, post-K2.6) should stay low but non-zero — it's the backstop when K2.6 OPENs
   - `claude` should be near zero (< 2%) — appearing more means the scorer is classifying too many tasks as "top band"

3. **Did any circuit breaker open more than 3 times?**
   - Check `aicp_circuit_breaker_trips_total{backend="..."}` deltas vs last week
   - `k2_6_openrouter` > 5 opens/week → OpenRouter stability concern; consider raising threshold or investigating
   - `local` > 10 opens/week → LocalAI container health; inspect Docker / GPU state
   - `claude` > 0 → chain was exhausted — cross-reference with `grep error $AICP_LOG_FILE`

4. **Is the total cost inside the weekly budget?**
   - From the report's `total_cost_usd` field
   - Profile budgets: `quality.yaml` max_cost_usd: 5.0/session; sum across sessions
   - OpenRouter dashboard visual cross-check

5. **Tasks routed to `claude` that should have been K2.6?**
   - Any `claude` rows — open the underlying task via `aicp --history <N>` and inspect the prompt
   - Common cause: force_cloud_modes picking claude when k2_6_openrouter would have sufficed (check failover_chain ordering)

## Red-flag thresholds

| Signal | Threshold | Action |
|--------|-----------|--------|
| `claude` share | > 5% of total | Tune complexity scorer — why so high? Check specific prompts. |
| `k2_6_openrouter` share | < 40% of non-local | Widen K2.6 bands — `router.complexity_thresholds` shift left |
| `k2_6_openrouter` breaker opens | > 10 / week | Network stability; check OpenRouter status page |
| `local` breaker opens | > 10 / week | LocalAI container health, GPU memory pressure |
| Weekly cost | > 2× median of last 4 weeks | Investigate which backend + which prompts drove it |
| `avg_latency(k2_6_local)` | > 60s (when enabled) | KTransformers tuning — see E008-m003 |

## What to tune

- **`router.complexity_thresholds`** — widen/narrow K2.6 bands (biggest lever for cost/quality balance)
- **`circuit_breaker.per_backend.<name>`** — trade false-opens vs slow-recovery per tier
- **`backends.<name>.timeout`** — upstream request timeout, affects how fast failures are recorded
- **Profile selection** — switch `AICP_PROFILE=quality` vs `=fast` vs `=reliable` if one profile is systematically misrouting

## Escalation

Three consecutive weeks of any of:
- Cost drift > 20% above trailing-4-week median
- Quality degradation (subjective — operator notices degraded responses)
- > 20 breaker opens total across all backends

→ Open a follow-up task / module to address root cause. Don't repeatedly hand-tune — find the structural fix.

## Artifact trail

Each review produces a log entry in `wiki/log/YYYY-MM-DD-routing-review.md` with:
- Date, operator, prior-week counters
- One-line observation per checklist item (or "nominal")
- Any tuning knob changes made (commit hash)
- Any red flags raised and their disposition

The first review log after M005 ships is the template for all subsequent ones.

## Non-goals

- This ritual is NOT a replacement for real-time alerting — it's the periodic sanity check. Urgent alerts come from `config/alerts.yaml` (Prometheus rules), not the review.
- This ritual does NOT re-benchmark models — latency/quality regressions caught here escalate into dedicated benchmark tasks (see `quality-performance` skill).
- Solo operator scope — multi-operator ritual coordination is out of scope until fleet expands.
