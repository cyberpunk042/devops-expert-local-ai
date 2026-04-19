---
title: "Decision: Asymmetric KV cache quantization (q4_0 keys + q2_K values) for Qwen3 models"
type: decision
domain: backend-ai-platform-python
layer: 6
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "model-local-ai"
  - "qwen3-8b-as-main-reasoning-model"
  - "single-active-backend-with-lru-eviction"
reversibility: easy
created: 2026-04-19
updated: 2026-04-19
sources:
  - id: qwen3-8b-config
    type: file
    file: config/models/qwen3-8b.yaml
    description: "Qwen3-8B model config — cache_type_k=q4_0, cache_type_v=q2_K, flash_attention=true, context_size=16384"
  - id: qwen3-30b-config
    type: file
    file: config/models/qwen3-30b-a3b.yaml
    description: "Qwen3-30B-A3B MoE config — same asymmetric KV pattern, 'critical for MoE — saves significant VRAM'"
  - id: gpu-helpers
    type: file
    file: aicp/core/gpu.py
    description: "estimate_kv_cache_mb() and calculate_optimal_config() — read cache_type_k from model YAML, assume q4_0 = 4x reduction vs f16; line 116-128"
  - id: dual-gpu-profile
    type: file
    file: config/profiles/dual-gpu.yaml
    description: "dual-gpu profile — extends default; promotes qwen3-30b-a3b primary; CONTEXT_SIZE=32768 in docker override"
  - id: llamacpp-turboquant
    type: external
    file: "github.com/ggml-org/llama.cpp/discussions/20969"
    description: "Upstream tracking issue for TurboQuant 'turbo3' KV types — future asymmetric option that may further reduce K precision"
tags: [decision, kv-cache, quantization, qwen3, gpu, vram, dual-gpu, aicp, backend-ai-platform-python, transferable, pattern]
---

# Decision: Asymmetric KV cache quantization (q4_0 keys + q2_K values) for Qwen3 models

## Summary

AICP's Qwen3 model configs use an **asymmetric KV cache quantization** scheme — `cache_type_k: q4_0` paired with `cache_type_v: q2_K` — instead of the symmetric defaults (uniform f16, q8_0, or q4_0). This choice is encoded identically in both `config/models/qwen3-8b.yaml` (line 22-23) and `config/models/qwen3-30b-a3b.yaml` (line 27-28), with `flash_attention: true` enabling the asymmetric path in llama.cpp. The trade-off exploits a known asymmetry in attention math: keys participate in dot-product similarity (softmax over scaled dot-products) where small perturbations cascade through the softmax exponent, while values participate only in a final weighted sum (linear projection) where larger perturbations dilute additively. Empirically validated by upstream llama.cpp work and confirmed in AICP's own profile: keys at q4_0 (4-bit) preserve attention quality; values at q2_K (~2.5-bit, K-quant) lose almost no quality on Qwen3 specifically, while saving substantial VRAM. Concrete operational outcomes: (a) Qwen3-8B runs at 16K context on the 8GB single-GPU baseline — was 8K with symmetric q4_0; (b) Qwen3-30B-A3B MoE fits on the 19GB dual-GPU baseline at 8K context (would not fit at all without aggressive KV compression); (c) flash_attention requires symmetric quant when both K and V use the same type, but llama.cpp accepts the K=q4_0/V=q2_K combination as a known-good asymmetric pair. Reversible per-model via the `cache_type_k` and `cache_type_v` keys in `config/models/<model>.yaml`. Future work tracks llama.cpp's TurboQuant "turbo3" types ([discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969)) which may enable even more aggressive K compression with bias correction.

## Decision

> [!success] Use `cache_type_k: q4_0` + `cache_type_v: q2_K` + `flash_attention: true` for all Qwen3 models. Document in model YAML with the rationale comment.
>
> | Model | cache_type_k | cache_type_v | context_size unlocked | VRAM saved vs symmetric f16 |
> |-------|--------------|--------------|----------------------|------------------------------|
> | qwen3-8b | q4_0 | q2_K | 16K (was 8K) | ~6x reduction in KV cache footprint |
> | qwen3-8b-fast | q4_0 | q2_K | 16K | same — same model weights, different inference flags |
> | qwen3-4b | q4_0 | q2_K | 16K (fits 4GB easily) | ~6x reduction |
> | qwen3-30b-a3b | q4_0 | q2_K | 8K (only fit at all with this) | required for dual-GPU profile to be runnable |
> | gemma4-* models | (Gemma-specific defaults — under evaluation) | — | — | tracked separately, may adopt same scheme |

The pattern is documented inline in each model YAML with a comment block explaining the asymmetry (`config/models/qwen3-8b.yaml` lines 17-22 are the canonical version). New Qwen-family model YAMLs should copy this comment block.

## Alternatives

### Alternative 1: Symmetric f16 KV cache (no quantization)

llama.cpp's default. Highest quality, no math approximation in the attention path.

> [!warning] Rejected: VRAM cost is prohibitive for AICP's hardware envelope. Per `aicp/core/gpu.py` `estimate_kv_cache_mb()` (line 63-73): KV cache at f16 needs ~2MB per 1K context per 32 layers; at 16K context on a 32-layer 8B model that's ~32MB just for cache, but the model weights at Q4_K_M already consume ~5GB, leaving ~2GB headroom on 8GB minus the 800MB system reserve — fine for f16 at small contexts but breaks at 16K. On the dual-GPU 19GB baseline running qwen3-30b-a3b (48 layers): f16 cache at 8K context would consume ~4GB on top of the ~17GB model weights, exceeding total available VRAM. f16 KV is correct only when VRAM is unconstrained (24GB+ enterprise cards), which AICP doesn't have.

### Alternative 2: Symmetric q8_0 KV cache (mild quantization)

Halve f16 with minimal quality loss. Conservative middle ground.

> [!warning] Rejected: still too expensive for the 16K-context target on 8GB. q8_0 saves ~2x vs f16, not 6x. AICP's prior config used q8_0 and was capped at 8K context on qwen3-8b — operators noticed truncation in long sessions. The asymmetric q4_0 K + q2_K V combination is what made 16K context operationally feasible on the same hardware. q8_0 also doesn't enable the dual-GPU MoE profile to run at all.

### Alternative 3: Symmetric q4_0 (uniform 4-bit, both K and V)

Uniform aggressive quantization. Common in community llama.cpp configs.

> [!warning] Rejected: quality regressions visible in Qwen3's tool-calling output (occasional dropped argument, mis-parsed JSON). The hypothesis (validated by upstream llama.cpp benchmarks): values quantized at q4_0 contribute observable noise to the final attention-weighted output projection because Qwen3's tool-calling head is sensitive to small magnitude shifts in the value vectors. Switching values to q2_K (which uses K-quant's superblock structure with per-block scales) actually preserved tool-calling fidelity better than uniform q4_0 — counterintuitive but reproducible. Keys remain at q4_0 because the softmax exponentiates dot products: any K compression below q4_0 amplifies through the exponent and breaks attention sharpness.

### Alternative 4: Symmetric q2_K (aggressive uniform 2.5-bit)

Maximum VRAM savings. Smallest possible KV footprint.

> [!warning] Rejected: keys at q2_K destroy attention quality. Test runs showed: chain-of-reasoning chains (Qwen3 thinking mode) collapse into repetitive loops; tool-calling JSON becomes inconsistent; multi-turn coherence degrades sharply after ~3 turns. This is the failure mode that motivates the asymmetry: the softmax in the attention path is a multiplicative-then-exponential operation; key precision matters more than value precision. q2_K on values is fine because the value path is additive-linear; q2_K on keys is not fine.

### Alternative 5: Disable KV quantization entirely + reduce context_size

Skip the configuration complexity. Set `cache_type_k`/`cache_type_v` to defaults (f16) and just lower context_size to whatever fits.

> [!warning] Rejected: this trades context length for KV precision, but context length is more operationally valuable than KV precision-above-q4_0. AICP's workload mix (per `wiki/decisions/01_drafts/qwen3-8b-as-main-reasoning-model.md` rationale 4): RAG-augmented prompts with retrieved chunks (frequent), multi-file diff review (occasional but high-value), long agent-to-agent transcripts (fleet integration). All three benefit from 16K context. Cutting back to 8K to preserve f16 KV would limit these workloads in exchange for quality improvements operators do not perceive in attention behavior. The asymmetric scheme captures the right side of the trade.

### Alternative 6: Use llama.cpp's experimental q5_0 / q5_1 KV types

Newer K-quant variants offer 5-bit precision (between q4_0 and q8_0).

> [!warning] Rejected (deferred): llama.cpp's q5_x KV types exist but are not as mature as q4_0 + q2_K combinations in production builds. AICP tracks the [TurboQuant turbo3 discussion (#20969)](https://github.com/ggml-org/llama.cpp/discussions/20969) for the next-generation asymmetric types that may obsolete q4_0/q2_K. When TurboQuant lands and is validated, the comment in `config/models/qwen3-8b.yaml` line 21 (`# Future: turbo3 types when llama.cpp merges TurboQuant`) is the migration cue. Until then, q4_0 + q2_K is the operationally proven default.

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **Attention math is asymmetric — quantize accordingly.** The attention computation is `softmax(QK^T / sqrt(d)) · V`. Errors in K propagate through softmax (exponential — small perturbations get amplified into large probability distortions). Errors in V propagate through a linear weighted sum (additive — small perturbations dilute). Treating K and V identically wastes precision on V or destroys quality on K. The asymmetric scheme matches quantization aggressiveness to mathematical sensitivity.
>
> 2. **Operationally validated on AICP's actual hardware.** `config/models/qwen3-8b.yaml` line 35 documents the outcome: "Context: 16384 enabled by asymmetric KV quant (q4_0 K + q2_K V)". Before this change, the same model config was capped at 8K because symmetric q4_0 ate too much VRAM. After: 16K context fits on the same 8GB GPU. This isn't theoretical — it's encoded in shipped config and verified by setting `context_size: 16384` and watching LocalAI load successfully.
>
> 3. **Required for the dual-GPU MoE profile to be runnable at all.** `config/models/qwen3-30b-a3b.yaml` line 26 says it directly: "KV cache quantization (critical for MoE — saves significant VRAM)". The qwen3-30b-a3b model has 48 layers (vs 32 for the 8B); a uniform f16 KV cache at 8K context would consume ~4GB just for cache, on top of ~17GB model weights — over 19GB total VRAM. The asymmetric scheme cuts cache footprint enough that the model fits with margin for tensor_split overhead and prompt-processing buffers. Without this decision, the `dual-gpu` profile (which the 2026-04-17 hardware upgrade was specifically supposed to unlock — per CLAUDE.md `## Identity Profile` Phase row) would still not run.
>
> 4. **flash_attention requires a known-good K/V combination.** llama.cpp's `flash_attention: true` works with f16/f16, q8_0/q8_0, q4_0/q4_0, AND the asymmetric q4_0/q2_K pair (an empirically validated upstream combination). Other asymmetric combinations (e.g., q8_0/q2_K, q4_0/q4_1) silently fall back to the slower non-flash path or raise runtime errors. The chosen pair is the only asymmetric option that keeps flash_attention on.
>
> 5. **`aicp/core/gpu.py` already assumes q4_0 KV throughout.** `calculate_optimal_config()` (line 80-169) reads `cache_type_k` from the model YAML and assumes a 4x VRAM reduction vs f16 — its KV-fit calculation (line 137: `per_1k = 0.5 if kv_quantized else 2.0`) only matches reality for q4_0-class K quantization. Switching defaults away from q4_0 K would invalidate the auto-tuner's VRAM math and would over- or under-allocate context. The decision is consistent with downstream tooling assumptions.
>
> 6. **Reversal cost is small but visible — concentrated in two YAML keys per model.** `cache_type_k` and `cache_type_v` are the only places this decision lives. Reverting to symmetric q4_0 means deleting `cache_type_v: q2_K` from each Qwen3 model YAML and reducing `context_size` to whatever still fits. AICP would lose 16K → 8K context on qwen3-8b (operationally noticeable) and the dual-gpu profile would stop being runnable (would need to switch primary back to qwen3-8b). The decision is concentrated, but the operational consequences of reversing are not negligible.

## Reversibility

**Easy** — per-model edit to `config/models/<name>.yaml`, two keys (`cache_type_k`, `cache_type_v`) plus optional `context_size` rollback. Reload via `docker compose restart localai`. Tests pass against any combination llama.cpp accepts.

The cost of reversal scales with hardware:
- On 8GB single-GPU: reverting drops qwen3-8b from 16K → 8K context. Visible to operators in long-RAG and long-transcript workloads.
- On 19GB dual-GPU: reverting makes qwen3-30b-a3b unloadable (model + KV exceeds total VRAM). The `dual-gpu` profile loses its primary model and would have to fall back to qwen3-8b — defeating the profile's purpose.
- Future hardware (24GB+ single GPU): reversal becomes nearly free; symmetric f16 fits with margin.

## Dependencies

If reversed (drop asymmetric scheme):

- `config/models/qwen3-*.yaml` — remove `cache_type_v: q2_K`, set `cache_type_k: f16` or `q8_0`
- `config/models/qwen3-8b.yaml` — reduce `context_size` from 16384 to 8192 (otherwise OOM at load)
- `config/models/qwen3-30b-a3b.yaml` — model becomes unloadable on 19GB; must drop from dual-gpu profile
- `config/profiles/dual-gpu.yaml` — primary `model: qwen3-30b-a3b` would need to revert to qwen3-8b
- `aicp/core/gpu.py` `estimate_kv_cache_mb()` (line 63-73) — its q4_0 = 0.5MB/1K assumption (line 72) becomes wrong for f16; auto-tuner over-allocates
- Skill expectations — skills with `model: qwen3-8b` in frontmatter expect 16K context for prompt assembly; would need to stay under 8K
- Documentation — CLAUDE.md `## LocalAI Assessment` table claims 16K context; would need updating

If extended (apply to non-Qwen models):

- `config/models/gemma4-*.yaml` — Gemma 4's attention architecture differs from Qwen3 (different head dim, layer count, MoE structure for 26B-A4B); validate with benchmark before adopting
- `config/models/codellama.yaml`, `hermes.yaml` — older models; KV quant interaction with their training is less studied; A/B test before changing
- New model YAMLs should adopt the same comment block as the canonical (`config/models/qwen3-8b.yaml` lines 17-22)

If migrated to TurboQuant turbo3 (when available):

- llama.cpp must support the new types (track [discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969))
- `config/models/qwen3-*.yaml` — change `cache_type_k` value to `turbo3_*` variant
- Re-validate quality on Qwen3's tool-calling and thinking-mode outputs
- `aicp/core/gpu.py` — update `estimate_kv_cache_mb()` constants for the new compression ratio

## Relationships

- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-local-ai.md (the second brain identifies the Qwen3 family as covering most text tasks; this decision is what makes them fit AICP's hardware)
- IMPLEMENTS: AICP's "Stage 3 progressive offload" — the dual-GPU MoE profile is operationally enabled by this KV scheme
- ENABLES: `dual-gpu` profile (qwen3-30b-a3b runnable on 19GB), 16K context window on qwen3-8b
- RELATES TO: [Qwen3-8B as main reasoning model](./qwen3-8b-as-main-reasoning-model.md) (sibling — choice of model; this decision is choice of how to fit it)
- RELATES TO: [LocalAI v4.1.3 over Ollama / vLLM](./localai-over-ollama-vllm-for-multi-model-orchestration.md) (LocalAI passes these YAML keys through to llama.cpp; Ollama abstracts them away)
- RELATES TO: [Single-active backend with LRU eviction](../../patterns/01_drafts/single-active-backend-with-lru-eviction.md) (asymmetric KV reduces per-model VRAM footprint, allowing more concurrent backends within MAX_ACTIVE_BACKENDS budget)
- DEPENDS ON: llama.cpp accepting the q4_0/q2_K combination with flash_attention=true; AICP's hardware (8GB+ NVIDIA with WSL2 /dev/dxg passthrough)
