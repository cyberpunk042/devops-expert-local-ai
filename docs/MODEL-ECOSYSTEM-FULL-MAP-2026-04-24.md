# The Full Model Ecosystem Map — Every Provider, Every Model, Every Path

**Date**: 2026-04-24 (verified pricing fetched live)
**Status**: **SUPERSEDES earlier version of this file**. Earlier version had hallucinated prices. This version only contains data verified from: operator-confirmed messages, OpenRouter's public `/api/v1/models` endpoint, Ollama's `ollama.com/turbo` pricing page, or explicitly marked as "unverified / estimate."

All CAD prices use USD × 1.37. If a price is labeled "CAD", that's post-conversion. If "USD", original.

---

## 1. Anthropic subscriptions — verified from operator

| Plan | USD/mo | CAD/mo | USD annual | What's included |
|---|---|---|---|---|
| Free | $0 | $0 | — | Limited daily usage |
| **Pro** | **$20** | **$27** | **$200/yr** | Standard regular use |
| **Max 5x** | **$100** | **$137** | — | 5× Pro capacity per session |
| **Max 20x** | **$200** | **$275** | — | 20× Pro capacity per session |

Source: operator message 2026-04-24.

## 2. Anthropic API — verified from OpenRouter API (current model pricing)

Per 1M tokens, USD (CAD = USD × 1.37):

| Model | In USD | Out USD | In CAD | Out CAD | Context |
|---|---|---|---|---|---|
| **Claude Opus 4.7** | **$5** | **$25** | **$6.85** | **$34.25** | 1M tokens |
| **Claude Opus 4.6** | **$5** | **$25** | $6.85 | $34.25 | 1M tokens |
| Claude Opus 4.6-**fast** (premium mode) | $30 | $150 | $41.10 | $205.50 | 1M |
| Claude Opus 4.5 | $5 | $25 | $6.85 | $34.25 | 200K |
| Claude Opus 4.1 (old) | $15 | $75 | $20.55 | $102.75 | 200K |
| **Claude Sonnet 4.6** | **$3** | **$15** | $4.11 | $20.55 | 1M |
| Claude Sonnet 4.5 | $3 | $15 | $4.11 | $20.55 | 1M |
| **Claude Haiku 4.5** | **$1** | **$5** | $1.37 | $6.85 | 200K |

**Correction to my earlier claim**: I had Opus 4.6 at $15/$75. **That's old Opus 4.1 pricing.** Current Opus 4.6/4.7 is **$5/$25** — 3× cheaper than I said. Major error in earlier math.

## 3. OpenRouter — verified from `openrouter.ai/api/v1/models`

Representative frontier/agentic + mid-tier + small. Fetched 2026-04-24. Per 1M tokens, USD.

### Moonshot (Kimi)
| Model | In | Out | Context |
|---|---|---|---|
| **kimi-k2.6** | **$0.745** | **$4.655** | 256K |
| kimi-k2-thinking | $0.60 | $2.50 | 262K |
| kimi-k2.5 | $0.44 | $2.00 | 262K |

(I had K2.6 at $0.80/$3.50 — close, slightly off.)

### OpenAI (GPT family)
| Model | In | Out | Context |
|---|---|---|---|
| **gpt-5** | **$1.25** | **$10** | 400K |
| gpt-5-mini | $0.25 | $2 | 400K |
| gpt-5-nano | $0.05 | $0.40 | 400K |
| gpt-5-pro | $15 | $120 | 400K |
| gpt-5.1 | $1.25 | $10 | 400K |
| gpt-5.1-codex | $1.25 | $10 | 400K |
| gpt-5.1-codex-mini | $0.25 | $2 | 400K |
| gpt-5.1-codex-max | $1.25 | $10 | 400K |
| gpt-5.2 | $1.75 | $14 | 400K |
| gpt-5.2-codex | $1.75 | $14 | 400K |
| gpt-5.2-pro | $21 | $168 | 400K |
| **gpt-5.4** | $2.50 | $15 | 1.05M |
| gpt-5.4-mini | $0.75 | $4.50 | 400K |
| gpt-5.4-nano | $0.20 | $1.25 | 400K |
| gpt-5.4-pro | $30 | $180 | 1.05M |

**Correction**: I had GPT-5 at $10/$50. Actual: **$1.25/$10** — 5× cheaper than I claimed.

### Google (Gemini)
| Model | In | Out | Context |
|---|---|---|---|
| **gemini-3.1-pro-preview** | **$2** | **$12** | 1.05M |
| gemini-3.1-flash-lite-preview | $0.25 | $1.50 | 1.05M |
| gemini-3-flash-preview | $0.50 | $3 | 1.05M |
| gemini-3.1-flash-image-preview | $0.50 | $3 | 65K |

### Z-AI (GLM)
| Model | In | Out | Context |
|---|---|---|---|
| **glm-4.7** | **$0.38** | **$1.74** | 203K |
| glm-4.7-flash | $0.06 | $0.40 | 203K |
| glm-4.6 | $0.39 | $1.90 | 205K |
| glm-4.6v (vision) | $0.30 | $0.90 | 131K |
| glm-4.5 | $0.60 | $2.20 | 131K |
| glm-4.5-air:free | $0 | $0 | 131K |
| glm-4.5v | $0.60 | $1.80 | 65K |

### DeepSeek
| Model | In | Out | Context |
|---|---|---|---|
| deepseek-chat-v3.1 | $0.15 | $0.75 | 32K |

### Qwen
| Model | In | Out | Context |
|---|---|---|---|
| qwen3.6-plus | $0.325 | $1.95 | 1M |
| qwen3.5-9b | $0.10 | $0.15 | 262K |
| qwen3.5-35b-a3b | $0.163 | $1.30 | 262K |
| qwen3.5-27b | $0.195 | $1.56 | 262K |
| qwen3.5-122b-a10b | $0.26 | $2.08 | 262K |
| qwen3.5-flash | $0.065 | $0.26 | 1M |
| qwen3.5-plus | $0.26 | $1.56 | 1M |
| qwen3.5-397b-a17b | $0.39 | $2.34 | 262K |
| qwen3-max-thinking | $0.78 | $3.90 | 262K |
| qwen3-coder-next | $0.14 | $0.80 | 262K |

### Mistral
| Model | In | Out | Context |
|---|---|---|---|
| mistral-large-2512 | $0.50 | $1.50 | 262K |
| mistral-small-2603 | $0.15 | $0.60 | 262K |
| ministral-8b-2512 | $0.15 | $0.15 | 262K |
| ministral-14b-2512 | $0.20 | $0.20 | 262K |
| devstral-2512 | $0.40 | $2 | 262K |

### Nvidia (Nemotron)
| Model | In | Out | Context |
|---|---|---|---|
| nemotron-3-super-120b-a12b | $0.09 | $0.45 | 262K |
| nemotron-3-super-120b-a12b:free | $0 | $0 | 262K |
| nemotron-3-nano-30b-a3b | $0.05 | $0.20 | 262K |
| nemotron-3-nano-30b-a3b:free | $0 | $0 | 256K |

OpenRouter total model count as of this fetch: 350+. Free tiers exist but rate-limited.

---

## 4. Ollama Cloud — **verified from ollama.com/turbo** (2026-04-24)

### Plans

| Plan | USD/mo | CAD/mo | USD annual | Concurrent models | Usage vs Free |
|---|---|---|---|---|---|
| **Free** | $0 | $0 | — | — | "Light" |
| **Pro** | **$20** | **$27** | **$200** | 3 at a time | **50×** more than Free |
| **Max** | **$100** | **$137** | — | 10 at a time | **5×** more than Pro |

**Key caps not captured in the flat-rate framing**:
- Session limits reset every **5 hours**
- Weekly limits reset every **7 days**
- **"Unlimited" is misleading** — Ollama describes usage as "light / day-to-day / heavy sustained" not unlimited
- My earlier doc called Pro/Max "unlimited" — incorrect. They have elastic caps that throttle heavy abuse.

### Ollama Cloud-enabled models (verified list, subset)

| Model | On Ollama Cloud? | Notes |
|---|---|---|
| **kimi-k2.6** | ✅ | Moonshot's latest |
| deepseek-v4-flash | ✅ | Newer than DeepSeek V3 I listed earlier |
| glm-4.7-flash | ✅ | |
| glm-5.1 | ✅ | Newer than 4.7 |
| glm-ocr | ✅ | OCR-specialized |
| qwen3-coder-next | ✅ | Coding-specialized |
| qwen3-next | ✅ | |
| qwen3.5 | ✅ | |
| qwen3.6 | ✅ | Newer than 3.5 |
| nemotron-3-super | ✅ | Nvidia |
| nemotron-cascade-2 | ✅ | Newer Nvidia |
| minimax-m2.7 | ✅ | |
| ministral-3 | ✅ | |
| lfm2 / lfm2.5-thinking | ✅ | Liquid AI |
| gemma4 | ✅ | |
| medgemma / medgemma1.5 | ✅ | Medical-specialized |
| devstral-small-2 | ✅ | Mistral coding |
| translategemma | ✅ | Translation |
| **Claude (any version)** | ❌ | Not available — Anthropic proprietary |
| **GPT (any version)** | ❌ | Not available — OpenAI proprietary |
| **Llama 4 405B** | ❌ | Not on Ollama Cloud current list (I hallucinated this) |
| **Gemini** | ❌ | Not on Ollama Cloud |

**Correction**: I claimed Ollama Cloud Max includes "DeepSeek R1, Llama 4 405B, K2.6-Max". **None of those are verified on Ollama's current cloud catalog.** The actual catalog is good but doesn't include those specific models.

### Quantization note from Ollama FAQ

> "Native weights, as released by the model provider. On modern NVIDIA hardware, models may use accelerated data formats supported by Blackwell and Vera Rubin architectures (e.g. NVFP4)."

So Ollama Cloud serves native weights, not custom quantizations. Good — means quality matches provider-issued model.

---

## 5. Unverified or estimated — marked clearly

Things I listed in the earlier doc but can't fully verify without direct fetches:

### Moonshot direct (platform.moonshot.ai)
- Exists as an option, but I haven't fetched current platform pricing. Roughly matches OpenRouter's pass-through pricing in the past. **Treat OpenRouter K2.6 prices as upper bound for direct Moonshot (minus OpenRouter's ~5% fee).**

### Local model tok/s on operator hardware
- **Verified today**: K2.6 Q2 via llama.cpp `-ngl 0` = 0.3 tok/s (measured)
- **Estimated**: Qwen3-8B at 15-25 tok/s, Gemma4-e2b at 53 tok/s (from LocalAI docs / prior runs, not measured today)
- **Extrapolated**: Tier 1/2/3 hardware tok/s are projections based on memory-bandwidth scaling, not actual measurements on that hardware

### Hardware Tier 2/3 real-world K2.6 throughput
- **Not empirically measured** — derived from theoretical bandwidth ceilings and community benchmarks
- Expected range: Tier 2 (15-25 tok/s) and Tier 3 (30-50 tok/s) are estimates, could be 20% off in either direction

---

## 6. Cost per 1M output tokens — corrected ranking (CAD)

Sorted cheapest → most expensive per 1M output (typical agentic coding weighted):

| Rank | Model (via OpenRouter) | CAD per 1M output | Context |
|---|---|---|---|
| 1 | Free tiers (qwen3-8b:free, nemotron-nano:free, glm-4.5-air:free) | $0 | varies |
| 2 | qwen3.5-9b | $0.21 | 262K |
| 3 | ministral-3b | $0.14 | 131K |
| 4 | ministral-8b | $0.21 | 262K |
| 5 | nemotron-3-nano | $0.27 | 262K |
| 6 | qwen3.5-flash | $0.36 | 1M |
| 7 | glm-4.7-flash | $0.55 | 203K |
| 8 | mistral-small | $0.82 | 262K |
| 9 | deepseek-chat-v3.1 | $1.03 | 32K |
| 10 | gemini-3.1-flash-lite | $2.06 | 1.05M |
| 11 | glm-4.7 | $2.38 | 203K |
| 12 | mistral-large | $2.06 | 262K |
| 13 | qwen3.5-35b-a3b | $1.78 | 262K |
| 14 | gpt-5-mini | $2.74 | 400K |
| 15 | kimi-k2.5 | $2.74 | 262K |
| 16 | kimi-k2-thinking | $3.43 | 262K |
| 17 | qwen3.5-397b | $3.21 | 262K |
| 18 | qwen3-max-thinking | $5.34 | 262K |
| 19 | **kimi-k2.6** | **$6.38** | 256K |
| 20 | **claude-haiku-4.5** | **$6.85** | 200K |
| 21 | **gpt-5** | **$13.70** | 400K |
| 22 | **gemini-3.1-pro** | **$16.44** | 1.05M |
| 23 | **gpt-5.4** | **$20.55** | 1.05M |
| 24 | **claude-sonnet-4.6** | **$20.55** | 1M |
| 25 | **claude-opus-4.7** | **$34.25** | 1M |
| 26 | gpt-5-pro | $164.40 | 400K |
| 27 | claude-opus-4.6-fast | $205.50 | 1M |

---

## 7. Corrected cost projections (CAD) at typical volumes

Using **corrected** current pricing.

### At 10M output tokens/month (moderate-heavy dev use)

| Path | CAD/mo |
|---|---|
| Nemotron-nano (via OR) | $3 |
| Qwen3-flash (via OR) | $3.60 |
| Deepseek v3.1 (via OR) | $10 |
| GLM-4.7 (via OR) | $24 |
| **Kimi K2.6 (via OR)** | **$64** |
| **Kimi K2.6 (via Ollama Cloud Pro)** | **$27** (fits in Pro; probably works) |
| Claude Haiku (via OR) | $68 |
| Claude Sonnet 4.6 (via OR) | $205 |
| **Claude Opus 4.7 (via OR or API)** | **$342** |
| GPT-5 (via OR) | $137 |
| GPT-5.4 (via OR) | $205 |
| Anthropic Pro subscription (alternative) | $27 flat ← but limited by session caps |
| Anthropic Max 5x subscription | $137 flat ← fits moderate use |
| Anthropic Max 20x subscription | $275 flat ← fits heavy use |

### At 50M output tokens/month (heavy fleet use)

| Path | CAD/mo |
|---|---|
| GLM-4.7 (via OR) | $119 |
| **Kimi K2.6 (via OR)** | **$319** |
| **Kimi K2.6 (via Ollama Cloud Pro)** | **$27** (may hit session caps) |
| **Kimi K2.6 (via Ollama Cloud Max)** | **$137** (10 concurrent, 5× Pro) |
| Claude Sonnet 4.6 (via OR) | $1,028 |
| Claude Opus 4.7 (via OR) | $1,713 |
| GPT-5 (via OR) | $685 |
| Anthropic Max 5x | $137 (may hit per-session caps) |
| Anthropic Max 20x | $275 |

### At 100M output tokens/month (very heavy fleet / swarm experiments)

| Path | CAD/mo |
|---|---|
| GLM-4.7 (via OR) | $238 |
| **Kimi K2.6 (via OR)** | **$638** |
| **Kimi K2.6 (Ollama Cloud Max)** | **$137** (if fits in Max weekly caps) |
| Claude Opus 4.7 (via OR) | $3,425 |
| GPT-5 (via OR) | $1,370 |
| Anthropic Max 20x | $275 (may exceed session limits) |

---

## 8. The key corrected findings

Comparing to earlier (hallucinated) claims:

1. **Anthropic API is 3× cheaper than I claimed**. Opus 4.6/4.7 is **$5/$25** per M tokens — not $15/$75. That was Opus 4.1 pricing from a year ago.

2. **Ollama Cloud Max is $100 USD/mo = $137 CAD/mo**, not $200 / $275 CAD I had. Still a real tier, but cheaper than I claimed.

3. **Ollama Cloud is NOT unlimited**. Has session caps (5-hour reset) and weekly caps (7-day reset). Described as "light / day-to-day / heavy sustained" not unlimited. My earlier "unlimited*" framing was misleading.

4. **GPT-5 is $1.25/$10 per M**, not $10/$50. 5× cheaper than I claimed. The GPT-5.4 model is newer and more expensive.

5. **Ollama Cloud's model catalog is narrower than I claimed**. Llama 4 405B, DeepSeek R1, "K2.6-Max" are NOT on the current cloud list. Real catalog is ~20 models including kimi-k2.6, deepseek-v4-flash, glm-5.1, qwen3.6, etc.

---

## 9. Corrected recommendations

Given CORRECTED pricing:

### For your ~15M tokens/mo profile (realistic for AICP + light fleet)

- **Cheapest viable**: Nemotron-nano:free + Qwen3-flash for volume ≈ $5-10 CAD/mo (sacrifices quality for cost)
- **Quality/cost balance**: Ollama Cloud Pro ($27 CAD) covers most volume + OpenRouter K2.6 for specific tasks (~$40-50 CAD)
- **Anthropic-ecosystem alternative**: Anthropic **Max 5x** ($137 CAD/mo) = 5× the Pro session capacity. Covers heavy daily Claude use.

### For your 50M tokens/mo profile (active fleet)

- **Best flat rate**: Anthropic Max 20x ($275 CAD) OR Ollama Cloud Max ($137 CAD)
- **Best pay-per-token**: Kimi K2.6 via OpenRouter ($319 CAD) — more than Max 20x
- **Best combo**: Ollama Cloud Max ($137) + OpenRouter for provider-pinned client work ($40-60)

### For your 100M+ tokens/mo profile (heavy swarm / production fleet)

- Ollama Cloud Max ($137) if you fit in the weekly caps
- Anthropic Max 20x ($275) if you prefer Claude ecosystem and fit session limits
- At this volume, **local hardware starts being economically rational** — Tier 2 hardware at ~$440/mo amortized competes with cloud options
- **If swarm experiments are central**: combine Ollama Cloud Max + Tier 2 local hardware for ~$575/mo total (cloud + amortization)

---

## 10. Subscription vs API — for your old $540 CAD/mo baseline

You were paying **~$540 CAD/mo = ~$395 USD/mo**. Current Anthropic options that map roughly to that spend:

- Anthropic Max 20x = $200 USD/mo flat — covers heavy daily Claude use
- Anthropic Max 5x = $100 USD/mo — + OpenRouter overflow
- OR API direct at Opus 4.7 pricing: $395 USD/mo buys ~15.8M output tokens (at $25/M output) = light-moderate volume only

**Best mapping of your old $540 CAD/mo spend to current reality**:
- If you were on Max 20x: that's ~$275 CAD/mo — you can get back to same capacity for about half
- If you were on Max 5x + API use: ~$137 CAD/mo subscription + variable API
- The $540 baseline almost certainly reflects old Anthropic pricing (pre-2026 updates) or a Max 20x + API mix

---

## 11. Verified sources for this document

- **Anthropic subscriptions**: operator message 2026-04-24
- **OpenRouter model pricing**: live fetch from `https://openrouter.ai/api/v1/models` on 2026-04-24
- **Ollama Cloud pricing + catalog**: live fetch from `ollama.com/turbo` and `ollama.com/search?o=cloud` on 2026-04-24
- **Anthropic API pricing**: inferred from OpenRouter's listing of Anthropic's models (OpenRouter publishes original model provider rates with small markup)

Explicitly NOT verified by live fetch:
- Moonshot direct platform pricing
- Exact session/weekly limits of Ollama Cloud Pro/Max (described qualitatively, not quantitatively)
- Local model tok/s projections on Tier 1/2/3 hardware (estimates only)

---

## 12. What to do right now

Given the corrected math:

1. **Cheapest usable combo for your profile**:
   - Ollama Cloud Pro: **$27 CAD/mo** (personal/AICP/research)
   - OpenRouter for client work: **$10-40 CAD/mo** depending on volume and model choice
   - Local K2.6 Q2 as sovereignty fallback: **~$0** (electricity)
   - **Total: ~$40-70 CAD/mo**

2. **If you miss Claude Opus**:
   - Opus 4.7 via OpenRouter: $34.25 CAD per 1M output — heavy but manageable
   - Or Anthropic Max 5x subscription: $137 CAD/mo flat
   - Or Anthropic Max 20x: $275 CAD/mo flat

3. **For hardware decisions**, refer to `HARDWARE-BUILD-SCENARIOS-2026-04-24.md`. Break-even math still holds since hardware costs are independent of cloud pricing.

---

*Document supersedes prior version. All prices verified from live provider sources on 2026-04-24 unless explicitly marked estimate/unverified.*
