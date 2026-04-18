---
title: "{{title}}"
type: lesson
domain: {{domain}}
layer: 4
status: synthesized
confidence: medium
maturity: seed
derived_from:
  - "{{derived_page_1}}"
created: {{date}}
updated: {{date}}
sources: []
tags: []
---

# {{title}}

## Summary

<!-- 2-3 sentences: the lesson stated clearly -->

## Context

<!-- When and where does this lesson apply? What situation triggers it? -->

## Insight

<!-- The core learning. Min 50 words. State it plainly.
     STYLING: Wrap the key insight in > [!warning] (failure-mode lessons)
     or > [!tip] (success/approach lessons). If there is a comparison or
     taxonomy, use a table inside > [!abstract].

     EXAMPLE Insight (replace with your content):

     > [!tip] CLI tools paired with skill files consistently outperform MCP
     > server integrations on token cost and output accuracy.
     >
     > | Aspect | Before (MCP) | After (CLI+Skills) | Evidence |
     > |--------|--------------|--------------------|----------|
     > | Schema overhead | All tools loaded at startup | On-demand load | Playwright comparison: 12x cost differential |
     > | Context efficiency | Tool schemas displace task content | Tools loaded only when invoked | Harness Engineering test: 3x more features |
     >
     > **The mechanism:** Unused MCP tool schemas occupy context tokens that could
     > hold task-relevant content. This is "context pollution" — high-entropy JSON
     > boilerplate displacing high-signal task context. The mechanism is structural,
     > not preferential — any project with many MCP tools faces the same trade-off. -->

## Evidence

<!-- Specific examples from derived_from pages. MINIMUM 3 from different sources.
     STYLING: Use > [!bug]- foldable for failure incidents with verbatim quotes.
     Use > [!success] for validated approaches.

     EXAMPLE evidence items (replace with your content):

     > [!bug]- Batch ingestion produced 37 thin pages in one sprint (2026-03-15)
     >
     > **What happened:** AI processed 12 URLs and scaffolded 37 pages in a single session.
     > **What the operator said:** "Volume is not quality. 37 files in one sprint = Mountain tier."
     > **Root cause:** No quality gate between scaffold and content generation.
     > **Impact:** 2 hours rework to audit and delete 19 pages that duplicated existing content.

     > [!success] E012 template enrichment using inline HTML comments
     >
     > **What changed:** Added EXAMPLE blocks inside template guidance comments.
     > **Result:** AI-generated pages improved from ~60% to ~90% structural compliance on first pass.
     > **Why it worked:** Examples make the implicit standard explicit — the AI sees a real target,
     > not just a description of what the target should be. -->

## Applicability

<!-- Which domains, projects, situations benefit from this lesson?
     STYLING: If listing multiple domains, use a table (domain | how it applies).
     If there is an enforcement hierarchy, use > [!abstract] with a table.

     EXAMPLE table (replace with your content):

     | Domain | How this lesson applies |
     |--------|------------------------|
     | TypeScript | Scaffold empty modules before writing business logic; prevents type-coupling creep |
     | Python/Wiki | Run pipeline post before claiming a wiki change is done; catches broken refs immediately |
     | Knowledge | Never promote a source synthesis to L3 without reading a real instance of the concept |
     | Infrastructure | Don't write systemd unit files manually; always encode them in reproducible tooling |

     The table forces precision: "applies everywhere" is not applicability — it's abdication. -->

## Relationships

- DERIVED FROM: {{derived_page_1}}
