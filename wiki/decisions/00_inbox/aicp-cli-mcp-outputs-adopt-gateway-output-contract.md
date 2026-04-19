---
title: "Decision: AICP CLI Subcommands and MCP Tool Outputs Adopt the Gateway Output Contract (5 Rules)"
type: decision
domain: ai-agents
layer: 6
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "gateway-output-contract"
  - "model-context-engineering"
  - "aicp-mcp-tool-surface-audit-2026-04-19"
reversibility: easy
created: 2026-04-19
updated: 2026-04-19
sources:
  - id: gateway-output-contract
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/standards/gateway-output-contract.md
    description: "Second brain L-spine standard (growing maturity, added 2026-04-15) — 5 structural rules every agent-readable tool output must honor"
  - id: aicp-cli-main
    type: file
    file: aicp/cli/main.py
    description: "AICP CLI dispatcher with 50+ flags producing agent-readable output (--task-cmd, --profile-cmd, --metrics, --dlq-status, --health-report, --status, --check, etc.)"
  - id: aicp-mcp-server
    type: file
    file: aicp/mcp/server.py
    description: "69 MCP tools producing agent-readable returns; 22 of these will migrate to CLI per the MCP audit decision; ALL outputs (kept-as-MCP and migrated-to-CLI) need to honor the contract"
  - id: aicp-cli-output-samples
    type: directive
    file: "live `aicp --task-cmd list` and `aicp --profile-cmd list` outputs sampled 2026-04-19"
    description: "Sample audits show missing NEXT lines and missing context-aware branching — current outputs partially honor the contract"
tags: [decision, output-contract, cli, mcp, context-injection, aicp, ai-agents, transferable]
---

# Decision: AICP CLI Subcommands and MCP Tool Outputs Adopt the Gateway Output Contract (5 Rules)

## Summary

The second brain's `gateway-output-contract` standard (added 2026-04-15, growing maturity) defines five structural rules every agent-readable tool output must honor: (1) Single Responsibility (one subcommand, one question answered), (2) Context-Aware Branches (output shape varies by location × freshness × declared state), (3) Size Ceiling (~60 lines default, opt-in for `--full-content`), (4) Read-Whole Marker (`⚠ READ THIS OUTPUT IN FULL — <reason>` when output contains buried decision-routing or context-critical info), (5) Closing Next-Move (`NEXT: <command>` so the agent doesn't invent actions). The contract was authored after a fresh agent (post-compaction in the second brain) invented a 5-layer onboarding plan because no gateway output declared the canonical next step. AICP has 50+ CLI flags and 69 MCP tools producing agent-readable outputs (Claude Code consumes these via the MCP server; CLI flags are also agent-callable). A spot audit on 2026-04-19 confirmed the gap: `aicp --task-cmd list` and `aicp --profile-cmd list` both lack closing `NEXT:` lines, leaving the invoking agent to invent next-action heuristics. This decision adopts the contract for all AICP agent-readable outputs and provides a phased remediation plan: (Phase A) Apply the contract to the 22 MCP→CLI tools migrated under the MCP audit decision — these are new surfaces, no deprecation cost, build them right; (Phase B) Audit and remediate existing CLI subcommand outputs (`--task-cmd`, `--profile-cmd`, `--metrics`, `--dlq-status`, `--health-report`, `--status`, `--check`, `--models`, `--dashboard`); (Phase C) Audit and remediate retained MCP tool returns (Categories A/B/C from the MCP audit — inference, KB, fleet) — most of these are data returns where the contract applies more loosely (Rule 5 "NEXT" may not always be appropriate for an inference response), but Rules 1-4 still hold. The decision is easy-reversible because it adds discipline without changing functionality — outputs continue to work; the contract is a quality bar not a behavioral change. The decision applies the second brain's teaching to AICP without modification: the contract is generic enough that it transfers as-written; AICP just becomes a second project applying it (the brain itself being the first).

## Decision

> [!success] Apply the Gateway Output Contract's 5 rules to ALL AICP agent-readable outputs (CLI subcommand outputs + MCP tool returns). Phased remediation: new surfaces from MCP audit (Phase A) → existing CLI outputs (Phase B) → retained MCP tool returns (Phase C).
>
> | Rule | What it requires | AICP application |
> |------|-----------------|------------------|
> | 1. Single Responsibility | One subcommand, one question answered | Audit each CLI flag's output: does it answer ONE question? Split if it mixes questions (e.g., `--check` may mix system status + config validation + backend health). |
> | 2. Context-Aware Branches | Output varies by location/freshness/declared state | Detect: AICP project root vs invoked-from-elsewhere; declared profile vs default; current task in `.aicp/state.yaml` vs no-task. Branch output shape per cell. |
> | 3. Size Ceiling (~60 lines) | Default ≤60, opt-in `--full` for more | Audit verbose outputs (`--health-report`, `--metrics`, `--dashboard`); add `--full` flag for exhaustive dump; default to summary. |
> | 4. Read-Whole Marker | `⚠ READ THIS OUTPUT IN FULL — <reason>` when buried decision content | Apply to outputs with task-routing or stage-gate info (e.g., `--task-cmd show` when current_stage forbids upcoming operation). |
> | 5. Closing Next-Move | `NEXT: <command>` or 1-2-option chooser | Apply to ALL operational outputs. `--task-cmd list` should close with `NEXT: aicp --task-cmd switch <id> <stage>` or `NEXT: create wiki/backlog/tasks/T<NNN>-<slug>.md`. |

### Phased remediation

**Phase A — Build new CLI surfaces right (concurrent with MCP audit Phase 2-3, ~22 tools):**
The 22 tools migrating from MCP to CLI per the MCP audit decision are GREENFIELD on the CLI side. Author them with the contract from line 1. Cost: zero added — the contract is a guideline for HOW to author, not a deprecation overhead.

**Phase B — Audit + remediate existing CLI subcommand outputs (~30 commands):**
Existing outputs that an agent might invoke (sample list — full audit pending): `--check`, `--health-report`, `--retry-dlq`, `--dlq-status`, `--metrics`, `--status`, `--models`, `--profile-cmd list/show/diff`, `--task-cmd list/show`, `--kb`, `--rag`, `--tools`, `--capabilities`, `--bench`, `--self-test`, `--observe`, `--dashboard`, `--stats`, `--history`, `--tasks`, `--extract-memories*`, `--router-debug`, `--session-list`, `--project-cmd list`, `--complete`, `--vision`, `--transcribe`. Per-command audit + add `NEXT:` lines + size-ceiling check. Cost: small (1-3 lines per command).

**Phase C — Audit + remediate retained MCP tool returns (Categories A/B/C, ~47 tools):**
Inference, KB, fleet tools. Most return data not decisions, so Rule 5 (NEXT line) applies less strictly — an inference response doesn't need a NEXT. But Rules 1-4 still apply: don't mix data + metadata in confused ways, branch on context where appropriate, cap response size with truncation marker, add Read-Whole if returning a decision (e.g., `aicp_route` returns a routing decision — that needs the marker if buried). Cost: per-tool review; most tools likely already comply on Rules 1-4 because they return clean data.

## Alternatives

### Alternative 1: Don't adopt; AICP CLI/MCP outputs are fine as-is

Skip the contract. AICP works today; the contract is a knowledge-project discipline, not a backend-platform discipline.

> [!warning] Rejected: the contract's first sentence is "Tool outputs from gateway subcommands are context injections to the invoking agent, not data returns." This generalizes from "gateway subcommands" to ANY tool whose output is consumed by an LLM agent. AICP's CLI and MCP outputs are exactly that: agent-consumed text that programs the agent's next move. The 2026-04-15 incident in the second brain (fresh agent inventing 5-layer plan) is a direct precedent for what would happen with an agent invoking AICP commands without NEXT lines — the agent invents heuristics. The principle transfers; AICP being a backend-platform doesn't exempt it from the principle (in fact, AICP being a TOOLING surface for agents makes the principle MORE applicable).

### Alternative 2: Adopt but only for the 22 migrated tools (Phase A only)

Apply the contract to the new CLI surfaces from the MCP audit. Leave existing CLI outputs alone.

> [!warning] Rejected: this leaves the existing ~30 CLI flags producing partial-contract outputs that agents continue to consume. The agents don't know which outputs follow the contract and which don't; they treat every output the same way. Inconsistent compliance is worse than uniform non-compliance because it teaches agents the wrong heuristic ("AICP outputs sometimes have NEXT, sometimes don't — guess"). Phase B is a small additional cost (per-command 1-3 line additions) and produces a coherent contract surface across AICP's tooling.

### Alternative 3: Adopt but rewrite all outputs at once (no phasing)

Big-bang adoption. Single PR, single audit, all outputs become contract-compliant.

> [!warning] Rejected: the audit is moderate-sized (~50 CLI flags + ~47 retained MCP tools = ~97 surfaces to review). A single PR would be hard to review, hard to test, and risk regression on commands that work today. Phasing reduces risk: Phase A is greenfield (no regression possible), Phase B audits known commands one category at a time, Phase C is data-return-heavy where most tools likely already comply. The total work is similar; the risk profile is much better with phasing.

### Alternative 4: Author AICP-specific output contract instead of adopting the second brain's

Define an AICP-specific contract (maybe shorter, maybe with different rules) tailored to backend-platform tooling.

> [!warning] Rejected: the second brain's contract is generic by design — it derives from `model-context-engineering` (a general principle) and applies the principle to outputs. Authoring an AICP-specific contract would: (a) duplicate the 5 rules with rewording, (b) risk drift from the second brain's contract as it evolves, (c) signal that AICP doesn't trust the second brain's contracts for transfer (which is the opposite of the adoption posture). The transferable shape of the second brain's contracts is the WHOLE POINT of having them in the spine. Adoption-as-written is the right default; deviation requires justification, not preference.

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **The contract's first principle covers AICP unambiguously.** The contract's introductory line: "Tool outputs from gateway subcommands are context injections to the invoking agent, not data returns. ... Apply the same structural rules to outputs that Principle 2 applies to inputs." AICP's CLI and MCP tools produce agent-consumed text. The principle applies; adoption is the default action.
>
> 2. **The 2026-04-15 incident is a transferable precedent.** A fresh agent in the second brain invented a 5-layer onboarding plan because no gateway output declared the canonical next step. AICP has equivalent risk: a fresh agent invokes `aicp --status` (or `aicp_dlq_status` MCP tool) and gets a list with no NEXT — the agent invents what to do with the information. Without explicit NEXT, agents improvise; improvisation has no quality floor.
>
> 3. **The MCP audit decision creates 22 greenfield CLI surfaces.** Per `aicp-mcp-tool-surface-audit-2026-04-19.md`, 22 tools migrate from MCP to CLI (Categories D and E). These are NEW CLI surfaces — no existing consumers, no deprecation overhead. Building them with the contract from line 1 is the cheapest possible adoption path. Phase A is essentially free if done concurrently with the migration.
>
> 4. **Sample audit confirms the gap is real.** `aicp --task-cmd list` and `aicp --profile-cmd list` were sampled 2026-04-19. Both lack closing `NEXT:` lines. `--task-cmd list` says "No tasks in wiki/backlog/tasks/" + "Create one at: wiki/backlog/tasks/T<NNN>-<slug>.md" — close to NEXT but not formatted as it. `--profile-cmd list` ends abruptly with no next-move guidance. Two out of two sampled commands violate Rule 5; the gap is structural, not isolated.
>
> 5. **Adoption cost per command is small.** Adding a `NEXT:` line to a CLI command's output is 1-3 lines of code (a print statement at the end of the handler). Adding context-aware branches (Rule 2) is more substantive but applies only to commands where context genuinely affects the answer. Most existing AICP CLI commands need only the NEXT line addition. Cumulative cost: hours, not days.
>
> 6. **The contract makes AICP commands more skill-friendly.** The skills system (.claude/skills/) teaches Claude Code agents when and how to invoke commands. A contract-compliant CLI output makes the SKILL.md trivial to author — the skill just says "run X; the output's NEXT line tells you what to do." Without the contract, every skill must duplicate next-action guidance that should live in the CLI output. Adoption REDUCES skill authoring burden.
>
> 7. **The contract's existence in the spine signals it's adoption-ready.** Standards in `wiki/spine/standards/` are framework-level discipline; their being there at growing+ maturity means the second brain considers them transferable. The brain's own gateway is documented in the contract as the precedent application; AICP becomes the second documented application. Co-adoption strengthens the contract by giving it a second instance.

## Reversibility

**Easy.** Each command's output is independent. Adding `NEXT:` lines is non-destructive (adds output, doesn't change existing). If the contract proves wrong for AICP's case (unlikely — the contract is generic), removal is per-line. Implementation effort is incremental and per-command; no architectural lock-in.

The contract does not require functional changes to commands — only output shape changes. CLI flag arguments, exit codes, JSON output structure (when `--json` is used) are unchanged. Operators see no behavioral difference; agents see better-shaped output.

## Dependencies

If executed (proceed with Phase A → B → C):

- `aicp/cli/main.py` — add a small helper `print_next(msg)` to standardize NEXT line formatting; refactor each command handler to call it
- `aicp/mcp/server.py` — for MCP tool returns that need Rule 4 (Read-Whole Marker), prepend the marker string to the response text where applicable
- `.claude/skills/` — skills authored for migrated tools (per MCP audit Phase 2-3) reference the NEXT line as the canonical next-action source; reduces duplication
- Tests — add a unit test pattern that asserts CLI command output ends with `NEXT:` (where applicable); skip for inference / data-return tools (Phase C exemptions)
- Doc — single line in CLAUDE.md `## CLI Conventions` (to be added) noting "AICP CLI/MCP outputs follow the Gateway Output Contract"

If reversed (drop the contract):

- Per-line removal of NEXT printlns
- Skills lose the "the output's NEXT tells you what to do" reference; would need to re-embed next-action guidance per skill
- Agents revert to inventing next actions on AICP outputs

## Relationships

- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/standards/gateway-output-contract.md (the standard being adopted)
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-context-engineering.md (the principle the contract applies — structured context governs behavior)
- BUILDS ON: [aicp-mcp-tool-surface-audit-2026-04-19](./aicp-mcp-tool-surface-audit-2026-04-19.md) (Phase A creates 22 greenfield CLI surfaces this contract applies to from day 1)
- IMPLEMENTS: AICP's adherence to the second brain's framework-level output discipline
- ENABLES: skills (.claude/skills/) become simpler to author because next-action lives in the CLI output
- ENABLES: agents calling AICP via CLI or MCP get consistent, predictable, NEXT-bearing outputs
- DEPENDS ON: AICP's CLI dispatcher pattern (`aicp/cli/main.py`) being amenable to a `print_next()` helper integration
- RELATES TO: [skills-as-primary-extension-pattern](../01_drafts/skills-as-primary-extension-pattern.md) (the contract supports the skills pattern by reducing per-skill action-guidance duplication)
- RELATES TO: [aicp-mcp-server-tool-surface-drift-from-claude-md](../../lessons/00_inbox/aicp-mcp-server-tool-surface-drift-from-claude-md.md) (sister discovery — the drift lesson; this contract is part of the same "AICP needs governance, not just code" theme)
