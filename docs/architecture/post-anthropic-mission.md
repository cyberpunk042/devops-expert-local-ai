# Post-Anthropic Self-Autonomous Stack — Mission Detail

> Extracted from CLAUDE.md `## The Mission` 2026-04-25. CLAUDE.md keeps a one-paragraph status banner and routes here for the full picture.

## Status

**Functionally reached 2026-04-25** (2 days early on the 2026-04-27 P0 deadline). Brain-assigned 2026-04-22. Authoritative directive log: `wiki/log/2026-04-22-k2-6-directive-and-post-anthropic-pivot.md`.

Kimi K2.6 (Moonshot, MIT-licensed, 1T/32B-active MoE) is now the primary cloud agentic tier via two paths:
- **OpenRouter** with pinned-provider for audit-safe / client-monetizable work ($0.745 in / $4.655 out per M USD).
- **Ollama Cloud Pro** subscription (~$27 CAD/mo flat) for personal / research / dev work — shared inference pool, NEVER for client-monetizable workloads.

Local K2.6 Q2 GGUF runs on operator's Tier 0 hardware via llama.cpp (sovereignty fallback only — empirically 0.045–0.10 tok/s, not interactive).

## Mission shift (2026-04-22 → 2026-04-25)

| Tier | Before | After |
|------|--------|-------|
| Primary cloud agentic | Claude Opus 4.7 (Anthropic API) | **Kimi K2.6** via OpenRouter (audit-safe) + **Ollama Cloud Pro** (personal/research) |
| Anthropic role | Default escalation target | Hard-gated last-resort fallback only |
| Local frontier | Qwen3-30B-A3B (dual-GPU) | + **K2.6 Q2 via llama.cpp** (318GB Unsloth UD-Q2_K_XL GGUF) — sovereignty-only on Tier 0; opt-in via `--backend k2_6_local` |
| Router tiers (default profile) | 4 (local → fleet → openrouter → claude) | **4** (local → k2_6_openrouter → openrouter → claude); `personal` profile inserts `ollama_cloud` between local and k2_6_openrouter |
| Hardware ceiling | 19GB VRAM | + **64GB RAM** (sufficient for llama.cpp mmap of 318GB Q2 GGUF; sglang+kt-kernel datacenter path rejected — see `docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md`) |
| Realistic monthly cost | ~$540 CAD (prior Anthropic) | ~$30–60 CAD blended (Ollama Pro flat + occasional OpenRouter spillover) |

AICP owns brain epic **E011 — Routing Integration** (5 modules, 15-20 tasks). Authoritative scope at `~/devops-solutions-research-wiki/wiki/backlog/epics/pre-milestone/E011-routing-integration-aicp-tiers.md`.

## Original LocalAI-independence stages (long arc)

The post-Anthropic milestone is the critical-path overlay; the original 5-stage independence arc continues underneath.

1. **Make LocalAI functional** — done (LocalAI v4.1.3 on Docker, 9 models loaded, OpenAI-compatible API on :8090)
2. **Route simple operations to LocalAI** — done (4-tier router with circuit breakers, DLQ, warmup, 9 profiles at the time, now 11)
3. **Progressive offload** — hardware unlocked 2026-04-17 (19GB VRAM, dual-gpu profile runnable). Now sits ALONGSIDE the K2.6 tier work.
4. **Reliability and failover** — partial (circuit breakers + DLQ + reliable profile shipped; cluster peering pending)
5. **Near-independent operation** — **functionally reached 2026-04-25** via Post-Anthropic milestone (Ollama Cloud Pro + OpenRouter K2.6 pinned + local K2.6 sovereignty fallback; Anthropic gated to last resort)

## Operator quotes (sacrosanct, verbatim)

> "I dont want to have to deal with Anthropic and Claude and Opus in the future......" (operator, 2026-04-22)

> "Its important that the main first mission is to make localAI functional and then make it more and more reliable to offload as much as possible the work from claude till one day maybe even try to actually run independently as much as possible."

## Related artifacts

- `docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md` — why the original KTransformers/sglang+kt-kernel path was rejected; how llama.cpp + Unsloth Q2 became the working path.
- `docs/EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md` — measured numbers for local K2.6 Tier 0 throughput.
- `docs/HANDOFF-COMPACTION-2026-04-24.md` Section 11 — what landed at mission completion.
- `docs/CLOUD-SPEND-SCENARIOS-2026-04-24.md` — economic math behind the routing strategy.
- `docs/SCALING-PROJECTION-5YR-2026-04-24.md` — 5-year cost projection at projected fleet scale.
- `docs/architecture/localai-routing.md` — LocalAI assessment, model inventory, routing strategy tables.
- `docs/architecture/profiles.md` — full 11-profile listing.
