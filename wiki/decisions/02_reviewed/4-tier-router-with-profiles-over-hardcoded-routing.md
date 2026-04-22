---
title: "Decision: 4-tier router with configurable profiles over hardcoded routing"
type: decision
domain: backend-ai-platform-python
layer: 6
status: synthesized
confidence: high
maturity: growing
promoted_from: "01_drafts"
promoted_at: "2026-04-22"
promotion_reason: "Evolve score 0.479 — lower than patterns because decisions are AICP-specific moments (lower cross-source convergence by nature). Substantively meets growing-tier bar: 4 alternatives with explicit rejection reasons, 6 evidence-backed rationale items, easy reversibility, full dependencies analysis (reverse + extend paths). 9 profiles in production use, 49 profile tests. Foundational architectural decision — every AICP routing behavior derives from this."
derived_from:
  - "model-local-ai"
  - "gateway-centric-routing"
reversibility: easy
created: 2026-04-18
updated: 2026-04-18
sources:
  - id: aicp-router
    type: file
    file: aicp/core/router.py
    description: 4-tier router implementation with score-based dispatch
  - id: aicp-profiles
    type: file
    file: config/profiles/
    description: 9 profile YAML files (default, fast, offline, thorough, code-review, fleet-light, reliable, dual-gpu, benchmark)
  - id: aicp-circuit-breaker
    type: file
    file: aicp/core/circuit_breaker.py
    description: Per-backend state machine (CLOSED → OPEN → HALF_OPEN)
  - id: profile-tests
    type: file
    file: tests/test_profiles.py
    description: 49 profile tests
tags: [decision, router, profiles, architecture, aicp, backend-ai-platform-python, local-first, transferable, pattern]
---

# Decision: 4-tier router with configurable profiles over hardcoded routing

## Summary

AICP routes inference requests through a 4-tier escalation chain (local LocalAI → fleet peer → OpenRouter free tier → Claude) with confidence-scoring at each tier and auto-escalation when quality scores below threshold. The chain order, complexity thresholds, escalation cutoff, and per-mode cloud overrides are all driven by named **configuration profiles** (9 shipped: default, fast, offline, thorough, code-review, fleet-light, reliable, dual-gpu, benchmark) rather than hardcoded in the router. A single `make profile-use PROFILE=<name>` switch coordinates backends + router thresholds + RAG depth + budget + cache + timeouts + circuit breaker config + Docker envs. This is the right design because it lets the same router serve heartbeat duty (Tier-1 only, $0), production fleet operation (full chain, reliability mode), and architecture review (full chain, thorough mode) without code changes.

## Decision

> [!success] Use the 4-tier router with profile-driven configuration. Never hardcode tier order, thresholds, or backend selection.
>
> | Scenario | Profile | Chain |
> |----------|---------|-------|
> | Air-gapped / no cloud | `offline` | local → fleet |
> | Heartbeat duty / status checks | `fleet-light` | local → fleet |
> | Quick interactive responses | `fast` | local → openrouter |
> | Balanced everyday use | `default` | local → fleet → openrouter → claude |
> | Code review / structured output | `code-review` | local → openrouter → claude |
> | Architecture / security audit | `thorough` | full chain (long context, deep RAG) |
> | Production fleet operation | `reliable` | full chain + breaker threshold=2 + warmup + DLQ retries=5 + reports/4h |
> | Dual-GPU MoE inference (19GB) | `dual-gpu` | full chain + qwen3-30b-a3b primary |
> | Deterministic evaluation | `benchmark` | local only, temp=0, seed=42 |

The router itself ([aicp/core/router.py](../../../aicp/core/router.py)) reads thresholds from the active profile at request time. Adding a new profile is a YAML file; adding a new tier is a code change with backwards-compatible defaults.

## Alternatives

### Alternative 1: Hardcoded routing (single tier order, fixed thresholds)

Hardcode `local → openrouter → claude` in the router with constant complexity thresholds (e.g., `[0.3, 0.6]`). No profiles, no per-mode overrides.

> [!warning] Rejected: AICP's mission spans heartbeat duty (1B-class local model is enough, $0 target) AND architecture review (Opus required, no compromise). One hardcoded threshold cannot serve both — heartbeat profile wants `[0.5, 0.9]` (push everything to local), audit profile wants `[0.1, 0.3]` (escalate aggressively). Hardcoded thresholds force every operator to fork the router.

### Alternative 2: Per-request explicit backend (no scoring, no escalation)

Caller specifies `backend=local` or `backend=claude` per request. Router becomes a thin dispatcher.

> [!warning] Rejected: Pushes routing decisions to every caller. Fleet agents calling AICP would need to score complexity themselves, defeating the purpose of a centralized router. Also breaks the $0 target — without auto-escalation on quality score, callers either over-call Claude (waste budget) or accept low-quality local-only responses.

### Alternative 3: Two-tier (local-or-cloud) without intermediate fallback

Router has only `local` and `claude`. No fleet peer tier, no OpenRouter free tier.

> [!warning] Rejected: Fleet peer tier (LocalAI cluster ↔ cluster) is the path to Stage 4 reliability — a single LocalAI failure shouldn't immediately escalate to paid Claude. OpenRouter free tier (qwen3-8b:free) is the path to Stage 5 — gives a free cloud fallback when local is degraded but the task doesn't warrant Claude. Removing intermediate tiers makes the chain brittle and expensive.

### Alternative 4: Single profile with runtime CLI flags only

Keep one default profile and let CLI flags (`--no-cloud`, `--max-tokens`, `--temperature`) override at request time.

> [!warning] Rejected: Profiles coordinate ~10 settings (backends, router, RAG, budget, cache, timeouts, circuit_breaker, warmup, dlq, metrics, reports, docker). Asking callers to pass 10 flags per request is unusable. Profiles also let `make profile-use` write `.env` so that Docker containers (LocalAI) restart with matching `CONTEXT_SIZE`, `THREADS`, etc. — runtime flags can't reach the container.

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **The 5-stage LocalAI Independence mission requires variable routing per stage.** Stage 1 (LocalAI functional) needs heartbeat-friendly thresholds. Stage 2 (route simple ops) needs balanced thresholds. Stage 3 (progressive offload) needs aggressive local-first thresholds. Stage 5 (near-independence) needs `force_cloud_modes: []`. One hardcoded set cannot serve all five stages without recompiling.
>
> 2. **9 profiles in production use** ([config/profiles/](../../../config/profiles/)): each one tested against [tests/test_profiles.py](../../../tests/test_profiles.py) (49 tests covering load order, inheritance via `extends:`, deep merge, circular detection). The profile system isn't theoretical — it's the operational interface.
>
> 3. **Circuit breaker at the per-backend level**, not per-request, means the router is stateful — needs config (failure_threshold, recovery_timeout) per profile. Aggressive `reliable` profile uses threshold=2 (open after 2 failures); permissive `default` uses higher threshold. Hardcoding either choice breaks the other.
>
> 4. **Docker context size and parallel slots are profile-coupled.** Long-context profiles (`thorough`) want CONTEXT_SIZE=32768 / LLAMACPP_PARALLEL=1; latency-sensitive profiles (`fast`) want CONTEXT_SIZE=8192 / LLAMACPP_PARALLEL=4. The profile must write `.env` AND restart the container, not just tune the router.
>
> 5. **Per-mode cloud overrides** (`force_cloud_modes: [edit, act]`) implement the "Edit/Act modes use Claude" rule from [CLAUDE.md](../../../CLAUDE.md) Three Permission Modes. Profile-driven means the rule is configurable per deployment (a research instance can disable Edit/Act forcing; a production instance can enforce it).
>
> 6. **Quality escalation threshold** (`score < 0.25 → auto-retry on next tier`) is a tunable. `benchmark` profile sets it to 0 (no escalation, deterministic); `reliable` profile sets it to 0.5 (aggressive escalation for quality). Hardcoded would make benchmark mode meaningless.

## Reversibility

**Easy** — `make profile-use PROFILE=<name>` switches behavior with one command. To remove a profile: delete the YAML, no code change. To add a new tier (e.g., a 5th tier for Anthropic Bedrock): code change in `aicp/core/router.py` with backwards-compatible default that ignores the new tier in profiles that don't reference it.

The only non-reversible aspect: profile names in operational tooling (Makefile, .env, docker-compose) reference profile filenames. Renaming `default` to something else breaks scripts. Adding new profiles is fully reversible.

## Dependencies

If reversed (i.e., switch back to hardcoded routing):

- [aicp/core/profiles.py](../../../aicp/core/profiles.py) — profile loader/validator/resolver/diff engine becomes dead code (~600 lines)
- [tests/test_profiles.py](../../../tests/test_profiles.py) — 49 profile tests become dead tests
- [Makefile](../../../Makefile) — profile-list, profile-show, profile-diff, profile-validate, profile-use targets become dead
- 9 YAML files in [config/profiles/](../../../config/profiles/) become dead config
- The reliability stack (circuit_breaker, dlq, warmup, health_report) loses its per-profile tuning — would need fixed defaults
- Docker compose envs become unmanaged — operators edit .env directly (regression)
- Fleet integration loses per-agent tier selection — every fleet agent gets the same routing

If extended (add a 5th tier):

- aicp/core/router.py: add tier dispatch + scoring
- All 9 profiles: opt in by adding the new tier to `failover_chain`
- New backend module (e.g., aicp/backends/bedrock.py)
- Circuit breaker config per new backend
- New tests for the 5th tier

## Relationships

- BUILDS ON: [model-local-ai](../../../wiki/config/templates/methodology/) (second brain — Local AI $0 Target model)
- IMPLEMENTS: [gateway-centric-routing](../../../wiki/config/templates/) (second brain — Gateway-Centric Routing pattern)
- ENABLES: [aicp/core/circuit_breaker.py](../../../aicp/core/circuit_breaker.py) (per-backend state machine, profile-tuned)
- ENABLES: [aicp/core/dlq.py](../../../aicp/core/dlq.py) (failed task persistence, retry count per profile)
- RELATES TO: [Skills audit 2026-04-17](../00_inbox/skills-audit-2026-04-17.md) (skills load conditionally per task; router selects backend per task — same per-request config principle)
- RELATES TO: [Three-layer autocomplete chain lesson](../../lessons/00_inbox/three-layer-autocomplete-chain-validated-in-production-fleet.md) (profile-driven knowledge depth complements profile-driven routing depth)
