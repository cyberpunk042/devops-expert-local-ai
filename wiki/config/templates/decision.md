---
title: "Decision: {{title}}"
type: decision
domain: {{domain}}
layer: 6
status: synthesized
confidence: medium
maturity: seed
derived_from:
  - "{{derived_page_1}}"
reversibility: moderate
created: {{date}}
updated: {{date}}
sources: []
tags: []
---

# Decision: {{title}}

## Summary

<!-- 2-3 sentences: the decision and recommendation.
     State the default choice upfront, then the nuance.
     
     EXAMPLE: "When integrating tools into LLM-powered workflows, CLI+Skills is the
     default preferred approach for operational tasks because it loads tool instructions
     contextually rather than exhausting the context window at startup. MCP servers are
     preferred for external service integration and tool discovery scenarios. The two
     approaches are complementary and the choice depends on the integration scenario."
     
     EXAMPLE: "Use Obsidian as the primary human knowledge interface and NotebookLM as
     the research grounding engine. They serve different layers: Obsidian for browsing
     and authoring structured wiki pages, NotebookLM for per-query factual retrieval
     grounded in raw sources. This is a complementary-tools decision, not either-or." -->

## Decision

<!-- Clear statement of what to do.
     STYLING: Wrap in > [!success] callout with a scenario-to-action table.
     
     EXAMPLE (from MCP vs CLI decision):
     > [!success] Default to CLI+Skills for operational tooling. MCP for external services.
     >
     > | Scenario | Integration Pattern |
     > |----------|-------------------|
     > | Wiki pipeline operations (ingest, validate, lint, export) | CLI tools via Bash + skills on demand |
     > | External services without native CLI (databases, APIs, SaaS) | MCP servers |
     > | Tools needing cross-conversation discoverability | MCP servers |
     > | Research workflows with defined sequences | CLI + skills |
     
     EXAMPLE (from work hierarchy decision):
     > [!success] Match work unit to scope, not to habit.
     >
     > | Scenario | Use |
     > |----------|-----|
     > | Strategic capability, weeks of work | Epic |
     > | Coherent subsystem, days of work | Module |
     > | Single-session atomic work | Task |
     > | Multiple epics that must ship together | Milestone |
     > | Known fix, emergency | Hotfix (skip to implement) | -->

## Alternatives

<!-- What else was considered. Min 2 alternatives with brief rationale for rejection.
     STYLING: Each alternative as a subsection. Use > [!warning] for the rejected reason.
     
     EXAMPLE:
     ### Alternative 1: MCP-First (All tools as MCP servers)
     Expose every tool as an MCP server. Single integration pattern, tools always
     available without explicit loading.
     > [!warning] Rejected: MCP loads all tool schemas into the context window at
     > conversation startup regardless of whether they are used. A wiki MCP with 13
     > tools adds schema overhead to every message in every conversation, even those
     > unrelated to wiki operations.
     
     ### Alternative 2: Skills-Only (No MCP, no CLI)
     All tool operations embedded as natural language instructions in SKILL.md files.
     > [!warning] Rejected: Ties executable capability to Claude's interpretation at
     > runtime. Pure skills cannot BLOCK dangerous operations (sudo, force-push, .env
     > writes); only executable hooks can. -->

## Rationale

<!-- Why this choice. Backed by evidence from derived_from pages. Min 100 words.
     Name specific sources and quantified data.
     
     EXAMPLE: "Multiple independent sources converge on CLI+Skills as more
     token-efficient than MCP. The core mechanism is timing of context loading: MCP
     servers register all tool schemas at conversation startup — hundreds of tokens
     added to every message. Skills load only when invoked. The Playwright CLI vs MCP
     comparison provides mechanical proof: MCP injects the full accessibility tree
     after every navigation step; CLI saves state to a YAML file and reads only when
     needed. In a 10-step test, MCP loads 10 full trees; CLI loads 2-3 targeted
     snapshots. Microsoft officially recommends CLI over MCP for AI agent use." -->

## Reversibility

<!-- How hard to undo. What changes downstream if reversed.
     State the difficulty level (easy/moderate/hard) and what migration would require.
     
     EXAMPLE (easy reversibility): "Easy to reverse. The CLI tools and MCP server are
     parallel interfaces to the same underlying Python modules — switching between them
     requires updating how tools are invoked, not rewriting tool logic. No data
     migration, no schema changes, no infrastructure teardown."
     
     EXAMPLE (hard reversibility): "Hard to reverse. Switching from wiki-first to
     RAG-first would require: (1) dismantling the curated page structure, (2) building
     a chunking pipeline, (3) re-embedding all content, (4) losing typed relationships
     that don't survive chunking. The accumulated synthesis in 200+ pages would need to
     be replicated as vector-searchable chunks — significant information loss." -->

## Dependencies

<!-- What this decision affects. Other decisions, systems, or pages impacted. -->

## Relationships

- DERIVED FROM: {{derived_page_1}}
