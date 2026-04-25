# Handoff — Pre-Compaction Session Summary (2026-04-24)

**Written**: 2026-04-24 evening, immediately before context compaction.
**For**: next session (same operator), to re-enter the work with full situational awareness.
**Read first**: this document. Then dive into specifics via the references at bottom.

---

## 1. Mission status (one paragraph)

Mission: post-Anthropic self-autonomous AI stack by 2026-04-27. **Local K2.6 Q2 serving on operator's Tier 0 hardware is technically reached** — server running on port 8091, AICP routing works, empirical tok/s measured. Cloud tier strategy (smart routing: Ollama Cloud Pro + OpenRouter + Local sovereignty fallback) identified as the **highest-ROI action** — drops $540/mo baseline spend to ~$40-70/mo with zero hardware investment. Hardware upgrades remain "capability insurance, not cost optimization" at operator's projected workload scale.

---

## 2. System state right now

### Local K2.6 server

- **Running**: llama-server PID ~155084 on `localhost:8091`
- **Memory**: ~47-52 GB RSS of 56 GB WSL cap
- **Model**: Unsloth Q2_K_XL GGUF at `/mnt/models/kimi-k2-6-q2/UD-Q2_K_XL/`
- **Config**: `-ngl 0`, `--ctx-size 4096`, threads 4, no chat-template override (uses K2.6 embedded template with thinking=1 default)
- **Launch script**: `scripts/llama-serve.sh`
- **Kill if needed**: `kill 155084` (or `pkill -x llama-server`)
- **Restart time if killed**: 60-90 min cold mmap reload (WSL invalidates page cache on process exit)

### AICP

- `config/default.yaml`: `backends.k2_6_local.enabled: true`, `timeout: 1800`, circuit breaker `failure_threshold: 3`
- **Uncommitted changes**: `config/default.yaml` (timeout + breaker edits from this session, not yet committed)
- `k2_6_local` adapter already built (committed `f66dd14`), OpenAI-compat HTTP to 8091
- AICP `--check` reports `[OK] k2_6_local: OK`
- Failover chain: `local → k2_6_local → k2_6_openrouter → openrouter → claude` (empirically validated via Experiment C)

### Storage (per `docs/STORAGE.md`)

- `/` (WSL root, /dev/sdc): 15 GB used of 1 TB
- `/mnt/models` (NVMe VHDX, 700 GB): 338 GB used — K2.6 weights + LocalAI weights
- `/mnt/dev-envs` (H:\ SATA RAID VHDX, 50 GB): 12 GB used — kt-kernel venv (now mostly unused), llama.cpp build (~2GB)
- WSL ubuntu-24.04 VHDX: reclaimed to ~55 GB actual allocation after fstrim (was 428 GB bloated)

### Git

- Branch: `main`, 3 commits ahead of origin
- Uncommitted: `config/default.yaml` (modified), `docs/EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md` (untracked)
- Recent commits: 2e272bd (docs + llama-serve.sh), 47a4f4d (initial handoff), f796bae, c429531, f66dd14

---

## 3. Empirical findings from this session (THE numbers)

### K2.6 Q2 on Tier 0 hardware — measured, not estimated

| Metric | Measured |
|---|---|
| Cold load (first time, NTFS warm) | 17 min |
| Cold load (after WSL restart, NTFS cold) | 85 min |
| Read rate during load | 85-500 MB/s (vs NVMe raw 3 GB/s — 3-17% efficiency) |
| RSS at steady-load | 47-54 GB stable (kernel managing page cache) |
| **Warm inference WITH thinking** | **0.045 tok/s** (22 sec per output token) |
| **Warm inference WITHOUT thinking** | **0.10 tok/s** (10 sec per output token) |
| Prefill cost (per fresh input token) | 15-22 sec |
| Prefill on cached input | near-free (13/14 cached in test 2) |
| Page cache hit rate | ~15% (47 GB / 318 GB file) |
| First-request wall time (simple Q&A) | 51 sec (thinking off) to 7+ min (thinking on, cut-off) |

### Earlier theory docs were wrong on Tier 0 throughput

- Earlier estimate: 0.3-1 tok/s warm
- Actual: 0.045-0.10 tok/s — **~10× worse**
- Reason: i7-7800X + DDR4-2666 + WSL is a LOW sub-tier of Tier 0; earlier estimate assumed newer consumer/workstation CPU

### Key operational insight discovered

**llama.cpp accepts `chat_template_kwargs: {"thinking": false}` via OpenAI-compat API passthrough**. K2.6 responds in "instant mode" without reasoning chain. Dramatically faster on slow hardware. BUT: llama.cpp stores instant-mode response in `reasoning_content` field rather than `content` — quirk to handle in AICP adapter if used.

### Tier 0 practical usability — empirically confirmed

| Response length | Thinking ON | Thinking OFF | Verdict |
|---|---|---|---|
| 3 tokens | 5+ min | **1 min** | tolerable |
| 20 tokens | 7 min | **3 min** | batch-tolerable |
| 100 tokens | 37 min | 17 min | overnight only |
| 500 tokens (typical) | 3 hrs | 1.4 hrs | not interactive |

---

## 4. Cloud tier findings (the mission-critical insight)

Operator's **prior $540 CAD/mo baseline** (2× $240 + tax, Anthropic + another) is **2-3× what smart routing actually costs at any scale**.

**Recommended routing strategy** (per `CLOUD-SPEND-SCENARIOS-2026-04-24.md`):
- **Ollama Cloud Pro** ($27 CAD/mo): personal / AICP dev / research (unlimited-ish up to ~30M tokens/mo via 5hr/7d caps)
- **OpenRouter K2.6** ($20-50 CAD/mo): client work with pinned provider, audit-required sessions
- **Local K2.6** (free electricity): sovereignty fallback, offline mode
- **Total: ~$40-70 CAD/mo** across typical to moderate workloads

**Break-even for hardware upgrade**:
- Tier 1 ($15-19k CAD): $250/mo cloud
- Tier 2 ($32k CAD): $440/mo cloud
- Tier 3 ($70k CAD): $995/mo cloud
- At operator's realistic workload → hardware doesn't economically pay back at any tier

**5-year projection** (per `SCALING-PROJECTION-5YR-2026-04-24.md`):
- Operator's projected full scale (2-3 sessions + 10-20 agents over 5 years) reaches 125M tokens/mo at Y5
- Smart-routed cloud at that scale: $330-500/mo
- 5-year cost: ~$11,460 CAD total
- vs hardware + cloud hybrid Tier 2: ~$38,100 over 5 years

---

## 5. Verified cloud pricing (2026-04-24, LIVE-fetched)

### Anthropic (operator-confirmed)
- Free / Pro $20/mo / **Max 5x $100/mo** / **Max 20x $200/mo** (all USD)

### OpenRouter (from API, representative)
- **Kimi K2.6**: $0.745 in / $4.655 out per M USD
- **Claude Opus 4.7**: $5 / $25 per M (NOT $15/$75 — that was 4.1)
- **Claude Sonnet 4.6**: $3 / $15
- **Claude Haiku 4.5**: $1 / $5
- **GPT-5**: $1.25 / $10 (NOT $10/$50)
- **GPT-5.4**: $2.50 / $15
- **Gemini 3.1 Pro**: $2 / $12
- **DeepSeek V3.1**: $0.15 / $0.75
- **GLM 4.7**: $0.38 / $1.74

### Ollama Cloud (live-fetched from ollama.com/turbo)
- **Free**: $0, limited
- **Pro**: **$20/mo** or **$200/yr**, 3 concurrent models, 50× Free usage
- **Max**: **$100/mo**, 10 concurrent models, 5× Pro usage
- Session caps: reset every 5 hours; Weekly caps: reset every 7 days
- NOT truly unlimited — has elastic caps

### Ollama Cloud models (verified list)
`kimi-k2.6`, `deepseek-v4-flash`, `glm-4.7-flash`, `glm-5.1`, `glm-ocr`, `qwen3-coder-next`, `qwen3-next`, `qwen3.5`, `qwen3.6`, `nemotron-3-super`, `nemotron-cascade-2`, `minimax-m2.7`, `ministral-3`, `lfm2`, `lfm2.5-thinking`, `gemma4`, `medgemma`, `medgemma1.5`, `devstral-small-2`, `translategemma`

**NOT on Ollama Cloud**: Claude (any version), GPT (any version), Llama 4, Gemini. Anthropic/OpenAI/Meta/Google are proprietary, not on Ollama's cloud catalog.

---

## 6. All documents produced this session

Ordered by topic/purpose. All in `docs/`.

### State + continuity
- **`HANDOFF-COMPACTION-2026-04-24.md`** (this file)
- `SESSION-2026-04-23-HANDOFF.md` — yesterday's handoff
- `SESSION-2026-04-24-HANDOFF.md` — earlier this session (pre-evening work)
- `SESSION-2026-04-24-CONVERSATION-LOG.md` — chronological narrative, operator corrections, decisions

### Why things took 2 days
- `POSTMORTEM-2026-04-24-k26-local-wrong-path.md` — forensic breakdown of the Moonshot-555GB wrong-path execution

### Architecture / theory
- `LOCAL-HOSTING-ARCHITECTURE-2026-04-24.md` — 9-layer stack, 8-tier hardware hierarchy
- `BOTTLENECKS-COMPLETE-HUNT-2026-04-24.md` — every bottleneck per layer, hidden firmware issues
- `STORAGE.md` — storage tier rules (still authoritative from yesterday)

### Economics
- `MODEL-ECOSYSTEM-FULL-MAP-2026-04-24.md` — every provider, verified 2026-04-24 pricing
- `CLOUD-SPEND-SCENARIOS-2026-04-24.md` — OpenRouter vs Ollama Cloud vs Local economics
- `HARDWARE-BUILD-SCENARIOS-2026-04-24.md` — Tier 1/2/3 builds with CAD pricing
- `SCALING-PROJECTION-5YR-2026-04-24.md` — 5-year cost projection at operator's projected workload (2-3 sessions + 10-20 agents)

### Decision framework
- `PERSPECTIVE-AI-INFRASTRUCTURE-DECISION-2026-04-24.md` — "hardware is capability insurance, not cost optimization" + phased decision rules

### Empirical record (newest, untracked)
- `EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md` — what we actually tested, measured, observed (including the 3 inference experiments and recalibrated Tier 0 throughput)

---

## 7. Open decisions / undone items

### High-priority operator decisions
1. **Cloud activation**: Ollama Cloud Pro at $27 CAD/mo? Pair with OpenRouter K2.6 for client work? Currently both disabled post-Anthropic-cancellation.
2. **Keep llama-server running** or kill it? Currently holding 47 GB RSS. If not actively used, killing frees RAM for Windows.
3. **Commit uncommitted changes**? `config/default.yaml` + new `EXPLORATION-LOG-*.md` still untracked/unstaged.
4. **Hardware decision**: the docs recommend staying on Tier 0 through Y1-Y2 and reassessing. No decision needed now.

### Lower-priority cleanup
- `scripts/kt-serve.sh` is obsolete (targets deleted Moonshot weights). Either delete or annotate as historical.
- `/mnt/dev-envs/ktransformers-env/` (sglang+kt-kernel venv, ~10 GB) unused now that we're on llama.cpp. Safe to remove.
- `/mnt/dev-envs/ktransformers-src/` clone unused. Safe to remove if we're not diagnosing sglang+kt-kernel further.

### Experiments deferred (valuable future work)
- Experiment A: `-ngl 1` or `-ngl 2` — small GPU offload, might 2-4× warm inference
- Experiment B: `--ctx-size 32768` — test long-context behavior (risk: memory pressure)
- Experiment D: raise WSL cap to 60 GB — marginal gain, risks Windows
- Experiment E: native Linux dual-boot comparison — would empirically validate 40% WSL-tax estimate
- Build AICP `ollama_cloud` backend adapter — required to actually implement the recommended smart routing

### Brain maintenance (NEVER do directly)
- E008 epic has internal inconsistencies (see postmortem) — needs brain contribution via `python3 -m tools.gateway contribute`
- `wiki/spine/references/operator-workstation-storage-tiering.md` has uncorrected disk mappings — same process

---

## 8. Critical non-negotiable rules for next session

**Persistent in `~/.claude/.../memory/`**:
1. **Never unauthorized large disk writes** — any download or write >100 MB needs explicit per-action "yes, do X to path Y". "Continue" does NOT count. See `feedback_never_unauthorized_large_disk_writes.md`.
2. **Storage tiers + WSL VDisk rule** — NVMe for hyperfast, NAS SSD for normal, WSL VDisk NEVER holds model weights. See `feedback_storage_tiers_and_wsl_vdisk_rule.md`.

**Additional rules from this session**:
3. **Never edit the second-brain directly** — use `python3 -m tools.gateway contribute` instead. Operator explicitly called this out.
4. **Match document count to operator's explicit request** — if asked for "multiple documents", don't collapse into one.
5. **Use verified pricing, not memory** — operator called out hallucinated Anthropic Opus prices this session (old 4.1 rates vs current 4.6/4.7 rates). Fetch live from provider APIs when possible.
6. **"Continue" = smallest safe next step, NOT biggest unblocker**. Treat repeated "continue" streaks as a signal to pause and re-confirm big-picture plan.
7. **Ollama Cloud is NEVER for client/monetizable work** — shared pool. Use OpenRouter with pinned provider OR Local for those workloads.

---

## 9. How to re-enter the context after compaction

**Option A — strategic / cloud decisions**:
1. Read this handoff
2. Read `PERSPECTIVE-AI-INFRASTRUCTURE-DECISION-2026-04-24.md`
3. Read `CLOUD-SPEND-SCENARIOS-2026-04-24.md` for specifics

**Option B — hardware upgrade planning**:
1. Read this handoff
2. Read `HARDWARE-BUILD-SCENARIOS-2026-04-24.md`
3. Read `LOCAL-HOSTING-ARCHITECTURE-2026-04-24.md` for layered understanding
4. Read `BOTTLENECKS-COMPLETE-HUNT-2026-04-24.md` for specific bottleneck analysis

**Option C — continuing local K2.6 tuning**:
1. Read this handoff
2. Read `EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md` for measured numbers
3. Check `aicp --check` for live backend state
4. Check `pgrep -x llama-server` to see if local server still running
5. Section 9 (deferred experiments) lists valuable next experiments

**Option D — economic / 5-year planning**:
1. Read this handoff
2. Read `SCALING-PROJECTION-5YR-2026-04-24.md`
3. Read `MODEL-ECOSYSTEM-FULL-MAP-2026-04-24.md` for provider pricing

**Option E — context on why 2 days were "wasted"**:
1. Read `POSTMORTEM-2026-04-24-k26-local-wrong-path.md` (long, dense, but captures the full story)

---

## 10. One-paragraph summary for the very impatient

Local K2.6 Q2 runs on operator's hardware but at 0.045-0.10 tok/s — sovereignty fallback only, not interactive. Smart cloud routing (Ollama Cloud Pro $27/mo + OpenRouter K2.6 for client work) replaces operator's old $540/mo Anthropic habit at 1/10 the cost and reaches the mission (post-Anthropic independence). Hardware upgrades don't economically pay back at operator's projected workload scale — defer until at least Y2 and only upgrade for sovereignty reasons, not cost. All technical work, economic math, decision framework, and empirical measurements documented in `docs/*-2026-04-24.md`. Current system has llama-server running, AICP routing configured and tested, all file references in this handoff.

---

## 11. UPDATE 2026-04-25 — Phase 4 + 5 complete (post-compaction continuation)

This addendum records what landed AFTER the original compaction, on the same mission arc.

### Things that changed from sections 2 and 7

- **llama-server killed.** Was holding 51 GB RSS with no benefit (LocalAI page-cache contention re-cold's K2.6 anyway on next call). Now launch-on-demand only via `scripts/llama-serve.sh`. 60–90 min cold reload accepted as the cost of sovereignty.
- **`k2_6_local` removed from default routing.** `enabled: false`, dropped from `failover_chain` and `tier_map`. Sovereignty-only opt-in via `--backend k2_6_local`. Empirical 0.045–0.10 tok/s makes it unfit for any band that auto-routes to it. Commit `f8aa2ba`.
- **Ollama Cloud adapter built and operational.** New `aicp/backends/ollama_cloud.py`, registered in `_build_backends`, OpenAI-compat at `https://ollama.com/v1`, Bearer auth via `OLLAMA_API_KEY`. 20 tests passing. Smoke verified end-to-end: 9.2 sec wall-time for a 1-token response (~5.5× faster than local K2.6 thinking-off). Commit `11d3235`.
- **`personal` profile added.** `config/profiles/personal.yaml` routes band 1 (medium-complexity, scores 0.25–0.45) to `ollama_cloud` instead of `k2_6_openrouter`. Privacy boundary documented: NEVER use `personal` for client/audit-required work — Ollama Cloud is a shared inference pool. Switch back to `default` for those.
- **Brain contribution submitted.** `python3 -m tools.gateway contribute` — E008 epic correction filed at `~/devops-solutions-information-hub/wiki/log/`, status `pending-review`. Documents the M001 vs M002 vs M004 internal inconsistency that caused the 2-day wrong-path execution. Recommends llama.cpp + Unsloth Q2 for consumer hardware, separate hardware-class gates per path.
- **Cleanup landed.** `scripts/kt-serve.sh` annotated as superseded (kept as historical reference; targets deleted Moonshot weights). `/mnt/dev-envs/ktransformers-env/` and `/mnt/dev-envs/ktransformers-src/` removed (~11 GB reclaimed).
- **Storage hygiene fixed.** `fstrim.timer` was systemd-skipped on WSL (`ConditionVirtualization=!container`). Drop-in override in `/etc/systemd/system/fstrim.{timer,service}.d/override.conf` clears the condition; schedule changed from weekly → 30-min interval. Operator-side. Will compact VHDXs going forward without manual intervention.

### Mission posture as of 2026-04-25 (2 days early on the 2026-04-27 deadline)

```
Phase 1 (storage)            ✅
Phase 2 (postmortem)         ✅
Phase 3 (local sovereignty)  ✅ (sovereignty-only, slow but proven)
Phase 4 (cloud activation)   ✅ (ollama_cloud + k2_6_openrouter live)
Phase 5 (smart routing)      ✅ (default profile + personal profile)
Brain feedback loop          ✅ (E008 correction submitted)
Cleanup                      ✅
```

**Cost shape now:**
- `aicp --profile personal "..."` — Ollama Cloud Pro ~$27 CAD/mo flat (5hr/7d caps, ~30M tokens/mo effective).
- default profile — OpenRouter K2.6 pay-per-token at $0.745/$4.655 per M.
- `--backend k2_6_local` — sovereignty fallback, free electricity.
- Claude — hard-gated last resort.

**Realistic blended:** ~$30–60 CAD/mo across personal + occasional client work. Replaces $540 CAD/mo prior Anthropic habit at ~1/10 the cost.

### Open follow-ups (none critical-path)

- Soak / observe Ollama Cloud Pro usage over 2-3 weeks vs the 5hr/7d elastic caps. If Pro caps regularly hit, evaluate Max ($100 USD/mo) vs OpenRouter spillover.
- Stress-validate failover: deliberately fail one tier and watch the chain cascade through. Routing math is verified by `--check`; full empirical validation deferred.
- The skill discovery test (`tests/test_skills.py::test_discover_global_skills`) leaks the project's `.claude/skills/` into `tmp_path`-isolated tests. Pre-existing, unrelated to Phase 4. Worth a fix in a separate PR.

### Key file references (current canonical paths)

- `aicp/backends/ollama_cloud.py` — the new adapter.
- `config/default.yaml` — `backends.ollama_cloud.enabled: true`, default routing on `k2_6_openrouter` (audit-safe).
- `config/profiles/personal.yaml` — research/dev routing through Ollama Cloud.
- `scripts/llama-serve.sh` — canonical local K2.6 launcher (sovereignty fallback).
- `scripts/kt-serve.sh` — superseded, kept for postmortem reference, do not run.
- `docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md` — full forensic.
- `docs/EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md` — measured numbers.

---

*End of pre-compaction handoff. Next session starts by reading this document.*
