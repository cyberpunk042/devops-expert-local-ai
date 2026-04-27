# Retrospective — Post-Anthropic Mission (2026-03-01 .. 2026-04-25)

**Slice**: the Post-Anthropic milestone, from mission framing through "functionally reached".
**Authored**: 2026-04-27 (2 days post-mission), retro-on-mission cadence.
**Authoritative scope**: brain epic E011 (Routing Integration), driven by directive `wiki/log/2026-04-22-k2-6-directive-and-post-anthropic-pivot.md`.

---

## Slice scope

This retro covers the Post-Anthropic milestone — the work that replaced Claude-Opus-as-default with Kimi K2.6 (OpenRouter pinned for audit-safe + Ollama Cloud Pro for personal/research) and added local K2.6 sovereignty fallback. The mission was framed 2026-04-22 with a 2026-04-27 deadline; functionally reached 2026-04-25 (2 days early). Out of scope: ongoing reliability work (cluster peering, Stage 4 evolutions), the skills audit Phase 2 (separately closed 2026-04-27), and unrelated sister-project work.

The slice spans 223 commits over ~8 weeks. Theme distribution: 87 `feat:` (greenfield growth), 14 `fix:` / `fix(*):`, 7 `docs(*):`, 2 `refactor:`. Volume: 1,205 files changed, 90,973 insertions vs 4,874 deletions — a strong net-additive phase.

---

## What worked (and why)

- **Mission shipped 2 days early**. Functionally reached 2026-04-25 against 2026-04-27 P0 deadline. Evidence: [docs/architecture/post-anthropic-mission.md](../architecture/post-anthropic-mission.md) status block + commit 875eec0 forward.

- **Cost reduction ~10×**. Prior baseline ~$540 CAD/month (Claude Opus default) → blended ~$30-60 CAD/month (Ollama Cloud Pro flat $27 + occasional OpenRouter spillover). Evidence: [docs/CLOUD-SPEND-SCENARIOS-2026-04-24.md](../CLOUD-SPEND-SCENARIOS-2026-04-24.md), [docs/SCALING-PROJECTION-5YR-2026-04-24.md](../SCALING-PROJECTION-5YR-2026-04-24.md).

- **Per-profile routing bands proved more valuable than expected**. Splitting `default` (audit-safe pinned K2.6, billable-compatible) from `personal` (Ollama Cloud Pro shared-pool, research-only) gave operator cost-vs-compliance choice with zero code branches. Evidence: [config/profiles/default.yaml](../../config/profiles/default.yaml), [config/profiles/personal.yaml](../../config/profiles/personal.yaml).

- **Vertical-slice approach for backend additions**. Ollama Cloud adapter shipped end-to-end in one session (`aicp/backends/ollama_cloud.py`, 217 lines, 20 tests, 9.2s verified round-trip) because the slice covered data + transport + UI for ONE backend rather than horizontal layer additions. Evidence: commit history + tests/test_ollama_cloud_backend.py.

- **Brain adoption Tier reached 4/4 STRUCTURAL**. Verified via `python3 -m tools.gateway compliance` over the slice. Driven by sustained alignment with brain standards (CLAUDE.md slim pattern, decision-log discipline, contribution flow exercised).

- **Documentation discipline carried weight**. CLAUDE.md slimmed 307→184 lines with detail extracted to `docs/architecture/` tree (7 files). AGENTS.md slimmed 193→162 lines with operational commands extracted to TOOLS.md. Evidence: [docs/architecture/_index.md](../architecture/_index.md). The pattern proved reusable — applied later to the skills audit.

- **Honest postmortem authored mid-slice**. The K2.6-wrong-path failure (2026-04-22 to 2026-04-24) was captured in [docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md](../POSTMORTEM-2026-04-24-k26-local-wrong-path.md) and [docs/EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md](../EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md). Empirical Tier-0 throughput numbers (0.045-0.10 tok/s) now exist; future sessions don't relearn from scratch.

---

## What didn't work (and why)

- **Local K2.6 wrong path for 2 days**. The model directed the operator down sglang+kt-kernel + Moonshot RAWINT4 (555GB safetensors, ~50GB peak RAM at startup, margin-of-zero on 48GB WSL cap, crashed Windows). Brain had specified llama.cpp + Unsloth Q2_K_XL GGUF (318GB, 30-40GB headroom on 64GB) from the start. Cost: ~929GB cumulative bandwidth, 575GB current disk, one forced Windows reboot. Evidence: [docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md](../POSTMORTEM-2026-04-24-k26-local-wrong-path.md).

- **Sunk-cost reasoning when the path failed**. When sglang+kt-kernel hit a dead-end (Unsloth GGUF not supported), the model recommended switching the WEIGHT FORMAT (preserve sglang setup) rather than switching the SERVING STACK (preserve the brain's spec). Sunk-cost on the adjacent thing locked in failure on the root thing. Evidence: postmortem section "Why we ended up on the wrong path".

- **Audit baselines went stale silently**. The skills audit decision (2026-04-17, brain) reported 47% boilerplate against Extension Standards. By the time the operator picked up Phase 2 (2026-04-27), in-flight cleanup had already eliminated boilerplate from many skills. The audit number should have been re-baselined before execution. Evidence: discovery during Phase 2 that 17 fleet skills were already tier-2 — the actual remaining gap was 26 fleet skills needing the gold-standard structure, not 47% of all 78.

- **MCP Phase 2b not started in this slice**. 21 MCP tools were soft-deprecated (Phase 2a, stderr warnings + CLI/skill replacements verified). Hard removal deferred. Evidence: [wiki/decisions/00_inbox/aicp-mcp-tool-surface-audit-2026-04-19.md](../../wiki/decisions/00_inbox/aicp-mcp-tool-surface-audit-2026-04-19.md). Not a failure of the mission, but a known leftover.

- **Lint debt not paid down to clean**. 1,271 → 359 (71% reduction via auto-fix + manual). Remaining 359 are all E501 line-too-long requiring per-case judgment. The slice didn't prioritize finishing this — defensible, but worth naming.

---

## Surprises (things we didn't expect to learn)

- **Local K2.6 on Tier 0 is sovereignty-only, not interactive.** Empirical 0.045-0.10 tok/s. The original mission framing implicitly assumed local would be interactive-acceptable. Reality: it's a fallback when nothing else is reachable, not a daily driver. This is a brand/expectation finding, not a hardware finding.

- **Brain contribution tooling had bugs that didn't break the work.** `relative_to()` crashed across repos but the contribution file landed successfully. Bug-tolerant tooling > bug-free tooling that fails closed; the contribution flow shipped useful output despite the crash.

- **Ollama Cloud Pro flat $27 CAD subscription was a fit nobody specified up-front.** It emerged as the right answer for the `personal` profile during the mission shift, not in the original framing. Flat-fee shared pool turns out to be exactly the right shape for "research / dev work that doesn't need audit safety" — a clean separation from per-token billable workloads.

- **The CLAUDE.md slim pattern has real second-order effects.** Reducing 307→184 lines + extracting `docs/architecture/` wasn't just docs hygiene — it freed every-message context for actual reasoning. The brain's "every-message context stays lean" rule paid off in practice; later sessions ran longer before compaction.

- **Operator quotes are evidence.** "I dont want to have to deal with Anthropic and Claude and Opus in the future......" (verbatim, 2026-04-22) carried more directional signal than any planning document. The retro should reproduce verbatim, not paraphrase.

---

## Keep / Stop / Start

- **Keep doing**: treat the brain as authoritative when operator says "the second-brain knows better". Re-read brain spec before implementing. Reason: the K2.6 wrong-path failure was avoidable — the right path was already in the brain. Re-reading is cheaper than two days of failed attempts.

- **Keep doing**: vertical slices per backend (data + transport + UI for ONE backend, ship, then next). Reason: the Ollama Cloud adapter shipped end-to-end in one session because of this discipline. Horizontal layer additions across all backends would have stretched it across 3-4 sessions with nothing usable mid-flight.

- **Keep doing**: per-profile routing bands as the abstraction for cost-vs-compliance choice. Reason: zero code branches, operator switches profile and routing changes; proved more valuable than initially expected.

- **Stop doing**: sunk-cost reasoning when picking technical paths. When a step fails, evaluate switching the ROOT (serving stack) rather than the ADJACENT (weight format). Reason: postmortem evidence — switching weight format to preserve sglang+kt-kernel infrastructure locked in a path that was always wrong for this hardware.

- **Stop doing**: pattern-matching plausible technical commands without verifying. Reason: the K2.6 path failed because plausible-looking sglang configs were not validated against the operator's actual hardware envelope. Verification is cheap; an unverified plausible command can cost two days.

- **Start doing**: re-baseline brain audits before execution if >2 weeks old. Reason: the skills audit number (47%) was stale by 6 weeks; in-flight work had moved the figure. Re-baselining at session start would have correctly framed the work as "26 skills need Quality Bar coverage" rather than "47% are boilerplate".

- **Start doing**: explicitly brand local sovereignty as "fallback only, not interactive". Reason: the empirical Tier-0 numbers (0.045-0.10 tok/s) need to be in the operator's framing of when to use local K2.6 — preventing future sessions from expecting interactive performance.

---

## Action items

- [ ] Contribute the "sunk-cost-in-technical-paths" lesson to brain. Owner: this session (Op3). Due: 2026-04-27. Skill: `pm-retrospective` Op3.
- [ ] Contribute the "audit-numbers-age-fast" lesson to brain. Owner: this session (Op3). Due: 2026-04-27. Skill: `pm-retrospective` Op3.
- [ ] MCP Phase 2b — hard removal of 21 deprecated MCP tools. Owner: next session (operator-scheduled). Due: 2026-05-31. Skill: `evolve-api-version`.
- [ ] Empirical routing-split measurement — capture actual local-vs-cloud share over a week of typical work to inform future profile tuning. Owner: next session. Due: 2026-05-15. Skill: `quality-performance`.
- [ ] 359 E501 lint cleanup — defer to next maintenance window; not blocking. Owner: maintenance cadence. Due: rolling. Skill: `ops-maintenance` + `quality-lint`.
- [ ] Update CLAUDE.md mission framing to brand local K2.6 explicitly as "sovereignty fallback only — empirically 0.045-0.10 tok/s, not interactive" (already partially done; verify). Owner: this session. Due: 2026-04-27. Skill: direct edit.

---

## Lessons (generalizable — candidates for brain contribution)

1. **Sunk-cost-in-technical-paths**: when a build/run/serving step fails, evaluate switching the ROOT thing (serving stack, runtime, framework) before switching the ADJACENT thing (weight format, config flag, version). Adjacent-switching preserves prior work but moves you further from the original spec; root-switching may discard prior work but realigns with the spec. Pre-condition: the original spec was correct. If the spec itself was wrong, root-switching is also wrong — but in the evidence-base case (K2.6 mission), the brain's original llama.cpp + Q2 spec WAS correct and the wrong path resulted from preferring the adjacent option.

2. **Audit-numbers-age-fast**: a brain audit reports a percentage at time T (e.g., "47% boilerplate"). At time T+N weeks, in-flight cleanup may have changed the figure silently. Before executing against an audit-driven plan, re-baseline the metric. This is especially true for code-quality audits where ongoing refactor work can erode the original signal.

3. **Per-profile routing bands as cost-vs-compliance abstraction**: in a multi-backend system, separating per-environment profiles (audit-safe pinned-provider for billable work; flat-fee shared-pool for research) into distinct YAML configs gives operators a switch without code branches. The pattern generalizes to any system with multiple backends that differ in compliance/cost shape.

4. **Local-sovereignty-as-fallback-not-interactive**: when local hardware can technically run a model but at <0.5 tok/s, brand the deployment EXPLICITLY as "fallback only, not interactive". Without the explicit brand, operators expect interactive use and the system disappoints. With the brand, operators reach for local only when cloud is unreachable and the system meets expectations.
