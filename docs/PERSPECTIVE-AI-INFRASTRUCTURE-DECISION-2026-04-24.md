# Perspective — AI Infrastructure Decision Framework

**Date**: 2026-04-24
**Status**: Strategic decision document. Sharp, opinionated, short.
**Meant for**: second-brain ingestion + durable reference for future AI-infrastructure decisions.
**Sourced from**: full analysis in `MODEL-ECOSYSTEM-FULL-MAP-2026-04-24.md`, `SCALING-PROJECTION-5YR-2026-04-24.md`, `HARDWARE-BUILD-SCENARIOS-2026-04-24.md`, `CLOUD-SPEND-SCENARIOS-2026-04-24.md`.

---

## The core insight

> **Hardware is capability insurance, not cost optimization.**
>
> Under realistic 5-year workload projections (2-3 personal sessions + 10-20 fleet agents), **no hardware tier economically pays back** against smart-routed cloud usage. The cheapest cloud strategy runs ~$2,300 CAD/year average over 5 years for the operator's projected full-scale workload — less than half the operator's pre-mission $540/month baseline.
>
> Hardware investment only justifies itself through non-economic factors: sovereignty, client-privacy requirements, offline capability, mission alignment (independence from any single provider). When those factors weigh enough, the hardware cost is the price of that capability — not a cheaper way to do what cloud already does.

---

## The corollary finding

> **The operator's prior $540 CAD/month baseline was 2-3× what the workload actually costs at any scale.** Smart routing across Ollama Cloud Pro/Max + OpenRouter with pinned providers + occasional local-sovereignty-fallback handles everything up to 2-fleet scale (125M tokens/mo) for **$330-500/mo maximum**. At today's usage, the same smart stack is **$40-70/mo**.
>
> The largest-ROI action from the entire 2-day analysis is: **switch from single-provider habit to smart-routed tiering. Saves $12-18K over 5 years. Zero hardware required.**

---

## The decision framework — what to decide, and when

### Phase 1 (2026, today): ramp-up

- Cloud-only, no hardware purchase
- Ollama Cloud **Pro** ($27 CAD/mo)
- OpenRouter selectively ($20-40 CAD/mo) for client work with pinned provider
- Local K2.6 Q2 as sovereignty fallback (already running; marginal cost)
- **Budget: $40-70 CAD/mo**

### Phase 2 (Q4 2026 - 2027): Pro → Max transition

**Trigger**: sustained >30M output tokens/mo for 2 consecutive months

- Ollama Cloud **Max** ($137 CAD/mo)
- OpenRouter client-work budget scales ($30-80 CAD/mo)
- **Budget: $150-220 CAD/mo**

### Phase 3 (2027-2028): hardware decision point

**Trigger**: sustained 50M+ tokens/mo for 6+ months AND sovereignty becoming critical (client work, regulatory, independence weighs heavily)

- Decision: Tier 2 hardware ($32k CAD) + Max subscription OR continue cloud-only
- Cloud-only: ~$2,400-3,400/year
- Hybrid: ~$7,500/year (+ one-time $32k)
- **Decide based on sovereignty weight, not cost**

### Phase 4 (2029+): scale

- If cloud-only: Max + OR at full scale = $4,000-6,000/year
- If hybrid (Tier 2 bought earlier): $7,000-8,000/year annualized
- Either works; tradeoff is independence vs capital efficiency

---

## The rules (what NOT to do)

1. **Never buy Tier 3 hardware ($78k CAD) unless**:
   - AI work is generating measurable revenue for 12+ months
   - You're serving multiple users/clients who need local
   - Sovereignty is a hard business requirement, not a preference

2. **Never default to Anthropic subscriptions at heavy volume**. Claude Max 20x at $275/mo is comparable cost to Ollama Max, but violates the mission (independence from Anthropic). Only reasonable if Anthropic brand-quality is load-bearing for specific work.

3. **Never route client/employer work through Ollama Cloud** (any tier). Shared pool, opaque providers. Use OpenRouter with pinned vetted provider OR local.

4. **Never upgrade cloud tier in response to a usage spike**. Wait for sustained usage (2+ consecutive months) before committing.

5. **Never buy hardware speculatively**. Only buy when you have 6+ months of usage data showing the capacity is actually needed AND mission/sovereignty weight justifies it.

6. **Never conflate cost optimization with independence mission**. They lead to different answers. Pick explicitly.

---

## The question to ask every decision point

**"Am I buying this because it's cheaper, or because I want the capability regardless of cost?"**

If cheaper → the math matters. Do the token volume calculation. Usually cloud wins.

If capability regardless of cost → the math is secondary. Decide based on:
- How long will this hardware stay relevant? (Blackwell in 2026-2027 will shift the calculus)
- What does operator-control feel like vs. cloud-dependency?
- Is the sovereignty value terminal (an end in itself) or instrumental (a means to some other end)?

---

## Risk to this framework

- **Cloud prices rise unexpectedly** — possible if provider consolidation happens. Historical trend is opposite (prices falling 30%/yr for open models) but not guaranteed.
- **Regulatory change** — data residency / client-contract terms may make local inference legally required, changing the calculus.
- **Mission weight increases** — operator may decide independence matters more than cost. Legitimate; the math doesn't fight the decision.
- **Next-gen model architectures shift hardware requirements** — K3 / GPT-6 / Claude 5 may need different hardware than today's Tier 1/2/3 specs.

---

## Reference matrix

| Question | Answer | Confidence |
|---|---|---|
| Cheapest viable path over 5 years | Ollama Pro → Max + OR overflow | High |
| Expected 5-year cost, cheapest path | ~$11,460 CAD | Medium (assumes projected ramp) |
| Break-even spend for Tier 2 hardware | ~$440 CAD/mo sustained cloud | High |
| Does operator's projected volume cross Tier 2 break-even? | Only Y4-Y5 at pure K2.6 routing; never at smart-routed blended | Medium |
| Should operator buy hardware this year (2026)? | **No** | High |
| Should operator subscribe to Anthropic Max? | **No** (mission violation) | High |
| Should operator activate Ollama Cloud Pro now? | **Yes** ($27 CAD/mo) | High |
| Should operator keep OpenRouter active? | **Yes** (for client/pinned work) | High |
| Should operator keep local K2.6 running? | **Yes** (sovereignty fallback, marginal cost) | High |

---

## What this perspective explicitly rejects

- "Bigger hardware = more capability = more value"— only if the capability is actually consumed. At the operator's realistic scale, most Tier 2/3 capability sits unused most of the time.
- "Flat-rate subscriptions are always cheaper than per-token" — only above the breakeven point, and both Ollama Pro and Max have usage caps that reintroduce per-token-like throttling at the top end.
- "Local is always better for privacy" — true in principle, but local at 0.3-1 tok/s on current hardware means most work STILL goes to cloud anyway. Sovereignty only meaningful if local tier is actually usable.
- "Claude is the benchmark" — it was for the last 2 years. K2.6 via OpenRouter is 5-7× cheaper at comparable agentic quality. The mission exists precisely because Claude is no longer the unique right answer.

---

## Anchor for future sessions

When operator (or future AI session) considers AI infrastructure spending:

1. **Start by asking**: what's the current sustained monthly token volume? (Not projected; measured.)
2. **Match to the phased table above.** Don't jump phases without evidence of sustained need.
3. **If considering hardware**: compute the break-even point. Then ask the "am I buying cost optimization or capability insurance" question honestly.
4. **If the answer is capability insurance**: proceed with eyes open about the 5-year cost. Don't pretend it's cheaper. It isn't.
5. **If the answer is cost optimization**: smart cloud routing almost always wins. Revisit hardware only when the tables clearly show otherwise.

---

## One-line summaries

- **For the brain's knowledge graph**: "AI infrastructure decisions split into cost-optimization (cloud wins almost always) and capability-insurance (hardware justifies on non-economic grounds)."
- **For operator's future self**: "Your $540/mo baseline was wrong. Smart routing replaces it at 1/10 the cost. Don't buy hardware for economic reasons. Buy it when sovereignty is worth the $30-80k tab."
- **For future sessions working with operator**: "Measure before proposing spend. Smart cloud routing is default. Hardware is a mission decision, not a cost decision."

---

*end of perspective — 2026-04-24*
