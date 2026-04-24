# Cloud Spend Scenarios — K2.6 via OpenRouter vs Ollama Cloud vs Local

**Date**: 2026-04-24
**Purpose**: Clean cost analysis of the three cloud/local access paths for K2.6 (and GLM 4.7, other cloud models). Standalone reference — no mission/hardware bias; just the economics. Companion to `HARDWARE-BUILD-SCENARIOS-2026-04-24.md` and `SESSION-2026-04-24-HANDOFF.md`.

**Brain reference**: `wiki/comparisons/kimi-k2-6-access-paths-openrouter-ollama-cloud-local.md`

---

## 1. Operator baseline (where we're starting from)

- **Prior cloud spend**: $240 CAD + $240 CAD + tax = **~$540 CAD/month** (Anthropic Claude Opus subscription + one other AI subscription/API budget).
- **Currently disabled**, will reactivate at least one when token balance runs out.
- **5-year projection at $540/mo sustained**: $32,400 CAD.

This is the cost baseline we're measuring everything else against.

---

## 2. The three cloud access paths

### Path A — OpenRouter (pay-per-token)

- **K2.6 pricing**: $0.80 USD/M input + $3.50 USD/M output = ~$1.10 / $4.80 CAD blended
- **Typical blended cost** (roughly 30% input / 70% output token mix): **~$4 CAD per 1M tokens**
- **Other models available**: 300+ models (GPT-5, Claude, Llama, Qwen, others) — prices vary
- **AICP integration**: already shipped as `k2_6_openrouter` backend (E011-m002 done)
- **Privacy posture**: medium — can pin specific providers via OpenRouter routing options
- **Agent swarm support**: passes through Moonshot's native swarm API

### Path B — Ollama Cloud Pro (flat-rate)

- **Price**: $20 USD/mo = **~$27 CAD/mo**
- **Includes**: unlimited K2.6 usage, plus GLM 4.7, Kimi K2.6-Coder, other Ollama cloud models
- **Throughput**: shared pool, datacenter-class
- **AICP integration**: **not yet built** — needs `ollama_cloud` backend adapter. `OLLAMA_API_KEY` is in operator's `.env`.
- **Privacy posture**: LOW — shared pool, opaque provider routing, per the brain's source article "prototyping only"
- **Agent swarm support**: untested — brain flags this as unknown

### Path C — Local llama-server (current deployment)

- **Cost**: electricity only (~$300 CAD/yr at 24/7 operation)
- **Throughput today**: ~0.3 tok/s on operator's current X299 + 64GB hardware (needs tuning)
- **Throughput after tuning**: expected ~1-3 tok/s
- **AICP integration**: `k2_6_local` backend enabled, operational (cold call needs >600s timeout)
- **Privacy posture**: HIGH — never leaves the machine
- **Agent swarm support**: full model capability exposed

---

## 3. Economic breakeven math

### Token-level: when does flat-rate beat pay-per-token?

Ollama Cloud Pro's $27 CAD/mo flat buys you the equivalent of:

- $27 CAD ÷ $4.80 CAD per M output tokens = **~5.6 M output tokens/month breakeven**

Assuming typical 30%/70% input/output mix, that's ~8M total tokens/month breakeven.

### Typical workload volumes (for calibration)

| Workload type | Output tokens per session | Sessions/mo | Monthly output |
|---|---|---|---|
| Light chat (quick Q&A) | 1-5k | 100 | 100k–500k |
| Single heavy coding session | 200k-500k | — | — |
| Heavy Claude-Code day (8 sessions) | 200k each | 30 days | **~48M/mo** |
| One fleet agent, 24/7 light work | 5k/hour × 24 | 30 days | **~3.6M/mo** |
| 10 fleet agents, 24/7 | 10× above | | **~36M/mo** |
| 300-agent swarm, one-shot task | 4,000 steps × ~3k = 12M | 1 | **12M/task** |

### Volume-based cost comparison (CAD)

| Output tokens/mo | OpenRouter CAD | Ollama Cloud CAD | Cheaper | Delta |
|---|---|---|---|---|
| 100k | $0.48 | $27 | OpenRouter | −$26.52 |
| 500k | $2.40 | $27 | OpenRouter | −$24.60 |
| 1M | $4.80 | $27 | OpenRouter | −$22.20 |
| 3M | $14.40 | $27 | OpenRouter | −$12.60 |
| 5M | $24 | $27 | OpenRouter | −$3 |
| **5.6M (breakeven)** | **$27** | **$27** | **tie** | $0 |
| 10M | $48 | $27 | Ollama Cloud | −$21 |
| 30M | $144 | $27 | Ollama Cloud | **−$117** |
| 50M | $240 | $27 | Ollama Cloud | **−$213** |
| 100M | $480 | $27 | Ollama Cloud | **−$453** |

### Key takeaways

1. **Light personal use** (< 1M tokens/mo): OpenRouter is cheaper. Ollama Cloud is overkill.
2. **Moderate daily use** (1-5M tokens/mo): Roughly tie. OpenRouter slight edge.
3. **Heavy use / fleet work** (> 6M tokens/mo): Ollama Cloud wins by a lot.
4. **Very heavy use** (> 50M tokens/mo): Ollama Cloud is **9-20× cheaper** than OpenRouter.

**Operator's prior $540/mo baseline** (if that was all K2.6) implies ~112M tokens/mo — deep into Ollama-Cloud-advantage territory. Would have been ~$27/mo on Ollama Cloud. **20× saving.**

---

## 4. Privacy/sovereignty factor (non-cost but critical)

Per brain's comparison doc (operator rule captured):

> **"Do not use Ollama Cloud for employer-adjacent work with private repos, regardless of cost math."**

Reason: Ollama Cloud uses a shared inference pool with opaque provider routing. The Njenga source article the brain cites explicitly frames it as "prototyping only, not client/monetizable work." A single misrouted session could send private-repo context through a shared pool.

### Workload → path mapping (authoritative)

| Workload | Allowed paths |
|---|---|
| Wiki research, open-source reading, general learning | Any (Ollama Cloud, OpenRouter, Local) |
| Personal prototypes, experimental builds | **Ollama Cloud** (best $/token, flat rate covers volume) |
| AICP development (operator's own stack) | **OpenRouter** preferred (per-request cost visibility helps self-measurement) |
| Employer work, private repos, client code | **OpenRouter** with pinned vetted provider, OR **Local** |
| Monetizable work, audit-requiring sessions | **OpenRouter** with pinned provider |
| Offline/travel/outage resilience | **Local** only |
| 300-agent swarm orchestration | **OpenRouter** (swarm passes through) or **Local** (Ollama Cloud untested) |
| Large batch experimentation, no sensitive data | **Ollama Cloud** (cheapest at volume) |

### The anti-pattern to avoid

> "Default Ollama Cloud to always on."

The flat rate makes it cheap and the `ollama launch` command makes it trivially easy to use for any session. That's exactly what creates the risk — a single misrouted session is all it takes. **Route by session context, not preference or cost alone.**

---

## 5. Projected monthly spend scenarios

Four realistic usage profiles for operator, with smart routing:

### Scenario A — Light personal (ex-current)
- Description: occasional local dev, some cloud help, mostly Anthropic habit
- Monthly tokens: ~2M output
- Routing: 100% OpenRouter K2.6 (nothing touches cloud client work)
- **Cost: ~$10 CAD/mo = $120 CAD/yr**

### Scenario B — Active developer profile (operator's likely real use)
- Description: daily AICP dev + some fleet agent experimentation + occasional client work
- Monthly tokens: ~15M output (mix of heavy dev sessions)
- Routing:
  - Personal/AICP/research (~70% volume): **Ollama Cloud Pro** ($27/mo covers unlimited)
  - Client work (~20% volume, ~3M tokens/mo): **OpenRouter** with vetted provider (~$14/mo)
  - Sovereignty-critical (~10% volume, ~1.5M): **Local** (electricity only)
- **Cost: ~$41 CAD/mo = $492 CAD/yr**

### Scenario C — Fleet-scaled (10 agents running regularly)
- Description: AICP + 10 fleet agents running daily workflows
- Monthly tokens: ~50M output
- Routing:
  - Personal + fleet + research (~80%): **Ollama Cloud Pro** ($27/mo)
  - Client-adjacent fleet work (~15%, ~7.5M tokens): **OpenRouter** (~$36/mo)
  - Sovereignty critical (~5%): **Local** (electricity only)
- **Cost: ~$63 CAD/mo = $756 CAD/yr**

### Scenario D — Heavy swarm + enterprise (theoretical)
- Description: 300-agent swarm runs + multi-user + enterprise integration
- Monthly tokens: ~300M output
- Routing:
  - Prototype/research (~50%): Ollama Cloud ($27/mo)
  - Client/audit-required (~40%, ~120M): OpenRouter (~$576/mo)
  - Sovereignty (~10%): Local
- **Cost: ~$600+ CAD/mo = $7,200+ CAD/yr**

At Scenario D, local hardware investment starts to make serious economic sense. At A, B, C it doesn't.

---

## 6. 5-year cloud-only cost projection

At the four scenarios above, pure-cloud 5-year spend:

| Scenario | Monthly | 5-year cloud cost |
|---|---|---|
| A: Light personal | $10 | **$600 CAD** |
| B: Active developer | $41 | **$2,460 CAD** |
| C: Fleet-scaled (10 agents) | $63 | **$3,780 CAD** |
| D: Heavy swarm/enterprise | $600+ | **$36,000+ CAD** |

**Operator's prior $540/mo baseline over 5yr: $32,400 CAD**

**With smart routing (Scenario B): $2,460 CAD over 5 years.**

That's a **92% reduction** from the prior pattern.

---

## 7. Action plan — smart cloud routing without hardware

### Immediate — stop the cost bleed
1. Don't renew Anthropic Opus subscription when it lapses (saves ~$240/mo).
2. Activate Ollama Cloud Pro ($27 CAD/mo) for personal/AICP/research use.
3. Keep OpenRouter K2.6 available for client/sovereignty-required work, with a specific provider pinned (via `:provider` routing modifier).
4. Keep local K2.6 running as sovereignty fallback (no recurring cost).

### Medium — enable routing
1. Build AICP's `ollama_cloud` backend adapter (mirrors `k2_6_openrouter` structure; points at `https://api.ollama.com` or `localhost:11434` via `ollama launch`).
2. Add `ollama_cloud` entry to `config/default.yaml` backends + tier_map.
3. Update tier_map to route by complexity + privacy context:
   - Wiki/research/prototype → `ollama_cloud`
   - AICP dev → `k2_6_openrouter` (for cost visibility)
   - Client/private → `k2_6_local` first, fallback to `k2_6_openrouter` with provider pin
4. Document in AICP which profile routes to which tier so operator can consciously pick per session.

### Long — monitor and adjust
1. Track monthly token volume per tier (AICP already has `aicp --routing-report` via E011-m005).
2. If Ollama Cloud volume exceeds what the flat rate reasonably sustains (they may throttle at very high volume), add OpenRouter overflow.
3. If local tier underutilized (< 5% of requests), reconsider keeping the 53GB RSS llama-server running when Windows needs memory.

---

## 8. Decision tree — which cloud path per session

```
Starting a session. Does the workload involve:

├── Employer repos / client code / monetizable output?
│   ├── YES → OpenRouter K2.6 with vetted provider
│   │        OR Local K2.6 (if offline / sovereignty-critical)
│   └── NO → continue
│
├── Expected heavy volume (> 5M output tokens this session)?
│   ├── YES → Ollama Cloud Pro (best $/token above breakeven)
│   └── NO → continue
│
├── Need per-request cost tracking / audit trail?
│   ├── YES → OpenRouter (itemized per-request cost visibility)
│   └── NO → continue
│
├── Working offline / no internet / sovereignty mandatory?
│   ├── YES → Local K2.6 only
│   └── NO → continue
│
└── Default for personal/research/AICP dev:
    → OpenRouter K2.6 for AICP dev (cost visibility)
    → Ollama Cloud Pro for research/prototype/volume
```

---

## 9. What this doesn't answer

Out of scope for this document (covered elsewhere):

- **Does hardware make sense to buy?** → See `HARDWARE-BUILD-SCENARIOS-2026-04-24.md`
- **What's the current state of local K2.6?** → See `SESSION-2026-04-24-HANDOFF.md`
- **Why did we go through 2 days of wrong execution?** → See `POSTMORTEM-2026-04-24-k26-local-wrong-path.md`

---

## 10. Summary numbers (CAD, annual)

| Path | Annual cost at realistic use (Scenario B) | Annual cost at heavy (Scenario C) |
|---|---|---|
| Anthropic Claude only (prior baseline) | $6,480 | $6,480+ |
| OpenRouter only | ~$720 | ~$2,160 |
| Ollama Cloud only | $324 | $324 (if volume sustained within pool) |
| **Smart routing mix** | **$492** | **$756** |
| Current unchanged | $6,480 | $6,480+ |

**The single highest-ROI action from this entire conversation**: switch to smart-routing cloud-only. Saves ~$6,000 CAD/year with zero hardware risk, preserves mission (K2.6 everywhere, no Anthropic dependency), and keeps options open for hardware later.
