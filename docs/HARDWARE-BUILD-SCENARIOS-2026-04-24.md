# Hardware Build Scenarios — Local K2.6 Inference Platforms

**Date**: 2026-04-24
**Purpose**: Standalone analysis of hardware upgrade paths for running K2.6 Q2 locally. CAD pricing, 2026 retail reality. Companion to `CLOUD-SPEND-SCENARIOS-2026-04-24.md` and `SESSION-2026-04-24-HANDOFF.md`.

---

## 1. Current hardware (the baseline)

### Tier 0 — operator's existing workstation

| Component | Spec | Relevant to K2.6 |
|---|---|---|
| CPU | Intel i7-7800X (Skylake-X, 6c/12t, 4.3 GHz boost) | AVX-512 yes, no AMX |
| Platform | X299 | PCIe 3.0 only (major bottleneck) |
| RAM | 64 GB DDR4-2666 (quad-channel) | ~85 GB/s bandwidth |
| GPU | RTX 2080 Ti (11 GB) + RTX 2080 (8 GB) | 19 GB total VRAM, imbalanced |
| Storage | WD_BLACK SN770 1TB NVMe (on PCIe 3.0) | ~3 GB/s practical |
| Total value if sold today | ~$1,500-2,000 CAD | |

### Measured K2.6 performance on Tier 0

- Local K2.6 Q2 via llama.cpp `-ngl 0`: **~0.3 tok/s** (CPU-only, mmap streaming)
- Cold load: ~10 minutes (mmap page faults from NVMe)
- First-call inference: 10+ min, exceeds AICP's 600s timeout
- Warm inference: 38s for 10 tokens (3.8 s/token)

**Verdict**: technically runs, mission minimum reached, NOT usable interactively.

---

## 2. Tier 1 — "Local K2.6 viable" (~$15-19k CAD)

**Target performance**: 5–8 tok/s single user, usable for batch/background work. Roughly **20× speedup over Tier 0**.

### Build (new components)

| Component | Spec | CAD |
|---|---|---|
| Motherboard | MSI Pro Z790 / ASRock W680 DDR5 | $450 |
| CPU option A (consumer) | Intel i9-14900K (24c/32t, 6 GHz boost) | $850 |
| CPU option B (workstation) | Intel Xeon W-2495X (24c, 4-ch DDR5 ECC, AMX) | $3,500 |
| RAM | 192 GB DDR5-6000 (4× 48GB) non-ECC | $1,800 |
| GPU | 2× RTX 5090 32 GB | $8,000 |
| Storage | 2× 2 TB PCIe 5.0 NVMe RAID 0 | $1,500 |
| PSU | 1500W Titanium | $500 |
| Case + cooling | Fractal Meshify XL + 360 AIO | $600 |
| Misc (fans, cables) | | $150 |
| Assembly/shipping | | $400 |
| **Pre-tax subtotal (consumer CPU)** | | **$14,250** |
| **Pre-tax subtotal (Xeon W-2495X)** | | **$16,900** |
| Tax (HST 13%) | | $1,850 / $2,200 |
| **Total** | | **$16,100 CAD / $19,100 CAD** |

### What you gain over Tier 0

- Memory bandwidth: 85 GB/s → ~96 GB/s (DDR5-6000 dual-channel)
- PCIe 3.0 → 5.0 (4× NVMe bandwidth, 2× GPU bandwidth)
- VRAM: 19 GB → 64 GB (2× RTX 5090)
- CPU IPC + clock: Skylake-X → Raptor Lake (huge leap)
- AMX (Xeon option only): ~5× INT8 matmul speedup where supported
- Expected K2.6 throughput: 5–8 tok/s

### What's compromised vs higher tiers

- Consumer motherboards are dual-channel only (Xeon W-2495X is 4-ch, but limited board ecosystem)
- RAM cap: 192 GB. Enough for ~60% expert cache hit rate; the rest streams from NVMe
- Single-user only; concurrent serving degrades quickly
- No ECC RAM on consumer build (minor reliability concern for 24/7)

### Upgrade paths from Tier 1

- Add more RAM later (up to 192 GB cap)
- Add a third GPU if board supports (most Z790 consumer boards: no)
- Cannot evolve to Tier 2 — different socket/platform

---

## 3. Tier 2 — "The sweet spot" (~$32k CAD all-in)

**Target performance**: 15–25 tok/s single user, 2–3 concurrent. Roughly **80× speedup over Tier 0**.

### Build

| Component | Spec | CAD |
|---|---|---|
| Motherboard | ASUS Pro WS TRX50-SAGE WIFI (sTR5, 8-channel) | $2,200 |
| CPU | AMD Threadripper Pro 7965WX (24c, 8-ch DDR5, PCIe 5.0) | $4,000 |
| RAM | 256 GB DDR5-5200 ECC RDIMM (8× 32GB) | **$10,000** |
| GPU | 2× RTX 5090 32 GB | $8,000 |
| Storage | 4× 2 TB PCIe 5.0 NVMe | $2,000 |
| PSU | 1600W Titanium | $700 |
| Case | Phanteks Enthoo Pro 2 Server or similar (CEB-capable) | $500 |
| CPU cooler | Noctua NH-U14S TR5-SP6 or 360 AIO TR-compatible | $450 |
| Fans + thermal paste + cables | | $150 |
| Assembly / shipping | | $500 |
| **Pre-tax subtotal** | | **$28,500** |
| Tax (HST 13%) | | $3,705 |
| **Total all-in** | | **~$32,200 CAD** |

### What you gain over Tier 1

- **8-channel DDR5-5200 ECC**: ~330 GB/s bandwidth (**3.4× Tier 1**)
- 128 PCIe 5.0 lanes (vs ~20 on consumer Z790)
- ECC memory (critical for 24/7 operation)
- Registered RAM: higher per-DIMM density, supports 256GB+ capacity
- 2 TB RAM ceiling (no practical limit for K2.6)
- Expected K2.6 throughput: 15–25 tok/s single user

### What's compromised

- No AMX (AMD ecosystem). Intel Xeon W-3400 Sapphire Rapids would edge out Threadripper on AMX-accelerated inference by ~20–40%.
- 7965WX is entry-tier Threadripper Pro; more cores available at higher cost
- Single GPU inference primarily — multi-GPU tensor-parallel with mixed VRAM isn't great for llama.cpp

### Savings variants (how to get Tier 2 cheaper)

| Variation | Savings | New total | Compromise |
|---|---|---|---|
| 1× RTX 5090 instead of 2 | −$4,000 | ~$28k | Single GPU only; fine for K2.6 solo |
| 192 GB RAM (6× 32GB) | −$2,500 | ~$29.5k | Lower expert cache hit rate |
| Both | −$6,500 | ~$25.7k | Acceptable for solo use |
| Used Threadripper Pro 5000 WX + sTRX4 mobo | −$3,500 | ~$28.5k | Prior-gen, still 8-channel DDR4 ECC |
| 2× used RTX 3090 24GB instead of 5090 | −$5,000 | ~$27k | 65% inference speed of 5090 |

### Upgrade paths from Tier 2

- Drop in H100 80GB later (~$30-40k) without replacing anything else → becomes Tier 3
- Add more RAM (up to 2 TB) → supports larger models without swap
- Add more GPUs (board has 7 PCIe 5.0 x16 slots)
- Evolves gracefully; most future-proof tier

### Alternative: Intel Xeon W-3400 Sapphire Rapids

Same price range (~$30-35k CAD all-in), with these tradeoffs:
- **Plus**: AMX instructions (10× INT8 matmul speedup on supported kernels). llama.cpp has AMX optimizations.
- **Plus**: Moonshot's official KTransformers config explicitly requires Sapphire Rapids (the datacenter example uses Xeon 6454S)
- **Minus**: Fewer cores at same price tier
- **Minus**: Older platform (launched 2023); Emerald Rapids and Granite Rapids are newer Xeon generations
- **For pure K2.6 inference throughput, Xeon W-3400 probably edges out Threadripper Pro 7000 by 10-20%.**
- **For mixed workstation use + multi-GPU + future-proofing, Threadripper Pro wins.**

---

## 4. Tier 3 — "Datacenter-at-home" (~$65-80k CAD)

**Target performance**: 30–50 tok/s single user, 5–8 concurrent, small agent-swarm capable. Roughly **150× speedup over Tier 0**.

### Build

| Component | Spec | CAD |
|---|---|---|
| Motherboard | ASUS Pro WS TRX50-SAGE WIFI | $2,200 |
| CPU option A | AMD Threadripper Pro 7985WX (64c) | $5,500 |
| CPU option B | AMD Threadripper Pro 7995WX (96c) | $10,000 |
| RAM | 512 GB DDR5-5200 ECC RDIMM (16× 32GB or 8× 64GB) | $20,000 |
| GPU primary | 1× H100 80 GB (used ~$30k, new ~$40k) | $30,000–40,000 |
| GPU secondary | 1× RTX 5090 32 GB | $4,000 |
| Storage | 8× 2 TB PCIe 5.0 NVMe | $4,000 |
| PSU | 2000W server-class | $900 |
| Case | Enterprise tower or 4U rackmount | $1,200 |
| CPU cooling | Server-grade AIO or air | $600 |
| Misc / assembly | | $800 |
| **Pre-tax subtotal (64c, used H100)** | | **$69,200** |
| Tax (HST 13%) | | $9,000 |
| **Total** | | **~$78,200 CAD** |

### What you gain over Tier 2

- H100 80 GB HBM3 = ~2 TB/s memory bandwidth on-GPU
- Enough VRAM to hold attention layers + hot experts + KV cache for full 64K context
- 1 TB RAM ceiling (comfortable for full expert cache)
- Meaningful concurrent serving (5–8 users)
- Small agent swarm feasible (10–30 concurrent workflows)
- Expected K2.6 throughput: 30–50 tok/s

### What's compromised

- Still can't match Moonshot's 300-agent swarm spec (that's Tier 4)
- H100 consumer market is thin; depreciation risk significant
- Power draw: 700-900W sustained. Serious cooling + UPS considerations
- Noise: H100 is a datacenter card, fans are loud
- Depreciation: H100 resale in 2-3 years may drop 40-60% as H200/B200 saturate market

### When Tier 3 makes sense

- You consistently serve 5+ concurrent users/agents
- Your work has a direct revenue attribution (client billable, SaaS)
- You're building a small AI service for a team
- The $45k+ premium over Tier 2 buys capability you will measurably use

### When Tier 3 doesn't

- Solo operator use
- Occasional inference only
- Uncertain whether you'll hit concurrent-user threshold
- You're not generating revenue from the extra throughput

---

## 5. Tier 4 — "Full Moonshot spec" (~$200-400k+ CAD)

Not realistic for personal use. Listed for completeness.

- 2-8× H100 80GB or H200 141GB GPUs
- 1-2 TB RAM
- Dual-socket server (Xeon Platinum or EPYC)
- 100 Gb networking
- Data-center rack + cooling + redundancy

**Matches Moonshot's published K2.6 deployment**: 8× L20 + 2× Intel 6454S delivers 640 tok/s prefill, 24 tok/s decode at 48-way concurrency. This is what OpenRouter providers run. No reason to replicate locally for personal use.

---

## 6. 5-year total cost of ownership (TCO)

### Assumptions

- Electricity: $0.13 CAD/kWh (Ontario average)
- Power draw at 14h/day avg active + 10h/day idle
- Maintenance: ~$500-1,000/yr (component replacement, cooling upgrades, etc.)
- Residual value at year 5: **~35%** of original cost (aggressive depreciation for AI workstation)

### Per-tier TCO

| Tier | Build cost | Electricity 5yr | Maintenance 5yr | Residual @ 5yr | **Net 5yr TCO** | **$/yr amortized** |
|---|---|---|---|---|---|---|
| Tier 0 (current) | $0 new | $1,500 | $0 | $0 | **~$1,500** | $300 |
| Tier 1 (~$17k) | $17,000 | $1,800 | $2,500 | −$5,950 | **~$15,350** | **$3,070** |
| Tier 2 (~$32k) | $32,000 | $2,100 | $3,500 | −$11,200 | **~$26,400** | **$5,280** |
| Tier 3 (~$78k) | $78,000 | $3,500 | $5,500 | −$27,300 | **~$59,700** | **$11,940** |

### Break-even cloud spend (CAD/month) for hardware to pay back

| Tier | Break-even monthly cloud spend |
|---|---|
| Tier 1 | ~$256 CAD/mo |
| Tier 2 | ~$440 CAD/mo |
| Tier 3 | ~$995 CAD/mo |

---

## 7. Hardware vs cloud decision matrix

### If your cloud spend (with smart routing per `CLOUD-SPEND-SCENARIOS-2026-04-24.md`) is:

| Monthly cloud spend | Recommended action |
|---|---|
| **< $100 CAD/mo** | Stay on Tier 0 + cloud. Hardware cannot pay back. |
| **$100 – $250 CAD/mo** | Consider Tier 1 if you want sovereignty/offline capability. Economically marginal. |
| **$250 – $450 CAD/mo** | Tier 1 economically justified. Consider Tier 2 if growth expected. |
| **$450 – $1,000 CAD/mo** | Tier 2 pays back over 5 years. Hardware becomes net-cheaper. |
| **> $1,000 CAD/mo** | Tier 3 economically justified if volume sustained. |

### Operator's baseline context

- Prior spend: $540 CAD/mo (unsmart routing, Anthropic-heavy)
- With smart routing (Scenario B from cloud doc): ~$41 CAD/mo → Tier 0 stays cheapest
- With fleet scaling (Scenario C): ~$63 CAD/mo → still Tier 0 cheapest
- Only if heading toward Scenario D (300-agent swarm) does hardware make economic sense

---

## 8. Decision factors beyond cost

### Hardware wins for:

- **Mission alignment** — "no cloud provider can turn off my AI"
- **Sovereignty** — client work, employer private repos, credential-scoped sessions
- **Offline capability** — travel, outages, air-gapped work
- **Agent swarm economics** — running 10+ agents 24/7 cloud gets expensive fast
- **Depreciation of cloud spend** — locking in $5,280/yr beats unbounded $500/mo growth
- **Dual-purpose** — hardware serves non-AI workloads too (compilation, rendering, CI, general workstation)

### Cloud wins for:

- **Pure cost optimization at low/moderate volume** — cheapest $/token at your scale
- **Zero maintenance burden** — no component failures, heat, noise, power bills
- **Rapid model evolution** — K2.7, K3, GPT-6 all show up in cloud first, no hardware upgrade required
- **Datacenter-class throughput** — Ollama Cloud Pro at $27/mo gives you throughput no $40k local system can match
- **Capital preservation** — $32k in markets + $100/mo cloud ≠ $32k in hardware
- **Flexibility** — can switch providers or models instantly, no sunk-cost lock-in

### Time-weighted factors

- **Next-gen hardware in 2026-2027**: Blackwell consumer (RTX 60xx), Granite Rapids Xeon, Zen 5 Threadripper. Likely 2× performance at similar price. Buying today means paying 2× effective cost per unit of 2027-perf.
- **K3 / next-gen model releases**: architecture may shift (new quantization methods, new attention variants). Tier 1 hardware bought for K2.6 might not suit K3.
- **OpenRouter / Ollama Cloud price evolution**: cloud prices typically drop 30-50% per year as models commoditize.

---

## 9. ASUS Pro WS TRX50-SAGE-specific assessment

Operator proposed this specific motherboard as a starting point. Assessment:

**Strengths**:
- Best-in-class for Threadripper Pro workstation builds
- 8-channel DDR5 (critical for MoE inference bandwidth)
- 128 PCIe 5.0 lanes (room for multi-GPU + multi-NVMe without bottleneck)
- ECC registered RAM support
- 10 Gb + 2.5 Gb LAN (useful for server-class networking)
- WiFi 7 (nice-to-have)
- Multi-GPU slot layout (7× PCIe x16 slots at full electrical)
- Good VRM for 64-core+ Threadripper Pro

**Trade-offs vs Xeon W-3400 Sapphire Rapids**:
- No AMX (Intel-only feature) — AMX gives 10× INT8 matmul speedup where used
- Higher TDP under full load (Threadripper Pro can pull 350W+ at 96 cores)
- AMD GPU compute stack less mature than Intel's for enterprise inference tools

**For K2.6 specifically**:
- Threadripper Pro 7965WX: ~15-20 tok/s expected (AMD, no AMX)
- Xeon W-3475X: ~18-25 tok/s expected (Intel, AMX-accelerated)
- Gap is ~20%; not dealbreaking

**Board is the right choice if**:
- You want multi-GPU capability (4+ GPUs in future)
- You plan mixed workloads (not just LLM inference)
- You prefer AMD ecosystem
- You want longest socket life (sTR5 supports future Threadripper 9000/11000)

**Consider W680 or Intel W790 Xeon boards if**:
- You want AMX for dedicated inference performance
- You're OK with Intel's shorter-socket-life pattern
- You want potentially better single-GPU inference throughput

---

## 10. Recommendations by operator profile

### If you want to stop this conversation with a decision NOW:

**Stay on Tier 0 + switch to smart cloud routing.** Per the cloud scenarios doc, that drops your bill from $540 → $41 CAD/mo. The $32k Tier 2 spend saved goes further in investment than in hardware depreciation at your current usage level.

Check back in 6 months: has actual usage volume hit Tier 1/2 break-even? Is fleet work scaling? Has sovereignty-critical work grown to 30%+? If yes to any, revisit Tier 2. If no, Tier 0 continues to be the cheapest answer.

### If you've decided the mission is worth the hardware investment regardless of cost:

**Go Tier 2 at ~$28k all-in (savings variant with 1× RTX 5090 + 192 GB RAM).** Gives you 15-25 tok/s local K2.6, room to upgrade GPU/RAM later, and locks in ~$5,280/yr cost for 5 years. Psychologically: "I own my AI stack."

Avoid jumping straight to Tier 3 unless you have concrete evidence you'll hit 5+ concurrent-user throughput or agent-swarm scale.

### If fleet work is actively scaling and you're hitting 10+ agents 24/7:

**Tier 2 at full $32k, or Tier 3 if you've proven the volume for 6 months.** The economic math flips in favor of hardware above $450/mo cloud spend.

---

## 11. Summary table

| Tier | Cost (CAD all-in) | K2.6 tok/s | Best for | Stop here if... |
|---|---|---|---|---|
| Tier 0 (current) | $0 | 0.3–1 | Sovereignty fallback only | Cloud usage < $250/mo |
| Tier 1 | $15–19k | 5–8 | Mixed cloud+local, occasional primary | Cloud usage ~$250-500/mo |
| Tier 2 | $26–32k | 15–25 | Primary local tier, small fleet host | Cloud usage $450-1000/mo or fleet scaling |
| Tier 3 | $65–78k | 30–50 | Multi-user, small-swarm, revenue-attributable | Sustained > $1000/mo cloud |
| Tier 4 | $200k+ | 100+ | Full Moonshot spec, not realistic for personal | Never for personal use |

---

## 12. What this doesn't cover

Out of scope (covered elsewhere):

- **Smart cloud routing strategy and OpenRouter/Ollama Cloud economics** → `CLOUD-SPEND-SCENARIOS-2026-04-24.md`
- **Current local K2.6 state and tuning needs** → `SESSION-2026-04-24-HANDOFF.md`
- **Why Tier 0's current state is what it is** → `POSTMORTEM-2026-04-24-k26-local-wrong-path.md`
- **Specific AICP code changes needed to wire up `ollama_cloud` backend** → Future epic (E013?)
