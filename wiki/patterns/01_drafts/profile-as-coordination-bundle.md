---
title: "Profile as Coordination Bundle"
type: pattern
domain: backend-ai-platform-python
layer: 5
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "4-tier-router-with-profiles-over-hardcoded-routing"
instances:
  - page: "config/profiles/default.yaml"
    context: "Balanced everyday profile coordinating backends + router thresholds + RAG depth + budget + cache + Docker envs (LLAMACPP_PARALLEL=2, CONTEXT_SIZE=16384) via single switch"
  - page: "config/profiles/reliable.yaml"
    context: "Production profile aggregating circuit_breaker (threshold=2) + warmup (qwen3-8b + nomic-embed) + dlq (max_retries=5) + reports (every 4h) — 4 reliability subsystems coordinated by one profile name"
  - page: "config/profiles/dual-gpu.yaml"
    context: "19GB VRAM profile coordinating qwen3-30b-a3b primary model + asymmetric KV cache (q4_0 on second GPU) + Docker envs (CONTEXT_SIZE=32768) + router failover chain — 4 cross-cutting concerns under one profile"
  - page: "config/profiles/benchmark.yaml"
    context: "Deterministic evaluation profile coordinating temperature=0 + seed=42 + escalation_threshold=0 (no auto-escalate) + cache=disabled + budget=unlimited — same parameters across backends, router, and inference layer"
created: 2026-04-18
updated: 2026-04-18
sources:
  - id: aicp-profiles-impl
    type: file
    file: aicp/core/profiles.py
    description: 600-line profile loader/validator/resolver/diff engine; supports 'extends:' inheritance with deep merge and circular detection
  - id: aicp-profile-tests
    type: file
    file: tests/test_profiles.py
    description: 49 tests covering load order, inheritance, deep merge, circular detection
  - id: aicp-makefile
    type: file
    file: Makefile
    description: profile-list, profile-show, profile-diff, profile-validate, profile-use targets
tags: [pattern, profile, coordination, configuration, aicp, backend-ai-platform-python]
---

# Profile as Coordination Bundle

## Summary

A **profile** is a single named handle that simultaneously coordinates settings across multiple subsystems whose tuning must move together. Switching profile (`make profile-use PROFILE=fast`) changes backends, router thresholds, RAG depth, budget, cache, timeouts, circuit breaker config, warmup config, DLQ config, metrics config, reports config, AND Docker environment vars in one atomic operation. The pattern works because the bundled settings have **shared meaning** — calling something "the fast profile" is more honest than asking the operator to tune 12 parameters consistently.

> [!info] Pattern Reference Card
>
> | Subsystem | What the profile controls | Why it must move together |
> |-----------|--------------------------|---------------------------|
> | backends | Primary model, failover chain | A "fast" profile can't pair qwen3-30b primary with low-latency expectations |
> | router | Complexity thresholds, escalation cutoff, force_cloud_modes | Aggressive escalation needs aggressive cloud routing — coupled |
> | RAG | Retrieval depth, reranker on/off | Long-context profiles want deep RAG; latency profiles want shallow |
> | budget | Token budget per request | "Thorough" profile wants larger budget; "fast" wants smaller |
> | cache | TTL, max size, key strategy | Benchmark profile disables cache (deterministic); reliable enables it |
> | timeouts | Request, cold start, retries | Heartbeat profile wants short timeouts; thorough wants long |
> | circuit_breaker | failure_threshold, recovery_timeout | Aggressive profile uses threshold=2; permissive uses threshold=5 |
> | warmup | enabled, model list | Production wants warmup; ephemeral runs don't |
> | dlq | max_retries, retry_delay | Production retries 5x; benchmark retries 0 |
> | metrics | persist, snapshot interval | Production persists; benchmark doesn't |
> | reports | enabled, interval, ntfy notification | Production reports every 4h; ephemeral doesn't |
> | docker envs | CONTEXT_SIZE, LLAMACPP_PARALLEL, THREADS | Coupled — CONTEXT_SIZE/PARALLEL = per-slot context; profile must restart container |

## Pattern Description

A **coordination bundle** is a named configuration grouping where the elements MUST move together to be coherent. The pattern recurs whenever a single tuning decision (e.g., "optimize for latency") propagates across multiple independent subsystems with their own native config formats. Without bundling, the operator must hand-coordinate N settings across N config files, hoping not to introduce inconsistency. With bundling, the operator picks ONE name and the system applies the consistent setting set everywhere.

> [!warning] **Recognition signal**: a config has settings that are individually valid but combinations are not.
>
> Example: setting `failover_chain: [local]` (offline) but `force_cloud_modes: [edit, act]` is incoherent — the chain says "no cloud" but the modes say "always cloud for edit/act." Each setting validates in isolation; only the combination is broken. This is the signature of a bundle that should be coordinated.

A profile bundle has three properties:

1. **Atomic switch** — one command (`make profile-use`) changes all bundled settings at once. No intermediate state where some subsystems use the new setting and others don't.
2. **Validation across subsystems** — `make profile-validate` checks coherence between bundled settings (incompatible combinations rejected before they reach runtime).
3. **Inheritance with deep merge** — profiles `extends:` other profiles. `reliable extends default` means "everything from default, plus the reliability-specific overrides." This avoids copy-paste of common settings across 9 profile files.

> [!abstract] **Profile lifecycle**
>
> | Stage | What happens | Mechanism |
> |-------|-------------|-----------|
> | Define | Operator authors `config/profiles/<name>.yaml` | YAML with optional `extends:` chain |
> | Validate | `make profile-validate` checks schema + cross-subsystem coherence | aicp/core/profiles.py validator |
> | Resolve | `make profile-show PROFILE=<name>` renders the merged final config | Resolver walks `extends:` chain, deep merges |
> | Compare | `make profile-diff PROFILE_A=fast PROFILE_B=offline` | Diff engine reports per-subsystem deltas |
> | Activate | `make profile-use PROFILE=<name>` writes `.env` + restarts containers | Atomic — Docker compose restart picks up new envs |
> | Override | CLI flag (`--profile fast`) or env var (`AICP_PROFILE=fast`) | Per-request override without rewriting `.env` |

## Instances

### Instance 1: AICP `default` profile — balanced everyday use

`config/profiles/default.yaml` coordinates: qwen3-8b as primary backend, full failover chain (local → fleet → openrouter → claude), complexity thresholds `[0.3, 0.6]`, escalation threshold `< 0.25`, RAG depth = 3 chunks, request timeout = 60s, circuit breaker threshold = 5, warmup disabled, DLQ retries = 3, metrics persist = true, Docker `LLAMACPP_PARALLEL=2 CONTEXT_SIZE=16384`. The 12 settings are individually valid but tuning them by hand requires understanding the interactions. The profile name "default" carries the shared meaning ("balanced everyday").

### Instance 2: AICP `reliable` profile — production fleet operation

`config/profiles/reliable.yaml` aggregates 4 reliability subsystems: aggressive circuit breaker (threshold=2 vs default 5), auto-warmup (qwen3-8b + nomic-embed pre-loaded), DLQ with max_retries=5 (vs default 3) and 30s retry_delay, health reports every 4 hours with ntfy notification. Each subsystem has its own config section (`circuit_breaker:`, `warmup:`, `dlq:`, `reports:`) but they make sense ONLY together — enabling warmup without aggressive breaker is wasteful (warmup prevents the failures the breaker would catch); enabling DLQ retries without breaker means failed tasks pile up against a dead backend.

### Instance 3: AICP `dual-gpu` profile — 19GB VRAM MoE inference

`config/profiles/dual-gpu.yaml` coordinates the qwen3-30b-a3b MoE model + asymmetric KV cache (q4_0 quantization on the smaller GPU) + expanded Docker context (CONTEXT_SIZE=32768) + tier dispatch that prefers the larger model. Hardware constraint: requires both RTX 2080 (8GB) and RTX 2080 Ti (11GB) to be present. Profile validation rejects this profile when only one GPU is detected. Hardware-coupled profiles are a sub-pattern: the bundle's coherence depends on the host environment, not just the config files.

### Instance 4: AICP `benchmark` profile — deterministic evaluation

`config/profiles/benchmark.yaml` enforces deterministic outputs across the entire stack: `temperature: 0` + `seed: 42` + `escalation_threshold: 0` (never escalate, return whatever local produces) + `cache: disabled` (no cache hits skewing measurement) + `budget: unlimited` (don't truncate for cost reasons during benchmarking). This is the classic anti-coordination problem: benchmarking requires that NO subsystem make non-deterministic choices, but each subsystem has its own determinism knob. The profile bundles all the knobs into one named "benchmark mode."

## When to apply

- **Multiple subsystems with shared tuning intent.** If switching from "production mode" to "debug mode" should change 5+ config sections at once, you need a profile.
- **Operator-facing knob count > 5.** When the operator must remember 5+ settings to make a coherent change, the cognitive load is too high — bundle them.
- **Subsystems can be combined into incoherent states.** If invalid combinations exist (e.g., "no cloud + force cloud for edit"), validate at the bundle level, not per-setting.
- **Settings live in multiple files / formats.** YAML configs + `.env` + Docker compose envs + Makefile vars — a bundle abstracts over the format split.
- **Environment-coupled overrides** (dev vs staging vs production). Profiles let `extends: default` add only the deltas per environment, no copy-paste.

## When NOT to apply

- **Single-subsystem tuning.** If you're only changing one config section, a CLI flag or single env var is simpler. Bundles add overhead — don't bundle one setting.
- **Truly orthogonal settings.** If two settings genuinely don't interact (e.g., logging verbosity vs network port), bundling them creates false coupling. Bundle settings whose meanings interact, not all settings.
- **Operator knows exactly which N settings they want.** If the operator is an expert who can tune 12 settings consistently, bundles slow them down. Profiles target the common case (need consistent behavior change without remembering details), not expert mode (override individual settings).
- **Settings change at different cadences.** If setting A changes every request and setting B changes once a week, bundling forces them to a single cadence. Keep different-cadence settings separate.

## Tradeoffs

> [!warning] The bundling cost
>
> | Cost | Mitigation |
> |------|-----------|
> | Profile files multiply (AICP has 9; future could have 30) | Use `extends:` to share common settings; name profiles by use case not by setting combination |
> | New settings must be added to all relevant profiles | Validator flags missing settings; CI check fails when a profile lacks a required field |
> | Profile semantics drift over time (today's "fast" becomes tomorrow's "default") | Document profile intent in the YAML's `description:` field; `make profile-diff` surfaces drift |
> | Operators may use profiles ritualistically without understanding the settings | Standards: every profile has `description:` explaining the use case; `make profile-show` renders the resolved settings for inspection |

## Relationships

- BUILDS ON: [Decision: 4-tier router with profiles over hardcoded routing](../../decisions/01_drafts/4-tier-router-with-profiles-over-hardcoded-routing.md)
- IMPLEMENTS: configuration-as-coordination architectural principle
- ENABLES: AICP's 9 profiles — operational presets the user can switch with one command
- RELATES TO: [Skills audit 2026-04-17](../../decisions/00_inbox/skills-audit-2026-04-17.md) (skills load conditionally per task; profiles configure conditionally per deployment — same per-context-config principle, different scope)
- RELATES TO: [Three-layer autocomplete chain lesson](../../lessons/00_inbox/three-layer-autocomplete-chain-validated-in-production-fleet.md) (per-tier context budgets are profile-coupled — opus tier wants 5-8K, lightweight tier wants 500 — same coordination-bundle pattern at the context layer)
