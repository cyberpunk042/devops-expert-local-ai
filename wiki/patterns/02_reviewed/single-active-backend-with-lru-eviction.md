---
title: "Single-Active Backend with LRU Eviction"
type: pattern
domain: backend-ai-platform-python
layer: 5
status: synthesized
confidence: high
maturity: growing
promoted_from: "01_drafts"
promoted_at: "2026-04-22"
promotion_reason: "Evolve score 0.779 (cross_source_convergence=1.0, evidence_density=1.0, maturity_gap=1.0, relationship_hub=0.38). 4 documented instances (LocalAI runtime, watchdog, default profile parallelism, dual-gpu profile). The constraint survives the 8GB→19GB hardware upgrade — confirming the pattern is about application coherence, not raw VRAM. Bedrock pattern for AICP's resource model."
derived_from:
  - "model-local-ai"
  - "localai-over-ollama-vllm-for-multi-model-orchestration"
instances:
  - page: "AICP LocalAI runtime"
    context: "8GB single-GPU baseline → MAX_ACTIVE_BACKENDS=3 with LRU eviction (GPU model + nomic-embed CPU + bge-reranker CPU). 19GB dual-GPU upgrade still uses MAX_ACTIVE_BACKENDS=3 — the constraint is application coherence, not just raw VRAM."
  - page: "LocalAI v4.x watchdog"
    context: "LOCALAI_WATCHDOG_IDLE=true (15m timeout) + LOCALAI_WATCHDOG_BUSY=true (10m) auto-evict stuck backends, complementing the LRU policy with crash-recovery"
  - page: "config/profiles/default.yaml LLAMACPP_PARALLEL=2"
    context: "Per-backend parallelism × per-slot context = total VRAM. AICP's profile system tunes this per workload (fast=4 parallel small context vs thorough=1 parallel large context) — both stay within MAX_ACTIVE_BACKENDS=3"
  - page: "config/profiles/dual-gpu.yaml"
    context: "Dual-GPU asymmetric profile loads qwen3-30b-a3b across both GPUs (8GB + 11GB) but still treats it as ONE active backend — LRU eviction operates at the model level, not the GPU level"
created: 2026-04-18
updated: 2026-04-18
sources:
  - id: aicp-compose
    type: file
    file: docker-compose.yaml
    description: LocalAI container with LOCALAI_MAX_ACTIVE_BACKENDS=3 + watchdog config
  - id: model-local-ai
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-local-ai.md
    description: Second brain's Local AI ($0 Target) model — VRAM is the primary physical constraint
  - id: aicp-models-config
    type: directory
    file: config/models/
    description: 14 model YAMLs — only ONE chat-class GPU model can be active at a time even with MAX=3 (the other 2 slots are CPU embedding + reranker)
tags: [pattern, gpu, vram, eviction, lru, backend, local-ai, aicp, backend-ai-platform-python, transferable]
---

# Single-Active Backend with LRU Eviction

## Summary

When multi-model AI inference is constrained by a fixed resource (VRAM, RAM, file handles, license seats) that any one model consumes a SIGNIFICANT fraction of, the right runtime pattern is **single-active per resource class with LRU (least-recently-used) eviction**: only one model per resource class is loaded at a time; switching models forces an eviction; eviction is automatic per usage history. This is what makes a 9-model library viable on a single 8GB GPU. The pattern composes with classes — AICP runs ONE chat-GPU-model + ONE CPU embedder + ONE CPU reranker simultaneously (`MAX_ACTIVE_BACKENDS=3`), each in its own resource class, LRU-evicted within its class. The PATTERN'S CORRECTNESS does not depend on resource size: 19GB dual-GPU AICP still uses single-active because the relevant constraint is application coherence (predictable warm-paths), not just raw VRAM.

> [!info] Pattern Reference Card
>
> | Component | Role | Why it must be single-active |
> |-----------|------|-----------------------------|
> | GPU chat model (e.g., qwen3-8b) | The reasoning workhorse | One full GGUF load saturates the GPU; concurrent loads OOM |
> | CPU embedder (e.g., nomic-embed) | Vector search / RAG | Different resource class (CPU+RAM vs GPU); can run alongside |
> | CPU reranker (e.g., bge-reranker) | Result reranking | Different resource class again; alongside embedder + GPU model |
> | LRU eviction policy | When MAX_ACTIVE_BACKENDS reached, oldest is evicted | Predictable VRAM bound + predictable warm cache for recent models |
> | Watchdog (idle / busy) | Auto-evict stuck or long-idle backends | Complements LRU with crash recovery |

## Pattern Description

**Single-active per resource class** is a runtime constraint: at any moment, at most ONE backend per (resource-class, capability) tuple is loaded. When a new request needs a different backend in the same class, the old backend is evicted before the new one loads. **LRU eviction** is the policy: when a slot is needed, the LEAST-RECENTLY-USED backend in that class is the one to go.

> [!warning] **Recognition signal**: a system that claims to "support N models" but where M < N can be loaded simultaneously due to a fixed resource constraint.
>
> Example: a 9-model library on 8GB VRAM. Each model is 2-7GB. Math: ~2 small models or 1 medium model per GPU. The system either rejects requests for models that don't fit (bad UX) or evicts a loaded model to make room (LRU). Single-active is the latter.

A correct implementation has 4 properties:

1. **Atomic switch** — eviction completes before the new backend starts loading. No two backends in the same class concurrently allocate the constrained resource.
2. **Predictable warm vs cold timing** — recently-used backends serve warm requests in milliseconds; freshly-loaded backends pay the full cold-start cost (10-80s for GGUF + GPU upload, per AICP measurements). The pattern doesn't HIDE the cold start — it makes it predictable per usage history.
3. **Configurable concurrency per class** — `MAX_ACTIVE_BACKENDS=3` in AICP means one slot per class (chat + embed + rerank). A different deployment with fewer classes might use MAX=1 (chat only); a richer deployment with vision + speech + rerank + embed + chat might use MAX=5.
4. **Watchdog complement** — LRU evicts based on USAGE; watchdog evicts based on HEALTH (stuck, idle too long, busy too long). Both are necessary; LRU alone leaks stuck-but-recently-used backends, watchdog alone permits unbounded growth.

> [!abstract] **The constraint determines the resource class**
>
> | Resource class | Constraint | Examples |
> |----------------|-----------|----------|
> | GPU VRAM | One large model saturates | LocalAI chat models (qwen3-8b, gemma4-e4b, llava) |
> | CPU + RAM | Often non-blocking; multiple can coexist | nomic-embed, bge-reranker, phi-2 (CPU fallback) |
> | License seats | API tokens with concurrent-call limits | Some cloud APIs; not yet relevant to AICP |
> | Network bandwidth | Streaming model downloads | Background; not enforced as a runtime class |
> | File handles / sockets | OS-level limits | Usually plentiful; not a typical class for inference |

The pattern PARTITIONS by class: same class → single-active; different classes → can coexist. AICP's 14 models partition as: 7 GPU-class chat models (one slot, LRU among them), nomic-embed (one CPU-embed slot), bge-reranker (one CPU-rerank slot), and several CPU fallbacks that share a slot via lazy load.

## Instances

### Instance 1: AICP LocalAI baseline (8GB single-GPU)

`docker-compose.yaml` config: `LOCALAI_MAX_ACTIVE_BACKENDS=3`. Active simultaneously: ONE GPU chat model + ONE CPU embedder (nomic-embed) + ONE CPU reranker (bge-reranker-v2-m3). Switching from `qwen3-8b` to `gemma4-e4b` for vision evicts qwen3-8b (LRU within the GPU-chat class). Cold-start cost: ~10-80s per swap (model size dependent). Warm inference: 1-1.2s. The pattern keeps 7-class library coherent on 8GB.

### Instance 2: LocalAI v4.x watchdog

`LOCALAI_WATCHDOG_IDLE=true LOCALAI_WATCHDOG_IDLE_TIMEOUT=15m` + `LOCALAI_WATCHDOG_BUSY=true LOCALAI_WATCHDOG_BUSY_TIMEOUT=10m`. The watchdog evicts based on health (long idle / stuck busy), complementing LRU's usage-based eviction. Without watchdog, a stuck backend pinning a slot would block all requests in that class until manual restart. With watchdog, eviction happens automatically and the next request triggers a fresh load.

### Instance 3: config/profiles/default.yaml LLAMACPP_PARALLEL=2

Per-backend parallelism (LLAMACPP_PARALLEL) × per-slot context (CONTEXT_SIZE divided by parallel slots) = effective per-request VRAM. AICP's `default` profile sets PARALLEL=2 + CONTEXT_SIZE=16384 → 8192 tokens per slot. A `fast` profile might set PARALLEL=4 + CONTEXT=8192 → 2048 per slot for low-latency small-context workloads. Both stay within MAX_ACTIVE_BACKENDS=3 — the parallelism knob tunes the SHAPE of the slot, not whether backends coexist.

### Instance 4: config/profiles/dual-gpu.yaml

19GB dual-GPU upgrade (RTX 2080 8GB + RTX 2080 Ti 11GB). One could naively set MAX_ACTIVE_BACKENDS=6 to "use all the VRAM." The dual-gpu profile keeps MAX=3 because: (a) coherence — knowing which model is active matters for routing decisions, (b) cold-start cost stays the same per swap, so preventing swap thrash is more valuable than maximizing concurrent loads, (c) the new resource (11GB second GPU) is used to load LARGER models (qwen3-30b-a3b MoE that needs 18GB), not more concurrent models. The pattern's correctness is independent of resource size; what changes is which models fit.

## When to apply

- Multi-model AI inference where any single model consumes a significant fraction of a fixed resource (typical: GPU VRAM, sometimes RAM)
- Library size > capacity (more models defined than can fit simultaneously)
- Workload mix: requests come for different models over time, but each request typically uses one model end-to-end (not pipelining 5 models per request)
- Cold-start cost is acceptable amortized over a session (warm hits dominate after first request to each model)
- Operator wants predictable VRAM bound — never OOM, even under load

## When NOT to apply

- **Single-model deployment** — if the system runs only one model, single-active is trivially satisfied and the pattern adds no value (just always-load that one model)
- **Small enough models that all fit** — if 5 models × 1GB each + 16GB VRAM, just load all of them; eviction adds latency for no benefit
- **Latency-critical workload that can't pay cold-start** — if any cold-start is unacceptable (e.g., real-time voice with 50ms budgets), use a one-model-per-instance pattern (vLLM-style) and accept the higher hardware cost
- **Different concurrency model** — pipelined multi-model requests (e.g., embed → rerank → chat in parallel for ONE request) need all participating models always-loaded; single-active forces serialization
- **Stateful sessions across many models** — if a single user session pings model A, B, C, A, B, C... single-active will thrash. Either pin those models always-loaded OR redesign the session to batch by model

## Tradeoffs

> [!warning] The single-active cost
>
> | Cost | Mitigation |
> |------|-----------|
> | Cold-start latency on first request to a new model (10-80s) | Warmup at deploy: pre-load expected models at startup. AICP's `reliable` profile uses `warmup.models: [qwen3-8b, nomic-embed]`. |
> | Thrashing if request mix alternates between many GPU models | Routing policy keeps requests on the same model when possible (router's complexity-tier selection has hysteresis); operator picks profile matching workload |
> | Loss of warm cache when a model is evicted | LRU keeps RECENTLY-used models warm; cold ones go first. Profile choice tunes which models are recently-used. |
> | Predictable cost upper bound but no SAVINGS from idle compute | If the GPU sits idle 90% of the time with one model loaded, that VRAM is "wasted" relative to a system that could swap in another workload. AICP accepts this — predictability beats marginal utilization. |

## Relationships

- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-local-ai.md (Local AI $0 Target — VRAM as primary constraint)
- IMPLEMENTS: per-resource-class single-active runtime pattern
- RELATES TO: [LocalAI v4.1.3 over Ollama / vLLM](../../decisions/01_drafts/localai-over-ollama-vllm-for-multi-model-orchestration.md) (sibling decision — single-active is the runtime pattern that LocalAI's MAX_ACTIVE_BACKENDS implements; vLLM's "one model per instance" is the OPPOSITE pattern, valid in different contexts)
- RELATES TO: [4-tier router with profiles](../../decisions/01_drafts/4-tier-router-with-profiles-over-hardcoded-routing.md) (router's per-tier model selection coordinates with single-active — a tier change can force a model swap)
- RELATES TO: [Profile as Coordination Bundle](./profile-as-coordination-bundle.md) (profiles tune the per-slot parameters: CONTEXT_SIZE, LLAMACPP_PARALLEL, warmup model list)
- ENABLES: AICP's $0 target on consumer hardware (8GB → 19GB with the same pattern, just larger model fit)
- CONTRASTS WITH: vLLM-style "one big instance per model" pattern — opposite tradeoff space (always-warm + horizontal scaling vs single-active + vertical capacity)
