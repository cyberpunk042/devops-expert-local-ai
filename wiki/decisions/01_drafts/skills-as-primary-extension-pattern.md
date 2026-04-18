---
title: "Decision: Skills as the primary AICP extension pattern (over MCP-everywhere or hooks-only)"
type: decision
domain: backend-ai-platform-python
layer: 6
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "model-skills-commands-hooks"
  - "model-claude-code"
  - "cli-tools-beat-mcp-for-token-efficiency"
reversibility: moderate
created: 2026-04-18
updated: 2026-04-18
sources:
  - id: aicp-skills
    type: directory
    file: .claude/skills/
    description: 78 skills (5 rewritten per Standards as of 2026-04-18; 32 still boilerplate)
  - id: aicp-mcp
    type: file
    file: aicp/mcp/server.py
    description: 11 MCP tools — chat, vision, route, deep_health, profile, kb_search, task_status, dlq_status, etc.
  - id: aicp-guardrails
    type: directory
    file: aicp/guardrails/
    description: Backend guardrails (paths, response filtering, mode enforcement) — AICP's hook-equivalent
  - id: skills-audit
    type: file
    file: wiki/decisions/00_inbox/skills-audit-2026-04-17.md
    description: Audit revealing 47% of 78 skills were instruction-dump boilerplate
  - id: cli-vs-mcp-lesson
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/lessons/03_validated/architecture/cli-tools-beat-mcp-for-token-efficiency.md
    description: Convergent evidence (12x cost differential) that CLI+skills outperform MCP for project-internal tooling
tags: [decision, skills, extension, mcp, architecture, aicp, backend-ai-platform-python, transferable, pattern]
---

# Decision: Skills as the primary AICP extension pattern (over MCP-everywhere or hooks-only)

## Summary

AICP exposes capability through three mechanisms: 78 conditional **skills** (`.claude/skills/`) loaded just-in-time per task, 11 always-available **MCP tools** (`aicp/mcp/server.py`) for cross-conversation programmatic access, and **guardrails** (`aicp/guardrails/`) that enforce permission modes structurally. Skills are the primary extension pattern; MCP is reserved for capabilities that need programmatic access from external clients (fleet agents, other projects); guardrails are reserved for fail-closed enforcement that must survive any reasoning. This split is correct because: skills load conditionally (no per-message context cost), MCP tools load eagerly (justified only for external interop), and guardrails are deterministic (instructions can be reasoned around). Mixing the patterns — exposing every skill as MCP, or putting domain knowledge in guardrails — defeats each pattern's purpose.

## Decision

> [!success] Match the extension mechanism to its load timing and enforcement need.
>
> | Capability shape | Mechanism | Why |
> |------------------|-----------|-----|
> | Domain workflow with multiple operations + quality bar (e.g. feature-implement, ops-deploy, idea-capture) | **Skill** in `.claude/skills/<name>/SKILL.md` | Conditional loading — only when triggered. No per-message context cost. Skill body teaches the agent HOW. |
> | External programmatic access (fleet agents → AICP, other projects → AICP) | **MCP tool** in `aicp/mcp/server.py` | MCP is the cross-process integration protocol. Worth the eager-load cost when external clients need it. |
> | Fail-closed enforcement (path protection, mode enforcement, dangerous operation blocking) | **Guardrail** in `aicp/guardrails/` | Deterministic check at runtime. Cannot be reasoned around. Survives any prompt or skill content. |
> | Cross-cutting always-needed knowledge (project structure, hard rules, identity) | **AGENTS.md / CLAUDE.md** | Loaded every message — only put HERE what's needed every message. |

## Alternatives

### Alternative 1: MCP-everywhere — expose all 78 capabilities as MCP tools

Wrap every skill as an MCP tool. Single integration pattern, capabilities always discoverable, no per-task loading.

> [!warning] Rejected: MCP loads all tool schemas into the context window at conversation startup, regardless of whether they are used. AICP's 78 skills as MCP tools = 78 tool schemas in every conversation. Even with terse schemas (~200 tokens each), that's 15,000+ tokens of schema overhead before the user types anything. The Claude Code lesson `cli-tools-beat-mcp-for-token-efficiency` quantifies this: 12x cost differential measured between CLI+skills and equivalent MCP-everywhere setups. AICP's heartbeat profile (target: 500 tokens per request) is structurally incompatible with MCP-everywhere.

### Alternative 2: Skills-only — no MCP, no guardrails

All capabilities as SKILL.md files. No programmatic interface, no fail-closed enforcement. The agent reads instructions and follows them.

> [!warning] Rejected on TWO grounds:
>
> (a) **Cross-process integration**: fleet agents call AICP from a different process. Without MCP, the integration is HTTP-with-no-schema or shell-piping — both lose the structured tool-use benefits Claude Code expects. AICP's `aicp_route` MCP tool wraps the controller's full routing decision; replicating that as "agent calls bash, parses output" is fragile.
>
> (b) **Fail-closed enforcement**: per Quality Standards, instructions alone get ~25% compliance, structured rules get ~60%, hooks/guardrails get ~98%. Skills are instruction-rich (operational guidance) but they cannot BLOCK dangerous operations (sudo, .env writes, force-push). AICP's guardrails handle that 38% gap. Removing guardrails means AICP routes Claude responses with no path-protection check — reasoning attacks could escape the permission mode.

### Alternative 3: Hooks-only / guardrails-only — push everything into pre/post-tool blocks

Use Claude Code PreToolUse/PostToolUse hooks for every behavior. Skills become unnecessary because hooks can inject context per tool call.

> [!warning] Rejected: hooks are powerful but expensive at scale. Per Extension Standards, "the everything hook" is an explicit anti-pattern: 100ms × every tool call × 50 tool calls per task = 5 seconds of hook overhead per task. Hooks should target dangerous operations (sudo, force-push, .env) and structural boundaries (stage gates), not encode domain workflows. Domain workflows belong in skills (loaded conditionally, no per-tool overhead). AICP today has no PreToolUse hooks (Step 9.5 is pending) and ships its enforcement via guardrails at the backend layer — same fail-closed property, narrower surface.

### Alternative 4: One mega-skill per role — collapse 78 skills into ~10 role skills

Instead of `feature-implement` + `feature-test` + `feature-review` + ..., have one `engineer` skill that handles all engineering operations.

> [!warning] Rejected: per Extension Standards, "a good skill is a system, not a text file." A 10-skill design can't have per-operation Quality bars and per-operation Gotchas — the skill becomes either a wall of conditional logic ("if doing implement, then... if doing test, then...") or a leaky abstraction. The feature-development chain (5 stages × ~180 lines per stage = 900 lines of focused guidance) is meaningfully better than one 1000-line "engineer" skill that conflates stages. Specificity is the value.

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **Conditional loading is the only way 78 capabilities fit in a context window.** Per Claude Code Standards: CLAUDE.md should be <200 lines because it loads every message. Skills load only when triggered. With 78 skills × ~150-200 lines each = 14,000+ lines of operational guidance — far too much for AGENTS.md/CLAUDE.md but fine as 78 conditional files.
>
> 2. **MCP for external interop pays for the cost.** Fleet agents calling AICP need a stable, schema-typed interface — MCP provides it. The 11 MCP tools represent the AICP capabilities that genuinely need cross-process discoverability (chat, route, vision, deep_health, etc.). The other 67 capabilities are project-internal and don't justify the schema cost.
>
> 3. **Guardrails complement skills with fail-closed enforcement.** Skills can teach "don't write .env files" but cannot enforce it — the agent's reasoning can override. Guardrails check at the backend boundary deterministically. Together: skills teach (60% compliance), guardrails enforce (98% compliance) — three-layer defense per Quality Standards.
>
> 4. **78 skills surface a real risk: scaffolded boilerplate.** The 2026-04-17 audit found 47% of AICP skills were identical generic Process boilerplate (instruction-dump anti-pattern). This is a maintenance hazard, not a refutation of the design — boilerplate skills are a quality bar problem to fix (Step 9.6 — 5/16 fleet-referenced rewritten as of 2026-04-18), not evidence the pattern is wrong. The skill mechanism is sound; the implementation needs Standards-level authoring.
>
> 5. **The ecosystem converges on this split.** OpenArms uses 50+ skills + ClawHub MCP marketplace + R01-R13 hooks. The second brain uses 9 skills + 21 MCP tools + minimal hooks. Both arrived at the three-layer split independently. AICP's split (78 + 11 + guardrails) follows the same shape, scaled to its larger skill library.
>
> 6. **78 skills is large but not unprecedented.** The Extension Standards Open Question "What's the optimal hook count per project?" is resolved: claude-code-harness ships 13 rules. For skills, no analogous optimum is documented, but OpenArms's 50+ shows the pattern scales. AICP's 78 is in the same order of magnitude.

## Reversibility

**Moderate** — the split is well-established but reversing requires coordinated changes:

- **To reverse to MCP-everywhere**: rewrite every SKILL.md as an MCP tool registration in `aicp/mcp/server.py`, update CLAUDE.md / AGENTS.md to remove skill references, accept the per-message context cost. Touches: 78 SKILL.md files (delete or convert), `aicp/mcp/server.py` (78 new tool entries), CLAUDE.md/AGENTS.md (remove skill catalog references), fleet's `config/agent-tooling.yaml` (rewrite skill references as MCP calls). 1-2 weeks.
- **To reverse to skills-only**: remove `aicp/mcp/server.py`, replace fleet integration with HTTP-with-no-schema or shell, remove guardrails, accept the 38% compliance gap. Touches: `aicp/mcp/server.py` (delete), all fleet-AICP integration (rewrite), `aicp/guardrails/` (delete), all consumers (regression risk). Multiple weeks.
- **To reverse to hooks-only**: requires Step 9.5 (PreToolUse hooks) to first ship, then deprecate skills + MCP. Multiple months.

The CHEAP reversibility direction is incremental: rewriting boilerplate skills doesn't change the design, only its quality.

## Dependencies

If reversed (any direction):

- **Fleet integration** (openfleet) — `config/agent-tooling.yaml` references 18 AICP skills + AICP MCP tools. Reversal in either direction breaks fleet. Coordination required.
- **Skills audit + rewrite work** — Epic B + Step 9.6 currently in progress. Reversal voids the rewrite work.
- **CLAUDE.md/AGENTS.md** — currently route to `.claude/skills/` and reference MCP tools. Reversal requires rewriting these.
- **Per-domain Standards adherence** — each rewritten skill follows Extension Standards. Reversal abandons that adherence.

If extended (e.g., add a 4th mechanism — Claude Skills marketplace via agentskills.io):

- New `.claude/skills/<external-skill>/` entries pulled from marketplace
- Skill loader (`aicp/core/skills.py`) needs marketplace fetcher
- Validation: marketplace skills should also pass Extension Standards (Step 9.6 Phase 4 — schema validation)

## Relationships

- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/agent-config/model-skills-commands-hooks.md
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/agent-config/model-claude-code.md
- IMPLEMENTS: ~/devops-solutions-research-wiki/wiki/lessons/03_validated/architecture/cli-tools-beat-mcp-for-token-efficiency.md (the convergence-evidence lesson)
- RELATES TO: [Skills audit 2026-04-17](../00_inbox/skills-audit-2026-04-17.md) (the boilerplate problem this decision's pattern surfaces but doesn't cause)
- RELATES TO: [4-tier router with profiles over hardcoded routing](./4-tier-router-with-profiles-over-hardcoded-routing.md) (sibling decision — both concern config-driven coordination)
- ENABLES: 78 conditional skills + 11 MCP tools + guardrails as three-layer extension architecture
- DEPENDS ON: future Step 9.5 PreToolUse hooks (would add a 4th layer for stage-gate enforcement, narrow scope)
