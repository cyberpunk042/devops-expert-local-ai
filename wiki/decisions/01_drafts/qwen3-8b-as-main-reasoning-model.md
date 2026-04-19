---
title: "Decision: Qwen3-8B as AICP's main reasoning model (over Hermes-7B, CodeLlama-7B, Gemma-3 4B)"
type: decision
domain: backend-ai-platform-python
layer: 6
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "model-local-ai"
  - "localai-over-ollama-vllm-for-multi-model-orchestration"
reversibility: easy
created: 2026-04-18
updated: 2026-04-18
sources:
  - id: aicp-models-config
    type: file
    file: config/models/qwen3-8b.yaml
    description: AICP's qwen3-8b model config — 4.9GB GGUF, 6GB+ VRAM, thinking mode, native tool calling
  - id: aicp-default-profile
    type: file
    file: config/profiles/default.yaml
    description: Default profile primary backend = qwen3-8b
  - id: model-evals
    type: directory
    file: docs/kb/models/
    description: Model evaluation notes (CLAUDE.md references this dir)
  - id: model-local-ai
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-local-ai.md
    description: 'Second brain Local AI model: Qwen3 family (8B, 4B, 30B MoE) covers most text tasks'
tags: [decision, qwen3, model, reasoning, aicp, backend-ai-platform-python, transferable, pattern]
---

# Decision: Qwen3-8B as AICP's main reasoning model (over Hermes-7B, CodeLlama-7B, Gemma-3 4B)

## Summary

AICP routes general-purpose reasoning, code analysis, and tool-calling workloads to **Qwen3-8B** by default — set as the primary backend in `config/profiles/default.yaml`, configured in `config/models/qwen3-8b.yaml` (4.9GB GGUF, 6GB+ VRAM, native tool calling, "thinking mode" for chain-of-reasoning, 119-language coverage). Smaller and weaker models considered (Hermes-2-Pro-Mistral 7B, CodeLlama 7B, Gemma 4 E4B at 5GB, Phi-2 2.7B for CPU fallback) trade off on different axes; Qwen3-8B wins for AICP because it's the only 7-8B-class model that simultaneously: (a) fits the 8GB single-GPU baseline (now generously fits 19GB dual-GPU), (b) supports thinking mode for harder reasoning tasks via a single config flag, (c) ships native tool-calling (no prompt-template hacks), (d) has 119-language coverage useful for multilingual fleet operations. The decision is profile-overridable: `fleet-light` profile uses Gemma 4 E2B (53 tok/s, multimodal); `dual-gpu` profile uses Qwen3-30B-A3B MoE (now runnable post-19GB upgrade); `code-review` profile pairs Qwen3-8B with low-temperature config. Qwen3-8B is the default; not the only choice.

## Decision

> [!success] Default to Qwen3-8B for general reasoning. Override per profile when workload favors different tradeoffs.
>
> | Workload | Active model (per profile) |
> |----------|----------------------------|
> | General reasoning, code analysis, tool calling | **Qwen3-8B** (default profile) |
> | Heartbeat / fleet-light operations | Gemma 4 E2B (fleet-light profile) — 53 tok/s, multimodal, smaller VRAM |
> | Architecture / security audit | Qwen3-8B + thorough profile (deep RAG, longer context, full failover chain) |
> | Code review / structured output | Qwen3-8B + code-review profile (low temp, structured output emphasized) |
> | MoE / heavy reasoning | Qwen3-30B-A3B (dual-gpu profile, 19GB VRAM required — runnable since 2026-04-17) |
> | Vision tasks | Gemma 4 E4B (preferred multimodal) or LLaVA 7B (legacy fallback) |
> | CPU fallback (no GPU) | Phi-2 2.7B (last resort) |

The default is Qwen3-8B's `qwen3-8b` config (thinking mode ON). The `qwen3-8b-fast` variant (thinking mode OFF, structured output emphasized) is selected for low-latency workloads where reasoning chains aren't needed.

## Alternatives

### Alternative 1: Hermes-2-Pro-Mistral 7B as default

The previous (legacy) AICP default. Hermes is well-tuned for instruction following and was the strongest local 7B option for several model generations.

> [!warning] Rejected: Hermes-2-Pro is from an older generation (Mistral 7B base, 2023-2024 era). Qwen3 (released 2025) was trained on substantially more data with native tool-calling support and a thinking-mode config that Hermes lacks. Specifically: (a) Hermes requires explicit prompt templates for tool-calling that AICP's router would have to assemble; Qwen3-8B's tool-calling is native and reliable. (b) Hermes has English-strong but limited multilingual coverage; Qwen3-8B handles 119 languages. (c) On AICP's qualitative test set (router complexity scoring + circuit-breaker reasoning + skill-loading decisions), Qwen3-8B produced more consistent structured outputs. Hermes remains in `config/models/hermes.yaml` as a legacy option.

### Alternative 2: CodeLlama 7B for code-heavy workloads

Specialized for code generation. AICP has substantial code work (router, profiles, MCP server, etc.).

> [!warning] Rejected as default (kept as specialist): CodeLlama is excellent for code COMPLETION (autocomplete-style) but less general for code REASONING (architecture decisions, debugging hypotheses, refactor analysis). AICP's actual workload mix is ~30% code generation, ~70% mixed (analysis, planning, document authoring, decision-making). A code-specialist default would underperform on the 70%. CodeLlama remains in `config/models/codellama.yaml` for tasks that genuinely benefit (raw code completion at scale).

### Alternative 3: Gemma 4 E4B as default

Google's 2026 multimodal model. ~5GB GGUF, 6GB+ VRAM, vision + audio + text in one model.

> [!warning] Rejected as default (kept as multimodal specialist): Gemma 4 E4B is the right choice when MULTIMODAL inputs are present (vision tasks, audio transcription paired with reasoning). For pure text reasoning, Qwen3-8B's thinking mode produces better-quality reasoning chains in informal benchmarks AICP has run. Gemma 4 E4B's strength is breadth (multimodal + text), not depth (thinking-mode reasoning). Default goes to depth; multimodal stays profile-selectable.

### Alternative 4: Always route to Claude (Opus or Sonnet) — skip local entirely

Forget local; route everything to Claude. The mission "make LocalAI functional" can be deferred.

> [!warning] Rejected: this contradicts AICP's stated mission ("LocalAI independence — progressive offload from Claude to LocalAI", per CLAUDE.md `## The Mission`). The 5-stage roadmap specifically targets ~80% Claude token reduction by Stage 5. Defaulting to Claude for general reasoning means Stage 2 (route simple operations to LocalAI) never happens. Qwen3-8B as default is the operational expression of the mission's commitment to local-first.

### Alternative 5: Smallest sufficient model (Qwen3-4B) as default

Use Qwen3-4B (3.3GB) as default instead of Qwen3-8B. Half the VRAM, half the load time.

> [!warning] Rejected as default (kept for fleet-lightweight): Qwen3-4B is genuinely useful for fleet heartbeats and structured-format tasks, but for general reasoning the quality drop is meaningful. Specifically: thinking-mode chain quality, tool-calling reliability under ambiguous inputs, and multi-turn coherence all favor 8B over 4B. The default targets the typical operator workload; 4B is deployed for fleet use cases where the size/quality tradeoff favors size (`fleet-light` profile uses gemma4-e2b which is even smaller).

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **Thinking mode + tool-calling are config flags, not prompt hacks.** Qwen3-8B's `qwen3-8b.yaml` config enables thinking mode via a single parameter (`thinking: true`). Tool calls are native, with structured output schemas. AICP's router doesn't need to template-engineer these; it just sets the flags. Hermes/CodeLlama require AICP to assemble prompt templates for the same capabilities — duplicated logic that drifts.
>
> 2. **8B fits 8GB → 19GB hardware comfortably.** AICP's single-active-backend pattern (per `wiki/patterns/01_drafts/single-active-backend-with-lru-eviction.md`) reserves the GPU for ONE chat model at a time. Qwen3-8B at 4.9GB fits in 6GB+ VRAM with comfortable margin for KV cache + context. On the new 19GB dual-GPU baseline, qwen3-8b shares space with embedders + reranker AND leaves room to occasionally swap in qwen3-30b for heavier tasks. A larger default (e.g., qwen3-14b) would saturate the 8GB baseline.
>
> 3. **119-language coverage is operationally useful.** AICP serves multiple projects (openfleet, second brain, NNRT) and may eventually accept tasks in non-English contexts (multilingual codebases, internationalized docs). Hermes/CodeLlama are English-strong; Qwen3-8B is broadly multilingual. Marginal benefit today, real benefit as fleet integration grows.
>
> 4. **`config/models/qwen3-8b.yaml` is operationally proven.** AICP has been running with qwen3-8b as default since the 2026-Q1 transition off Hermes. The model swap mechanism, watchdog timeouts, GPU loading patterns, and warmup behavior are all calibrated for qwen3-8b's specific characteristics (4.9GB load, ~10-30s cold start, ~1-1.2s warm inference). Re-tuning all of this for a different default would be substantial work without commensurate benefit.
>
> 5. **The fast variant (`qwen3-8b-fast`) covers latency-sensitive workloads** without changing the default. `qwen3-8b-fast.yaml` keeps the same model weights but disables thinking mode + emphasizes structured output. For fleet operations or high-throughput batches, the fast variant gives ~2x throughput while keeping qwen3-8b-class quality. Different defaults for different profiles aren't needed.
>
> 6. **Profile system makes the choice safely reversible.** Per the `4-tier-router-with-profiles-over-hardcoded-routing` decision, model selection is per-profile. Switching from qwen3-8b to a different default would mean editing `config/profiles/default.yaml` (one line). Other profiles (fleet-light, dual-gpu, code-review, etc.) keep their model overrides. The decision is concentrated in the default profile, not spread across the codebase.

## Reversibility

**Easy** — `config/profiles/default.yaml` `backends.local.model: qwen3-8b`. Change to a different model name, run `make profile-validate` to confirm the new model exists in `config/models/`, run `make profile-use PROFILE=default` to apply. Tests pass against any model that satisfies the OpenAI-compatible chat completions interface (which all GGUF models served by LocalAI do).

The cost of reversal scales with how operationally embedded the choice is:
- Routine swap (default model → e.g., gemma4-e4b): minutes
- Architectural swap (drop thinking mode entirely): days (router scoring + skill expectations would need updating)
- Drop Qwen3 family entirely: hours (delete config/models/qwen3-*.yaml, switch dual-gpu profile away from qwen3-30b-a3b, retune AICP's circuit breaker thresholds for the new model's failure modes)

## Dependencies

If reversed (switch primary model away from Qwen3-8B):

- `config/profiles/default.yaml` `backends.local.model` — the one-line change
- `config/profiles/code-review.yaml` and `thorough.yaml` also reference qwen3-8b explicitly — would need updating
- Router complexity scoring (`aicp/core/router.py`) — thresholds were calibrated for qwen3-8b's quality envelope; may need recalibration
- Skill model overrides (`.claude/skills/*/SKILL.md` frontmatter `model:` field) — many skills reference qwen3-8b as expected backend
- KB embeddings — currently nomic-embed CPU; unaffected by chat model change (different resource class)
- Testing — `make benchmark-qwen3` exists; would need a new benchmark target for the new default

If extended (add a new model as default candidate):

- `config/models/<new-model>.yaml` — define the model
- Test it via `make benchmark-<model>`
- A/B test against Qwen3-8B on representative workload
- If wins, edit `config/profiles/default.yaml`
- Consider whether existing profiles (fleet-light, code-review, thorough, etc.) should also adopt

## Relationships

- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-local-ai.md (the Qwen3 family is highlighted there as covering "most text tasks")
- IMPLEMENTS: AICP's "primary local model is Qwen3-8B with thinking mode" operational choice
- ENABLES: `default` profile + `qwen3-8b-fast` variant + per-profile overrides for specialized workloads
- RELATES TO: [LocalAI v4.1.3 over Ollama / vLLM](./localai-over-ollama-vllm-for-multi-model-orchestration.md) (sibling — the runtime that hosts qwen3-8b)
- RELATES TO: [4-tier router with profiles](./4-tier-router-with-profiles-over-hardcoded-routing.md) (the router that picks among local/cloud per request — qwen3-8b is the "local" tier's default model)
- RELATES TO: [Single-active backend with LRU eviction](../../patterns/01_drafts/single-active-backend-with-lru-eviction.md) (the runtime pattern that determines qwen3-8b's GPU residency vs swap-out)
- DEPENDS ON: AICP's hardware (8GB → 19GB GPU baseline); a much smaller VRAM constraint would force a smaller default
