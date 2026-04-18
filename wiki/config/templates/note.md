---
title: "{{title}}"
type: note
domain: {{domain}}
note_type: {{note_type}}
status: synthesized
confidence: medium
created: {{date}}
updated: {{date}}
sources: []
tags: []
---

# {{title}}

<!-- NOTE TYPE determines structure. Pick one:
     - directive: operator instruction — verbatim quotes, interpretation, action items
     - session: session record — decisions made, artifacts produced, state changes
     - completion: task/stage completion — what passed, what concerns, what's next
-->

## Summary

<!-- What happened, what was decided, or what was directed.
     Notes are short — MIN 10 words. MAX 3 sentences.
     
     EXAMPLE (directive): "Operator mandated that all infrastructure must be
     reproducible through tooling, never created manually. This changes how we
     approach systemd units, cron jobs, and service configuration."
     
     EXAMPLE (session): "Session focused on methodology evolution: upgraded 6
     templates, created milestone page, planned 12 epics for v2.0 milestone."
     
     EXAMPLE (completion): "E012 template enrichment complete. All 8 target
     templates now have inline example content as HTML comments." -->

<!-- ═══ DIRECTIVE NOTE STRUCTURE ═══ -->
<!-- Use this structure when note_type: directive -->

## Operator Directive

<!-- VERBATIM operator words. Quote exactly. Do not paraphrase.
     Use > blockquote for each distinct statement.
     STYLING: > [!warning] for critical directives, plain > for standard.
     
     EXAMPLE:
     > [!warning] Critical Directive
     > "fix it at the root instead.. its not hard"
     >
     > "we need to establish a strong method of work with the Wiki LLM structure
     > and Methodology"
     
     EXAMPLE:
     > "we are also going to offer an sdlc rules and structure that will allow
     > project to customize not only their methodologies but the whole sdlc"
     >
     > "So its would be logical to have a middle ground and at least one simplified
     > and one full chain and the default is the middle ground." -->

> "{{verbatim operator words here}}"

## Interpretation

<!-- YOUR interpretation of what the directive means.
     Clearly separated from the verbatim section.
     What does this change about how we work?
     
     EXAMPLE: "The operator is saying that when we hit a blocker, we must solve it
     with tooling (scripts, hooks, pipeline commands) rather than handing the problem
     back to the operator for manual resolution. This is a design principle for all
     future tool work: if something can be automated, it MUST be automated. Builds
     on the 'infrastructure over instructions' lesson."
     
     EXAMPLE: "Three distinct requirements here: (1) SDLC is bigger than methodology
     — it encompasses the full lifecycle including project phase and scale. (2) Three
     chain levels: simplified, middle ground (default), full. (3) Projects must be
     able to customize, not just copy. This means building a FRAMEWORK, not an
     instance." -->

## Action Items

<!-- Numbered list of concrete actions this directive requires.
     Each item: specific, verifiable, tied to a file or system.
     
     EXAMPLE:
     1. Update `wiki/config/methodology.yaml` to support three chain levels
     2. Create `wiki/domains/cross-domain/sdlc-customization-framework.md` page
     3. Add chain-level field to the Goldilocks identity profile schema
     4. Log this directive in MEMORY.md for cross-session persistence -->

1. {{action}}

<!-- ═══ SESSION NOTE STRUCTURE ═══ -->
<!-- Use this structure when note_type: session -->

## Decisions Made

<!-- Numbered list of decisions with brief rationale.
     Format: Decision — because reason.
     
     EXAMPLE:
     1. Use HTML comments for template examples instead of pre-filled content —
        because pre-filled sections risk being left in final pages by mistake.
     2. Enrich 8 templates in this session, defer remaining 16 to next session —
        because depth on each template matters more than breadth across all.
     3. Milestone target set to 2026-05-15 — because 12 epics at current pace
        needs approximately 4 weeks with operator review checkpoints. -->

## Artifacts Produced

<!-- Table: artifact | path | status -->

| Artifact | Path | Status |
|----------|------|--------|
| {{name}} | {{path}} | {{done/partial/blocked}} |

## State Changes

<!-- What changed in the wiki, configs, tools, or backlog.
     Metrics before → after where possible.
     
     EXAMPLE:
     - Templates with inline examples: 6 → 14 (8 enriched this session)
     - Milestone page created: `wiki/backlog/milestones/second-brain-v2-0.md`
     - Epic pages created: E010 through E021 (12 epics scaffolded)
     - Pipeline post errors: 3 → 0 (fixed missing frontmatter fields)
     - Wiki page count: 267 → 279 (12 new pages) -->

<!-- ═══ COMPLETION NOTE STRUCTURE ═══ -->
<!-- Use this structure when note_type: completion -->

## What Was Done

<!-- Brief description of the completed work.
     Reference task ID if applicable. -->

## Validation

<!-- What gates passed? Pipeline post output? Test results?
     STYLING: > [!success] for passes, > [!bug] for issues found.
     
     EXAMPLE:
     > [!success] Pipeline post: 0 errors
     > All 6 validation steps passed: index, manifest, validate, obsidian, lint, stats.
     > 279 pages, 17 domains, 0 orphans.
     
     EXAMPLE:
     > [!bug] 2 lint warnings remain
     > - `wiki/spine/model-methodology.md`: Summary below 30 words (28 words)
     > - `wiki/decisions/02_validated/tools/mcp-vs-cli.md`: Missing alias field -->

## Concerns Raised

<!-- Any concerns filed during this work.
     If none: "No concerns filed." -->

## Next Steps

<!-- What should happen after this completion.
     What work does this unblock? -->

## Relationships

- RELATES TO: {{related_page}}
