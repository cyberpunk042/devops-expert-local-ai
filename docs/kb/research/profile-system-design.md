# Profile System Design & Research

**Date:** 2026-04-07
**Inspired by:** Airhead Institute "Local LLM Forge" Episode 1 — local model ecosystem overview

## Problem Statement

AICP had 19 independent profile-like patterns scattered across backends, router, RAG,
budget, cache, timeouts, and Docker — all uncoordinated. Changing operational mode
(e.g., "go fast" or "go offline") required manually editing multiple config files.

## Research Findings

### No Existing Tool Has Profiles
LocalAI, Ollama, vLLM, text-generation-inference — all use flat per-model config files
with no inheritance or preset system. AICP's profile layer is a genuine value-add.

### Best Patterns from the Ecosystem

1. **Kustomize base/overlay** — Base config + overlay files that patch specific fields
   via deep merge. Proven at Kubernetes scale. Maps naturally to YAML.

2. **Docker Compose profiles** — AICP already used `profiles: ["monitoring"]`. Extended
   to conditionally control docker settings per profile.

3. **Dynaconf** — Python library with native environment switching. Evaluated but
   rejected — the existing 60-line loader.py with deep merge was sufficient.

4. **12-factor principle** — Profiles resolve to environment variables. Profile is
   convenience, env vars are truth.

5. **Hydra experiment pattern** — Useful for parameter sweeps. Overkill for v1.

### Config Load Order (Final Design)

```
1. config/default.yaml             — repo defaults (committed)
2. config/profiles/<name>.yaml     — profile overlay (selected)
3. ~/.aicp/config.yaml             — user-level overrides
4. <project>/.aicp/config.yaml     — per-project overrides
5. --config <path>                 — explicit CLI override
```

## What Profiles Control

| Section | Key Settings | Previously |
|---------|-------------|-----------|
| backends | model, fast_model, fleet_model, max_tokens | Config-driven |
| router | complexity_thresholds, failover_chain, force_cloud_modes | **Hardcoded** |
| mode_profiles | temperature per think/edit/act | Partially configurable |
| rag | top_k, rerank, max_context_chars | Config-driven |
| budget | max_cost, duration, steps | Per-pipeline only |
| cache | enabled, ttl, max_entries | Config-driven |
| quality | escalation threshold | **Hardcoded at 0.25** |
| timeouts | request, cold_start, retries | **Hardcoded at 120s/60s/3** |
| docker | context_size, threads, parallel_slots, mem_limit | .env only |

## 8 Profiles Delivered

| Profile | Purpose | Primary Model |
|---------|---------|--------------|
| default | Balanced everyday | qwen3-8b |
| fast | Low latency | qwen3-8b-fast |
| offline | No cloud | qwen3-8b |
| thorough | Max quality | qwen3-8b |
| code-review | Code analysis | qwen3-8b |
| fleet-light | Heartbeat duty | gemma4-e2b |
| dual-gpu | Two GPUs, MoE | qwen3-30b-a3b |
| benchmark | Deterministic eval | qwen3-8b |

## Routing Refactor

The `classify_task_with_reason()` function was refactored from keyword-based to
score-based routing using `analyze_complexity()`. Key changes:

- **Before:** edit/act mode hardcoded to always route to Claude
- **After:** `force_cloud_modes` config key controls which modes require cloud
- **Offline profile:** sets `force_cloud_modes: []` — edit/act stays local
- Complexity thresholds configurable: `[0.3, 0.6]` default, profiles can override

## Test Coverage

- 49 profile-specific tests (validation, loading, extends, merge, diff, config integration)
- 14 new tests across router, controller, backend for config-driven behavior
- All 8 profiles validated against schema + merged config

## Key Files

- `aicp/core/profiles.py` — 250 lines, profile engine
- `config/profiles/*.yaml` — 8 profile definitions
- `tests/test_profiles.py` — 49 tests
- `aicp/config/loader.py` — profile layer inserted
- `aicp/core/router.py` — score-based routing, configurable thresholds
- `aicp/core/controller.py` — configurable failover chain
- `aicp/backends/localai.py` — configurable timeouts/retries
