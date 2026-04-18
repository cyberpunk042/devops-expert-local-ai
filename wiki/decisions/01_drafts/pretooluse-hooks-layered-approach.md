---
title: "Decision: Layered PreToolUse hooks — universal R01-R04 baseline first, stage-gate enforcement later"
type: decision
domain: backend-ai-platform-python
layer: 6
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "model-quality-failure-prevention"
  - "model-claude-code"
  - "model-skills-commands-hooks"
reversibility: easy
created: 2026-04-18
updated: 2026-04-18
sources:
  - id: aicp-settings
    type: file
    file: .claude/settings.json
    description: AICP's Claude Code settings — currently has permissions allowlist but no hooks
  - id: aicp-guardrails
    type: directory
    file: aicp/guardrails/
    description: AICP's BACKEND-LAYER guardrails (paths, response, checks) — server-side enforcement; this decision adds CLIENT-LAYER (Claude Code) hooks
  - id: claude-code-harness-r01-r13
    type: external
    url: https://github.com/shanraisshan/claude-code-best-practice
    description: 13 baseline hook rules per the Claude Code harness conventions
  - id: openarms-evidence
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-quality-failure-prevention-standards.md
    description: 'Quality Standards: instructions alone get ~25% compliance, hooks get ~98%'
tags: [decision, hooks, claude-code, enforcement, security, aicp, backend-ai-platform-python, transferable]
---

# Decision: Layered PreToolUse hooks — universal R01-R04 baseline first, stage-gate enforcement later

## Summary

AICP adds Claude Code PreToolUse hooks in TWO layers, shipped sequentially: **Layer A (NOW)** is a universal safety baseline (R01-R04 from claude-code-harness conventions: block `sudo`, `.git/` writes, `.env` writes, `--force` git operations) — these rules are STATELESS, requiring no task-state tracking, and apply to every Claude Code session in this repo. **Layer B (LATER)** is stage-gate enforcement (block `Write`/`Edit` to forbidden paths per the active task's `current_stage`) — STATEFUL, requires AICP's wiki/backlog/tasks/ to have live tasks with `current_stage` frontmatter that the hook can read. Layer A delivers the well-documented 60% → 98% compliance jump for safety-critical operations immediately. Layer B requires harness/state-mechanism design first; deferred to a future task. This split is correct because: (a) Layer A's value is independent of any AICP-specific state, (b) Layer B's design depends on resolving where task state actually lives at runtime, (c) shipping Layer A now removes a class of incidents (accidental .env commits, force-pushes to main) without blocking on Layer B.

## Decision

> [!success] Ship Layer A (R01-R04 baseline) NOW. Defer Layer B (stage-gate) to a separate task once AICP has live task-state tracking.
>
> | Layer | Scope | State required | Status |
> |-------|-------|----------------|--------|
> | **A — Universal safety baseline** | sudo, .git/ writes, .env (+secrets) writes, --force pushes | NONE — stateless rules that apply always | **Ship in this decision** |
> | **B — Stage-gate enforcement** | Block writes to forbidden paths per active task's current_stage (per `wiki/config/domain-profiles/backend-ai-platform-python.yaml` per-stage `forbidden_zones`) | Needs current_stage from active task in wiki/backlog/tasks/ | **Deferred — separate task once state mechanism lands** |
>
> Implementation of Layer A: a single Python hook script at `tools/hooks/pretool_safety.py` registered in `.claude/settings.json` under `hooks.PreToolUse`. Matches `Bash`, `Write`, `Edit` tools. Returns `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}` for matches, otherwise allows.

## Alternatives

### Alternative 1: Skip hooks, rely on AGENTS.md "Hard rules" + backend guardrails

Continue with the current state — no Claude Code hooks. Methodology lives in AGENTS.md (10 hard rules), and `aicp/guardrails/` enforces at the BACKEND when AICP routes a request to a backend.

> [!warning] Rejected: AICP's `aicp/guardrails/` enforces SERVER-SIDE — when AICP itself is the runtime executing tool calls. But Claude Code is a SEPARATE agent runtime that uses its own tool calls (Bash, Edit, Write) BEFORE AICP enters the picture. A Claude Code session writing to `.env` directly via the `Write` tool bypasses AICP's backend guardrails entirely. Per Quality Standards: instructions alone get ~25% compliance, hooks get ~98%. AGENTS.md hard rules without enforcement leave the 73-point gap. This decision closes it for the universal-safety subset.

### Alternative 2: Implement all 13 R01-R13 rules at once

Adopt the full claude-code-harness rule set immediately: R01-R04 (denial: sudo, .git, .env, force-push) + R05-R07 (query: out-of-scope writes, unexpected installs) + R08-R10 (security: --no-verify, direct main pushes, credential patterns) + R11-R13 (post-execution: assertion tampering, test skipping, coverage reduction).

> [!warning] Rejected: R05-R07 (query rules) require user-prompt routing — the hook returns `ask` not `deny`, which depends on the harness supporting interactive ask-and-defer. Claude Code does support `ask`, but ROUTING the question through the conversation flow needs careful UX work. R11-R13 (post-execution) need PostToolUse hooks (different event, different state — the tool already ran). Layer A intentionally limits scope to R01-R04 (denial-only, PreToolUse-only) so the first hook ships clean. R05-R13 follow as separate decisions once R01-R04 is operationally proven.

### Alternative 3: Implement Layer B first (stage-gate enforcement)

Build the stage-gate hook now: read `current_stage` from the active task, block writes to that stage's `forbidden_zones`. This is the high-leverage long-term goal.

> [!warning] Rejected: AICP doesn't currently have a "live active task" mechanism. The wiki/backlog/tasks/ folder has `_index.md` placeholders but no actual tasks with `current_stage` frontmatter. Without state to read, the hook would have no source of truth for "what stage are we in?" — it would either block everything (false positive) or block nothing (no enforcement). Building the state mechanism is a multi-step task in itself. Layer A doesn't block on this; ship it and queue Layer B as the follow-up that EARNS the harness/state work.

### Alternative 4: One bash script per rule (4 separate hook scripts)

Instead of one Python script with 4 rules, register 4 separate hook entries in settings.json — one per rule. Each is a bash one-liner.

> [!warning] Rejected: Bash one-liners can't easily produce the structured JSON response Claude Code hooks expect (`{"hookSpecificOutput": {...}}`). They also can't match against multiple tool types (Bash + Write + Edit) without 12 separate hook entries (4 rules × 3 tools). One Python script with a routing function is cleaner: parse the input JSON, dispatch to per-rule check, emit structured response.

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **The compliance gap is quantified.** Per Quality Standards (the second brain's `model-quality-failure-prevention-standards.md`), instruction-only enforcement is ~25% compliance, structured rules ~60%, hooks ~98%. AICP's AGENTS.md "Hard rule 9: Preserve working state. Never run destructive commands without explicit instruction." is currently at the 25% layer. Hooks for the safety subset move that to 98%.
>
> 2. **Layer A's rules are universally correct.** No AICP profile or task type should EVER write to `.env` directly via Edit/Write — `.env` should be edited by the user out-of-band. No session should `git push --force` to main without explicit operator approval. These rules don't have edge cases that require context awareness.
>
> 3. **Layer A is independent of AICP's task-state design.** A safety hook that blocks `sudo` doesn't need to know which methodology stage we're in. Shipping Layer A NOW doesn't preempt Layer B's design space — they're orthogonal.
>
> 4. **Bypass exists for legitimate cases.** Per Extension Standards "Enforcement Must Be Mindful — Hard Blocks Need Justified Bypass", when an operator needs to legitimately edit `.env` (rare, but valid), they do it OUT-OF-BAND (terminal, IDE) — Claude Code is not the right tool for it. The hook's deny message names the bypass: "Edit .env directly in your terminal — this hook is for AI agent safety, not for you."
>
> 5. **AICP's existing `aicp/guardrails/` is server-side**; this hook is client-side. Both layers are needed (defense in depth). Server-side catches what Claude Code lets through; client-side catches what Claude Code does directly.
>
> 6. **Reversibility is trivial.** A hook is one entry in `settings.json`. Removing it = delete the entry. The hook script itself can stay as a library for Layer B to extend.

## Reversibility

**Easy** — `.claude/settings.json` is one file; removing the `hooks` block disables all hooks. The hook script (`tools/hooks/pretool_safety.py`) becomes dead code if disabled but doesn't break anything else. Reversal of Layer A: delete the `hooks` block. Reversal of Layer B (when added): same shape — additional `hooks` entry, removable by deletion.

## Dependencies

If reversed (remove Layer A):

- AGENTS.md hard rules return to ~25% compliance for safety-critical operations
- Risk of accidental `.env` commits, force-pushes to main, sudo-mediated state changes increases
- `aicp/guardrails/` (server-side) still catches operations that REACH the AICP backend, but Claude Code's direct tool use (Bash, Write, Edit) bypasses
- No tooling debt accrued — hook script can stay

If extended (add Layer B — stage-gate enforcement):

- Requires a "live active task" mechanism. Candidates:
  - **A**: A `~/.aicp/active-task.json` symlink/file pointing to the wiki/backlog/tasks/<id>.md the operator is working on. Hook reads it.
  - **B**: A `.aicp/state.yaml` per repo root tracking `current_task` + `current_stage`. Hook reads it.
  - **C**: Inferred from git branch name pattern (`feat/T<id>-<slug>` → look up task ID in wiki/backlog/). Hook parses git HEAD.
- Needs design decision on which mechanism. Out of scope for this decision; track as separate task.
- Needs hook script extension to read state + apply per-stage `forbidden_zones` from `wiki/config/domain-profiles/backend-ai-platform-python.yaml`.

## Implementation (Layer A, this decision)

### Files

- **NEW**: `tools/hooks/pretool_safety.py` — hook script, ~80 lines, implements R01-R04 deny rules
- **MODIFIED**: `.claude/settings.json` — add `hooks.PreToolUse` entry pointing to the script
- **MODIFIED**: `AGENTS.md` — note that hooks are now in place for the safety subset; update the "Three-layer defense" framing if applicable

### R01-R04 specifics

| Rule | Tool | Match | Deny reason |
|------|------|-------|-------------|
| R01 | Bash | command starts with `sudo ` or contains ` sudo ` | "sudo blocked — AICP's IaC must work without elevated privileges; if you genuinely need it, run the command in your own terminal" |
| R02 | Write/Edit | path contains `/.git/` (excluding `.gitignore`, `.gitattributes` at root) | ".git/ writes blocked — modifying git internals via Write/Edit risks corrupting the repo; use git CLI in your terminal" |
| R03 | Write/Edit | path matches `**/.env*` (except `.env.example`, `.env.template`) | ".env writes blocked — secrets must be edited out-of-band; .env.example is the placeholder template" |
| R04 | Bash | command matches `git push.*--force\|git push.*-f ` (with word boundaries) | "git --force push blocked — confirm out-of-band that you want this destructive operation; force pushes can lose remote work" |

### Verification

After landing the hook, manually verify each rule fires:
1. Try to use Bash tool with `sudo apt-get install foo` → expect denial
2. Try to use Write tool with path `.git/config` → expect denial
3. Try to use Write tool with path `.env` → expect denial
4. Try to use Bash tool with `git push --force origin main` → expect denial

For each, confirm the deny reason text appears in the response.

## Relationships

- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-quality-failure-prevention-standards.md (the 25%/60%/98% compliance evidence)
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-skills-commands-hooks-standards.md (Extension Standards — hook patterns)
- COMPLEMENTS: [Skills as primary extension pattern](./skills-as-primary-extension-pattern.md) (skills teach 60% compliance; this decision adds the 38% hook layer)
- ENABLES: future stage-gate enforcement (Layer B — separate decision once state mechanism lands)
- REFERENCES: AICP's [aicp/guardrails/](../../../aicp/guardrails/) (server-side equivalent — defense in depth, not replacement)
- TRACKED IN: [wiki/backlog/epics/_index.md](../../backlog/epics/_index.md) Step 9.5 PreToolUse hooks
