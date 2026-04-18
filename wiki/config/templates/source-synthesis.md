---
title: "Synthesis: {{title}}"
type: source-synthesis
domain: {{domain}}
status: synthesized
confidence: medium
maturity: seed
created: {{date}}
updated: {{date}}
sources:
  - id: {{source_id}}
    type: {{source_type}}
    url: "{{source_url}}"
tags: []
---

# Synthesis: {{title}}

## Summary

<!-- 2-3 sentences: what this source teaches and why it matters.
     MIN 30 words. Reader should DECIDE whether to use this tool/pattern/idea
     without reading the raw source. If they need the original, the synthesis failed.
     STYLING: Follow with a reference card.
     
     EXAMPLE: "Harness engineering is the practice of building structured control
     systems around an LLM coding agent — not just prompt engineering but runtime
     guardrails, quality validation, and rerunnable verification. The community
     claude-code-harness project implements this as a 5-verb workflow (Setup, Plan,
     Work, Review, Release) with a TypeScript guardrail engine enforcing 13 rules
     at execution time through hooks."
     
     EXAMPLE: "A practitioner's guide to 7 techniques for improving Claude Code
     accuracy, presented by a former Amazon/Microsoft senior AI engineer building
     a startup entirely with Claude Code. The tips form a progressive stack from
     basic context hygiene to full agentic orchestration."
     
     Followed by:
     > [!info] Source Reference
     > | Attribute | Value |
     > |-----------|-------|
     > | Source    | Building Claude Code with Harness Engineering |
     > | Type      | article |
     > | Author    | Chachamaru127 / LevelUp GitConnected |
     > | Date      | 2026-04-01 |
     > | Key claim | Runtime guardrails via hooks achieve higher compliance than prompt-based guidance |
-->

## Key Insights

<!-- 5-12 numbered insights. Each a distinct aspect of the source.
     Use CONCRETE data points — "98% reduction" not "significant improvement."
     STYLING: If an insight reveals a constraint or gotcha, wrap in > [!warning].
     If there are comparative data, use a table.
     
     EXAMPLE (from Harness Engineering synthesis):
     > [!abstract] Harness = runtime guardrails, not prompts
     > The distinction between prompt-based guidance and runtime enforcement is
     > critical. Harness engineering operates at execution time through hooks,
     > blocking dangerous operations before they happen (sudo, force-push, .env
     > writes) rather than hoping the model follows instructions.
     
     - **5-verb community framework**: /harness-setup (init), /harness-plan (spec
       with acceptance criteria), /harness-work (parallel workers with self-checks),
       /harness-review (4-perspective analysis), /harness-release (changelog + version).
     
     - **CLI over MCP is emerging consensus**: Multiple sources now converge on
       CLI+Skills being more token-efficient and accurate than MCP for tool
       integration. Skills load contextually (only when relevant), MCP loads all
       schemas upfront.
     
     EXAMPLE (from Accuracy Tips synthesis):
     > [!tip] CLI+Skills over MCP trend
     > CLI+Skills loads tool instructions only when relevant (skill loading is
     > contextual), while MCP loads all tool schemas into context at startup. Result:
     > CLI is more token-efficient, produces fewer hallucinations, costs less.
     > Google Trends shows CLI overtaking MCP. -->

## Deep Analysis

<!-- Optional for source-synthesis but encouraged for rich sources.
     Break into subsections by topic area.
     DEPTH RULE: If the source DESCRIBES a tool/format/pattern, you MUST
     examine a real INSTANCE of the thing (Layer 1) before synthesizing.
     A README about X ≠ understanding X — read the actual X. -->

## Open Questions

<!-- What the source doesn't answer. What would need follow-up research.
     
     EXAMPLE:
     - Has hybrid search been empirically benchmarked against pure wiki navigation
       at the 200-500 page transition zone? (Requires: empirical testing or external
       research; the wiki only documents the theoretical boundary at ~200 pages)
     - How does the 5-verb harness workflow interact with the wiki's own 5-stage
       methodology? Are they isomorphic or complementary? -->

## Relationships

- RELATES TO: {{related_page}}
