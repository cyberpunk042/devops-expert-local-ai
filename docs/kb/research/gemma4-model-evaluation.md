# Gemma 4 Model Evaluation

**Date:** 2026-04-07
**LocalAI version:** v4.1.3 (upgraded from v4.0.0 for Gemma 4 architecture support)
**Hardware:** NVIDIA GPU 8GB VRAM, WSL2, CUDA 12

## Models Tested

| Model | Params (effective) | GGUF size | VRAM | Source | Architecture |
|-------|-------------------|-----------|------|--------|-------------|
| gemma4-e2b | 2.3B | 2.9 GB | ~4 GB | unsloth Q4_K_M | Dense, multimodal |
| gemma4-e4b | 4.5B | 4.7 GB | ~6 GB | unsloth Q4_K_M | Dense, multimodal |
| gemma4-26b-a4b | 4B active (26B total) | 16.8 GB | ~18 GB | ggml-org Q4_K_M | MoE, multimodal |

## Benchmark Results

### Test Setup
- 5 prompts: photosynthesis Q&A, prime function, TCP/UDP table, K8s explanation, bug finding
- max_tokens=512, default sampling parameters
- Cold start between model switches (single active backend)

### Gemma 4 E2B vs Qwen3-8B vs Qwen3-4B (Round 1 — 3 prompts)

| Metric | Gemma 4 E2B | Qwen3-8B | Qwen3-4B |
|--------|------------|----------|----------|
| P1 latency | **8.5s** | 29.2s | 21.7s |
| P1 tok/s | **51.7** | 9.5 | 2.6 |
| GGUF size | **2.9 GB** | 4.9 GB | 3.3 GB |

### Full Benchmark (Round 2 — 5 prompts, all 3 Gemma 4 sizes vs Qwen3-8B)

| Prompt | Gemma 4 E2B | Gemma 4 E4B | Qwen3-8B |
|--------|------------|------------|----------|
| P1: Photosynthesis | 25.4s, 17.3 t/s, content | 28.3s, 12.8 t/s, content | 29.1s, 9.6 t/s, content |
| P2: Prime function | **9.6s, 53.1 t/s**, content | 27.7s, 18.5 t/s, content | 122.4s, 4.2 t/s, thinking-only |
| P3: TCP/UDP table | 50.6s, 10.1 t/s, thinking-only | 27.6s, 18.5 t/s, content | **20.1s, 24.6 t/s, content** |
| P4: K8s explanation | 50.5s, 10.1 t/s, thinking-only | 156.7s, 3.3 t/s, thinking-only | 123.0s, 4.2 t/s, thinking-only |
| P5: Bug finding | 51.0s, 10.0 t/s, thinking-only | 156.9s, 3.3 t/s, thinking-only | **21.2s, 24.1 t/s, content** |
| **TOTAL** | **187s** | 397s | 316s |

### Content Success Rate (answer produced, not just thinking)

| Model | Content / Total | Rate |
|-------|----------------|------|
| Gemma 4 E2B | 3/5 | 60% |
| Gemma 4 E4B | 3/5 | 60% |
| Qwen3-8B | 3/5 | 60% |

## Key Findings

1. **Gemma 4 E2B is the speed king.** 53 tok/s peak, 187s total vs 316s (Qwen3-8B). 20x faster than qwen3-4b on simple Q&A.

2. **Gemma 4 E4B does NOT justify its size.** Slower than both E2B and Qwen3-8B (397s total). Same content success rate. Similar VRAM to Qwen3-8B. No advantage.

3. **Qwen3-8B has better content completion on complex prompts.** P3 (table) and P5 (bug finding) both produced content where E2B/E4B only produced thinking tokens.

4. **Thinking tokens are the bottleneck.** All models spend significant tokens on reasoning before generating content. With max_tokens=512, 2/5 prompts exhausted the budget on thinking alone for every model.

5. **Multimodal is free.** Gemma 4 models handle text+image+audio natively. Could replace the separate llava model for vision tasks (untested).

## Recommendations

| Slot | Current | Recommendation | Reason |
|------|---------|---------------|--------|
| Main reasoning | qwen3-8b | **Keep qwen3-8b** | Best content completion on complex prompts |
| Fleet/heartbeat | qwen3-4b | **Switch to gemma4-e2b** | 20x faster, smaller VRAM |
| Fast mode | qwen3-8b-fast | Consider gemma4-e2b | 53 tok/s, but needs testing without thinking mode |
| Vision | llava (separate) | Consider gemma4-e4b | Multimodal built-in, avoids model swap (untested) |
| Dual GPU MoE | qwen3-30b-a3b | Also try gemma4-26b-a4b | When dual GPU available, benchmark both |

## Action Taken

- fleet-light profile updated to use gemma4-e2b (from qwen3-4b)
- Model configs created: `config/models/gemma4-e2b.yaml`, `gemma4-e4b.yaml`, `gemma4-26b-a4b.yaml`
- Makefile targets added: `make model-gemma4`, `make model-gemma4-26b`
- Setup script catalog updated with Gemma 4 entries
- LocalAI upgraded to v4.1.3 for Gemma 4 architecture support

## Download URLs

```bash
# E2B (3.1 GB)
https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf

# E4B (5.0 GB)
https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf

# 26B-A4B MoE (16.8 GB — dual GPU only)
https://huggingface.co/ggml-org/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-Q4_K_M.gguf
```

## TurboQuant Note

Google's TurboQuant (ICLR 2026) achieves 3-bit KV cache quantization with zero accuracy loss.
Multiple llama.cpp forks are implementing it but it's NOT yet merged into main llama.cpp.
When it lands, it would significantly reduce VRAM for large context windows — directly
benefiting our 8GB VRAM constraint. Track: https://github.com/ggml-org/llama.cpp/discussions/20969
