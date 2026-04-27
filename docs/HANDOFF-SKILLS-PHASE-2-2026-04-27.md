# Handoff — Skills Audit Phase 2 (2026-04-27)

**Status**: ✅ **COMPLETE** as of 2026-04-27. All 26 fleet-referenced skills rewritten to brain Extension Standards gold-standard pattern.
**Written**: 2026-04-27, originally mid-Phase-2; updated at completion.
**For**: future sessions referring back to this handoff for the gold-standard pattern itself (it's reusable for any future skill authoring).
**Read first**: section 3 (the pattern) is the reusable artifact. Sections 4-7 are the historical record of how Phase 2 went.

---

## 1. North star (mission posture, one paragraph)

**Post-Anthropic milestone**: functionally reached 2026-04-25 (2 days early on the 2026-04-27 P0 deadline). Cloud routing is live (Ollama Cloud Pro + OpenRouter K2.6 pinned + local K2.6 sovereignty fallback; Anthropic gated to last resort). All work since then is **post-mission polish + the skills audit Phase 2** the brain has long called for.

**Current direction**: rewriting the 26 fleet-referenced AICP skills against the brain's Extension Standards. The brain's audit (2026-04-17) found 47% boilerplate; significant cleanup happened between then and now (boilerplate eliminated; 17 fleet skills already at tier-2). The remaining work is the 26 fleet-referenced skills that have NOT yet been rewritten to gold standard. Operator directed this on 2026-04-27 with the framing: "the second-brain knows better. but get back on track after going and ingesting what it has to teach."

---

## 2. Brain references (the source of truth)

These are where the standards and the audit decision LIVE. Re-read them on resume — don't trust this handoff alone.

| Reference | Location |
|-----------|----------|
| Extension Standards (gold-standard pattern for skills) | `~/devops-solutions-information-hub/wiki/spine/standards/model-standards/model-skills-commands-hooks-standards.md` |
| Boilerplate-skill anti-pattern lesson (AICP-specific) | `~/devops-solutions-information-hub/wiki/lessons/01_drafts/contributed/boilerplate-skill-anti-pattern-at-scale-47pct-aicps-78-ski.md` |
| Phased rewrite plan (this project's audit decision) | `wiki/decisions/00_inbox/skills-audit-2026-04-17.md` |
| Gold-standard exemplar skill | `~/devops-solutions-information-hub/skills/model-builder/skill.md` |
| Sister exemplar skill | `~/devops-solutions-information-hub/skills/wiki-agent/skill.md` |
| Fleet skill consumer manifest | `~/openfleet/config/agent-tooling.yaml` (43 AICP skills referenced; 26 still need rewrite) |

Brain's status note: AICP is at adoption Tier 4/4 STRUCTURAL (per `python3 -m tools.gateway compliance`). The skills audit is the only major deferred Tier-3-evolution-pipeline item.

---

## 3. The gold-standard pattern (apply per skill rewrite)

Every rewritten SKILL.md MUST have these 9 sections, in this order, populated with skill-specific content (no boilerplate).

```markdown
---
name: <kebab-case-name>
description: <one-paragraph operational description with trigger phrases inlined>
argument-hint: [optional argument shape]   # only if the skill takes args
allowed-tools: <comma-separated subset of {Read, Write, Edit, Bash, Glob, Grep}>
effort: low | medium | high
---

# <name>

<2-3 sentence intro: what this skill is, where in the project lifecycle it sits>

## Trigger phrases (when to load this skill)

Load when the conversation matches any of:
- **<category>**: <specific signal — file state, operator phrase, stage transition>
- ...

Do NOT load when:
- ...

## Operations

This skill has N named operations. Execute in order.

### Operation 1: <name>

**Trigger**: <when this op fires within the skill>.

**Process**:
1. ...
2. ...

**Quality bar (Operation 1 done when)**:
- [ ] <testable assertion>
- [ ] ...

### Operation 2-N: <same shape>

## Gotchas (known failure modes — read before doing)

### Gotcha 1: <named failure mode>

<one-paragraph description of the failure>

**The rule**: <single-sentence prescription with detection step>

### Gotcha 2-N: <same shape>

## Reference exemplars

The Extension Standards reference exemplars for skills are the second brain's `model-builder` and `wiki-agent` skills — see `~/devops-solutions-research-wiki/skills/`. This skill follows their structure: trigger phrases, multiple named operations, per-operation Process + Quality bar, Gotchas with detection + rule + reasoning.

## Domain context

This skill operates in the **backend-ai-platform-python** domain. <AICP-specific scope notes — what's relevant from CLAUDE.md / domain profile / known constraints>.

## Related skills

| Skill | When | Why distinct |
|-------|------|--------------|
| <sibling> | <use case> | <boundary that differentiates from this skill> |
| ...
```

Authoring conventions captured across the 14 already-rewritten skills:
- 3-4 named Operations is typical; 2 minimum for trivial skills, 4-5 for complex.
- 5 Gotchas per skill is the sweet spot — each must name a SPECIFIC failure mode, not generic advice.
- Quality bars are CHECKBOXES with testable assertions ("`grep -r ... returns nothing`", "`exits 0`", "≥1 named consumer file"), not feel-good statements.
- Domain-context section frequently calls out AICP-specific scope (this skill is for sister fleet projects / this skill has LOW APPLICABILITY here / this skill spans AICP+OpenFleet) — be honest about applicability.
- Related-skills table is disambiguation, not a generic "see also" — every row says WHY the sibling is distinct.

---

## 4. Progress (final — 2026-04-27)

### ✅ Done — all 26 fleet-referenced skills rewritten

**Session 1** (14 skills):
1. `architecture-propose` — 3 ops + 5 gotchas
2. `architecture-review` — 3 ops + 5 gotchas
3. `foundation-auth` — 4 ops + 5 gotchas
4. `foundation-ci` — 4 ops + 5 gotchas
5. `foundation-config` — 4 ops + 5 gotchas
6. `foundation-deps` — 4 ops + 5 gotchas
7. `foundation-docker` — 4 ops + 5 gotchas
8. `foundation-testing` — 4 ops + 5 gotchas
9. `idea-capture` — 3 ops + 5 gotchas
10. `openclaw-add-agent` — 3 ops + 5 gotchas
11. `openclaw-fleet-status` — 2 ops + 5 gotchas
12. `openclaw-health` — 2 ops + 5 gotchas
13. `openclaw-setup` — 4 ops + 5 gotchas
14. `ops-backup` — 4 ops + 5 gotchas

**Session 2** (12 skills, completing the audit):
15. `ops-deploy` — 4 ops + 5 gotchas
16. `ops-incident` — 3 ops + 5 gotchas
17. `ops-maintenance` — 4 ops + 5 gotchas
18. `ops-rollback` — 4 ops + 5 gotchas
19. `pm-assess` — 3 ops + 5 gotchas
20. `pm-changelog` — 3 ops + 5 gotchas
21. `pm-handoff` — 3 ops + 5 gotchas (this skill itself; cites this handoff doc as live exemplar)
22. `pm-plan` — 4 ops + 5 gotchas
23. `pm-retrospective` — 3 ops + 5 gotchas
24. `pm-status-report` — 3 ops + 5 gotchas
25. `scaffold` — 4 ops + 5 gotchas
26. `scaffold-subagent` — 4 ops + 5 gotchas

Total: ~5,400 lines of skill-specific content. Cluster shape achieved (ops / pm / foundation / architecture / openclaw / scaffold / idea / backup).

### Already-tier-2 fleet skills (do NOT rewrite — already gold-standard)

These 17 already had Triggers + Operations + Per-operation-Quality-bars + Gotchas at session start (verified 2026-04-27):

`config-deploy, config-secrets, feature-document, feature-implement, feature-iterate, feature-plan, feature-review, feature-test, infra-monitoring, infra-security, quality-accessibility, quality-audit, quality-coverage, quality-debt, quality-lint, refactor-architecture, refactor-extract, refactor-split`

(Plus the 6 AICP-namespace skills that were authored fresh this milestone: `aicp-ops-dlq, aicp-ops-metrics, aicp-ops-tasks, aicp-ops-runtime, aicp-model-mgmt, aicp-lora`.)

---

## 5. How to resume orderly

```
1. Read this handoff in full.
2. Read the Extension Standards (section 2 link). It's the source of truth for the gold-standard pattern.
3. Sample one of the already-rewritten skills as a template — `feature-implement` or any of the 14 in section 4.
4. Pick the next skill from section 4's "Remaining" list (start with ops-deploy unless operator picks).
5. Read the EXISTING `<skill>/SKILL.md` to understand the current state and the operations the skill should cover.
6. Rewrite per section 3's pattern. Don't skimp on Gotchas — 5 per skill is the bar.
7. Show the file path to the operator. They'll say "its commited, continue" — that's authorization to move to the next.
8. Repeat for the remaining 12 skills.
```

### What "orderly" means (rules from the session)

- ✅ DO read the brain's standards before authoring. Don't guess the pattern.
- ✅ DO use AICP-specific context (CLAUDE.md identity, [docs/architecture/](architecture/) detail files) — every skill reflects the project's actual reality.
- ✅ DO be honest about LOW APPLICABILITY where it exists (e.g., `quality-accessibility` for a backend platform). The brain's gold-standard treats honesty as a feature.
- ❌ DON'T try to teach the brain. The brain's audit, the brain's lesson, the brain's standards are authoritative; this work APPLIES them. Operator was explicit: "DON'T TRY TO TEACH THE BRAIN... WHAT DID I ASK YOU TO DO?"
- ❌ DON'T fabricate. If a fact (an env var, a CLI flag, a deployment detail) isn't verified, either verify it or note "(verify before relying)" — don't pattern-match a plausible value.
- ❌ DON'T deflect with options when a recommendation is clearer. Operator pattern: pick the right next thing per the brain's plan, do it, report.

---

## 6. Critical context outside the skills audit

These are the OTHER concerns this session has touched. Most are STABLE (committed). Some are ACTIVE (uncommitted at this handoff).

### Stable — committed earlier this session

- **CLAUDE.md slim** — 307 → 184 lines. Detail extracted to [docs/architecture/](architecture/) (7 files: `_index.md`, `post-anthropic-mission.md`, `localai-routing.md`, `profiles.md`, `project-structure.md`, `reliability.md`, `intelligent-infrastructure.md`, `fleet-integration.md`).
- **AGENTS.md slim** — 193 → 162 lines. Operational commands extracted to `TOOLS.md` (new, 108 lines, mirrors the brain's `TOOLS.md` pattern).
- **MCP Phase 2a** — 21 deprecated tools annotated with stderr deprecation warnings in `aicp/mcp/server.py`. CLI/skill replacements verified to exist. Audit doc updated at [wiki/decisions/00_inbox/aicp-mcp-tool-surface-audit-2026-04-19.md](../wiki/decisions/00_inbox/aicp-mcp-tool-surface-audit-2026-04-19.md).
- **Lint debt** — 1,271 → 359 (auto-fix 895 + manual 17). Remaining are all E501 (line-too-long, manual judgment per case).
- **Real bugs fixed**: 3 F821 (undefined-name in CLI handlers), 5 F841 (incl. discarded `lora_load` server response), 2 profile k2_6_local re-introductions, 1 test isolation (HOME-leak in `test_discover_global_skills`), 5 deprecation-message accuracy fixes.
- **StrEnum migration** in `aicp/core/tasks.py` (Python 3.11 canonical). One regression caught + fixed in `tests/test_tasks.py`.
- **Brain contribution submitted** — E008 epic correction at `~/devops-solutions-information-hub/wiki/log/e008-epic-—-internal-stack-vs-format-inconsistency-caused-2-.md`, status `pending-review`.

### Active — uncommitted at handoff (operator pattern: they commit between turns)

The 14 skill rewrites in section 4 were each committed by operator after presentation. As of THIS handoff: the most recent skill (`ops-backup`) is committed; working tree should be clean. Verify with `git status` on resume.

### Pre-existing technical debt (separate concerns)

- **MCP Phase 2b — hard removal** of the 21 deprecated MCP tools. Deferred to next milestone after consumers cut over to CLI/skill replacements.
- **Cluster peering (Stage 4)** — LocalAI Alpha ↔ Bravo. Multi-day infra; planned but unscheduled.
- **Empirical routing-split measurement** on Stage 3 hardware — open question in brain.
- **The skill discovery test fix pattern** — fixed for `test_discover_global_skills`. Other tests may have similar HOME-leak bugs latent. Audit deferred.

---

## 7. The right way to act on resume

The operator's frame at the start of this Phase 2 work:

> "the second-brain knows better. but get back on track after going and ingesting what it has to teach... Take your time"

That framing still applies on resume. Specifically:

1. **Ingest the brain first** (section 2 references). Don't pattern-match this handoff alone.
2. **Apply, don't extend**. The brain has the plan; this work APPLIES it. Don't propose new variations of the pattern; don't try to update the brain mid-execution.
3. **Take your time** on each skill. ~250 lines of careful authoring per file. Operator authorized "20+ requests as needed" earlier in the session — that posture extends to this work.
4. **One skill per turn** is the working cadence. Operator commits, says "continue", next skill begins. Don't batch.
5. **Verify replacement coverage**. Each skill's Trigger phrases must distinguish it from siblings (the Related-skills table is the proof). If two skills have identical triggers, the boundary is wrong.

---

## 8. One-paragraph summary for the very impatient

Phase 2 complete. All 26 fleet-referenced AICP skills now match the brain's Extension Standards gold-standard pattern: 2-4 named operations with per-op Process + Quality bar, 5 Gotchas with rule+detection+reasoning, plus Reference exemplars + Domain context + Related-skills disambiguation. The pattern in section 3 of this doc is the reusable artifact for any future skill authoring (new skills, sister-project skills, evolved versions). The brain-prescribed audit (`wiki/decisions/00_inbox/skills-audit-2026-04-17.md`) is closed. Pre-existing tech debt in section 6 ("Pre-existing technical debt") is the next pickable work — none of it is Phase 2 leftover; each is independent.

---

*End of Phase 2 handoff. Audit closed 2026-04-27. The pattern documented in section 3 lives on as the canonical AICP skill structure.*
