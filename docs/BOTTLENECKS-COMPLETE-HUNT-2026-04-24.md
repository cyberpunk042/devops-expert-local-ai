# Complete Bottleneck Hunt — Every Layer, Every Component, Every Failure Mode

**Date**: 2026-04-24
**Purpose**: Exhaustive catalogue of bottlenecks, limitations, capabilities, and performance numbers everywhere in local LLM hosting. Companion to `LOCAL-HOSTING-ARCHITECTURE-2026-04-24.md` (which covered the tier hierarchy at a high level). This doc goes deep into specifics — single-threaded code paths, thermal throttling, cache coherency, DMI links, NUMA effects, every hidden choke point.

**Structure per entry**:
- **Bottleneck**: what slows throughput
- **Limitation**: what becomes impossible
- **Capability**: what the component unlocks
- **Performance**: measured or expected numbers

---

## 1. STORAGE LAYER — Deep dive

### 1.1 HDD (spinning rust)

- **Bottleneck**: rotational latency (7200 RPM = 8 ms avg seek, 5400 RPM = 11 ms)
- **Limitation**: cannot serve mmap'd LLM models practically — each expert fetch would be milliseconds instead of microseconds
- **Capability**: massive cheap capacity (20+ TB), good for cold archives
- **Performance**: sequential read ~200-250 MB/s; random 4K ~150 IOPS → basically useless for LLM

### 1.2 SATA III SSD

- **Bottleneck**: SATA protocol hard cap at 6 Gbps → ~550 MB/s ceiling
- **Limitation**: not enough bandwidth for frontier-model cold loads under 10 minutes
- **Capability**: 10-100× HDD random IOPS, decent for smaller models (< 30 GB)
- **Performance**: sequential read 500-560 MB/s, random 4K 50-100k IOPS
- **Hidden gotcha**: DRAM-less SATA SSDs lose 3-5× on random IOPS vs DRAM-cached ones

### 1.3 PCIe 3.0 NVMe (your current WD_BLACK SN770 bottleneck)

- **Bottleneck**: PCIe 3.0 x4 = 32 Gbps = ~3.5 GB/s theoretical ceiling regardless of drive Gen
- **Limitation**: even plugging a Gen5 SSD into this platform caps at Gen3 speed — you can't cheat the lane generation
- **Capability**: 6-10× SATA speed; first tier with realistic LLM mmap potential
- **Performance**: sequential read 3.0-3.4 GB/s sustained; random 4K ~500k IOPS
- **Hidden gotchas**:
  - **TLC/QLC thermal throttling**: after ~30-60 seconds of sustained writes at high rate, controller throttles to 500-800 MB/s
  - **SLC cache exhaustion**: drives have a small fast SLC cache (100-300 GB); writes beyond that drop to native TLC/QLC speed (~800 MB/s on QLC)
  - **DRAM-less NVMes** (host memory buffer) lose 30-50% on random reads
  - **Controller generations**: a Gen3 drive's controller may still be optimized for smaller queue depths; Gen4/5 controllers handle QD32 better
  - **Write amplification**: with poorly-aligned I/O, you can get 1.5-2× physical writes per logical write

### 1.4 PCIe 4.0 NVMe

- **Bottleneck**: PCIe 4.0 x4 = 64 Gbps = ~7 GB/s theoretical
- **Limitation**: still single-drive; cannot exceed x4 lanes per drive
- **Capability**: 2× Gen3 bandwidth, enough for most LLM workloads
- **Performance**: top Gen4 drives (990 Pro, Firecuda 530): sequential read 7 GB/s, random 4K ~1M IOPS
- **Hidden gotcha**: at 7 GB/s, the **controller and NAND become the next bottleneck**, not PCIe. Cheap Gen4 drives only hit 5 GB/s.

### 1.5 PCIe 5.0 NVMe

- **Bottleneck**: PCIe 5.0 x4 = 128 Gbps = ~14 GB/s theoretical
- **Limitation**: **thermal** — Gen5 drives run HOT (8-12W under load), need active cooling (heatsinks + fans) or they throttle below Gen4 speeds
- **Capability**: 2× Gen4; approaches DDR4 bandwidth for sequential
- **Performance**: Samsung 9100 Pro / Crucial T705: sequential read 13-14 GB/s; random 4K ~1.5M IOPS
- **Hidden gotchas**:
  - **Heatsinks on motherboard M.2 slots may not be adequate** — aftermarket is often needed
  - **4KB random reads are NOT 2× Gen4** — latency improvements don't scale with bandwidth
  - **Power envelope**: Gen5 drives at 12W mean 4× Gen5 drives in a workstation = 48W just for storage heat

### 1.6 NVMe RAID 0

- **Bottleneck**: PCIe lane budget of the platform (how many x4 slots can run simultaneously), stripe overhead in the RAID implementation
- **Limitation**: RAID 0 = no redundancy; one drive failure = lose all data
- **Capability**: linear bandwidth scaling for sequential reads (90%+ efficiency at low stripe sizes)
- **Performance**: 2× Gen5 in RAID 0 = ~25 GB/s sequential; 4× Gen5 = ~50 GB/s (if lanes allow)
- **Hidden gotchas**:
  - **Software RAID (mdadm) on Linux**: CPU does the stripe math, adds latency (~1-2 μs per op)
  - **Hardware RAID (motherboard Intel VROC, AMD RAIDXpert)**: free, but tied to specific chipset; often has boot-time setup friction
  - **Random I/O scales less than sequential** (~1.3-1.6× per drive) because of stripe-boundary penalty
  - **Mixing drive models in RAID 0**: slower drive caps the stripe; homogeneous arrays strictly better

### 1.7 NAND flash fundamentals (the underlying storage)

- **Bottleneck**: NAND program-erase cycles (P/E) finite — TLC 3,000-5,000 cycles; QLC 1,000 cycles; SLC 100,000+
- **Limitation**: write endurance of typical consumer NVMe ~600-1200 TBW; sustained writes at 5 GB/s = 432 TB/day → wears a 600 TBW drive in < 2 days
- **Capability**: current NAND reaches 200+ layers, enabling 4TB+ consumer drives
- **Performance**: 
  - **Read latency**: 30-50 μs per page (~16 KB)
  - **Write latency**: 200-700 μs per page (asymmetric — writes are slow)
  - **Erase latency**: 2-10 ms per block
- **Hidden gotcha**: LLM workloads are read-heavy. Write endurance usually isn't the limit — read throughput is.

---

## 2. INTERCONNECT LAYER — Deep dive

### 2.1 PCIe lanes from CPU (direct)

- **Bottleneck**: CPU SKU determines max lanes. Consumer 16+4 = 20 lanes. HEDT (X299 at 44 lanes). Workstation (WRX90 at 128). Server (EPYC SP5 at 128 per socket, 160 if dual-socket).
- **Limitation**: can't add devices beyond the lane budget. A PCIe 5.0 x16 slot + PCIe 5.0 x4 NVMe = 20 lanes consumed → no more x4 devices on a 20-lane consumer CPU.
- **Capability**: CPU-direct lanes are full-speed, no DMI bottleneck
- **Performance**: Gen5 x16 = 128 GB/s; Gen5 x4 = 16 GB/s
- **Hidden gotchas**:
  - **PCIe slot labels lie**. A "PCIe x16" slot may only be electrically x8 or x4. Read the motherboard manual's block diagram.
  - **Lane bifurcation**: the CPU may support x8/x8 or x4/x4/x4/x4 bifurcation, but the board may not expose it. Custom riser/bifurcation cards can unlock it.
  - **Retimers/redrivers on long traces**: motherboard vendors add these for signal integrity on long PCIe traces, but they add 10-30 ns latency each.

### 2.2 Chipset PCIe lanes (consumer/HEDT)

- **Bottleneck**: **DMI link from CPU to chipset is the shared bottleneck**. DMI 4.0 (Intel) / Infinity Fabric (AMD) = typically **~8 GT/s x8 = 16 GB/s total** for ALL chipset devices combined.
- **Limitation**: 20+ chipset PCIe lanes share the DMI bandwidth. 4× Gen4 NVMes on chipset = 28 GB/s potential but capped at 16 GB/s DMI.
- **Capability**: extra connectivity for non-bandwidth-critical devices (USB, SATA, audio, slower NVMe)
- **Performance**: full lane width only on low-concurrency workloads; under contention, effective throughput drops to ~1/N of DMI with N simultaneous users
- **Hidden gotcha**: **do NOT put your primary NVMe on a chipset slot if CPU slots are available.** Even when the chipset slot is labeled PCIe 4.0 x4, it bottlenecks through DMI.

### 2.3 DMI link (Intel CPU↔chipset) / Infinity Fabric I/O die links (AMD)

- **Bottleneck**: Intel DMI 4.0 = PCIe 4.0 x8 = ~16 GB/s (effectively ~15 GB/s). Newer Z890 has DMI 5.0 = 32 GB/s.
- **Limitation**: cross-chip traffic (GPU accessing storage via chipset) routes through DMI, capped.
- **Capability**: acceptable for one chipset NVMe + modest I/O peripherals
- **Performance**: Z790 ~16 GB/s shared; Z890 ~32 GB/s shared
- **Hidden gotcha**: with AMD Zen 4 ryzen, I/O die communicates over Infinity Fabric at ~2 GHz with variable efficiency; workstation TR Pro dies have NUMA boundaries within a single package.

### 2.4 NVLink (GPU-to-GPU)

- **Bottleneck**: topology — if not all GPUs in a NVSwitch'd domain, some pairs route slower
- **Limitation**: ONLY available on datacenter cards (A100, H100/H200, Blackwell). Consumer RTX since 30-series dropped NVLink.
- **Capability**: GPU-to-GPU tensor transfers at 600-1800 GB/s (10-30× PCIe 5.0 x16)
- **Performance**:
  - NVLink 3 (A100): 600 GB/s pair
  - NVLink 4 (H100): 900 GB/s
  - NVLink 5 (B200): 1.8 TB/s
  - 8-way NVSwitch domain: non-blocking full bandwidth per pair
- **Hidden gotchas**:
  - **Consumer multi-GPU is severely bandwidth-starved** for tensor-parallel inference. 2× RTX 5090 with PCIe 5.0 x8 each = only 63 GB/s GPU-to-GPU (via CPU), **~30× slower** than 2× H100 with NVLink 4.
  - NVLink topology differs by server: GH200 grace-hopper has CPU-GPU NVLink C2C; DGX H100 has 8-way NVSwitch.

### 2.5 Cross-socket (NUMA) links

- **Bottleneck**: UPI (Intel) / Infinity Fabric xGMI (AMD) between sockets. ~100 GB/s total between sockets on modern platforms.
- **Limitation**: memory access across sockets = ~2× latency, ~1/2 bandwidth vs local access
- **Capability**: doubles total memory channels and cores
- **Performance**:
  - Dual-socket Intel Xeon SPR: 2× 8-channel DDR5 = 16 channels effective, but cross-socket traffic penalized
  - Dual-socket EPYC Turin: 2× 12-channel = 24 channels, 160 GB/s cross-socket link
- **Hidden gotcha**: `numactl --cpunodebind=0 --membind=0` pins process to one socket. Without NUMA awareness, LLM workloads can waste 30-50% of their theoretical bandwidth on cross-socket traffic.

---

## 3. MEMORY LAYER — Deep dive

### 3.1 DDR generations and their real-world limits

| Gen | Typical speed | Bandwidth/channel | Server max | Notes |
|---|---|---|---|---|
| DDR4 | 2666-3200 | 21-25 GB/s | 3200 (ECC RDIMM) | 2014-2022 dominant |
| DDR5 | 4800-8000 | 38-64 GB/s | 5200 (ECC RDIMM), 6400 (non-ECC UDIMM) | 2021-now |
| MRDIMM | 8800+ | 70 GB/s | server-only | Intel Granite Rapids +; "Multiplexed Rank DIMM" |
| DDR6 | projected 12800+ | 100 GB/s | ~2027 | future |

- **Bottleneck**: **integrated memory controller (IMC) in CPU** caps max speed regardless of DIMM rating. i7-7800X IMC maxes at DDR4-2666 official (OC to 3200 possible). Xeon W-3495X IMC maxes at DDR5-4800 official.
- **Limitation**: dual-rank DIMMs (32/64/128 GB) often force slower speeds than single-rank (16/32 GB). Populating more DIMM slots per channel also drops speed.
- **Capability**: higher-speed DIMMs give bandwidth headroom but marginal benefit if IMC/channel-count is the real limit
- **Performance** (real-world blended CAS latency + bandwidth):
  - DDR4-3200 CL16: ~50 GB/s real, ~80 ns latency
  - DDR5-5600 CL28: ~85 GB/s real, ~65 ns latency
  - DDR5-8000 CL40: ~120 GB/s real, ~70 ns latency (latency worse at higher speed!)

### 3.2 Memory channels (often the real ceiling)

- **Bottleneck**: **board-level routing determines channel count** — cannot be upgraded without new motherboard + CPU socket.
- **Limitation**:
  - Consumer (LGA1700/AM5): 2 channels, ceiling ~130 GB/s on DDR5-8400
  - HEDT (X299): 4 channels DDR4, ceiling ~115 GB/s
  - TRX50 Threadripper 7000: 4 channels DDR5-5200, ~170 GB/s
  - WRX90 Threadripper Pro 7000: **8 channels** DDR5-5200 ECC, ~330 GB/s
  - W790 Xeon W-3400: 8 channels DDR5-4800, ~310 GB/s
  - EPYC SP5: **12 channels** DDR5-4800+, ~460 GB/s per socket
  - MRDIMM-capable Granite Rapids: 12 channels DDR5-8800, **~840 GB/s per socket**
- **Capability**: channels scale MORE linearly than speed for MoE workloads (expert fetches spread across channels)
- **Performance**: for K2.6's MoE fetches, **doubling channels is worth more than 2× speed**. An 8-ch DDR5-4800 machine beats a 2-ch DDR5-8400 machine on K2.6 inference.

### 3.3 DIMM slot count and populating rules

- **Bottleneck**: populating more DIMMs drops speed (memory controller "derate" rules)
- **Limitation**:
  - 2-DIMM-per-channel (2DPC) drops speed vs 1DPC (typical: DDR5-6400 at 1DPC → DDR5-5200 at 2DPC)
  - Mixed-rank DIMMs further derate
- **Capability**: more DIMM slots = more max capacity (4 slots × 48 GB = 192 GB consumer cap; 16 slots × 128 GB = 2 TB workstation)
- **Performance**: ALWAYS prefer fewer, larger DIMMs than many small ones. 2× 128 GB > 4× 64 GB for bandwidth.

### 3.4 RDIMM vs UDIMM

- **Bottleneck**: UDIMM max 64 GB per DIMM typically (2DIMM × 2 channels = 128 GB × 2 = 256 GB max desktop)
- **Limitation**:
  - UDIMM: consumer, unregistered, cheaper per GB but capped in density
  - RDIMM: registered, server/workstation, can go to 256 GB per DIMM → 2-6 TB platform max
  - LRDIMM: Load-Reduced, even higher density but higher latency
- **Capability**: RDIMM supports ECC, higher density, mandatory for server platforms
- **Performance**: RDIMM adds ~1-2 ns latency vs UDIMM but allows much higher capacity

### 3.5 ECC (Error-Correcting Code)

- **Bottleneck**: ECC adds ~5-10% cost, ~5-15 ns latency, requires CPU+board support
- **Limitation**: consumer AM5 Ryzen supports ECC UDIMM functionally; LGA1700 Intel Core does NOT (only Xeon W/Scalable)
- **Capability**: detects + corrects single-bit errors in real time; logs double-bit errors (uncorrectable but visible). For 24/7 LLM serving on large RAM, ECC prevents silent corruption.
- **Performance**: 5-15% overhead; for MoE inference, typically 2-5% real-world impact
- **Hidden gotcha**: even if your platform technically supports ECC, the CPU's IMC may not always correct — check specific SKU's features.

### 3.6 NUMA (Non-Uniform Memory Access)

- **Bottleneck**: cross-socket memory access adds latency (~2× local) and reduces bandwidth
- **Limitation**: applications without NUMA awareness waste 30-50% of theoretical throughput on dual-socket systems
- **Capability**: on AMX-capable dual-socket Xeon SPR, each socket independently serves its own experts
- **Performance**: 
  - Local memory access: 65-80 ns, full channel bandwidth
  - Remote socket access: 130-180 ns, ~1/2 bandwidth
- **Hidden gotcha**: **on some systems NUMA can be disabled in BIOS for "uniform" memory, but this TRADES latency for simplicity** — it actually hurts LLM performance usually. Enable NUMA and use numactl-aware applications.

---

## 4. CPU LAYER — Deep dive

### 4.1 Core count vs single-thread performance

- **Bottleneck**: **llama.cpp's model load phase is largely single-threaded** — core count doesn't help load time
- **Limitation**: during warm inference, CPU-side work is parallelizable across experts → more cores help
- **Capability**: high core count enables many concurrent agents if each uses few cores
- **Performance**:
  - Model load: benchmarked ~1.5-2× faster on modern single-thread (Zen 5/Raptor Lake) vs Skylake-X
  - Inference: 4-8 cores saturate llama.cpp's CPU side for single-user
  - Fleet serving: each concurrent user needs 2-4 dedicated threads → 10-agent fleet wants 20-40 cores

### 4.2 SIMD instruction sets

- **Bottleneck**: without SIMD, MoE expert matmul runs at ~1/10 speed
- **Limitation**:
  - Pre-AVX-512 CPUs (before Skylake-X 2017): SSE/AVX2 only → slow
  - AVX-512: Skylake-X, Cascade Lake, Ice Lake SP, Sapphire Rapids, Emerald Rapids, Granite Rapids, Zen 4, Zen 5 → mainstream now
  - **AMX (Advanced Matrix Extensions)**: Sapphire Rapids (2023), Emerald Rapids, Granite Rapids — Intel-only
  - AMD NO AMX through Zen 5 — compensates with more cores
- **Capability**:
  - AVX-512: 2× AVX2 on FP32/FP16, 4× on INT8
  - AMX: additional ~5-10× on INT8/BF16 matrix operations specifically
- **Performance**: for K2.6 Q2 inference with Q8 weights, AMX-accelerated llama.cpp can be 3-5× faster than AVX-512 alone on the same CPU family

### 4.3 Cache hierarchy

- **Bottleneck**: L1 (32-64 KB per core), L2 (256 KB - 4 MB per core), L3 (shared, 10-500 MB)
- **Limitation**: working set must fit in L3 for zero-copy expert compute; when it doesn't, memory bandwidth becomes the ceiling
- **Capability**: workstation CPUs have 128-512 MB L3 → can cache a full attention layer's active weights
- **Performance**:
  - X299 i7-7800X: 8.25 MB L3 (small)
  - Z790 i9-14900K: 36 MB L3
  - TR Pro 7965WX: 128 MB L3 (massive)
  - EPYC 9654: 384 MB L3 (enormous)
- **Hidden gotcha**: **AMD's Zen 4/5 V-Cache** (3D-stacked L3) adds 96 MB more L3 per CCD → dramatic for memory-bandwidth-bound workloads. Ryzen 7 9800X3D outperforms 9950X on some LLM tasks despite fewer cores.

### 4.4 Thermal throttling

- **Bottleneck**: CPU clocks automatically drop when core temp exceeds ~95°C (Intel) / ~95°C (AMD); can drop 20-40% under sustained load
- **Limitation**: air coolers often insufficient for 200W+ workstation CPUs at sustained load → AIO or custom loop required
- **Capability**: adequate cooling allows sustained all-core boost clocks
- **Performance**: 
  - Stock cooling on i9-14900K: hits 100°C at full tilt, throttles to ~4.8 GHz from 5.6 GHz peak
  - 360mm AIO: sustains 5.4 GHz all-core
- **Hidden gotcha**: **sustained LLM inference is a THERMAL workload**, not a burst workload. Benchmarks show fine short-term performance but real inference is hours of sustained load → cooling matters more than benchmark suggests.

### 4.5 Power delivery (VRM)

- **Bottleneck**: motherboard VRM phase count + heatsinking
- **Limitation**: cheap motherboards with 4-phase VRM can't sustain i9-14900K's 250W+ draw → throttles via VCore drop
- **Capability**: workstation boards (TRX50-SAGE) have 36-phase VRM, handles 350W+ TR Pro easily
- **Performance**: VRM temperature >90°C = 10-20% performance loss under sustained load
- **Hidden gotcha**: **board VRM rating is often the hidden limit**, not CPU TDP. A "supports Threadripper Pro 7995WX" board might spec for short bursts, not sustained.

### 4.6 Boost vs all-core clocks

- **Bottleneck**: advertised boost clocks are single-core only; all-core sustained is 20-40% lower
- **Limitation**: LLM inference rarely uses only 1 core → single-core boost numbers are misleading
- **Capability**: all-core efficiency scales better on newer architectures (Sapphire Rapids, Zen 5)
- **Performance**:
  - i9-14900K: 6.0 GHz single-core boost, ~4.8 GHz all-core sustained
  - EPYC 9654: 3.7 GHz boost, 2.4 GHz all-core sustained (96 cores though)

---

## 5. GPU LAYER — Deep dive

### 5.1 VRAM capacity (first-order bottleneck)

- **Bottleneck**: VRAM is physically fixed per card
- **Limitation**: for K2.6 at Q2:
  - 8 GB VRAM (RTX 2080, 3060 Ti): can't fit even attention layer → CPU-only fallback
  - 12 GB (RTX 3060 12GB): fits attention + basic KV cache, ~3-4 experts max on GPU
  - 16 GB (RTX 4060 Ti 16GB, RTX 4080): fits full attention + small expert rotation
  - 24 GB (RTX 3090, 4090): fits attention + 8K context + some expert hot-path
  - 32 GB (RTX 5090): fits attention + 32K context + modest expert cache
  - 80 GB (H100): fits entire hot path + 64K context + many experts
- **Capability**: VRAM determines what CAN be resident; swaps to CPU/NVMe otherwise
- **Performance**: every VRAM miss = PCIe transfer + CPU involvement → 10-100× slower than VRAM-resident

### 5.2 VRAM bandwidth (second-order bottleneck)

- **Bottleneck**: even with enough VRAM, the memory bus limits how fast weights stream to compute units
- **Limitation**:
  - GDDR6: 14-21 Gbps per pin, 256-384 bit bus → 616 GB/s - 1 TB/s
  - GDDR6X: 19-24 Gbps → 1-1.2 TB/s
  - GDDR7: 28-36 Gbps → 1.8-2.2 TB/s (RTX 5090)
  - HBM2e: 2.4 TB/s (A100)
  - HBM3: 3.35 TB/s (H100 80GB)
  - HBM3e: 4.8 TB/s (H200) → 8 TB/s (B200)
- **Capability**: HBM3e gives H200 roughly 3× the memory bandwidth of RTX 5090 at ~25× the price per card
- **Performance**: for LLM decode (per-token generation), memory bandwidth directly maps to tok/s

### 5.3 Compute units (tensor cores + CUDA cores)

- **Bottleneck**: compute throughput for the operation you're doing (matmul dominates LLM inference)
- **Limitation**:
  - Consumer cards: limited BF16 throughput, no FP8 acceleration
  - Hopper+: FP8 tensor cores at 2× FP16 throughput
  - Blackwell: FP4 at 2× FP8 → 4× vs FP16
- **Capability**: modern tensor cores can do 1,000+ TFLOPS of low-precision matmul
- **Performance**:
  - RTX 2080 Ti: 13 TFLOPS FP16
  - RTX 5090: 105 TFLOPS FP16 (~8× 2080 Ti)
  - H100 80GB: 989 TFLOPS FP8 (~75× 2080 Ti)
  - B200: 2,250 TFLOPS FP4 (~170× 2080 Ti)

### 5.4 PCIe bandwidth to host (critical for offload)

- **Bottleneck**: partial-model serving (some layers on GPU, rest on CPU) moves tensors across PCIe per token
- **Limitation**:
  - PCIe 3.0 x16: 16 GB/s → can only do ~1 expert transfer per 100 ms at 1.6 GB expert size
  - PCIe 5.0 x16: 64 GB/s → 4× faster expert transfers
- **Capability**: full-GPU-resident models avoid this entirely
- **Performance**: offload-heavy workloads are 5-10× slower than full-GPU on equivalent compute

### 5.5 GPU thermal and power limits

- **Bottleneck**:
  - RTX 4090: 450W TGP, 600W power connector, needs 3× 8-pin adapters or native 12V-2x6 PSU
  - RTX 5090: 575W TGP, stricter 12V-2x6 requirement
  - H100 80GB: 700W (SXM5) or 350W (PCIe variant); needs datacenter cooling
- **Limitation**: consumer PSUs rated at 1000-1200W may sag under RTX 5090 + high CPU TDP; need 1500-2000W for dual-5090
- **Capability**: with proper cooling, sustained full-power inference
- **Performance**: thermal throttling on air-cooled 5090 can drop 15-25% vs liquid-cooled under sustained load

### 5.6 Multi-GPU interconnect (without NVLink)

- **Bottleneck**: consumer multi-GPU goes CPU→PCIe→GPU1→PCIe→CPU→PCIe→GPU2, ~30-50 μs latency per sync
- **Limitation**: tensor-parallel inference needs tens of syncs per token; consumer multi-GPU with PCIe sync is 10-30× slower than NVLink
- **Capability**: pipeline-parallel (one layer per GPU) works OK without NVLink; tensor-parallel needs NVLink for efficiency
- **Performance**: 2× RTX 5090 via PCIe for tensor-parallel inference ≈ 1.2× single 5090, not 2×

---

## 6. VIRTUALIZATION LAYER — Deep dive (THE BIGGEST SKIPPABLE BOTTLENECK)

### 6.1 WSL2 on Windows specifically

- **Bottleneck**: HCS (Host Compute Service) bridges WSL VM to Windows I/O subsystem. Every block-device read goes guest → HCS → Windows driver → physical.
- **Limitation**:
  - VHDX file I/O is ~2× slower than raw block device on native Linux
  - NTFS caches the VHDX file AND the guest caches pages inside it → double-caching wastes RAM
  - GPU passthrough to WSL works (via WSLg + DirectX) but adds ~5-15% latency per CUDA API call
  - Memory management: guest kernel's page cache is NOT visible to Windows — Windows can't evict WSL pages to serve its own apps without pagefile thrashing
- **Capability**: easy Windows integration, convenient for dev workflows
- **Performance**:
  - Sequential storage read: ~40% slower than native Linux on same hardware
  - Random I/O: ~50-60% slower
  - Pure compute: 5-10% slower
  - LLM inference specifically: ~15-25% throughput loss, ~30-40% slower cold load

### 6.2 Docker on native Linux

- **Bottleneck**: namespace isolation adds <1% overhead; volumes via bind mounts essentially free
- **Limitation**: running on top of WSL compounds both overheads
- **Capability**: reproducible environments, clean LLM service deployment
- **Performance**: essentially equal to host Linux for LLM serving

### 6.3 KVM/QEMU (enterprise hypervisor)

- **Bottleneck**: paravirtualized drivers (virtio-blk, virtio-net) good but not free
- **Limitation**: GPU passthrough requires VFIO, needs IOMMU-capable board + BIOS setup
- **Capability**: full VM isolation with near-native performance
- **Performance**: 3-8% overhead on most workloads with PCIe passthrough GPU

### 6.4 Containers vs VMs vs bare metal for LLM

- **Bare metal native Linux**: 100% baseline
- **Docker native Linux**: 98-100%
- **KVM with VFIO GPU**: 92-97%
- **WSL2 with GPU**: 75-85%
- **Docker on WSL2**: 70-80% (compounds overhead)
- **Hyper-V on Windows (not WSL)**: 80-90%

---

## 7. OS KERNEL LAYER — Deep dive

### 7.1 Page cache management

- **Bottleneck**: default `vm.swappiness=60` causes kernel to swap RAM out under pressure → catastrophic for LLM mmap (disk-to-swap shuffling)
- **Limitation**: out-of-the-box Linux configs aren't tuned for multi-hundred-GB mmap workloads
- **Capability**: with `swappiness=10` and `vfs_cache_pressure=50`, kernel prioritizes keeping LLM pages hot
- **Performance**: default-tuned system can see 30-50% cold load penalty vs tuned system

### 7.2 Transparent Hugepages (THP)

- **Bottleneck**: THP in "always" mode forces 2 MB page allocation which can stall under memory pressure; "never" mode gives up latency wins
- **Limitation**: some LLM engines (vLLM) specifically need THP-aware allocation; others (llama.cpp) don't care
- **Capability**: 2 MB pages reduce TLB misses → 5-15% faster inference on memory-bound ops
- **Performance**: "madvise" mode (application opts in) is usually optimal
- **Hidden gotcha**: THP can cause random 200-400ms latency spikes during memory compaction — enterprise sometimes disables entirely

### 7.3 I/O scheduler

- **Bottleneck**: default Linux I/O scheduler varies by kernel version
- **Limitation**: bfq scheduler (desktop-oriented) adds latency on NVMe
- **Capability**: `none` (multi-queue direct) or `mq-deadline` minimizes scheduler overhead
- **Performance**: `none` scheduler on PCIe 5.0 NVMe = 20-30% better random IOPS vs bfq

### 7.4 Page fault handling

- **Bottleneck**: default page fault handler is synchronous per-fault, single-threaded per syscall
- **Limitation**: **llama.cpp's single-threaded mmap load is a major bottleneck here** — kernel serves one fault at a time
- **Capability**: io_uring async I/O + madvise(MADV_WILLNEED) lets userspace prefetch
- **Performance**: properly-prefetched mmap load can be 2-3× faster than default
- **Hidden gotcha**: WSL2 on Windows doesn't fully benefit from io_uring due to HCS layer

### 7.5 NUMA scheduling policy

- **Bottleneck**: default policy is "local allocation" — memory allocated on the CPU's closest node
- **Limitation**: when a process migrates between NUMA nodes, its memory stays behind → cross-node access penalty
- **Capability**: `numactl --cpunodebind --membind --localalloc` pins everything to one node
- **Performance**: NUMA-aware LLM serving on dual-socket = 1.5-2× throughput vs unaware

### 7.6 IRQ affinity

- **Bottleneck**: NVMe/NIC interrupts by default go to CPU 0, can bottleneck on single-core
- **Limitation**: high-I/O workloads (RAID 0 storage + LLM serving) can saturate CPU 0
- **Capability**: `irqbalance` + manual pinning spreads interrupts across cores
- **Performance**: 10-20% throughput improvement on I/O-heavy workloads

---

## 8. RUNTIME LAYER — Deep dive

### 8.1 CUDA version compatibility

- **Bottleneck**: CUDA version must match GPU architecture + driver
- **Limitation**:
  - CUDA 11.x max → Ampere (A100, RTX 30xx)
  - CUDA 12.0+ → Hopper (H100)
  - CUDA 12.6+ → Blackwell (B200, RTX 5090)
  - CUDA 13.0+ → NVFP4, accelerated formats on Blackwell
- **Capability**: higher CUDA = access to newer tensor core types
- **Performance**: running FP8 code on a card without FP8 tensor cores falls back to FP16 → 2× slower

### 8.2 CUDA kernel launch overhead

- **Bottleneck**: ~3-5 μs per kernel launch via cudaLaunchKernel
- **Limitation**: small, frequent kernels (token-by-token decode) pay launch overhead repeatedly
- **Capability**: CUDA graphs + CUDA streams can batch launches
- **Performance**: an unoptimized inference loop can spend 30-50% of wall time in launch overhead

### 8.3 cuDNN / FlashAttention version

- **Bottleneck**: older cuDNN versions don't have fused attention; older FlashAttention doesn't support sliding window
- **Limitation**:
  - cuDNN <8.9: no FlashAttention-2
  - cuDNN 9.0+: supports grouped-query attention fusion
  - FlashAttention-2: 2-4× faster than unfused attention
  - FlashAttention-3: 1.5-2× faster than -2 on Hopper (FP8 support)
- **Capability**: proper FlashAttention makes long-context inference viable
- **Performance**: 32K context without FlashAttention = ~5× slower vs with

### 8.4 cuBLAS vs custom kernels

- **Bottleneck**: generic GEMM via cuBLAS isn't optimal for LLM shapes (batch=1, very tall matrices)
- **Limitation**: specific LLM shapes (e.g., MoE expert batched GEMM) need custom kernels
- **Capability**: frameworks like Flash-Decoding, SGLang's custom kernels, ktransformers' expert-batched matmul specialize for these shapes
- **Performance**: custom LLM-shape kernels can be 2-4× faster than cuBLAS for the same operation

### 8.5 CPU-side runtime (MKL / OpenBLAS / oneDNN)

- **Bottleneck**: BLAS library choice affects CPU inference speed dramatically
- **Limitation**:
  - OpenBLAS: generic, ~50% of MKL performance on Intel
  - Intel MKL: Intel-optimized, uses AMX automatically on SPR+
  - oneDNN: Intel's newer alternative with better AMX support
  - AOCL: AMD's BLAS, optimized for Zen
- **Capability**: the right library on the right CPU can 3-5× CPU inference speed
- **Performance**: llama.cpp compiled with MKL + AMX on Xeon SPR is 5-10× faster than default on same CPU

---

## 9. APPLICATION LAYER — Deep dive

### 9.1 llama.cpp bottlenecks

- **Bottleneck**: single-threaded model load; manual `-ngl` tuning; no PagedAttention
- **Limitation**: 
  - Cannot do continuous batching (enhanced concurrent serving)
  - KV cache is per-request, no sharing across prompts
  - GPU offload is static (set at startup, not dynamic)
- **Capability**: lowest memory footprint; best consumer-hardware support
- **Performance**: 
  - Single-user interactive: 80-95% of theoretical throughput
  - Concurrent users: scales poorly (linear degradation with N users)
  - Cold load: slowest among major engines due to single-threaded loader

### 9.2 vLLM bottlenecks

- **Bottleneck**: large static memory pre-allocation (~90% of VRAM at startup); assumes large-scale hardware
- **Limitation**: poor fit for consumer hardware (<64 GB VRAM); no GGUF support for all archs
- **Capability**: PagedAttention enables efficient KV cache management; continuous batching scales to 100s of users
- **Performance**: 
  - Single-user: comparable to llama.cpp
  - Multi-user (8+): 10× better throughput than llama.cpp (amortized)
  - Prefill efficiency: 3-4× better on long prompts

### 9.3 sglang bottlenecks

- **Bottleneck**: like vLLM + RadixAttention for shared prefix caching; complex scheduler
- **Limitation**: high memory overhead, requires GPU-heavy setup
- **Capability**: best performance on structured agentic workloads (many short variations of similar prompts)
- **Performance**: for agentic workflows with prompt-reuse patterns, 2-5× vLLM throughput

### 9.4 Python GIL

- **Bottleneck**: Python's Global Interpreter Lock serializes pure-Python code across threads
- **Limitation**: LLM application servers written in Python bottleneck on orchestration at high concurrency
- **Capability**: subinterpreters (Python 3.13+) and asyncio help; C-extensions (CUDA calls) bypass GIL
- **Performance**: on 30+ concurrent users, Python GIL can add 10-20% latency vs Rust/Go orchestration

---

## 10. CROSS-CUTTING BOTTLENECKS

### 10.1 Cold start bottleneck chain

The chain of dependencies at cold start:

```
Storage read → kernel page fault → CPU index build → memory allocation → GPU copy → KV allocation → HTTP server ready
```

Each stage is gated by the slowest preceding stage. On your X299 today:
- Storage: 3 GB/s physical → 500 MB/s effective (WSL overhead)
- Kernel page faults: single-threaded → bottleneck
- CPU index build: single-threaded → further bottleneck
- Memory allocation: fast (not bottleneck)
- GPU copy: not used (-ngl 0) 
- KV allocation: fast
- **Total cold load: ~17-40 minutes, dominated by storage + kernel page faults**

### 10.2 Warm decode (per-token) bottleneck chain

```
Router dispatch → 8 expert weight fetches → attention compute → output projection → sampler → token
```

On your hardware today:
- Router dispatch: CPU, fast
- Expert fetches: **memory bandwidth bottleneck** (85 GB/s DDR4 / 8 experts = ~10 GB each = 80 GB needed = ~1 second per token at bandwidth limit)
- Attention compute: CPU (no GPU at -ngl 0), ~slow
- Output projection: CPU
- Sampler: trivial
- **Total per token: ~3 seconds, dominated by memory bandwidth**

### 10.3 Prefill (long prompt) bottleneck chain

Prefill is like doing N tokens' worth of compute in parallel, but the KV cache has to be built sequentially:
- Sequential attention computation for N tokens
- Each token's attention requires previous tokens' KV
- Compute-bound on long contexts
- Parallelizes across attention heads on GPU

**Bottleneck shifts with length**:
- Short prompt (<1K): launch overhead dominates
- Medium (1-8K): compute dominates
- Long (16K+): KV cache writes become memory-bandwidth-bound

### 10.4 Concurrent serving bottlenecks

- 1 user: compute + memory bandwidth split roughly evenly
- 2-3 users: batching kicks in, amortizes overhead → **efficiency increases**
- 4-8 users: memory bandwidth saturates, throughput plateaus
- 8+ users: KV cache memory pressure, may OOM VRAM

---

## 11. HIDDEN / FIRMWARE BOTTLENECKS

These are the ones that don't show up in specs or benchmarks:

### 11.1 BIOS/UEFI settings that matter

- **CSM (Compatibility Support Module) enabled**: disables full PCIe 5.0 training → 30-50% bandwidth loss silently
- **Memory profile (XMP/DOCP/EXPO)** not enabled: RAM runs at JEDEC base speed (often 4800 vs rated 6400)
- **Resizable BAR disabled**: GPU memory access is paginated in 256 MB chunks → slower
- **PCIe link speed "Auto"**: may negotiate Gen3 even with Gen5 hardware (bad trace length, dirty contacts)
- **IOMMU disabled**: required for VFIO passthrough; default often off
- **SR-IOV disabled**: some virtualization features silently slow

### 11.2 Firmware versions

- **NVMe firmware**: controller bugs fixed in firmware updates. Sometimes ships with legacy firmware that caps at 80% of rated speed.
- **GPU firmware (VBIOS)**: rare but can affect PCIe training
- **CPU microcode**: security patches (Meltdown/Spectre etc.) cost 5-15% performance; new microcode partly restores

### 11.3 Cable quality for PCIe/riser

- PCIe risers with cheap cable: downgrade to Gen3 or Gen2 silently
- USB-C cables misidentified as PCIe: full retraining failures
- PCIe slot re-timers: can add jitter

### 11.4 Power delivery under load

- Cheap PSU sags under transient load (GPU going to 600W in 1 ms → voltage drop)
- Cheap power cables (daisy-chained 8-pin adapters) heat up, resistance increases
- Wall circuit breaker limits (15A = 1800W peak; 20A = 2400W)

### 11.5 Cooling under sustained workload

- CPU AIO pump degrades over time (3-5 year lifespan)
- GPU thermal paste dries out over years
- Case airflow design matters: bad pre-purchased cases can trap heat

---

## 12. MEASURED PERFORMANCE ON YOUR HARDWARE VS EACH LAYER'S POTENTIAL

Your current X299 K2.6 Q2 cold load was measured at 85-500 MB/s read (variable). Let's decompose by layer:

| Layer | Your measured | Your hardware ceiling | Native Linux ceiling on same HW | Tier 2 upgrade ceiling |
|---|---|---|---|---|
| Physical NVMe | 85-500 MB/s | 3 GB/s | 3 GB/s | 14 GB/s (Gen5) |
| PCIe 3.0 x4 | gated same | 3.5 GB/s | 3.5 GB/s | 16 GB/s |
| Linux block device | WSL-gated | ~2.5 GB/s | 2.8 GB/s | 13 GB/s |
| mmap page fault | single-thread | ~1.5 GB/s | 2 GB/s | 10 GB/s |
| WSL HCS bridge | **~40% tax** | — | 0 (native) | 0 (native) |
| llama.cpp loader | single-thread | ~1 GB/s | 1.5 GB/s | 5 GB/s |

**Your effective throughput is layer-6-limited (WSL)** at 500 MB/s. Remove WSL (native Linux) → get 1.5 GB/s. Upgrade to Tier 2 hardware → get 5 GB/s. Upgrade BOTH → 10+ GB/s.

---

## 13. Summary — every bottleneck ranked by how much it costs you today

1. **WSL virtualization** — 40% throughput loss on storage, 20% on inference → **free fix: native Linux**
2. **PCIe 3.0 platform** — 4× loss vs Gen5 → **fix: new platform ($2-35k CAD)**
3. **Single-threaded llama.cpp load** — 2-3× loss on load → **fix: upstream improvement or switch to loader with io_uring**
4. **Memory channel count** — 4× loss vs 8-channel → **fix: workstation platform**
5. **VRAM capacity** (for K2.6) — forces CPU fallback → **fix: H100 or 2× RTX 5090 ($4-40k CAD)**
6. **i7-7800X single-thread** — 2× loss vs Raptor Lake → **fix: any modern CPU**
7. **Default kernel tuning** (swappiness, scheduler) — 10-15% loss → **free fix: sysctl tuning**
8. **No AMX** on consumer CPU — 5× loss on INT8 matmul → **fix: Xeon SPR/EMR**
9. **No NVLink on multi-GPU** — 30× loss on tensor-parallel sync → **fix: datacenter GPU**

The stack is hierarchical: fixing #9 doesn't help if #1-#5 are still dominant.

---

## 14. What this document NOT does

- Does not recommend buying anything — see `HARDWARE-BUILD-SCENARIOS-2026-04-24.md` for that
- Does not tell you what you SHOULD use — see `PERSPECTIVE-AI-INFRASTRUCTURE-DECISION-2026-04-24.md`
- Does not predict future hardware — specs are current as of 2026-04-24
- Does not cover all edge cases — focused on mainstream LLM serving workloads

## 15. Key insight condensed

**No single bottleneck dominates.** The system is a chain: you can fix the most expensive single bottleneck (PCIe 3.0, ~4× loss) and suddenly the NEXT bottleneck (memory channels, ~4× loss) is your new ceiling. This is why total hardware upgrade (Tier 0 → Tier 4) gives 30-100× improvement — **each layer's fix compounds with the others.**

And why WSL removal alone, while free, only gives you 1.5-2× improvement — **you're still capped by hardware below it.**

---

*Complete bottleneck enumeration. Use as reference when planning upgrades or diagnosing performance.*
