# Local LLM Hosting — The Full Layered Architecture + Hardware Tier Hierarchy

**Date**: 2026-04-24
**Purpose**: Educational reference. Understand every layer of local LLM hosting, every bottleneck at each layer, and how hardware generations stack from consumer (X299 at the bottom) to datacenter (8× H200 servers at the top).
**Scope**: Pure knowledge document. No decisions, no recommendations. Just the stack.

---

## 1. The layer cake

Every local LLM inference system is a stack of nine logical layers. A bottleneck in ANY layer limits overall throughput.

```
┌──────────────────────────────────────────────────────────┐
│  9. APPLICATION          (llama.cpp, vLLM, sglang, TGI)  │  ← what serves the model
├──────────────────────────────────────────────────────────┤
│  8. RUNTIME              (CUDA, cuDNN, BLAS, kernels)    │  ← math primitives
├──────────────────────────────────────────────────────────┤
│  7. OS KERNEL            (Linux vmap, mmap, page cache)  │  ← memory + I/O management
├──────────────────────────────────────────────────────────┤
│  6. VIRTUALIZATION       (WSL/HCS, Docker, VMs — or NONE)│  ← overhead (skippable!)
├──────────────────────────────────────────────────────────┤
│  5. GPU                  (VRAM, tensor cores, compute)   │  ← hot-path inference
├──────────────────────────────────────────────────────────┤
│  4. CPU                  (cores, SIMD, AMX, caches)      │  ← dispatch + CPU-side compute
├──────────────────────────────────────────────────────────┤
│  3. MEMORY               (DDR generation, channels, ECC) │  ← MoE expert access
├──────────────────────────────────────────────────────────┤
│  2. INTERCONNECT         (PCIe gen + lanes, NVLink)      │  ← bandwidth between layers
├──────────────────────────────────────────────────────────┤
│  1. STORAGE              (NVMe, SATA, RAID, disk)        │  ← model weights at rest
└──────────────────────────────────────────────────────────┘
```

### What each layer does during K2.6 inference

**Cold start** (model load, once per server launch):
- Layer 1: Storage → reads 318 GB GGUF file sequentially + selectively
- Layer 2: Interconnect → shuttles data from storage controller to RAM
- Layer 3: Memory → caches recently-read pages (page cache grows)
- Layer 4: CPU → handles every page fault, builds tensor index
- Layer 6: Virtualization tax (if WSL) — every syscall pays HCS overhead
- Layer 7: Kernel → coordinates all of the above
- Layers 5, 8, 9: initialize, allocate KV cache, open HTTP port

**Warm inference** (per token generated):
- Layer 9: Application routes the prompt, manages slot state
- Layer 8: Runtime orchestrates kernel launches
- Layer 5: GPU runs attention + active expert compute
- Layer 4: CPU runs routing decisions, tokenization, sampling
- Layer 3: Memory supplies MoE expert weights to CPU (critical path!)
- Layer 1: Storage supplies cold experts on cache misses
- Layers 2, 6, 7: carry the data flows

**The bottleneck shifts by phase**: cold start is storage + CPU bound; warm inference is GPU + memory bandwidth bound.

---

## 2. The hardware tier hierarchy

From lowest to highest. Each tier represents a generation + socket family + market segment.

### Tier -1 — Pre-2017 consumer
Examples: LGA1151 (Z170/Z270 Skylake), AM4 Zen 1 (X370/B350)
- DDR4-2400, dual-channel
- PCIe 3.0 x16 total (16 lanes from CPU)
- ~20 PCIe lanes chipset-side
- **LLM status**: too slow + too little PCIe. Can't even run Tier B models (Qwen3-32B) interactively.

### Tier 0 — X299 / HEDT Skylake-X (2017-2019) **← operator's current**
Examples: i7-7800X, i9-7900X, i9-9900X, i9-10980XE
- DDR4-2666 to 3200, **quad-channel** (meaningful — ~85 GB/s)
- PCIe 3.0, 44 lanes from CPU
- AVX-512 (first consumer with this)
- No AMX, no DLBoost
- **LLM status**: K2.6 Q2 runs at 0.3-1 tok/s (CPU-bound MoE). Enough to prove sovereignty, not enough for productive daily use.

### Tier 1 — Consumer mainstream 2020-2022
Examples: AM4 X570 (Zen 3 / Zen 3+), LGA1200 Z590 (Rocket Lake)
- DDR4-3200 to 4000, dual-channel (~51 GB/s)
- PCIe 4.0 x16 + 4 (CPU) + ~24 lanes chipset
- No AMX
- **LLM status**: faster CPU per core, but **dual-channel halves your memory bandwidth** vs X299. Paradoxically worse for MoE inference than quad-channel DDR4.

### Tier 2 — Consumer late 2022-2024
Examples: LGA1700 Z690/Z790 (Alder Lake / Raptor Lake), AM5 X670E (Zen 4)
- DDR5-5600 to 7200, dual-channel (~90-115 GB/s)
- PCIe 5.0 x16 (GPU slot) + 4 (one NVMe) + PCIe 4.0 chipset
- No AMX (consumer)
- **LLM status**: first generation where DDR5 memory bandwidth catches up to HEDT DDR4. Usable for K2.6 Q2 at 3-6 tok/s. Still dual-channel bottleneck.

### Tier 2b — Consumer latest 2024-2026
Examples: AM5 X870E (Zen 5), LGA1851 Z890 (Arrow Lake)
- DDR5-6400 to 8400+, dual-channel (~115-130 GB/s)
- PCIe 5.0 x16 GPU + more NVMe slots
- Arrow Lake introduces AVX10 but NO AMX (still workstation+)
- **LLM status**: marginal improvement over Tier 2. Same channel count is still the ceiling for MoE.

### Tier 3 — Prosumer workstation 2020-2023
Examples: sTRX4 Threadripper 3000, sWRX8 Threadripper Pro 3000/5000, W680 Xeon W-1300/2400
- **Quad-channel DDR4 ECC** (Threadripper non-Pro) or **8-channel** (Threadripper Pro, Xeon W)
- PCIe 4.0 or 5.0
- 64-128 PCIe lanes (Threadripper Pro has 128)
- Older than Sapphire Rapids → no AMX yet
- **LLM status**: 8-channel DDR4 on Threadripper Pro gives ~170 GB/s → 2× HEDT X299, ~4× consumer. K2.6 Q2 at 8-15 tok/s here.

### Tier 4 — Modern workstation 2023-2026
Examples: sTR5 Threadripper 7000 (TRX50/WRX90), LGA4677 Xeon W-2400/3400 (Sapphire Rapids)
- **4-channel or 8-channel DDR5-5200 ECC** (TRX50 is 4-channel, WRX90 is 8-channel, Xeon W-3400 is 8-channel)
- PCIe 5.0, 112-128 lanes
- **Xeon W-3400 has AMX** (10× INT8 matmul acceleration) — Threadripper Pro doesn't
- **LLM status**: 8-channel DDR5 = ~330 GB/s. K2.6 Q2 at 15-25 tok/s. With AMX, closer to 30 tok/s.

### Tier 5 — Entry-level datacenter CPU 2022-2026
Examples: SP5 EPYC 9004/9005 Genoa/Turin (AMD), LGA4677 Xeon Scalable 4th/5th gen (Intel)
- **12-channel DDR5-4800+** (EPYC) or **8-channel DDR5-5600+** (Xeon SPR/EMR)
- PCIe 5.0 with 128+ lanes
- Up to 96 cores (EPYC Turin) or 64 cores (Xeon EMR)
- Intel has AMX; AMD relies on core count + bandwidth
- Dual-socket supported — doubles memory channels and cores
- **LLM status**: memory bandwidth > 400 GB/s per socket. K2.6 at 30-60 tok/s single-socket.

### Tier 6 — Modern datacenter 2024+
Examples: LGA7529 Xeon 6 Granite Rapids, AMD EPYC Turin Dense (Bergamo successors)
- **12-channel MRDIMM** (Intel GR) — up to 8800 MT/s, ~840 GB/s per socket
- Dual-socket = 1.5-1.7 TB/s aggregate memory bandwidth
- Many more cores (GR up to 128 P-cores, AMD EPYC up to 192)
- AMX enhanced on Granite Rapids
- Up to 2-4 TB RAM per socket
- **LLM status**: 100+ tok/s on K-class models. Memory bandwidth stops being the dominant bottleneck.

### Tier 7 — GPU datacenter
Examples: 8× A100 80GB (2020), 8× H100 80GB (2022), 8× H200 141GB (2024), 8× B200/GB200 (2025)
- HBM3/HBM3e memory, 3.35-8 TB/s per GPU
- NVLink 4th/5th gen: 900 GB/s - 1.8 TB/s GPU-to-GPU
- Typically paired with Tier 5/6 dual-socket CPUs
- **LLM status**: Moonshot's official K2.6 serving config = 8× H200 or 8× L20 + dual Xeon SPR. **640 tok/s prefill, 24 tok/s/user at 48-way concurrency.**

---

## 3. Each layer in depth — what it does, where it bottlenecks

### Layer 1: Storage

**Role**: persistent home of the model weights. Read-heavy during cold start, also read-heavy during inference (MoE expert fetches from cold storage).

| Tier | Physical | Raw throughput | Real throughput |
|---|---|---|---|
| SATA SSD (SATA III) | 6 Gbps | ~550 MB/s | 500 MB/s |
| PCIe 3.0 x4 NVMe | 32 Gbps | ~3.5 GB/s | 3 GB/s |
| PCIe 4.0 x4 NVMe | 64 Gbps | ~7 GB/s | 6-6.5 GB/s |
| PCIe 5.0 x4 NVMe | 128 Gbps | ~14 GB/s | 11-13 GB/s |
| PCIe 5.0 x4 NVMe RAID 0 ×2 | doubled | ~25 GB/s | 15-22 GB/s |
| PCIe 5.0 x4 NVMe RAID 0 ×4 | doubled again | ~50 GB/s | 30-40 GB/s |

**Key bottlenecks at this layer**:
- **PCIe generation of the platform** caps the NVMe (your X299 is PCIe 3.0 — even Gen4/Gen5 drives run at 3.0 speeds)
- Number of NVMe slots for RAID (consumer: 2-3 slots; workstation: 4-7 slots; datacenter: 8-32 slots)
- PCIe lane sharing (consumer boards share lanes between GPU + NVMe — getting a second full x4 NVMe requires dropping GPU to x8)
- SSD controller thermals (sustained write throttles after ~30 sec on cheap drives)
- **NTFS + VHDX (Windows layer) cuts practical throughput 30-40%** vs native ext4 on raw block device

**LLM-specific**: for a 318 GB model, going from 3 GB/s to 15 GB/s NVMe RAID cuts cold-load from ~2 min to ~20 sec at optimal; real-world load time also limited by CPU.

### Layer 2: Interconnect (PCIe + NVLink)

**Role**: data pipes between CPU, RAM, GPU, storage.

| Interconnect | Generation | Per-lane | x16 | x4 |
|---|---|---|---|---|
| PCIe 3.0 | 2011+ | 985 MB/s | 16 GB/s | 4 GB/s |
| PCIe 4.0 | 2019+ | 2 GB/s | 32 GB/s | 8 GB/s |
| PCIe 5.0 | 2022+ | 4 GB/s | 64 GB/s | 16 GB/s |
| PCIe 6.0 | 2026+ | 8 GB/s | 128 GB/s | 32 GB/s |
| NVLink 3 | A100 | — | — | 600 GB/s GPU-GPU |
| NVLink 4 | H100 | — | — | 900 GB/s GPU-GPU |
| NVLink 5 | B200 | — | — | 1.8 TB/s GPU-GPU |

**Key bottlenecks**:
- **Consumer platforms have ~20-28 PCIe lanes from CPU** (limits multi-device setups)
- Workstation platforms have 64-128 lanes (multi-GPU + multi-NVMe without sharing)
- Datacenter servers have 128+ lanes (dual-socket doubles this)
- **NVLink only exists on datacenter GPUs** — consumer RTX cards have no NVLink since RTX 30-series
- PCIe lane partitioning (bifurcation) controlled by motherboard — consumer boards often hide this behind BIOS settings

**LLM-specific**: for multi-GPU tensor-parallel inference, NVLink matters enormously. Without it, GPU-to-GPU traffic goes via PCIe through the CPU, adding 10-50× latency per sync.

### Layer 3: Memory (DRAM)

**Role**: holds the active model working set. For MoE models, every token requires fetching 8 active experts' weights from RAM.

| Generation | Typical speed | Bandwidth per channel | Dual-channel | Quad-channel | 8-channel |
|---|---|---|---|---|---|
| DDR4-2666 | standard HEDT era | 21 GB/s | 42 | **85 (your X299)** | 170 |
| DDR4-3200 | mid | 25.6 GB/s | 51 | 102 | 205 |
| DDR4-3600 (OC) | enthusiast | 28.8 GB/s | 57 | 115 | 230 |
| DDR5-4800 | server standard | 38 GB/s | 76 | 154 | **307** |
| DDR5-5200 | ECC RDIMM | 42 GB/s | 84 | 167 | **333** |
| DDR5-6000 | consumer enthusiast | 48 GB/s | 96 | 192 | 384 |
| DDR5-7200 | consumer extreme | 58 GB/s | 115 | — | — |
| DDR5-8800 MRDIMM | server next-gen | 70 GB/s | — | — | **840 per 12-channel** |

**ECC vs non-ECC**: ECC costs ~10-15% premium, catches single-bit flips (critical for 24/7 workstation/server). Required on server platforms (EPYC/Xeon W). Optional on consumer.

**RDIMM (Registered DIMM)**: buffered, higher capacity (up to 256 GB per DIMM), needed for workstation/server. Consumer uses UDIMM (unbuffered, max 48-64 GB per DIMM).

**Key bottlenecks**:
- **Channel count** is the biggest lever. Consumer = 2 channels. HEDT = 4. Workstation = 8. Server = 12.
- DIMM speed matters less than channel count once you're past DDR5
- RAM capacity: consumer max 192-256 GB, workstation 2 TB, server 4-6 TB per socket

**LLM-specific**: MoE expert fetching during inference is memory-bandwidth-bound. Going from 85 GB/s (X299) to 333 GB/s (8-channel DDR5) is a 4× speedup on this specific kernel. That's why Moonshot's datacenter spec includes 8-channel Sapphire Rapids.

### Layer 4: CPU

**Role**: orchestrates everything. Does tokenization, sampling, routing decisions, and handles CPU-side MoE expert compute.

**Critical CPU features for LLM inference**:

| Feature | Intel | AMD | Impact |
|---|---|---|---|
| AVX-512 (vector math) | since Skylake-X/SP | since Zen 4 | 5-10× speedup over AVX2 |
| **AMX (matrix extensions)** | Sapphire Rapids+ (2023+) | **not available** | **10× speedup on INT8 matmul** (critical for MoE) |
| SVE2 (ARM) | — | — | Apple/Graviton equivalent of AMX |
| BF16 native support | Ice Lake SP+ | Zen 3+ | 2× inference throughput |
| Core count | varies | varies | More helps parallel expert compute |
| Per-core IPC | Alder Lake+ competitive | Zen 4+ competitive | Matters for routing/sampling |

**Key bottlenecks**:
- **No AMX = no shortcut for INT8 matmul**. On AMX-capable CPUs, llama.cpp runs MoE expert compute 10× faster.
- **Single-threaded mmap handling**: during load, llama.cpp opens the file single-threaded. CPU core speed matters here.
- **Cache hierarchy**: larger L2/L3 caches help expert hot-path (L3 > 128 MB on workstation CPUs)
- **NUMA**: on dual-socket servers, expert placement across sockets matters (cross-socket memory access is 2-3× slower)

**LLM-specific**: for MoE inference with CPU-resident experts, Xeon W-3475X (Sapphire Rapids with AMX) is currently the king per-dollar. AMD Threadripper Pro compensates with more cores + more bandwidth but loses the AMX edge.

### Layer 5: GPU

**Role**: runs the hot path (attention layers, KV cache, currently-loaded experts).

| GPU | VRAM | Memory BW | Compute (FP16) | Gen |
|---|---|---|---|---|
| RTX 2080 Ti | 11 GB | 616 GB/s GDDR6 | 13 TFLOPS | Turing (2018) |
| RTX 3090 | 24 GB | 936 GB/s GDDR6X | 35 TFLOPS | Ampere (2020) |
| RTX 4090 | 24 GB | 1 TB/s GDDR6X | 82 TFLOPS | Ada (2022) |
| RTX 5090 | 32 GB | 1.8 TB/s GDDR7 | 105 TFLOPS | Blackwell (2025) |
| A100 80GB | 80 GB | 2 TB/s HBM2e | 78 TFLOPS (FP16), 312 (TF32) | Ampere (2020) |
| H100 80GB | 80 GB | 3.35 TB/s HBM3 | 197 TFLOPS (FP16), 989 (FP8) | Hopper (2022) |
| H200 141GB | 141 GB | 4.8 TB/s HBM3e | same as H100 | Hopper refresh (2024) |
| B200 192GB | 192 GB | 8 TB/s HBM3e | 2,250 TFLOPS (FP4) | Blackwell (2025) |

**Key bottlenecks**:
- **VRAM capacity** first — can you fit what needs to be resident
- **Memory bandwidth** second — once it fits, how fast can you feed the compute
- **FP8/FP4 compute** matters for quantized models (H100+ only)
- **Tensor cores generations** differ — Ampere → Hopper is ~3× on FP8, Hopper → Blackwell is 2× again

**LLM-specific for K2.6**: needs ~40-60 GB VRAM for hot path at 32K context. Fits comfortably on 1× H100 80GB. On consumer 24 GB cards (RTX 4090/5090), must aggressively offload to CPU — caps throughput.

### Layer 6: Virtualization

**Role**: (where applicable) isolates workloads from host OS. **Costs performance**.

| Virtualization | Overhead for LLM serving |
|---|---|
| **Native Linux** | 0% (baseline) |
| WSL2 (Hyper-V) | 20-40% on I/O-heavy workloads, 5-15% on pure compute |
| Docker on native Linux | <5% |
| Docker on WSL2 | compounds WSL2 overhead |
| KVM/QEMU | 5-15% |
| VMware ESXi | similar to KVM |

**Key points**:
- Native Linux = best performance. Used by all serious local-LLM hosts.
- **WSL2 is the biggest overhead source** in the operator's current stack (~40% lost on storage I/O specifically)
- Container runtime (Docker, Podman) on native Linux is essentially free
- GPU passthrough to VMs requires VFIO setup, adds another layer of overhead

**LLM-specific**: switching from WSL2 to native Linux on the same hardware = 30-50% speed gain on cold load, 10-20% gain on warm inference.

### Layer 7: OS Kernel

**Role**: manages memory (page cache for mmap), I/O (block device queuing), process scheduling.

**Key tunables for LLM serving**:
- `vm.swappiness` (0-100, default 60): lower = prefer dropping page cache over swapping. Set to 10-20 for LLM workloads.
- `vm.vfs_cache_pressure` (0-200, default 100): how aggressive the kernel evicts inode/dentry cache. For mmap-heavy workloads, 50-75.
- `madvise()` hints (per-application): tell kernel whether pages are sequential, random, or willneeded
- Transparent hugepages (THP) — can help or hurt depending on workload; default "madvise" mode usually safe
- I/O scheduler (mq-deadline, kyber, bfq): for NVMe, `none` (multi-queue direct) is optimal

**Key bottlenecks**:
- Default kernel settings are general-purpose, not LLM-optimized. Tuning can yield 5-15% on mmap-heavy loads.
- Kernel version matters: newer kernels (6.x+) have better NVMe handling, better io_uring support

**LLM-specific**: `--mlock` in llama.cpp pins model pages in RAM (no eviction), at the cost of memory capacity. Useful on systems with enough RAM.

### Layer 8: Runtime (CUDA / BLAS / kernels)

**Role**: provides the mathematical primitives.

| Runtime | Version relevant | Key feature |
|---|---|---|
| CUDA | 12.0+ | H100 support, FP8 |
| CUDA | 13.0+ | Blackwell support, FP4 |
| cuDNN | 9.0+ | Fused attention, flash attention |
| cuBLAS | with CUDA | GEMM |
| MKL/oneMKL | recent | AMX codepaths |
| OpenBLAS | any | fallback, slower than MKL |

**Key points**:
- **CUDA version must match GPU generation** — can't run H100-specific code on RTX 2080 Ti
- **cuDNN version couples with sglang/vLLM versions** — mismatches cause crashes
- Runtime is typically set by the application (llama.cpp handles this transparently)

### Layer 9: Application (inference engine)

**Role**: top of the stack. Loads model, serves HTTP, orchestrates inference.

| Engine | Best for | Memory profile | Concurrency |
|---|---|---|---|
| **llama.cpp** | Consumer hardware, GGUF | Low (~20-30 GB startup) | Limited (server variant works) |
| **vLLM** | Datacenter, safetensors | High (~100 GB+ for frontier) | Excellent (PagedAttention) |
| **sglang** | Datacenter, complex scheduling | High | Excellent (RadixAttention) |
| **TGI (HF)** | Production APIs | Medium-high | Good |
| **TensorRT-LLM** | Nvidia-optimized | Medium | Excellent, but complex setup |
| **exllama/ExLlamaV2** | Consumer GPU-only | Medium | Limited |
| **KTransformers (classic)** | CPU-offload MoE | Low | Basic |
| **sglang+kt-kernel** | Datacenter MoE with AMX | High | Excellent |

**Key points**:
- **Memory profile differs 3-5× between engines** for the same model
- Datacenter engines (vLLM, sglang) pre-allocate aggressively — good for sustained high concurrency, bad for "quick serve on 64 GB consumer"
- llama.cpp is the consumer standard for a reason: flexible, light, reads GGUF directly

---

## 4. Tier × layer bottleneck matrix

Where does the bottleneck LIVE at each hardware tier? Reading the table: at Tier X, if you upgrade Y, you hit Z next.

| Tier | Dominant bottleneck for K2.6 Q2 | Secondary | Approximate ceiling |
|---|---|---|---|
| -1 (pre-2017) | All layers simultaneously | — | Doesn't run productively |
| 0 (X299, your current) | Layer 2 (PCIe 3.0) + Layer 6 (WSL) | Layer 4 (old CPU IPC) | **0.3-1 tok/s** |
| 1 (mainstream 2020) | Layer 3 (dual-channel DDR4) | Layer 5 (VRAM cap) | 2-4 tok/s |
| 2 (Z790 consumer) | Layer 3 (dual-channel DDR5) | Layer 5 (VRAM cap) | 4-8 tok/s |
| 3 (Threadripper Pro 5000) | Layer 5 (VRAM cap for frontier) | Layer 4 (no AMX) | 10-18 tok/s |
| 4 (Xeon W-3475X SPR) | Layer 5 (VRAM cap) | Layer 1 (storage for cold experts) | 25-40 tok/s |
| 5 (EPYC Turin / Xeon EMR dual-socket) | Layer 5 (VRAM for frontier) | Layer 2 (NVLink vs PCIe for multi-GPU) | 50-100 tok/s |
| 6 (Granite Rapids + 8× H100) | Layer 9 (application batching) | Layer 2 (NVLink saturation) | 300+ tok/s single model; multi-model |

---

## 5. Example workload: K2.6 on each tier, end-to-end

### Tier 0 — X299 + dual 2080 Ti (your today)
- **Cold load**: 17-40 min (PCIe 3.0 + WSL mmap + old CPU)
- **Warm inference (-ngl 0)**: 0.3 tok/s
- **Concurrent users**: 1, slow
- **Dominant bottleneck**: storage virtualization + CPU mmap handling
- **Biggest single upgrade**: ditch WSL, go native Linux → 30-50% gain for free

### Tier 2 — Z790 consumer + DDR5 + RTX 5090
- **Cold load**: 5-10 min (PCIe 5.0 NVMe + modern CPU, still WSL)
- **Warm inference**: 5-8 tok/s (dual-channel DDR5 is the ceiling for MoE)
- **Concurrent users**: 1
- **Dominant bottleneck**: Layer 3 (memory channels)
- **Biggest single upgrade**: move to 8-channel workstation platform

### Tier 4 — TRX50 Threadripper Pro 7965WX + 256 GB DDR5 + 2× RTX 5090
- **Cold load**: 2-5 min
- **Warm inference**: 15-25 tok/s
- **Concurrent users**: 2-3 with minor latency
- **Dominant bottleneck**: Layer 5 (VRAM for sustained long context)
- **Biggest single upgrade**: add H100 for GPU capacity

### Tier 5 — EPYC Turin 9654 (96c, 12-channel DDR5) + 1 TB RAM + 2× H100
- **Cold load**: ~1 min (once; whole model fits in page cache permanently after)
- **Warm inference**: 40-80 tok/s
- **Concurrent users**: 5-10 smoothly
- **Dominant bottleneck**: Layer 9 (application scheduler — vLLM/sglang becomes the ceiling)
- **Biggest upgrade**: 8× H100 for full Moonshot concurrency spec

### Tier 7 — 8× H200 141GB + dual Xeon SPR + 2 TB RAM + PCIe 5.0 NVMe RAID
- **Cold load**: <30 sec (full model in HBM3e + host RAM)
- **Warm inference**: 250+ tok/s aggregate, 30 tok/s per concurrent user at 48-way
- **Concurrent users**: 48+ per Moonshot's published config
- **Dominant bottleneck**: None local — network or application design becomes the bottleneck
- **This is Moonshot's official serving tier.**

---

## 6. The memory-bandwidth-per-dollar ranking

For MoE inference specifically, memory bandwidth dominates cost-effectiveness. Ranked:

| Platform | $/GB/s (CAD) | GB/s total | Practical use |
|---|---|---|---|
| Consumer AM5 Zen 5 | ~$8/GB/s | ~130 | Home enthusiast LLM |
| TRX50 (4-channel DDR5) | ~$12/GB/s | ~165 | Prosumer |
| LGA1700 Z790 DDR5 | ~$10/GB/s | ~115 | Home enthusiast |
| WRX90 Threadripper Pro 7000 | ~$20/GB/s | ~330 | Serious workstation |
| W790 Xeon W-3400 SPR | ~$18/GB/s | ~310 + AMX bonus | Workstation with inference edge |
| SP5 EPYC Turin single-socket | ~$25/GB/s | ~460 (12-channel DDR5-4800) | Entry datacenter |
| Intel Granite Rapids with MRDIMM | ~$35/GB/s | ~840 | Datacenter |
| 1× H100 80GB (GPU-only) | ~$400/GB/s | 3,350 | GPU-bound workloads |

The GPU is ~20× more expensive per GB/s of bandwidth than server CPU RAM. That's why MoE models try to keep most weights in CPU RAM + hot path on GPU.

---

## 7. Quick-reference: when does each tier become insufficient?

For K2.6 Q2 workload specifically:

- **Single user, occasional use**: Tier 2 (Z790 DDR5) is enough
- **Single user, daily driver**: Tier 4 (Threadripper Pro 7965WX or Xeon W-3475X)
- **Small team (2-5 users)**: Tier 4 + add H100; or Tier 5 entry
- **Small fleet (10 agents)**: Tier 5 (EPYC Turin) + 2× H100
- **Production API serving**: Tier 7 datacenter (8× H100/H200)
- **300-agent swarm**: Tier 7, full Moonshot config

---

## 8. Summary reference card

```
                                    K2.6 Q2 tok/s
Tier -1 (pre-2017 consumer)         0.01-0.1    — unusable
Tier 0 (X299, your current)         0.3-1       — sovereignty fallback only
Tier 1 (mainstream 2020)            1-3         — marginal
Tier 2 (Z790/X670E DDR5)            3-8         — personal usable
Tier 3 (TR Pro 3000/5000)           8-15        — workstation capable
Tier 4 (TRX50 / W790 SPR)           15-30       — interactive daily driver
Tier 5 (EPYC Turin/Xeon EMR)        30-80       — multi-user / small fleet
Tier 6 (Granite Rapids + B200)      80-200      — pre-production
Tier 7 (8×H100 NVLink)              250+/aggreg — Moonshot spec

Operator cost to acquire NEW (CAD):
Tier 0      already owned    
Tier 1      $1-3k            
Tier 2      $15-20k          
Tier 3      $8-15k (used Threadripper Pro)
Tier 4      $25-35k          
Tier 5      $60-100k         
Tier 6      $150-250k        
Tier 7      $250-500k+
```

---

## 9. The 30× story, precisely

Operator's current Tier 0 → hypothetical end-tier (a realistic build around Tier 4-5 crossover):

| Layer | Current | End-tier | Improvement factor |
|---|---|---|---|
| Storage (effective) | ~500 MB/s | ~15 GB/s (PCIe 5 NVMe RAID 0) | 30× |
| Memory bandwidth | 85 GB/s | 330-460 GB/s | 4-5× |
| CPU single-thread | ~old IPC | modern + AMX | 5-10× on specific kernels |
| GPU inference | ~13 TFLOPS FP16 | ~700 TFLOPS FP8 (H100) | 50× |
| Virtualization tax | WSL ~40% | native Linux 0% | 1.4-2× reclaim |

**Blended improvement**: 30-100× depending on workload. Your "30×" estimate is correct as an end-to-end average across load + inference phases.

---

## 10. The key knowledge (one-page distillation)

1. **LLM serving has 9 layers**. A weakness in any layer caps the whole stack.
2. **X299 is bottom-tier in 2026**. Quad-channel DDR4 was strong 2017-2019; now it's below consumer DDR5 dual-channel for most workloads except MoE (where more channels still win).
3. **Memory channels > memory speed** for MoE inference. 8-channel DDR5 at 5200 beats 2-channel DDR5 at 7200.
4. **PCIe generation gates everything downstream**. PCIe 3.0 vs 5.0 alone = 4× on storage and interconnect.
5. **AMX is Intel's secret weapon** for LLM inference — no AMD equivalent. Sapphire Rapids Xeon W is the sweet spot.
6. **WSL costs ~40% on I/O-heavy loads**. Native Linux is the single biggest free upgrade.
7. **VRAM capacity is the GPU bottleneck**, not just bandwidth. K2.6's hot path needs 60+ GB VRAM; consumer cards max at 32 GB.
8. **Datacenter GPUs (H100/H200) have 10-50× the TFLOPS of consumer cards** — not just more VRAM.
9. **NVLink only exists on datacenter GPUs**. Multi-consumer-GPU setups are capped by PCIe, which cripples tensor-parallel.
10. **Every upgrade tier has a clear next-bottleneck**. You don't skip tiers — each tier teaches you where the next bottleneck will be before you spend to move it.

---

## 11. Further reading (pointers, not external links)

- For hardware purchasing: `HARDWARE-BUILD-SCENARIOS-2026-04-24.md`
- For cloud alternatives instead of hardware: `MODEL-ECOSYSTEM-FULL-MAP-2026-04-24.md`
- For scaling projections: `SCALING-PROJECTION-5YR-2026-04-24.md`
- For decision framework: `PERSPECTIVE-AI-INFRASTRUCTURE-DECISION-2026-04-24.md`
- For the storage tier architecture specifically: `docs/STORAGE.md`
- For today's concrete setup: `SESSION-2026-04-24-HANDOFF.md`
- For why we went through 2 days on the wrong path: `POSTMORTEM-2026-04-24-k26-local-wrong-path.md`

---

*Educational reference. Specs based on publicly-documented platform architectures as of 2026-04. Future generations (PCIe 6.0, DDR5-10000, B200/GB300 successors) will shift numbers but not the layered structure.*
