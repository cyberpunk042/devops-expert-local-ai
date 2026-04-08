# Stable Diffusion 3.5 Evaluation — Local Deployment Feasibility

**Date:** 2026-04-08
**Hardware:** NVIDIA RTX 3060 Ti 8GB VRAM, WSL2, CUDA 12
**Current SD config:** `config/models/stablediffusion.yaml` (SD 1.5 Q4_0 GGUF)

## Executive Summary

Stable Diffusion 3.5 is a genuine generational leap over SD 1.5. The Medium variant
(2.5B params) fits on 8GB VRAM when quantized, producing 1024x1024 images with coherent
text rendering and strong prompt adherence. However, running it alongside an LLM on a
single 8GB GPU is impractical — the model swap cost (34-65s downtime + destroyed KV cache)
makes it unsuitable for fleet operation. The correct architecture is a dedicated image
generation machine in the P2P fleet.

---

## Model Variants

SD 3.5 was released by Stability AI in October 2024. Three variants exist:

| Variant | Parameters | Architecture | Steps | Resolution | Release |
|---------|-----------|--------------|-------|------------|---------|
| **Large** | 8.1B | MMDiT | 28-50 | Up to 1024x1024 | Oct 22, 2024 |
| **Large Turbo** | 8.1B | MMDiT + ADD distillation | **4** | Up to 1024x1024 | Oct 22, 2024 |
| **Medium** | 2.5B | MMDiT-X (improved) | 25-50 | 0.25-2 megapixel | Oct 29, 2024 |

All three use three text encoders: CLIP-L/14, CLIP-G/14, and T5-XXL.

Large Turbo is NOT a smaller model — same 8.1B params, but distilled via Adversarial
Diffusion Distillation (ADD) to generate in 4 steps instead of 28-50.

---

## Text Encoders (The Hidden VRAM Cost)

SD 3.5 uses three text encoders working in concert. These are separate from the
denoising transformer and add significant VRAM overhead:

| Encoder | Parameters | FP16 Size | FP8 Size | Purpose |
|---------|-----------|-----------|----------|---------|
| **CLIP-L/14** (OpenAI) | ~124M | ~246 MB | ~123 MB | Short-range semantics |
| **CLIP-G/14** (OpenCLIP bigG) | ~694M | ~1.39 GB | ~700 MB | Broad visual concepts |
| **T5-XXL** (Google) | ~4.7B (encoder half) | ~9.6 GB | ~4.8 GB | Text understanding, prompt following |

**Can you drop T5-XXL?** Yes — SD 3.5 was trained with "encoder dropout" specifically
to allow this. Impact:
- Saves ~9.6 GB (FP16) or ~4.8 GB (FP8)
- Image quality and semantics remain largely intact
- Text rendering in images degrades noticeably
- Complex/long prompt following gets slightly worse
- At low CFG values, difference is minimal

**For 8GB VRAM:** Drop T5-XXL or offload it to CPU. Use FP8 variants of CLIP encoders.

---

## VRAM Requirements

### Full Pipeline (FP16, no offloading)

| Variant | Transformer | Text Encoders | VAE | Total |
|---------|------------|---------------|-----|-------|
| **Large** | ~16 GB | ~11.2 GB | ~168 MB | ~27.4 GB |
| **Large Turbo** | ~16 GB | ~11.2 GB | ~168 MB | ~27.4 GB |
| **Medium** | ~5 GB | ~11.2 GB | ~168 MB | ~16.4 GB |

### With CPU offloading (text encoders offloaded after prompt encoding)

| Variant | Peak GPU VRAM | Notes |
|---------|--------------|-------|
| **Large** | ~18 GB | Still needs 24GB GPU |
| **Medium** | ~9.9 GB | Stability AI says "at least 12 GB" |

### With FP8 (NVIDIA TensorRT, RTX 40-series)

| Variant | VRAM | Reduction | Speed Boost |
|---------|------|-----------|-------------|
| **Large** | ~11 GB | 40% less | 2.3x faster |
| **Medium** | ~6 GB | ~40% less | 1.7x faster |

### GGUF Quantized (community, by city96 on HuggingFace)

**SD 3.5 Medium GGUF (transformer only, text encoders separate):**

| Quantization | File Size | Approx. VRAM |
|-------------|-----------|--------------|
| Q3_K_S | 1.45 GB | Easily fits 8 GB |
| Q4_K_S | 1.74 GB | Easily fits 8 GB |
| Q4_K_M | 1.79 GB | Easily fits 8 GB |
| Q5_K_S | 2.02 GB | Easily fits 8 GB |
| Q5_K_M | 2.07 GB | Easily fits 8 GB |
| Q6_K | 2.32 GB | Easily fits 8 GB |
| **Q8_0** | **2.86 GB** | **Easily fits 8 GB (recommended)** |
| F16 | 4.94 GB | Fits 8 GB |

**SD 3.5 Large GGUF (transformer only):**

| Quantization | File Size | Approx. VRAM |
|-------------|-----------|--------------|
| Q4_0 | 4.77 GB | Tight on 8 GB |
| Q4_1 | 5.27 GB | Tight on 8 GB |
| Q5_0 | 5.77 GB | Tight on 8 GB |
| Q5_1 | 6.27 GB | Very tight |
| Q8_0 | 8.78 GB | Needs 16 GB |
| F16 | 16.3 GB | Needs 24 GB |

**SD 3.5 Large Turbo GGUF:** Same sizes as Large (same 8.1B params).

**Critical note:** GGUF sizes are for the transformer ONLY. Text encoders (CLIP-L,
CLIP-G, T5-XXL) must be loaded separately. T5-XXL FP16 is ~9.5 GB (FP8 variant
~4.9 GB). In ComfyUI, text encoders can be offloaded to CPU.

### NF4 (4-bit, HuggingFace bitsandbytes)

| Variant | VRAM | Quality |
|---------|------|---------|
| **Medium NF4** | ~5.9 GB | Good, usable |
| **Large NF4** | ~8 GB (very tight) | Noticeable loss |

---

## Generation Speed on Consumer GPUs

| GPU | Model | Quantization | Resolution | Time/Image | Notes |
|-----|-------|-------------|------------|------------|-------|
| RTX 4060 (8 GB) | Medium | FP8 + medvram | 1024x1024 | ~5-8s | With optimization |
| RTX 4060 (8 GB) | Large | Q4 GGUF | 1024x1024 | ~5 min | Heavy quant, slow |
| RTX 3060 (12 GB) | Medium | FP16 | 1024x1024 | ~5s/iter | 2.8 GB during inference |
| RTX 4060 Ti (16 GB) | Large | Q8 GGUF | 1024x1024 | Manageable | Near-lossless |
| RTX 4090 (24 GB) | Large | FP16 | 1024x1024 | Fast | No quant needed |

### Recommended Inference Settings

| Variant | Steps | CFG Scale | Sampler | Resolution |
|---------|-------|-----------|---------|------------|
| **Large** | 28-50 | 3.5-7.0 | Euler / dpmpp_2m | 1024x1024 |
| **Large Turbo** | 4 | 0-1.0 | Euler | 1024x1024 |
| **Medium** | 25-50 | 3.5-7.0 | Euler / dpmpp_2m | 1024x1024 |

Official recommendation: 40 steps / 3.5 CFG. Community finding: 20 steps / 7 CFG works well.

---

## Quality Comparison

### SD 3.5 vs Previous Generations

| Feature | SD 1.5 (983M) | SDXL (3.5B) | SD 3.5 Large (8.1B) | SD 3.5 Medium (2.5B) |
|---------|--------------|-------------|---------------------|---------------------|
| Prompt adherence | Basic | Good | **Market-leading** | Good |
| Text rendering | Poor | Poor | **Good (coherent signs)** | Decent |
| Anatomy | Weak | Better | Better (still imperfect) | Weaker than Large |
| Native resolution | 512x512 | 1024x1024 | 1024x1024 | 1024x1024 |
| Min VRAM | ~4 GB | ~6-8 GB | ~11 GB (FP8) | ~6 GB |
| Community/LoRA ecosystem | Massive | Large | Growing | Small |
| Fine-tuning ease | Easiest | Moderate | Harder | Easier than Large |

### SD 3.5 vs FLUX.1

| Aspect | SD 3.5 Large | FLUX.1 |
|--------|-------------|--------|
| Photorealism | Good | **Better** |
| Artistic styles | **Better** | Good |
| Text rendering | Good | **Better** |
| Prompt adherence | **Excellent** | Good |
| Speed (same HW) | Faster | Slower |
| Self-hosting | **Better** (open weights) | Restricted |
| Max prompt length | 256 tokens | 512 tokens |

Community consensus: FLUX wins for photorealism. SD 3.5 wins for self-hosting,
customization, and artistic styles.

---

## The Model Swap Problem (Single GPU)

### Why coexistence is impossible on 8GB

```
Qwen3-8B Q4_K_M:  ~6.5 GB VRAM (model + KV cache + CUDA overhead)
SD 3.5 Medium:     ~3-6 GB VRAM (any quantization)
Available VRAM:    8 GB
                   ─────────
Combined need:     ~9.5-12.5 GB → DOES NOT FIT
```

Even the smallest viable SD model needs more VRAM than is free after loading the LLM.
The VAE decode stage alone requires ~2.2 GB of transient memory.

### Swap round-trip cost

| Step | Time |
|------|------|
| Unload LLM (process kill, VRAM release) | ~1s |
| Load SD model into VRAM | ~10-15s |
| Generate image (25 steps, 1024x1024) | ~5-8s |
| Unload SD | ~1s |
| Reload LLM (cold start) | ~15-30s |
| Re-process conversation KV cache | ~2-10s |
| **Total LLM downtime** | **~34-65s** |

### KV cache destruction

The KV cache is **completely destroyed** on every model swap. After generating one
image, the LLM must re-process every token in the conversation from scratch.

llama.cpp supports `--slot-save-path` for KV cache persistence to disk, but:
- LocalAI does not expose this feature through its API
- Save/restore adds overhead on top of model loading
- For a 16K context conversation, re-ingestion takes 5-10s at ~100 tok/s

### Known LocalAI bug

[GitHub Issue #1498](https://github.com/mudler/LocalAI/issues/1498): After using the
diffusers backend on GPU, switching back to llama.cpp fails with `CUDA error: out of
memory`. The diffusers pipeline does not properly release GPU VRAM.

The `stablediffusion-ggml` backend (stable-diffusion.cpp) may not have this exact
issue, but backend switching on a single GPU is a fragile path in LocalAI.

---

## CPU-Only Image Generation (No GPU Swap)

Can SD run on CPU while the LLM keeps the GPU?

| Method | Time for 512x512 | Notes |
|--------|-------------------|-------|
| stable-diffusion.cpp (4 threads) | ~10-12 min | 29s/step × 25 steps |
| stable-diffusion.cpp (8 threads) | ~7-8 min | 18s/step × 25 steps |
| FastSD CPU + OpenVINO (SD Turbo, 1 step) | **1.7s** | Needs ~11 GB RAM, lower quality |
| FastSD CPU + OpenVINO (SDXS, 1 step) | **0.82s** | Fastest, lowest quality |

The OpenVINO path is interesting as a sidecar container — doesn't touch VRAM at all.
But quality of 1-step models is significantly lower, and it needs 11 GB RAM
(your Docker limit is 12 GB, so very tight).

---

## LocalAI Compatibility

### Path A: `stablediffusion-ggml` backend (stable-diffusion.cpp)
- stable-diffusion.cpp **explicitly supports SD3/SD3.5** architecture
- LocalAI wraps it as `stablediffusion-ggml` backend
- LocalAI does NOT officially document SD 3.5 support
- Would use GGUF quantized models
- Current config uses this backend with SD 1.5

### Path B: `diffusers` backend (HuggingFace)
- LocalAI supports `pipeline_type: StableDiffusion3Pipeline` via diffusers
- [Issue #4144](https://github.com/mudler/LocalAI/issues/4144): problems loading local
  SD3 models — closed as NOT_PLANNED
- Less validated path

### Alternative: ComfyUI (recommended for SD 3.5)

ComfyUI is purpose-built for image generation with a mature pipeline:
- Supports SD 3.5, SDXL, FLUX, ControlNet, LoRA, IP-Adapter, upscaling, inpainting
- Node-based workflow system for complex pipelines
- Headless REST API via [SaladTechnologies/comfyui-api](https://github.com/SaladTechnologies/comfyui-api)
- Docker containers available (ai-dock, YanWenKun, etc.)
- Active ecosystem with thousands of custom nodes
- **Better choice than LocalAI's SD backend for serious image generation**

---

## Fine-Tuning

### LoRA Training

SD 3.5 fully supports LoRA fine-tuning (advantage over FLUX which is distilled
and harder to train).

| LoRA Rank | File Size | VRAM Needed | Time (24GB GPU) |
|-----------|-----------|-------------|-----------------|
| 8 | 3-8 MB | 12-15 GB | ~20 min |
| 16 | 8-15 MB | 15-19 GB | ~30-45 min |
| 32 | 15-30 MB | 19-20 GB | ~1-2 hours |
| 64 | 30-60 MB | 19-24 GB | ~1-3 hours |
| 128 | 60-120 MB | 24+ GB | ~2-4 hours |

**On 8GB VRAM:** Training is NOT feasible. Minimum 12GB with heavy optimization
(gradient checkpointing, text encoder caching, batch size 1, 8-bit optimizer).
24GB recommended.

**Practical approach:** Train on cloud GPU (RunPod A100 ~$1/hr, 10-45 min per run),
deploy the LoRA adapter locally for inference. LoRA files are tiny (3-60 MB).

**Important:** LoRAs trained on SD 3.5 Large are NOT compatible with SD 3.5 Medium
(different architectures: MMDiT vs MMDiT-X).

### Training Tools

1. **SimpleTuner** (bghira) — most mature for SD3/SD3.5
2. **Kohya sd-scripts** — widely used, good documentation
3. **OneTrainer** (Nerogar) — GUI-friendly
4. **HuggingFace Diffusers** — programmatic

### What "Multiple Levels of Fine-Tuning" Means

| Level | Method | VRAM | Time | Use Case |
|-------|--------|------|------|----------|
| 1 | Prompt engineering | 0 | 0 | Style via text |
| 2 | LoRA rank 8-16 | 12-19 GB | 20-45 min | Style transfer |
| 3 | LoRA rank 32-128 | 19-24 GB | 1-3 hours | Character consistency |
| 4 | DreamBooth LoRA | 19-24 GB | 1-4 hours | Specific identity |
| 5 | Full fine-tune | 80+ GB | Days | New domain |
| 6 | Distillation | 40+ GB | Days-weeks | Speed optimization |

---

## Inference Speed Optimizations

| Optimization | Speed Gain | VRAM Impact | Requirements |
|-------------|-----------|-------------|--------------|
| torch.compile | 10-20% | Neutral | PyTorch 2.0+, cold start penalty |
| SDPA (Scaled Dot-Product Attention) | Auto-selects best | Reduced | PyTorch 2.0+ built-in |
| xFormers | ~20-30% | Reduced | Legacy, superseded by SDPA |
| Flash Attention 2 | Similar to xFormers | Reduced | Ampere+ GPUs |
| TensorRT (NVIDIA) | 2.3x (Large), 1.7x (Medium) | -40% | RTX 40-series, FP8 |
| CPU offloading | Slower but fits | Major savings | Universal |
| Regional torch.compile | Avoids full recompile | Neutral | Compile just the MMDiT |

---

## License

**Stability AI Community License:**

| Usage | Cost |
|-------|------|
| Non-commercial (research, personal) | **Free** |
| Commercial (revenue < $1M/year) | **Free** |
| Commercial (revenue >= $1M/year) | Enterprise license required |

More restrictive than SD 1.5 (CreativeML Open RAIL-M) and SDXL.
You own the generated outputs.

---

## Recommended Architecture for AICP Fleet

### Current Single Machine (MINING-Station, 8GB)

**Do NOT run SD alongside the LLM.** The 34-65s downtime per image + destroyed
KV cache + potential VRAM leak bug makes this impractical for fleet operation.

**Best option for one-off images now:** Keep SD 1.5 Q4_0 in current config.
Accept the model swap penalty (~45s) for occasional use.

### Two-Machine Fleet (the real answer)

```
Machine 1 (MINING-Station, 8GB VRAM):
├── Qwen3-8B (always warm, no swaps)
├── Gemma4-E2B (fleet fast mode)
├── nomic-embed + BGE reranker (CPU)
└── Routes image requests → Machine 2

Machine 2 (Fleet Bravo, ?GB VRAM):
├── SD 3.5 Medium (always warm, dedicated)
│   └── ComfyUI headless API (better than LocalAI SD)
├── LoRA hot-swap for styles (tiny files, <100ms swap)
├── Own Qwen3-8B for LLM tasks when idle
└── Accepts image requests from AICP router
```

### AICP Integration Points

1. Add `image` backend type to AICP router
2. Route `/v1/images/generations` to Machine 2's ComfyUI API
3. OpenArms extension already registers `ImageGenerationProvider`
4. Circuit breaker protects against Machine 2 being down
5. DLQ captures failed image generation requests for retry

### Upgrade Path

| Phase | Action | When |
|-------|--------|------|
| 1 | Keep SD 1.5 Q4_0, accept swap penalty | Now |
| 2 | Set up Machine 2 with ComfyUI + SD 3.5 Medium | When Machine 2 available |
| 3 | Add AICP image routing to Machine 2 | After Phase 2 |
| 4 | Train custom LoRAs on cloud, deploy locally | When needed |
| 5 | Upgrade to SD 3.5 Large when 16+ GB GPU available | Future |

---

## LocalAI Configuration (stable-diffusion.cpp backend)

SD 3.5 Medium requires 4 separate GGUF files — the diffusion transformer + 3 text encoders.
Config at `config/models/sd35-medium.yaml`. Download via `make model-sd35-medium`.

### Required Files

| Component | File | Size | Purpose |
|-----------|------|------|---------|
| Diffusion model | `sd3.5_medium-Q8_0.gguf` | 3.19 GB | MMDiT-X transformer |
| CLIP-L | `clip_l-Q8_0.gguf` | 131 MB | Text encoder (small) |
| CLIP-G | `clip_g-Q8_0.gguf` | 739 MB | Text encoder (large) |
| T5-XXL | `t5xxl-Q4_0.gguf` | 2.75 GB | Text encoder (largest) |
| **Total** | | **~6.8 GB** | |

Source: [second-state/stable-diffusion-3.5-medium-GGUF](https://huggingface.co/second-state/stable-diffusion-3.5-medium-GGUF)

### LocalAI YAML Config

```yaml
name: sd35-medium
backend: stablediffusion-ggml
parameters:
  model: sd3.5_medium-Q8_0.gguf
step: 25
cfg_scale: 4.5
options:
  - "diffusion_model"
  - "clip_l_path:clip_l-Q8_0.gguf"
  - "clip_g_path:clip_g-Q8_0.gguf"
  - "t5xxl_path:t5xxl-Q4_0.gguf"
  - "sampler:euler"
  - "keep_clip_on_cpu:true"
  - "keep_vae_on_cpu:true"
  - "diffusion_flash_attn:true"
```

Key options:
- `diffusion_model` (bare flag) — tells LocalAI to use `--diffusion-model` mode (separate files)
- `keep_clip_on_cpu:true` — offloads 3 text encoders to RAM (~3.8 GB freed from VRAM)
- `keep_vae_on_cpu:true` — offloads VAE decode to CPU
- `diffusion_flash_attn:true` — flash attention saves ~600 MB VRAM on CUDA

### VRAM Usage with Offloading

| Configuration | GPU VRAM | RAM Usage |
|---------------|----------|-----------|
| Q8_0 + clip-on-cpu + vae-on-cpu + flash-attn | **~3.2 GB** | ~3.8 GB |
| Q4_0 + clip-on-cpu + vae-on-cpu + flash-attn | ~1.5 GB | ~3.8 GB |
| Q8_0 all on GPU | ~6.8 GB | minimal |

### Known Issues

- VAE attention burn bug (fixed in commit 4570715) — use current sd.cpp master
- `--clip-on-cpu` may crash on some setups ([#1210](https://github.com/leejet/stable-diffusion.cpp/issues/1210)) — fallback: remove the flag, use more VRAM
- Vulkan backend produces black images for SD3.x — use CUDA

### LocalAI v4.1.3 Compatibility Issue (Confirmed 2026-04-08)

**LocalAI v4.1.3's `stablediffusion-ggml` backend CANNOT load SD 3.5.**

The `libgosd-*.so` shared libraries ship an older stable-diffusion.cpp that fails
with `tensor 'first_stage_model.decoder.up.3.*' not in model file` — it expects
a VAE architecture that doesn't match SD 3.5's actual tensor layout.

Tested with:
- second-state GGUF (4 separate files) → missing VAE tensors
- gpustack all-in-one GGUF → segfault (incompatible tensor format)
- Official safetensors (5.1 GB with VAE) → same decoder.up.3 error

**Root cause:** The Go/CGo wrapper libraries (`libgosd-avx2.so` etc.) were compiled
from an older stable-diffusion.cpp that has an incomplete model definition for SD 3.5.
The tensors exist in the file (confirmed via safetensors header parsing — 26
`decoder.up.3` tensors present) but the loader can't map them.

### Workaround: Build sd.cpp from Source (Confirmed Working)

Built latest stable-diffusion.cpp (commit `8afbeb6`) from source with CUDA on the
host machine. The standalone `sd-cli` binary successfully generates SD 3.5 images.

**Build commands:**
```bash
cd /tmp && git clone --depth 1 https://github.com/leejet/stable-diffusion.cpp.git sd-cpp-build
cd sd-cpp-build && git submodule update --init --recursive
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DSD_CUDA=ON -DBUILD_SHARED_LIBS=ON -DCMAKE_CUDA_ARCHITECTURES="86"
make -j$(nproc)
```

**Test result (RTX 3060 Ti, 8GB VRAM):**
```
sd-cli -m sd3.5_medium.safetensors \
  --clip_l clip_l-Q8_0.gguf --clip_g clip_g-Q8_0.gguf --t5xxl t5xxl-Q4_0.gguf \
  --clip-on-cpu --vae-on-cpu --sampling-method euler --cfg-scale 4.5 --steps 25 \
  -H 512 -W 512 -p "a red sports car on a mountain road at sunset" \
  -o /tmp/sd35_test.png

Results:
  Text encoding (CPU):     16.8s
  Sampling (25 steps, GPU): 13.3s @ 1.88 it/s
  VAE decode (CPU):         36.4s
  Total:                    67s
  GPU VRAM:                 ~182 MB (with full CPU offloading)
  Output:                   512x512 PNG, 469 KB ✓
```

**Binaries built:** `/tmp/sd-cpp-build/build/bin/sd-cli` (211 MB), `sd-server` (213 MB)

### Paths Forward

1. **sd-server sidecar** — run sd.cpp's built-in HTTP server on a separate port,
   route image requests from AICP. Bypasses LocalAI's broken wrapper entirely.
2. **File LocalAI issue** — request updated sd.cpp in stablediffusion-ggml backend
3. **Wait for LocalAI v4.2+** — will likely update the backend
4. **ComfyUI sidecar** — Docker container with proven SD 3.5 support (alternative)

---

## P2P / Distributed Architecture Research

### LocalAI P2P Modes (NOT recommended)

| Mode | Purpose | Model Routing? | Status |
|------|---------|---------------|--------|
| P2P Worker (`p2p-llama-cpp-rpc`) | Shard one model across nodes | No | **Broken in v3.7+** |
| P2P Federation (`--p2p --federated`) | Load-balance across nodes | **No — random routing** | Experimental |
| Distributed Mode (PostgreSQL + NATS) | Production multi-node | **Yes — SmartRouter** | Production-grade |

### Why LocalAI P2P Doesn't Work For Us

**P2P Federation** picks a random node for each request. If Node A has Qwen3-8B and
Node B has SD 3.5, a chat request could land on Node B (no LLM) and fail. There is no
model-aware routing. [Discussion #3711](https://github.com/mudler/LocalAI/discussions/3711)
confirms this is broken for heterogeneous model setups, with zero maintainer response.

**P2P Worker** is broken since v3.7+ due to upstream llama.cpp RPC changes
([#7355](https://github.com/mudler/LocalAI/issues/7355)).

### Why AICP's Own Routing Is Better

AICP already has model-aware routing at the application layer:
- `aicp/core/cluster.py` — `find_best_node()` selects nodes by model + VRAM
- `aicp/core/router.py` — score-based routing with configurable thresholds
- `aicp/agent/server.py` — agent daemon on each node (HTTP API)
- `config/fleet.yaml` — fleet topology configuration
- Circuit breaker per backend prevents thundering herd
- DLQ captures failed requests for retry

This is lighter than LocalAI's Distributed Mode (no PostgreSQL, no NATS) and
already works with our existing infrastructure.

### Recommended Architecture

```
Machine 1 (192.168.40.10, 8GB VRAM):
├── LocalAI (port 8090) — Qwen3-8B, Gemma4-E2B, nomic-embed
├── AICP agent daemon (port 9100)
├── Routes image requests → Machine 2
└── No model swaps for image gen

Machine 2 (192.168.40.250, 8GB VRAM):
├── LocalAI (port 8090) — SD 3.5 Medium (dedicated)
├── AICP agent daemon (port 9100)
├── Accepts image requests from Machine 1
└── Can also run lightweight LLM when idle
```

Communication: AICP agent-to-agent over HTTP (existing `cluster.py` + `fleet.yaml`).
No P2P networking layer needed — simple HTTP routing at the application level.

---

## Download URLs

```bash
# SD 3.5 Medium GGUF (Q8_0, recommended for 8GB — 2.86 GB)
# Source: https://huggingface.co/city96/stable-diffusion-3.5-medium-gguf

# SD 3.5 Large GGUF (Q4_0 — 4.77 GB, tight on 8GB)
# Source: https://huggingface.co/city96/stable-diffusion-3.5-large-gguf

# SD 3.5 Large Turbo GGUF (Q4_0 — 4.77 GB, 4 steps)
# Source: https://huggingface.co/city96/stable-diffusion-3.5-large-turbo-gguf

# T5-XXL FP8 (text encoder, ~4.8 GB — for CPU offloading)
# Source: https://huggingface.co/comfyanonymous/flux_text_encoders
```

---

## Sources

### Official
- [Introducing Stable Diffusion 3.5 — Stability AI](https://stability.ai/news/introducing-stable-diffusion-3-5)
- [SD 3.5 Large (HuggingFace)](https://huggingface.co/stabilityai/stable-diffusion-3.5-large)
- [SD 3.5 Medium (HuggingFace)](https://huggingface.co/stabilityai/stable-diffusion-3.5-medium)
- [SD 3.5 Large Turbo (HuggingFace)](https://huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo)
- [Stability AI Community License](https://stability.ai/license)
- [NVIDIA TensorRT + SD 3.5](https://stability.ai/news/stable-diffusion-35-models-optimized-with-tensorrt-deliver-2x-faster-performance-and-40-less-memory-on-nvidia-rtx-gpus)

### GGUF Models
- [SD 3.5 Large GGUF (city96)](https://huggingface.co/city96/stable-diffusion-3.5-large-gguf)
- [SD 3.5 Medium GGUF (city96)](https://huggingface.co/city96/stable-diffusion-3.5-medium-gguf)
- [SD 3.5 Large Turbo GGUF (city96)](https://huggingface.co/city96/stable-diffusion-3.5-large-turbo-gguf)

### LocalAI / Backend
- [stable-diffusion.cpp (SD3.5 support)](https://github.com/leejet/stable-diffusion.cpp)
- [LocalAI Image Generation](https://localai.io/features/image-generation/)
- [LocalAI SD3 Issue #4144](https://github.com/mudler/LocalAI/issues/4144)
- [LocalAI VRAM Leak Bug #1498](https://github.com/mudler/LocalAI/issues/1498)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI API (SaladTechnologies)](https://github.com/SaladTechnologies/comfyui-api)

### Performance / Benchmarks
- [SD GPU Requirements Guide (SynpixCloud)](https://www.synpixcloud.com/blog/stable-diffusion-gpu-requirements-guide)
- [SD VRAM Reduced 40% (TweakTown)](https://www.tweaktown.com/news/105761/stable-diffusion-3-5-vram-requirement-reduced-by-40-to-run-on-more-geforce-rtx-gpus/index.html)
- [SD Benchmarks (Tom's Hardware)](https://www.tomshardware.com/pc-components/gpus/stable-diffusion-benchmarks)
- [Lambda Labs Inference Benchmark](https://lambda.ai/blog/inference-benchmark-stable-diffusion)
- [FastSD CPU (OpenVINO)](https://github.com/rupeshs/fastsdcpu)

### Fine-Tuning
- [SD 3.5 Large Fine-Tuning Tutorial](https://www.pelayoarbues.com/literature-notes/Articles/Stable-Diffusion-3.5-Large-Fine-Tuning-Tutorial)
- [Fine-tuning SD 3.5M (LearnOpenCV)](https://learnopencv.com/fine-tuning-stable-diffusion-3-5m/)
- [LoRA Training on RunPod (CivitAI)](https://civitai.com/articles/8485/training-a-stable-diffusion-35-lora-using-ai-toolkit-on-runpod)
- [Kohya sd-scripts LoRA Training](https://www.mintlify.com/kohya-ss/sd-scripts/training/lora-sd3)
- [SimpleTuner SD3 Discussion](https://github.com/bghira/SimpleTuner/discussions/619)
- [LoRA Training GPU Analysis (Puget Systems)](https://www.pugetsystems.com/labs/articles/stable-diffusion-lora-training-consumer-gpu-analysis/)

### Quantization
- [Quantized Models Comparison (GGUF vs NF4 vs FP8)](https://www.stablediffusiontutorials.com/2025/05/quantized-models-gguf-vs-nf4-vs-fp8-vs.html)
- [Memory-efficient Diffusion with Quanto (HuggingFace)](https://huggingface.co/blog/quanto-diffusers)
- [bitsandbytes Quantization (HuggingFace Diffusers)](https://huggingface.co/docs/diffusers/quantization/bitsandbytes)

### Comparisons
- [SD 3.5 vs FLUX (Modal)](https://modal.com/blog/best-text-to-image-model-article)
- [FLUX vs SD 3.5 (AI Photo Labs)](https://aiphotolabs.com/compare/flux-vs-stable-diffusion-35-complete-2025-performance-comparison/)
- [Getting Started with SD 3.5 (CivitAI)](http://education.civitai.com/getting-started-with-stable-diffusion-3-5/)
- [SD 3.5 Large Overview (sandner.art)](https://sandner.art/stable-diffusion-35-large-what-you-need-to-know/)
- [Dropping T5-XXL Impact (HuggingFace Discussion)](https://huggingface.co/stabilityai/stable-diffusion-3-medium/discussions/42)
