# Qwen3 Model Evaluation for AICP

**Type:** Research Finding
**Date:** 2026-04-03
**Status:** RESEARCHED — compatibility verified, awaiting GGUF download + benchmark
**Sources:** Qwen team blog, HuggingFace, llama.cpp PRs, LocalAI container inspection

---

## Summary

Qwen3 (released 2025-04-28) is the next-generation model family from Alibaba.
Confirmed compatible with our LocalAI v4.0.0 stack — `qwen3.cpp` and `QWEN3MOE`
are compiled into the `cuda12-llama-cpp` backend binary.

---

## Model Lineup

| Model | Type | Params | Active | Native Context | Training Data |
|-------|------|--------|--------|---------------|--------------|
| Qwen3-0.6B | Dense | 0.6B | 0.6B | 32K | 36T tokens |
| Qwen3-1.7B | Dense | 1.7B | 1.7B | 32K | 36T tokens |
| Qwen3-4B | Dense | 4B | 4B | 32K | 36T tokens |
| **Qwen3-8B** | Dense | 8B | 8B | 32K | 36T tokens |
| Qwen3-14B | Dense | 14B | 14B | 32K | 36T tokens |
| Qwen3-32B | Dense | 32B | 32B | 32K | 36T tokens |
| **Qwen3-30B-A3B** | MoE | 30B | ~3B | 32K | 36T tokens |
| Qwen3-235B-A22B | MoE | 235B | ~22B | 32K | 36T tokens |

All models support YaRN extension up to 131K tokens (VRAM permitting).

---

## GGUF Sources

| Source | URL | Notes |
|--------|-----|-------|
| Official Qwen | `huggingface.co/Qwen/Qwen3-8B-GGUF` | Official quantizations |
| bartowski | `huggingface.co/bartowski/Qwen3-8B-GGUF` | Full quant ladder + imatrix |
| unsloth | `huggingface.co/unsloth/Qwen3-8B-GGUF` | Alternative quants |
| bartowski (MoE) | `huggingface.co/bartowski/Qwen3-30B-A3B-GGUF` | MoE variant |

---

## VRAM Planning — 8GB Single GPU (Current Machine)

| Model + Quant | File Size | VRAM (model) | VRAM (+8K ctx) | Fits 8GB? | Recommendation |
|--------------|-----------|-------------|----------------|-----------|---------------|
| Qwen3-0.6B Q8_0 | ~0.7 GB | ~1.0 GB | ~1.5 GB | Yes | Heartbeat/trivial tasks |
| Qwen3-1.7B Q8_0 | ~1.8 GB | ~2.1 GB | ~2.8 GB | Yes | Light fleet ops |
| Qwen3-4B Q6_K | ~3.3 GB | ~3.6 GB | ~4.5 GB | Yes | **Comfortable replacement for hermes-3b** |
| Qwen3-4B Q8_0 | ~4.5 GB | ~4.8 GB | ~5.8 GB | Yes | Better quality, still fits |
| **Qwen3-8B Q4_K_M** | **~4.9 GB** | **~5.2 GB** | **~6.5 GB** | **Yes (tight)** | **Maximum capability on 8GB** |
| Qwen3-8B Q5_K_M | ~5.7 GB | ~6.0 GB | ~7.3 GB | Marginal | 4K context max |
| Qwen3-8B Q6_K | ~6.6 GB | ~6.9 GB | ~8.2 GB | No | Exceeds with context |
| Qwen3-14B Q4_K_M | ~8.7 GB | ~9.0 GB | ~10.5 GB | No | Needs 12GB+ |

**With KV cache quantization (q4_0, already enabled in our config):** VRAM for context is
reduced ~4x, so Qwen3-8B Q4_K_M with 8K context is comfortable. 16K context may work with
KV cache quant but needs testing.

---

## VRAM Planning — 8GB + 11GB Dual GPU (Future Machine)

Combined 19GB with tensor splitting across GPUs.

| Model + Quant | File Size | VRAM Total | Fits 19GB? | Notes |
|--------------|-----------|-----------|-----------|-------|
| **Qwen3-30B-A3B Q4_K_M** | **~17 GB** | **~18 GB** | **Yes** | MoE: 3B active = fast inference |
| Qwen3-30B-A3B Q5_K_M | ~19 GB | ~20 GB | Barely | Very tight |
| Qwen3-14B Q4_K_M | ~8.7 GB | ~10 GB | Yes | Comfortable, 16K ctx |
| Qwen3-14B Q6_K | ~11.4 GB | ~13 GB | Yes | High quality |
| Qwen3-32B Q4_K_M | ~19 GB | ~20 GB | Barely | Dense, slower than 30B-A3B |

**Dual GPU config:** llama.cpp `--tensor-split` (e.g., `0.42,0.58` for 8GB/11GB).
Docker needs both GPUs exposed: `device_ids: ["0", "1"]`.

---

## Qwen3 vs Current Models

| Aspect | Hermes 7B (Mistral) | Hermes-3b (Llama 3.2) | Qwen3-8B | Qwen3-4B |
|--------|--------------------|-----------------------|----------|----------|
| Release | 2023 | 2024 | 2025 | 2025 |
| Training data | ~2T tokens | ~15T tokens | **36T tokens** | **36T tokens** |
| Thinking mode | No | No | **Yes** | **Yes** |
| Languages | ~10 | ~8 | **119** | **119** |
| MoE variants | No | No | Yes (30B-A3B) | No |
| Function calling | Via grammar | Via grammar | **Native** | **Native** |
| Chat template | ChatML | ChatML | **ChatML** (compatible) | **ChatML** |

---

## LocalAI Compatibility — VERIFIED

**Checked:** 2026-04-03 on running container `devops-expert-local-ai-localai-1`

```
# Binary has Qwen3 support compiled in:
strings /backends/cuda12-llama-cpp/llama-cpp-avx2 | grep qwen3
→ n_expert must be > 0 for QWEN3MOE
→ /LocalAI/backend/cpp/llama-cpp-avx2-build/llama.cpp/src/models/qwen3.cpp
```

- **Backend:** `cuda12-llama-cpp` (same as hermes/codellama)
- **Architecture:** `qwen3` (dense) and `qwen3moe` (MoE) both recognized
- **Chat template:** ChatML — same as current hermes configs
- **No LocalAI upgrade needed** — v4.0.0 already has Qwen3 support

---

## Thinking Mode

Qwen3 has a built-in "thinking" mode. The model outputs `<think>...</think>` tags
before the actual response when reasoning.

**For AICP usage:**
- **Structured tasks** (heartbeat, status, simple Q&A): Use `/no_think` in system prompt to skip reasoning overhead
- **Complex tasks** (analysis, planning): Allow thinking for better quality
- **Router consideration:** Thinking mode adds tokens but improves quality — router should decide based on task type

**Config approach:** Two model profiles per Qwen3 model:
- `qwen3-8b` — thinking enabled (for complex tasks)
- `qwen3-8b-fast` — `/no_think` in system prompt (for simple tasks)

---

## Recommended Upgrade Path

### Phase 1: 8GB Single GPU (Now)

1. **Download Qwen3-8B Q4_K_M** — replace hermes 7B as main reasoning model
2. **Download Qwen3-4B Q6_K** — replace hermes-3b as lightweight fleet model
3. **Keep codellama** — evaluate later if Qwen3-8B handles code well enough
4. **Keep phi-2** — CPU fallback unchanged

### Phase 2: 8GB + 11GB Dual GPU (Future)

5. **Download Qwen3-30B-A3B Q4_K_M** — flagship model for complex reasoning
6. **Move Qwen3-8B to secondary role** — mid-tier tasks
7. **Qwen3-4B stays as lightweight** — heartbeats, trivial ops

---

## IaC Requirements

The model setup must be:
- **VRAM-adaptive:** Detect available VRAM, select best model + quantization automatically
- **Reproducible:** `make setup` or `make model-setup` downloads + configures everything
- **Multi-machine:** Same config works on 8GB machine and 19GB machine with different model selection
- **Rollback-safe:** Keep old models until new ones are benchmarked and verified

---

## Next Steps

1. Download Qwen3-8B Q4_K_M GGUF
2. Create `models/qwen3-8b.yaml` config (based on hermes.yaml pattern)
3. Create `models/qwen3-4b.yaml` config (based on hermes-3b.yaml pattern)
4. Benchmark: Qwen3-8B vs hermes on same prompts
5. Benchmark: Qwen3-4B vs hermes-3b on same prompts
6. Update `config/default.yaml` if benchmarks are positive
7. Update router to leverage thinking mode
8. Build VRAM-adaptive model selection in `scripts/setup.sh`
