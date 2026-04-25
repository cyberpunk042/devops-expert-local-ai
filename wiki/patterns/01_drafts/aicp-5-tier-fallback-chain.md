---
title: "AICP 5-Tier Fallback Chain"
type: pattern
domain: backend-ai-platform-python
layer: 5
status: draft
confidence: medium
maturity: seed
promoted_from: "00_inbox"
promoted_at: "2026-04-22"
promotion_reason: "evolve-score 0.725 — top seed-tier pattern. cross_source_convergence=1.0, evidence_density=1.0, maturity_gap=1.0. Specializes the growing-tier per-backend-circuit-breaker pattern for E011-m004's 5-tier routing. Live-verified via baf7e09 snapshot wiring + 25 tests in test_circuit_breaker.py."
derived_from:
  - "per-backend-circuit-breaker-with-failover-chain"
  - "4-tier-router-with-profiles-over-hardcoded-routing"
instances:
  - page: "AICP controller failover (aicp/core/controller.py lines 170-171, 446-483)"
    context: "Build-time: `build_breakers(list(backends.keys()), config)` creates one breaker per registered backend with per-backend thresholds from `config.circuit_breaker.per_backend`. Run-time: `breaker.call(fn)` wraps each backend.execute; CircuitBreakerOpen short-circuits the outer try/except into the failover loop which walks `self.failover_chain` in order."
  - page: "AICP default.yaml (config/default.yaml `circuit_breaker:` + `router.failover_chain:`)"
    context: "Per-tier thresholds encode tier-specific failure semantics: local=2/10s (fast-recover), k2_6_openrouter=3/30s (network hiccups), openrouter=3/30s, claude=5/120s (last-resort). k2_6_local out of default chain since 2026-04-25 (sovereignty-only opt-in via --backend, breaker entry retained at 3/15s for opt-in flow)."
created: 2026-04-22
updated: 2026-04-22
sources:
  - id: aicp-circuit-breaker
    type: file
    file: aicp/core/circuit_breaker.py
  - id: aicp-controller
    type: file
    file: aicp/core/controller.py
  - id: aicp-default-config
    type: file
    file: config/default.yaml
  - id: e011-m004-spec
    type: wiki
    file: wiki/backlog/modules/e011-m004-circuit-breakers-and-fallback-chain.md
tags: [pattern, aicp, fallback, failover, reliability, circuit-breaker, 5-tier, k2-6, e011]
---

# AICP 5-Tier Fallback Chain

## Summary

A tier-specific specialization of the growing-tier [per-backend-circuit-breaker-with-failover-chain](../02_reviewed/per-backend-circuit-breaker-with-failover-chain.md) pattern for E011's 5-band tier_map routing (5 score bands → 4 distinct backends in the default failover_chain: local → k2_6_openrouter → openrouter → claude). Documents per-tier breaker thresholds, trigger conditions, HALF_OPEN recovery semantics, and an operator playbook keyed to each tier. The parent pattern explains the *mechanism*; this page explains the *tier-specific* failure semantics: why `local` opens at 2/10s (fast recover), `k2_6_openrouter` at 3/30s (network transients), `claude` at 5/120s (reluctant last-resort). **As of 2026-04-25**, `k2_6_local` is sovereignty-only (opt-in via `--backend k2_6_local`, NOT in default chain — empirical 0.045-0.10 tok/s on Tier 0 made it unfit for auto-routing).

## Why a specialization

The growing-tier pattern [per-backend-circuit-breaker-with-failover-chain](../02_reviewed/per-backend-circuit-breaker-with-failover-chain.md) describes the mechanism. This page captures the **tier-specific semantics** of the E011-m001 5-tier routing design: which tier is expected to carry load, what "OPEN" means for each, and what an operator looks for when a specific tier trips.

## The chain (in order)

```
┌──────────────┐   picked      ┌──────────────────────────┐   picked      ┌──────────────────────────┐
│   local      │ ───success──▶ │ k2_6_openrouter          │ ───success──▶ │ openrouter (Opus/GPT-5)  │
│ Qwen3-8B etc │ ──failure──┐  │ Moonshot Kimi K2.6       │ ──failure──┐  │   generic paid tier      │
└──────────────┘            │  │ via OpenRouter (pinned)  │            │  └──────────────────────────┘
                            ▼  └──────────────────────────┘            ▼                  │
                     breaker OPEN                              breaker OPEN               │
                      skip to next                             skip to next               │
                                                                                          ▼
                                                                            ┌───────────────────────┐
                                                                            │       claude          │
                                                                            │  Anthropic direct     │
                                                                            │  (last resort, gated) │
                                                                            └───────────────────────┘
```

**Sovereignty fallback (NOT auto-routed):** `k2_6_local` (llama.cpp serving Unsloth Q2 GGUF on localhost:8091) — opt in explicitly via `--backend k2_6_local`. See [docs/EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md](../../docs/EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md) for empirical numbers (0.045-0.10 tok/s on Tier 0) explaining why it's not in the chain.

**Optional `personal` profile** swaps band 1 (medium-complexity) to `ollama_cloud` (Ollama Cloud Pro subscription, shared inference pool — never for client/audit-required work). See [config/profiles/personal.yaml](../../config/profiles/personal.yaml).

Failover order from [aicp/core/router.py](../../aicp/core/router.py) + [config/default.yaml](../../config/default.yaml):
`[local, k2_6_openrouter, openrouter, claude]`

## Per-tier thresholds (rationale)

| Tier | threshold | recovery (s) | Why |
|------|-----------|--------------|-----|
| local | 2 | 10 | LocalAI recovers fast (container restart ~s); fail-fast + retry-fast maximizes local share |
| k2_6_local | 3 | 15 | Sovereignty opt-in path. llama.cpp cold mmap can take minutes — tolerate before opening. Not in default chain since 2026-04-25; entry retained for `--backend k2_6_local` flow |
| k2_6_openrouter | 3 | 30 | Network / OpenRouter transients are common and resolve quickly — tolerate more before giving up |
| openrouter | 3 | 30 | Same semantics as k2_6_openrouter — OpenRouter-side stability is shared |
| claude | 5 | 120 | Last-resort tier; opening it means the whole chain is broken. Open reluctantly, recover slowly to avoid thundering the Anthropic API |

## Trigger conditions

A tier is skipped when ANY of:
1. **Breaker OPEN** — consecutive failures ≥ threshold in recent window
2. **`is_available() == False`** — initial probe at build-time or runtime health check (local TCP probe, HTTP HEAD)
3. **Not in `backends` dict** — tier not registered (e.g., `k2_6_local` when `enabled: false` (default since 2026-04-25); `k2_6_openrouter` skipped when `OPENROUTER_API_KEY` absent; `ollama_cloud` skipped when `OLLAMA_API_KEY` absent or `enabled: false`)
4. **Same name as originating backend** — `failover_chain` loop at [aicp/core/controller.py:457](../../aicp/core/controller.py#L457) skips the one that just failed

## Recovery semantics (HALF_OPEN probe)

After `recovery_timeout` elapsed in OPEN state, the breaker moves to HALF_OPEN and allows exactly `half_open_max` (default 1) probe requests:
- **Probe succeeds** → breaker → CLOSED, failure_count reset
- **Probe fails** → breaker → OPEN immediately, `open_since` reset to now

Implication: if a backend is genuinely flapping (succeeds intermittently), it will oscillate between OPEN and HALF_OPEN, which is the desired behavior — the chain routes around it on OPEN stretches without ping-ponging every request through a dying backend.

## Operator playbook

**k2_6_openrouter breaker opens frequently (>3 times/week)**
- Check OpenRouter dashboard for outage / degraded model signal
- `grep breaker.*k2_6_openrouter $AICP_LOG_FILE | tail -20` — check error pattern (timeout? 500? 429 rate limit?)
- If 429: raise `backends.k2_6_openrouter.timeout` or lower request rate
- If network: verify egress to `openrouter.ai`
- Possible response: temporarily raise `circuit_breaker.per_backend.k2_6_openrouter.failure_threshold` to smooth over transients

**k2_6_local breaker opens during a sovereignty-mode session**
- `--backend k2_6_local` requires `scripts/llama-serve.sh` running on `localhost:8091` (60–90 min cold reload on fresh WSL boot)
- 3 consecutive timeouts within `timeout=1800s` is signal that the server isn't actually serving — check `pgrep -x llama-server` and `curl -s localhost:8091/v1/models`
- During normal default-routed operation this breaker should never open: `enabled: false` keeps `k2_6_local` out of the registered backends entirely
- The `--profile personal` chain also doesn't include it; it's strictly opt-in via the `--backend` flag

**claude breaker opens (threshold=5 means 5 failures in a row)**
- This is a red alert — the entire chain before it has failed AND Anthropic itself is unreachable
- Check: Anthropic status page, `ANTHROPIC_API_KEY` validity, outbound network
- Failover-exhausted tasks land in the [DLQ](../02_reviewed/per-day-jsonl-dlq-with-retry-budget.md) for later retry

**local breaker opens repeatedly**
- Inspect Docker: `docker ps --filter name=localai` + `docker logs localai --tail 100`
- Common causes: OOM (model swap into constrained VRAM), GPU driver reset, container crash
- Per the [single-active-backend-with-LRU-eviction](../02_reviewed/single-active-backend-with-lru-eviction.md) pattern, large-model loads can evict smaller models — a swap-storm looks like local flapping

## What to tune (per review ritual — E011-m005)

- `router.complexity_thresholds` — shift tier bands left/right to change which tier carries load
- `circuit_breaker.per_backend.<name>.failure_threshold` — trade false-opens for slow-recovery
- `circuit_breaker.per_backend.<name>.recovery_timeout` — trade quick probe vs backing off a flaky tier
- `backends.<name>.timeout` — upstream request timeout; affects how fast failures are recorded

## Non-goals

- Does NOT implement weighted / probabilistic routing — strict priority order per `failover_chain`
- Does NOT retry the same tier on transient failure — that's the individual backend's responsibility (e.g., httpx retry in `aicp/backends/openrouter.py`)
- Does NOT preserve request-level idempotency across failover — a task that failed halfway through on k2_6_openrouter may produce a different result on openrouter

## Relationships

- SPECIALIZES: [per-backend-circuit-breaker-with-failover-chain](../02_reviewed/per-backend-circuit-breaker-with-failover-chain.md)
- DERIVES_FROM: [4-tier-router-with-profiles-over-hardcoded-routing](../../decisions/02_reviewed/4-tier-router-with-profiles-over-hardcoded-routing.md)
- REFERENCED_BY: [aicp-routing-review-ritual](aicp-routing-review-ritual.md)
- IMPLEMENTED_BY: aicp/core/circuit_breaker.py + aicp/core/controller.py (failover loop lines 446-483)
