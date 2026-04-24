# 5-Year Scaling Projection — Your Specific Workload Pattern

**Date**: 2026-04-24
**Operator's stated workload at full scale**:
- 1 to 2 fleets of 10 agents each (10-20 agents running 24/7)
- 2-3 personal sessions in parallel (your own coding / research work)
- Ramping up over ~5 years (not day-1 at full scale)

**Pricing source**: verified 2026-04-24 from OpenRouter API + Ollama Cloud + operator-confirmed Anthropic. See `MODEL-ECOSYSTEM-FULL-MAP-2026-04-24.md` for methodology.

---

## 1. Token volume assumptions

### Your personal sessions (2-3 in parallel, ramping)

| Activity | Output tokens/hour |
|---|---|
| Idle browsing / research | 2-5K |
| Moderate coding | 15-25K |
| Heavy Claude-Code session | 30-60K |
| Tight agentic loop (planning + tool use) | 40-80K |

Assuming ~8 productive hours/day × 2-3 concurrent sessions × avg 25K tokens/hour:
- **Low estimate**: 2 sessions × 8h × 15K = **240K tokens/day** = ~7.2M/mo
- **Mid estimate**: 2.5 sessions × 8h × 25K = **500K tokens/day** = ~15M/mo
- **High estimate**: 3 sessions × 10h × 40K = **1.2M tokens/day** = ~36M/mo

**Personal baseline: ~15M output tokens/mo** at moderate use (2-3 sessions).

### Per-fleet-agent volume

| Agent activity pattern | Active hours/day | Tokens/active hour | Daily |
|---|---|---|---|
| Dormant / polling (most agents most of the time) | 2-4 | 5-10K | 10-40K |
| Moderate task execution | 8-12 | 10-20K | 80-240K |
| High-utilization agent (busy all day) | 16-20 | 20-40K | 320-800K |

Assuming mixed agent patterns (most dormant, some bursts):
- **Per-agent average: ~100-300K output tokens/day = 3-9M tokens/mo/agent**

### Fleet sizes

| Configuration | Agents | Monthly tokens |
|---|---|---|
| 3 agents (early ramp) | 3 | ~10-25M |
| 10 agents (1 fleet) | 10 | ~35-80M |
| 20 agents (2 fleets) | 20 | ~70-160M |

### Total combined (personal + fleet)

| Phase | Personal | Agents | **Monthly total** |
|---|---|---|---|
| Phase 1 (now) | 5M | 0 | **~5M** |
| Phase 2 (early ramp) | 10M | 10M (3 agents) | **~20M** |
| Phase 3 (1 fleet) | 15M | 50M (10 agents) | **~65M** |
| Phase 4 (1 fleet + heavy usage) | 15M | 70M (10 agents, heavier) | **~85M** |
| Phase 5 (2 fleets) | 15M | 110M (20 agents) | **~125M** |

### Critical correction — model mix, not all K2.6

A realistic fleet doesn't use K2.6 for everything. Typical breakdown:
- **30% frontier (K2.6/Opus/GPT-5)**: planning, complex reasoning, critical coordination
- **40% mid-tier (Sonnet/K2.5/Haiku/Qwen3-32B)**: routine agent tasks
- **30% small/fast (Qwen3-8B/Gemma4/nano models)**: routing, classification, simple Q&A

This changes the cost math dramatically. Weighted blended cost per 1M output tokens (CAD):
- 30% K2.6 @ $6.38
- 40% Sonnet @ $20.55 (if Anthropic) OR K2.5 @ $2.74 OR Haiku @ $6.85
- 30% small @ ~$1

**Blended rate if using Sonnet for mid-tier**: (0.3 × 6.38) + (0.4 × 20.55) + (0.3 × 1) = **$10.44 CAD per 1M output**
**Blended rate if using K2.5 for mid-tier (mission-aligned)**: (0.3 × 6.38) + (0.4 × 2.74) + (0.3 × 1) = **$3.30 CAD per 1M output**
**Blended rate at pure K2.6 (worst case)**: $6.38 CAD per 1M output

---

## 2. Year-by-year projection

Assuming realistic ramp: start small (2026), add agents quarterly, reach full 20-agent fleet by 2028-2029.

### Your projected ramp

| Year | Phase | Monthly tokens | Blended cost @ $3.30/M (mission-aligned) | Blended @ $6.38/M (K2.6-heavy) |
|---|---|---|---|---|
| **Y1 (2026)** | Phase 2 (early ramp, 3 agents) | **20M** | $66/mo | $128/mo |
| **Y2 (2027)** | Phase 3 (1 fleet, 10 agents) | **65M** | $215/mo | $415/mo |
| **Y3 (2028)** | Phase 3 stable + growth | **80M** | $264/mo | $510/mo |
| **Y4 (2029)** | Phase 4 (1 fleet heavy) | **100M** | $330/mo | $638/mo |
| **Y5 (2030)** | Phase 5 (2 fleets, 20 agents) | **125M** | $413/mo | $798/mo |

### Per-year CAD cost (smart-routed, blended $3.30/M)

| Year | Mo volume | Monthly | **Annual** |
|---|---|---|---|
| Y1 | 20M | $66 | **$790** |
| Y2 | 65M | $215 | **$2,574** |
| Y3 | 80M | $264 | **$3,168** |
| Y4 | 100M | $330 | **$3,960** |
| Y5 | 125M | $413 | **$4,954** |
| **5yr total** | | | **~$15,450 CAD** |

### Per-year CAD cost (pure K2.6 routing, $6.38/M)

| Year | Mo volume | Monthly | **Annual** |
|---|---|---|---|
| Y1 | 20M | $128 | **$1,532** |
| Y2 | 65M | $415 | **$4,976** |
| Y3 | 80M | $510 | **$6,125** |
| Y4 | 100M | $638 | **$7,656** |
| Y5 | 125M | $798 | **$9,571** |
| **5yr total** | | | **~$29,860 CAD** |

---

## 3. Fixed-rate subscription fits

### Ollama Cloud Pro ($27 CAD/mo)

Pro specs: 3 concurrent models, 50× Free usage, session + weekly caps.

Realistic capacity: ~20-30M tokens/mo before weekly caps start throttling (estimate, not officially documented).

| Year | Volume | Pro sufficient? |
|---|---|---|
| Y1 (20M) | | ✅ Fits |
| Y2 (65M) | | ❌ Exceeds — will hit weekly caps frequently |
| Y3 (80M) | | ❌ Exceeds |
| Y4 (100M) | | ❌ Exceeds |
| Y5 (125M) | | ❌ Exceeds |

**Pro is a Y1 solution only.**

### Ollama Cloud Max ($137 CAD/mo)

Max specs: 10 concurrent models, 5× Pro usage, session + weekly caps.

Realistic capacity: ~100-150M tokens/mo (estimate, 5× Pro).

| Year | Volume | Max sufficient? |
|---|---|---|
| Y1 (20M) | | ✅ Fits (overkill) |
| Y2 (65M) | | ✅ Fits comfortably |
| Y3 (80M) | | ✅ Fits |
| Y4 (100M) | | ✅ Fits — at edge |
| Y5 (125M) | | ⚠️ May hit weekly caps at peak weeks |

**Max is good Y2-Y4 with possible overflow by Y5.**

### Anthropic Max 20x ($275 CAD/mo)

Covers Y1-Y3 comfortably for Claude-heavy usage. Y4+ starts hitting session caps.

**BUT**: violates the anti-Anthropic mission. Listed for completeness.

---

## 4. Cloud-only strategies — 5-year total cost

### Strategy 1: "Pure OpenRouter smart routing"
- Year-over-year pay-per-token with model diversity (K2.6 + Sonnet/K2.5/Haiku + small models)
- Blended rate scales with volume

| Blended rate | 5-year total |
|---|---|
| $3.30/M (mission-aligned, K2.5 mid-tier) | **$15,450 CAD** |
| $6.38/M (K2.6-heavy) | **$29,860 CAD** |
| $10.44/M (Claude-heavy) | **$48,940 CAD** |

### Strategy 2: "Ollama Pro Y1, Max Y2-Y5"
- Y1: Pro ($27) + some OR for overflow ($20) = $47/mo × 12 = $564
- Y2: Max ($137) + OR overflow ($30) = $167/mo × 12 = $2,004
- Y3: Max ($137) + OR overflow ($50) = $187/mo × 12 = $2,244
- Y4: Max ($137) + OR overflow ($80) = $217/mo × 12 = $2,604
- Y5: Max ($137) + OR heavy client overflow ($200) = $337/mo × 12 = $4,044
- **5-year total: ~$11,460 CAD**

### Strategy 3: "Ollama Max from Y2, with heavy OR fallback"
- Y1: Pro ($27) alone = $324
- Y2-Y5: Max ($137) + provider-pinned OR for client work (scales $30 → $250/mo) = avg $300/mo × 48 = $14,400
- **5-year total: ~$14,724 CAD**

### Strategy 4: "Anthropic Max 20x all 5 years"
- $275/mo × 60 months = **$16,500 CAD**
- BUT: violates mission, caps out Y4-Y5, doesn't scale

### Strategy 5: "Anthropic Max 20x + overflow"
- Base: $275/mo
- Overflow via OR when capped: $50-200/mo scaling
- Y1-Y5 average: ~$400/mo
- **5-year total: ~$24,000 CAD**

---

## 5. Hardware + cloud hybrid strategies

### Strategy 6: "Tier 1 hardware + Ollama Pro"
- Hardware: $17,000 upfront, amortized $3,070/yr over 5yr (with residual)
- Cloud: Pro $27/mo + OR overflow scales with years

| Year | HW amort | Cloud | Annual total |
|---|---|---|---|
| Y1 | $3,400 (incl. year-0) | $324 | $3,724 |
| Y2 | $3,070 | $1,000 | $4,070 |
| Y3 | $3,070 | $1,500 | $4,570 |
| Y4 | $3,070 | $2,000 | $5,070 |
| Y5 | $2,740 (adjusted for resale) | $3,000 | $5,740 |

**5-year total: ~$23,170 CAD**

Tier 1 caveat: only serves 1 user at 5-8 tok/s. Doesn't scale to 20-agent fleet locally. Most work still goes to cloud.

### Strategy 7: "Tier 2 hardware + Ollama Max"
- Hardware: $32,000 upfront, amortized $5,280/yr
- Cloud: Max $137/mo for overflow + OR for client work
- Y1-Y5 cloud varies: $1,800-3,500/yr
- Hardware can serve ~3 concurrent agents at 15-25 tok/s for K2.6, OR many more at Qwen3-8B/Gemma4 speeds

| Year | HW amort | Cloud | Annual |
|---|---|---|---|
| Y1 | $5,600 (yr-0) | $2,000 | $7,600 |
| Y2 | $5,280 | $2,000 | $7,280 |
| Y3 | $5,280 | $2,200 | $7,480 |
| Y4 | $5,280 | $2,500 | $7,780 |
| Y5 | $4,960 | $3,000 | $7,960 |

**5-year total: ~$38,100 CAD**

Tier 2 caveat: can absorb much of the fleet's smaller-model work (Qwen3-8B, Gemma4) locally. K2.6-quality work still flows to cloud until Tier 3.

### Strategy 8: "Tier 3 hardware + Ollama Pro minimal"
- Hardware: $78,000 upfront, amortized $11,940/yr
- Cloud: Pro $27/mo minimal backup = $324/yr
- Can serve most fleet work locally (30-50 tok/s K2.6, 5-8 concurrent)

| Year | HW amort | Cloud | Annual |
|---|---|---|---|
| Y1-Y5 | ~$11,940 | $324 | ~$12,264 |

**5-year total: ~$61,320 CAD**

Tier 3 caveat: handles full 20-agent fleet for most work. Cloud for swarm experiments or sovereignty-sensitive overflow only.

---

## 6. Strategy comparison summary

| Strategy | 5-yr total CAD | Notes |
|---|---|---|
| S2: Pro → Max + OR | **$11,460** | Cheapest. No hardware. Model diversity via Max catalog. |
| S1 blended (K2.5 mid): pay-per-token | $15,450 | Flexible, more per-request control |
| S3: Max Y2-Y5 + heavy OR | $14,724 | More headroom than S2 |
| S4: Max 20x fixed | $16,500 | Anthropic-ecosystem lock-in, violates mission |
| S5: Max 20x + overflow | $24,000 | |
| S6: Tier 1 hardware + Pro | $23,170 | Adds sovereignty; limited capacity |
| S1 (K2.6 heavy): pay-per-token | $29,860 | No subscriptions; volume-priced |
| S7: Tier 2 hardware + Max | $38,100 | Real local capacity |
| S1 (Claude heavy): pay-per-token | $48,940 | Tempting but mission-violating |
| S8: Tier 3 hardware | $61,320 | Datacenter-at-home, full sovereignty |

**Cheapest viable answer: Strategy 2 at ~$11,460 over 5 years = $2,292/yr average.** 

That's remarkably low compared to your prior $540/mo = $6,480/yr baseline — **65% reduction** by scaling smartly.

---

## 7. Break-even points

### When does each hardware tier pay back via cloud spend avoidance?

At what **monthly cloud spend** does each hardware tier become economically justified?

| Hardware tier | Break-even | Your profile reaches this at |
|---|---|---|
| Tier 1 ($17k) | ~$250/mo cloud | **Y2** (65M tokens = $215/mo) — close |
| Tier 2 ($32k) | ~$440/mo cloud | **Y4-Y5** (100-125M tokens = $330-413/mo at blended rate) — borderline |
| Tier 3 ($78k) | ~$995/mo cloud | **Never at smart-routed blended rate** |

### Reading the math

**At the mission-aligned blended rate ($3.30/M)**:
- None of the hardware tiers pay back on pure cost through Y5
- Hardware is justified ONLY by non-economic factors (sovereignty, independence, capability insurance)

**At K2.6-heavy rate ($6.38/M)**:
- Tier 1 pays back in Y3-Y4
- Tier 2 pays back right at Y5

**At Claude-heavy rate ($10.44/M)**:
- Tier 1 pays back in Y2
- Tier 2 pays back in Y3-Y4
- Tier 3 doesn't pay back even here

---

## 8. Phased strategy recommendation

### Phase 1 (now - Q3 2026): ramp-up, minimize commitment

- Pure cloud, smart routing
- Ollama Cloud **Pro** ($27 CAD/mo)
- Add OpenRouter selectively for client/audit work (~$20-40/mo)
- **Cost: ~$40-70 CAD/mo**
- Watch volume trends via `aicp --routing-report`

### Phase 2 (Q4 2026 - 2027): decision point

If monthly volume > 30M sustained, you've outgrown Pro:

- **Upgrade to Ollama Cloud Max** ($137 CAD/mo) + OR for client work
- **Cost: ~$150-200 CAD/mo**
- Continue monitoring for Y2 volume trend

### Phase 3 (2027-2028): stabilize or invest

At sustained 50-80M tokens/mo (your Y2-Y3 projection):

- **Option A (cloud-only)**: Max + OR = ~$200-280/mo. Annual ~$2,400-3,400.
- **Option B (hybrid)**: Tier 2 hardware ($32k) + Max ($137). Annual ~$7,500. Adds sovereignty.

**Decision factor**: is sovereignty/independence becoming more important? If yes → Option B. If cost-optimized → Option A.

### Phase 4 (2029+): scale to 2 fleets

At 100-125M tokens/mo:

- **Option A (cloud-only)**: Max + heavy OR overflow = ~$330-500/mo. Annual ~$4,000-6,000. Still cheaper than your prior $540/mo baseline.
- **Option B (Tier 2 bought earlier)**: same hardware still serves, cloud overflow scales. Annual ~$7-8k.
- **Option C (Tier 3 if revenue-attributable)**: ~$12k/yr all-in, handles full fleet locally.

---

## 9. Key assumptions and risks

### Assumptions

1. Ollama Cloud Pro realistic capacity ~20-30M tokens/mo before weekly caps throttle.
2. Max realistic capacity ~100-150M tokens/mo.
3. OpenRouter pricing stays within 20% of 2026-04-24 levels through 2030.
4. Token-to-work ratios don't dramatically change (model efficiency improves but is offset by more agent complexity).
5. Electricity in Ontario stays around $0.13/kWh through 2030.
6. Hardware depreciates to ~35% residual at 5 years.

### Risks that would change the math

**Risks that favor cloud (S1-S5)**:
- Cloud prices drop further (historical: ~30%/yr for open-weight models)
- K3 / next-gen models arrive and immediately supersede your hardware investment
- You don't actually reach the volumes projected (agents are lighter than expected)
- Hardware has an unexpected failure requiring replacement before 5-year depreciation
- Blackwell consumer GPUs land in 2026-2027 and are 2× cheaper than your Tier purchase

**Risks that favor hardware (S6-S8)**:
- Cloud prices rise (possible if vendor consolidation happens)
- You hit a sovereignty-mandatory workload that requires local (contract, regulation, client demand)
- Ollama Cloud's "5x Pro usage" cap turns out to be stricter than 150M tokens/mo
- Your volume grows faster than projected (3 fleets instead of 2)
- Mission weight increases — you decide local independence has standalone value

### Hidden risks

- **Agent inefficiency**: bad prompts can make a single agent consume 10× the expected tokens. If 1/20 agents misbehaves at 10M/mo extra, that's another $50-$100/mo.
- **Tool-call loops**: agents stuck in loops can burn tokens quickly. AICP needs good circuit breakers.
- **Context management**: long-horizon agent work with large contexts multiplies per-token cost (input tokens grow, not just output).
- **Experimentation**: occasional 300-agent swarm run spikes to 10-15M tokens in a single task.

---

## 10. My honest recommendation for your path

Given the projection:

1. **Through Y1-Y2**: Stay cloud-only on Strategy 2 (Pro → Max + OR). Cost: $500-2,000/yr. **No hardware investment.** Save the $30k for later capability purchases.

2. **Y2-Y3 checkpoint**: Review actual usage. If sustained ~50M tokens/mo for 6+ months AND sovereignty becomes critical (client work, regulatory) → buy **Tier 2 hardware**.

3. **Y3-Y4**: If still cloud-only and working fine at Strategy 2 → continue. If hardware bought, amortization kicks in; continue with hybrid.

4. **Y5+**: At 2-fleet scale, hybrid becomes meaningful. Tier 2 + Max overflow is the equilibrium for full operation at ~$8k/yr. That's economically comparable to cloud-only at K2.6-heavy rate.

5. **Do NOT buy Tier 3 ($78k) unless**:
   - You've been generating revenue from AI work for 12+ months
   - You're serving multiple users/clients
   - Sovereignty isn't just a preference but a business requirement

### The critical insight

Your **prior $540/mo baseline was 2-3× what you actually need**. Even at full 2-fleet scale (Y5), smart-routed cloud costs ~$330-500/mo — **still below your old pattern**. 

The decision isn't "spend more to get more capability." It's **"spend less, get more capability, save ~$12-18K over 5 years just from smart tier selection."**

Hardware investment is capability insurance, not cost optimization. The economic case doesn't close strongly on hardware under normal Y1-Y5 growth — only mission-alignment does.

---

## 11. Quick reference — what this means for decisions in 2026

| Question | Answer |
|---|---|
| Should I buy Tier 2 hardware today? | **No** — you haven't proven the volume yet. Wait for Y2 data. |
| Should I buy Tier 1 hardware today? | **Only if sovereignty for Y1 feels critical.** Otherwise no. |
| Ollama Pro or Max right now? | **Pro** ($27). You're not at Max-justifying volume yet. |
| Keep Anthropic Max 20x? | **No** — violates mission, 2-3× more expensive than smart routing. |
| Activate OpenRouter? | **Yes** — for client/private work with pinned provider. ~$20-40/mo. |
| When to revisit Max subscription? | When you hit sustained 30M+ tokens/mo for 2 consecutive months. |
| When to revisit Tier 2 hardware? | When you sustain 50M+ tokens/mo for 6 months AND can make a case for sovereignty being worth $30k. |

---

## 12. File references

- Cloud economics detail: `CLOUD-SPEND-SCENARIOS-2026-04-24.md`
- Hardware tier detail: `HARDWARE-BUILD-SCENARIOS-2026-04-24.md`
- Model catalog / pricing: `MODEL-ECOSYSTEM-FULL-MAP-2026-04-24.md`
- Today's handoff index: `SESSION-2026-04-24-HANDOFF.md`
- Conversation persistence: `SESSION-2026-04-24-CONVERSATION-LOG.md`

---

*Projection based on verified 2026-04-24 pricing. Assumptions explicitly stated. Volume estimates based on typical agent/session patterns — operator's actual measured usage may differ. Revisit annually.*
