---
title: "AICP MCP Server Tool Surface Drift — Documentation Claimed 11 Tools, Reality Was 64"
type: lesson
domain: ai-agents
layer: 4
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "cli-tools-beat-mcp-for-token-efficiency"
  - "model-mcp-cli-integration"
  - "model-quality-failure-prevention"
created: 2026-04-19
updated: 2026-04-19
sources:
  - id: aicp-claude-md-pre-fix
    type: file
    file: CLAUDE.md
    description: "Pre-fix CLAUDE.md (lines 22, 74, 176) claimed '11 tools' for the MCP server in three separate places"
  - id: aicp-mcp-server
    type: file
    file: aicp/mcp/server.py
    description: "Actual MCP server implementation — 64 distinct @mcp.tool() decorators registered (verified by grep on 2026-04-19)"
  - id: cli-beats-mcp-lesson
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/lessons/03_validated/tools-architecture/cli-tools-beat-mcp-for-token-efficiency.md
    description: "Validated lesson — '12x cost differential' for CLI vs MCP; explicitly names AICP as a candidate for early CLI-first default to prevent MCP proliferation"
  - id: mcp-cli-integration-model
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/models/ecosystem/model-mcp-cli-integration.md
    description: "Model state-of-knowledge note flags 'The wiki's own MCP server at 17 tools — is this too many?' as an open question; AICP at 64 is far beyond that threshold"
tags: [lesson, mcp, cli, tool-surface, drift, documentation, aicp, ai-agents, transferable]
---

# AICP MCP Server Tool Surface Drift — Documentation Claimed 11 Tools, Reality Was 64

## Summary

On 2026-04-19, while reading the second brain's `cli-tools-beat-mcp-for-token-efficiency` lesson and the `mcp-cli-integration` model to verify AICP was adhering to its guidance, a routine `grep -n "@mcp.tool"` on `aicp/mcp/server.py` returned **64 matches**. AICP's own `CLAUDE.md` claimed "11 tools" in three separate locations (line 22 Identity Profile table, line 74 Project Structure, line 176 Intelligent Infrastructure). The 11-tool claim was probably accurate at some past point and the documentation never got updated as tools were added incrementally over many commits. The lesson: **MCP tool surfaces grow incrementally per-commit; documentation describing the surface as a fixed count drifts immediately and silently**. This drift is not transient (a 1-2 tool gap during a feature branch) — it had compounded to ~6x understated and lived in the canonical project file that every consumer reads first. The deeper issue: the second brain's `cli-tools-beat-mcp-for-token-efficiency` lesson explicitly named AICP as a candidate for "establish the CLI-first default now before MCP proliferates as the default integration pattern." AICP did not establish that default and did proliferate. The drift in CLAUDE.md was the symptom; the root cause is that adding an MCP tool was easy (one decorator) and adding a guard against MCP proliferation was not done. This lesson is about the documentation drift specifically; a follow-up audit decision is needed to triage the 64 tools against the MCP-vs-CLI criteria. The transferable insight: **count-based documentation of an extension surface (MCP tools, CLI subcommands, skills, hooks) becomes wrong the moment a new entry lands; either compute the count at read time (linter, doc generator) or describe the surface by category and bound, not exact count**.

## Context

This lesson applies whenever:

- A project documents an extension surface (MCP tools, CLI subcommands, skills, hooks, plugins, agents) by exact count in markdown.
- The extension surface grows incrementally — small commits adding one or two entries each.
- The documentation lives in a canonical file (CLAUDE.md, README, AGENTS.md) that consumers form their mental model from.
- There is no doc-generator or linter that validates the count against reality.
- The project sits in an ecosystem with established guidance on the surface's preferred shape (e.g., "CLI default, MCP for external bridges").

In AICP's case all five conditions were met. The 11-tool claim was made in one of the early commits, and over time tools were added in batches (inference, KB, stores, model management, embeddings, audio, advanced) without anyone updating the count. By 2026-04-19 the count was understated by ~6x.

## Insight

> [!warning] Counts in documentation drift on every commit; categories don't.
> An exact count is wrong the moment the next tool is added. A category description ("inference + KB + stores + operational + advanced") survives many additions before becoming wrong because it describes the SHAPE of the surface, not the SIZE.

> [!info] Three-layer documentation strategy for extension surfaces
>
> | Layer | What it documents | Drift tolerance |
> |-------|-------------------|-----------------|
> | Generated index (computed at read time, by linter or doc gen) | Exact list of tools with one-line each | Zero — always correct |
> | Categorized prose (in CLAUDE.md or equivalent) | Categories + general bounds + audit notes | High — survives many additions |
> | Strategy/decision document (separate file) | The intended shape (when to use MCP vs CLI) | Lowest — only changes with deliberate strategy decisions |

The mistake AICP made: tried to do (1) exact count in (2) categorized-prose location, with no (3) strategy doc to constrain growth. The result: drift in (2) AND no governance on what should grow.

## Evidence

**Direct measurement (2026-04-19):** `grep -n "@mcp.tool" aicp/mcp/server.py` returned 64 matches. CLAUDE.md grep for "11 tools" returned 3 matches across lines 22, 74, 176. The drift is 11 → 64, a factor of 5.8x understated.

**The lesson explicitly named AICP:** The second brain's `cli-tools-beat-mcp-for-token-efficiency` lesson, in its "Domains where this lesson applies directly" section, lists: "**AICP and devops-control-plane**: Any future agent in the ecosystem faces the same tradeoff. Establish the CLI-first default now before MCP proliferates as the default integration pattern." AICP did not establish that default. The lesson predicted exactly the failure mode that occurred.

**Tool growth was incremental, not bulk:** The MCP server file grew from 11 tools to 64 over many commits, each adding 1-3 tools. There was no single PR adding 53 tools (which would have triggered a "wait, is this proliferation?" review). The death-by-paper-cuts pattern is what makes this kind of drift insidious — each individual addition was justified locally, but the cumulative surface exceeds the principle.

**The wiki itself flagged this concern:** The `model-mcp-cli-integration` page's "State of Knowledge" section under "Thin or unverified" flags: "The wiki's own MCP server at 17 tools — is this too many? No measured overhead comparison." If 17 was already considered questionable by the source authority, 64 is structurally past acceptable on the same axis.

**Three-place duplication of the wrong number:** CLAUDE.md said "11 tools" in three separate sections (Identity Profile, Project Structure, Intelligent Infrastructure). Each of those was added at a different time. Each was wrong by 2026-04-19. This is a doc-locality failure: when the same fact lives in N places, drift compounds — you have to update N places to fix one drift event, and any single missed update produces inconsistency.

**Drift was discovered by reading the second brain, not by AICP's own tools:** AICP has lint, evolve, export, and CI tooling. None of them validated CLAUDE.md against `aicp/mcp/server.py`. The discovery happened only because a /loop iteration was specifically tasked with "regather context and continue adhering and integrating the knowledge from the second-brain" — i.e., comparing AICP's claims to second-brain guidance. Without that comparative read, the drift could have persisted indefinitely.

## Applicability

**Domains where this lesson applies directly:**

- **Any project with an MCP server** that documents tool counts in markdown. AICP, openfleet (10 agents but each may grow MCP exposure), wiki-tools (already concerned about its 17→26 growth).
- **Any project with a skill library** that documents skill counts. AICP has 78 skills documented in CLAUDE.md; skills audit decision (`wiki/decisions/00_inbox/skills-audit-2026-04-17.md`) found 0/78 met Standards — the COUNT was right but the QUALITY claim was implicit.
- **Any project with a CLI subcommand surface** that grows incrementally. The CLI surface has the same drift pattern as the MCP surface; the only difference is exposure mechanism.
- **Any documentation of a generated artifact** — when humans write the count of something machines can compute.

**When this lesson does NOT apply:**

- Surfaces that grow rarely and deliberately (e.g., the 16 second-brain models — adding a new one is a major decision, not a casual commit). Counts of these are stable.
- One-off counts in transient documents (PR descriptions, session notes). These are accepted-stale.
- Counts that are bounded by the schema (e.g., "5 stages: document/design/scaffold/implement/test" — the count is part of the definition, not a measurement).

## Corrective action — what was done

**Immediate (this iteration):**
1. Updated CLAUDE.md three locations to reflect 64 tools and reference this lesson as an audit-pending marker.
2. Authored this lesson capturing the discovery and the broader pattern.

**Short-term follow-up (separate iteration / decision):**
3. Audit the 64 tools against `mcp-vs-cli-for-tool-integration` decision criteria. Categorize: legitimate MCP (external bridge for cross-conversation discoverability) vs should-be-CLI (operational, project-internal). Author the audit as a decision page.
4. Migrate any "should-be-CLI" tools to CLI+Skills. The migration cost per tool is small (replace `@mcp.tool()` decorator with a CLI subcommand + SKILL.md); the cumulative benefit is reduced consumer schema overhead.

**Long-term (governance, separate work):**
5. Establish a CI check that fails if `CLAUDE.md` claims a count that doesn't match the computed reality. Either: (a) generate the relevant CLAUDE.md sections from the source of truth, or (b) lint that any `\d+ tools` reference matches a fresh `grep` count.
6. Establish a per-PR check that if a new `@mcp.tool()` is added, the PR description must justify the choice over CLI+Skills. This is the proliferation guard that should have existed from day one.

## Pattern recognition — when to suspect this drift

> [!warning] Self-Check — Am I about to ship documentation that will drift?
>
> 1. **Am I writing an exact count of something machines can compute?** If yes — refactor to "category + bound + computed source" instead.
> 2. **Am I documenting an extension surface (tools/skills/hooks/CLI subcommands)?** If yes — assume it will grow incrementally and the count will be wrong by next quarter.
> 3. **Am I duplicating a fact across multiple sections of the same doc?** If yes — pick ONE canonical location; reference it from others.
> 4. **Does my project have a CI check that validates documentation against code?** If no — assume drift is the steady state, not the exception.
> 5. **Am I in an ecosystem with explicit guidance about the shape of this surface?** If yes — write a strategy doc (decision page) that constrains additions, not just describes the current state.

## How this connects — navigate from here

| Direction | Go to |
|-----------|-------|
| **What's the underlying lesson on MCP overhead?** | [[cli-tools-beat-mcp-for-token-efficiency]] (second brain L4 validated) — the 12x cost differential and AICP being explicitly named |
| **What's the model for MCP vs CLI?** | [[model-mcp-cli-integration]] (second brain) — eager vs deferred loading, when each wins |
| **What's the audit decision needed?** | TODO — to be authored: `wiki/decisions/00_inbox/aicp-mcp-tool-surface-audit.md` (categorize 64 tools, decide migrations) |
| **What's the structural prevention layer?** | [[model-quality-failure-prevention]] — three-layer enforcement; this lesson is failure of layer 1 (structural prevention) for MCP proliferation |
| **What lesson covers count claims drift more broadly?** | This page is the seed; broader lesson candidate: "Documentation counts drift; categories survive" — could be promoted from this domain-specific instance to a transferable principle |

## Relationships

- BUILDS ON: [[cli-tools-beat-mcp-for-token-efficiency]] (second brain validated lesson — explicitly named AICP)
- BUILDS ON: [[model-mcp-cli-integration]] (second brain model — eager-loading mechanism)
- INSTANCE OF: documentation drift on extension surfaces — likely transferable as a broader principle once more instances accumulate
- ENABLES: AICP MCP tool audit decision (TODO, separate iteration)
- DEPENDS ON: AICP's CLAUDE.md being the canonical project file consumers read (the drift only matters because the file is canonical)
- CONTRADICTS: implicit assumption in CLAUDE.md authoring that exact counts would stay accurate without governance
