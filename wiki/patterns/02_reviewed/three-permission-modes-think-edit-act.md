---
title: "Three Permission Modes (Think / Edit / Act) — Operator-Selected AI Authority Tiers"
type: pattern
domain: backend-ai-platform-python
layer: 5
status: synthesized
confidence: high
maturity: growing
promoted_from: "01_drafts"
promoted_at: "2026-04-22"
promotion_reason: "Evolve score 0.754 (cross_source_convergence=1.0, evidence_density=1.0, maturity_gap=1.0). 4 documented instances (CLAUDE.md+AGENTS.md naming, force_cloud_modes routing dimension, guardrails server-side enforcement, Claude Code Plan Mode parallel). Pattern generalizes — Anthropic's Plan Mode is structurally identical to Think — confirming cross-tool applicability beyond AICP."
derived_from:
  - "model-quality-failure-prevention"
  - "model-claude-code"
instances:
  - page: "AICP CLAUDE.md + AGENTS.md"
    context: "Three modes named: Think (read/analyze/plan, no edits, no commands), Edit (modify files in scope, produce patches/diffs), Act (run commands, workflows, tools — highest authority, most controlled). Selected per-session by operator."
  - page: "AICP profiles force_cloud_modes"
    context: "Per-profile setting: which modes route to cloud (Claude) vs local. Default profile routes Edit + Act to cloud; fast/offline profiles can keep Edit local. Mode IS a routing dimension, not just a guardrail."
  - page: "AICP guardrails (aicp/guardrails/)"
    context: "Mode is enforced server-side by the guardrails layer: Think mode rejects Write/Edit tool invocations regardless of model; Edit mode rejects out-of-scope writes; Act mode applies command allowlist."
  - page: "Claude Code's Plan Mode"
    context: "Anthropic's Claude Code has a 'Plan Mode' that's structurally identical to AICP's Think — analysis without execution. The Three-Modes pattern generalizes: Plan Mode = Think, normal mode ≈ Edit, autonomous mode ≈ Act. AICP names all three explicitly."
created: 2026-04-18
updated: 2026-04-18
sources:
  - id: aicp-modes
    type: file
    file: aicp/core/modes.py
    description: AICP's mode enforcement code (Think/Edit/Act definitions + per-mode tool allowlists)
  - id: aicp-claude-md
    type: file
    file: CLAUDE.md
    description: 'AICP CLAUDE.md ## Architecture > Three Permission Modes — operator-facing description'
  - id: aicp-agents-md
    type: file
    file: AGENTS.md
    description: 'AICP AGENTS.md ## Stage gates table — modes show up as enforcement layer per stage'
  - id: model-quality-fp
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-quality-failure-prevention-standards.md
    description: 'Quality Standards: enforcement-level migration (Level 0 instructions → Level 1 skills → Level 2 hooks → Level 3 deterministic). Modes operate at Level 2-3.'
tags: [pattern, modes, permission, authority, aicp, backend-ai-platform-python, transferable, principle]
---

# Three Permission Modes (Think / Edit / Act) — Operator-Selected AI Authority Tiers

## Summary

A robust AI orchestration platform exposes **three tiers of authority** that the operator selects per session: **Think** (the AI may read, analyze, and plan — but cannot edit files or execute commands), **Edit** (the AI may modify files in a controlled scope and produce patches/diffs — but cannot execute commands), **Act** (the AI may run commands, workflows, and tools — highest power, most controlled). The pattern is operator-controlled, mechanically enforced (not just instructionally), and tier-shifting between modes is an explicit operation. AICP names and enforces these three modes; Claude Code's "Plan Mode" is structurally a Think instance; the broader pattern transfers to any system where AI capability needs to be GATED by authority rather than truly safety-checked per call.

> [!info] Pattern Reference Card
>
> | Mode | What the AI MAY do | What the AI MAY NOT do | Default backend |
> |------|--------------------|------------------------|------------------|
> | **Think** | Read files, search, analyze, plan, propose, summarize, query MCP read-only tools | Modify files, run commands, write to disk, invoke side-effecting tools | local (cheaper — analysis dominant) |
> | **Edit** | All Think capabilities + Write/Edit tools targeting explicit scope, produce diffs | Run shell commands beyond a small allowlist, push to remote, invoke deploy tools | cloud (configurable per profile — diff quality matters) |
> | **Act** | All Edit capabilities + Bash tool, run scripts, invoke deploy/test workflows | Bypass guardrails (no mode → no enforcement) | cloud (most authority demands strongest model) |

## Pattern Description

The pattern partitions AI authority into three tiers. **Authority is monotonic**: Edit ⊃ Think (Edit has every capability Think has plus writes); Act ⊃ Edit (Act has every capability Edit has plus commands). Tier selection happens BEFORE the AI session begins — the operator chooses based on what they're trying to accomplish + how much autonomous AI authority they're comfortable granting.

The pattern's correctness depends on FOUR properties:

1. **Mechanical enforcement, not instructional.** Telling the AI "you're in Think mode, don't write" achieves the documented ~25% compliance baseline (per Quality Standards). Enforcing via runtime checks (Think mode REJECTS Write tool calls regardless of what the AI claims) achieves ~98%. The pattern requires Level 2+ enforcement (per Extension Standards Migration); instruction-only is insufficient.

2. **Tier transitions are explicit operations.** The operator EXPLICITLY changes mode (e.g., `aicp --mode edit`); the AI does not self-promote. An AI in Think mode that asks "should I switch to Edit so I can implement this?" is asking correctly — the answer comes from the operator, not the AI's own judgment.

3. **Per-tier backend coupling is a profile choice.** AICP's profiles can route different modes to different backends (`force_cloud_modes: [edit, act]` routes Edit + Act to Claude even on local-first profiles, because the consequences of bad Edits/Acts are higher than bad Thinks). The mode is THE PRIMARY routing dimension that's correlated with cost-of-mistake.

4. **Modes COMPOSE with stage gates.** A task in `document` stage in `Edit` mode still has its `forbidden_zones` (no `aicp/`, `tests/`, `config/profiles/` writes per the document stage). Modes are SESSION-level authority; stages are TASK-level scope. Both layer.

> [!warning] **Recognition signal**: a system that exposes "autonomous mode" vs "guided mode" without a middle tier OR without enforcement is approximating this pattern but missing key properties.
>
> Common failure modes:
> - Two modes only (Think vs Act) — collapses the diff-producing middle tier; operators want "I'll review the diff before applying" semantics that Edit provides.
> - Three names but no enforcement (mode is just instruction text in the prompt) — fails Quality Standards' compliance bar.
> - Mode is set IN-SESSION by the AI itself ("I'll switch to autonomous mode now") — defeats operator control.
> - Modes don't compose with other authority dimensions (e.g., scope, stage, role) — mode becomes the only authority knob, which over-loads it.

## Instances

### Instance 1: AICP CLAUDE.md + AGENTS.md three-mode declaration

CLAUDE.md `## Architecture > Three Permission Modes` and AGENTS.md `## Hard rules` together define and reference the three modes by name. The DEFINITION lives in CLAUDE.md (operator-facing); the ENFORCEMENT lives in `aicp/core/modes.py` (machine-readable). Per CLAUDE.md: "Think — read, analyze, plan. No edits, no commands. Edit — modify files in a controlled scope. Produce patches/diffs. Act — run commands, workflows, tools. Highest power, most controlled."

### Instance 2: AICP profiles `force_cloud_modes`

The profile system encodes per-mode routing decisions: `force_cloud_modes: [edit, act]` in the default profile routes Edit + Act requests to Claude regardless of the local-first router policy. Rationale: an Edit mode session is producing diffs that the operator will review and apply; the diff QUALITY matters more than the per-request cost. Profile authors set this per their cost/quality tradeoff.

### Instance 3: AICP guardrails (`aicp/guardrails/`)

The mode is ENFORCED server-side. Think mode requests that include Write/Edit tool calls get the tool calls rejected by the guardrails layer before they reach the backend or leave the AICP runtime. The AI cannot "talk its way out" of mode enforcement — the check is mechanical, not LLM-mediated.

### Instance 4: Claude Code's Plan Mode (cross-platform validation)

Anthropic's Claude Code has a "Plan Mode" that's structurally identical to AICP's Think — the AI analyzes and plans without executing. Claude Code doesn't name the equivalent of AICP's Edit explicitly (it's just "the default mode where Edit+Bash work"), and there's no formal Act tier separate from default. AICP's Three-Modes pattern is a more explicit articulation of an authority gradient that Claude Code partially implements. This convergence (independent designs landing on the same partition) is evidence the pattern reflects a real design constraint, not just an AICP idiosyncrasy.

## When to apply

- AI orchestration platforms where the AI can invoke tools with side effects (Write, Edit, Bash, deploy)
- Multi-tenant or multi-context deployments where some sessions are exploratory (Think suffices) and others are operational (need Edit/Act)
- Cost-sensitive deployments where mode-based routing materially changes per-session cost (Think → cheap local; Act → expensive cloud)
- Compliance/security contexts where authorized actions must be auditable per session (mode IS the auth tier in the audit log)
- Teams with mixed trust profiles: junior contributors get Think-only sessions; trusted operators get Act

## When NOT to apply

- **Single-purpose AI tools** — a chatbot that never writes anything has no Edit or Act tier; mode partitioning adds no value
- **Fully autonomous agent systems with no human-in-loop** — mode selection assumes an operator. A system designed to run unattended needs different authority mechanisms (capability-based authorization, signed commands, etc.)
- **Read-only assistants** — if the AI never edits or executes, "Think" is the only mode and naming it adds noise
- **Systems with simpler authority models that work** — if a binary "tool-use enabled / disabled" toggle suffices for the workload, three modes is over-engineering

## Tradeoffs

> [!warning] The three-mode cost
>
> | Cost | Mitigation |
> |------|-----------|
> | Operators must choose mode per session (cognitive overhead) | Default to Think for new sessions; operators upgrade explicitly when needed. Lowest-authority default reduces accidents. |
> | Mode transitions in-session require restart (or per-tool authorization prompts) | Per-tool authorization prompts work but increase friction; AICP defaults to per-session mode (set once, valid for the session) |
> | Three modes add vocabulary the operator must remember | Names map to intuition (Think before Edit before Act); skill descriptions reference modes; permission prompts surface the active mode |
> | Mode + stage + role + scope is 4 authority dimensions to compose | Per Quality Standards, each axis adds enforcement signal — the cost is real but bounded; AICP's profile system bundles mode-related settings so operators tune one knob, not four |

## Cross-cutting design principles this pattern surfaces

1. **Authority is monotonic and tiered, not binary** — Think ⊂ Edit ⊂ Act. Operators want a middle tier (Edit) for review-before-apply workflows.
2. **Authority must be enforced mechanically** — instructions alone insufficient (Quality Standards: 25% compliance).
3. **Authority transitions are operator operations** — the AI cannot self-promote.
4. **Authority IS a routing dimension** — higher authority correlates with higher cost-of-mistake, which justifies stronger backends.
5. **Authority composes with scope** — modes (session-level) layer with stages (task-level) layer with paths (file-level).

## Relationships

- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-quality-failure-prevention-standards.md (enforcement-level evidence)
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/agent-config/model-claude-code.md (Claude Code's Plan Mode is one Think instance)
- IMPLEMENTS: monotonic-authority-tiers + mechanical-enforcement principles
- RELATES TO: [Skills as primary extension pattern](../../decisions/01_drafts/skills-as-primary-extension-pattern.md) (skills load conditionally; modes gate authority — different axes, both compose)
- RELATES TO: [PreToolUse hooks layered approach](../../decisions/01_drafts/pretooluse-hooks-layered-approach.md) (hooks enforce universal R01-R04; modes enforce per-session authority — both Layer 2 enforcement, complementary)
- RELATES TO: [4-tier router with profiles](../../decisions/01_drafts/4-tier-router-with-profiles-over-hardcoded-routing.md) (profiles' force_cloud_modes is the mechanism that makes mode a routing dimension)
- ENABLES: AICP's tiered cost model — Think sessions stay cheap, Act sessions earn the cloud cost via consequence weight
- CONTRASTS WITH: capability-based authorization (per-call signed permissions) — different model, suited to fully autonomous systems with no operator
