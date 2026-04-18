---
title: "{{title}}"
type: epic
domain: backlog
status: draft
priority: {{priority}}
task_type: epic
current_stage: document
readiness: 0               # 0-100: derived from children. Are the requirements, design, plan DEFINED?
progress: 0                 # 0-100: derived from children. How far is the WORK across all modules/tasks?
stages_completed: []
artifacts: []
confidence: high
created: {{date}}
updated: {{date}}
sources:
  - id: operator-directive
    type: file
    file: "{{directive_file}}"
tags: []
---

# {{title}}

## Summary

<!-- 2-3 sentences: what this epic delivers and WHY it matters.
     Every epic MUST trace to a verbatim operator directive.
     The summary IS the charter — it defines scope boundaries.
     
     EXAMPLE: "Transform every page template from a structural skeleton with
     placeholder comments into a RICH EXAMPLE that teaches through its own content.
     A template is proto-programming: the STRUCTURE of the template programs the
     agent's behavior when filling it. After this epic, templates have INLINE EXAMPLE
     CONTENT showing what a good page looks like — the agent learns by SEEING, not
     by READING instructions."
     
     EXAMPLE: "Build a Python gateway that serves as the unified interface between
     humans, agents, and MCP clients for querying and operating on the wiki. The
     gateway replaces ad-hoc tool invocations with a structured API that understands
     stages, domains, chains, and artifact requirements." -->

## Operator Directive

<!-- Verbatim quote(s) that originated this epic.
     STYLING: > blockquote for each directive.
     This section is the AUTHORITY — when in doubt, re-read the directive.
     
     EXAMPLE:
     > "Then there is the template which should themselves be example of rich usage
     > and strong structure and example of contents."
     >
     > "Markdown offer proto-programming and proto-programming is what AI does best."
     >
     > "Preach by example."
     
     EXAMPLE:
     > "we are going to need to add python script to make the Wiki LLM for internal
     > and for external (other project to second-brain) and we are going to allow
     > those to cleanup the Wiki LLM, to run certain operation like archiving
     > documents, moving things to other folders and updating all the references." -->

> "{{verbatim operator directive}}"

## Goals

<!-- Bulleted list of concrete goals. Each goal is a CAPABILITY or DELIVERABLE.
     Not vague aspirations — specific outcomes that can be demonstrated.
     GOOD: "Agent can query all artifacts required for a stage via MCP tool"
     BAD: "Improve agent experience" -->

- {{goal_1}}
- {{goal_2}}

## Done When

<!-- Checklist of verifiable completion criteria. Each item names specific FILES,
     COMMANDS, or OBSERVABLE BEHAVIORS — not abstractions.
     GOOD: "- [ ] `python3 -m tools.pipeline post` returns 0 errors"
     BAD: "- [ ] System works correctly"
     Include at least one validation step per major deliverable.
     
     EXAMPLE (from E012 — Template Enrichment):
     - [ ] `wiki/config/templates/comparison.md` — has example Comparison Matrix inline
     - [ ] `wiki/config/templates/decision.md` — has example scenario-action table inline
     - [ ] Scaffolding any template with `pipeline scaffold <type> "Test"` produces
           a page passing `pipeline post` with 0 errors
     - [ ] Operator confirms: templates TEACH through their content, not just structure
     
     EXAMPLE (from gateway epic):
     - [ ] `python3 -m tools.gateway query --stage document --domain typescript`
           returns correct artifact list
     - [ ] `python3 -m tools.gateway move "Old Title" --to domains/new/` updates
           all wiki references automatically
     - [ ] MCP server exposes all 17 gateway operations as tools in `.mcp.json` -->

- [ ] {{specific_verifiable_criterion_1}}
- [ ] {{specific_verifiable_criterion_2}}
- [ ] Pipeline post returns 0 errors after all changes
- [ ] Operator confirms deliverables are findable (discoverability test)

## Scale and Model

<!-- Which methodology model governs this epic?
     What quality tier: Skyscraper (full process), Pyramid (deliberate compression)?
     How many modules/tasks expected? -->

> [!info] Epic Parameters
>
> | Parameter | Value |
> |-----------|-------|
> | **Model** | feature-development |
> | **Quality tier** | Skyscraper |
> | **Estimated modules** | {{N}} |
> | **Estimated tasks** | {{N}} |
> | **Dependencies** | {{list or "none"}} |

## Stage Artifacts (per methodology model)

<!-- What does each stage produce for THIS epic?
     Reference wiki/config/methodology.yaml for the model's artifact chain.
     Be specific — name the wiki pages, config files, tool changes. -->

> [!abstract] Stage → Artifact Map
>
> | Stage | Required Artifacts | Template |
> |-------|--------------------|----------|
> | Document | Directive log, research synthesis, gap analysis | wiki/config/templates/methodology/gap-analysis.md |
> | Design | Requirements spec, design plan, decisions | wiki/config/templates/methodology/requirements-spec.md |
> | Scaffold | Config changes, templates, schema updates | N/A — per deliverable |
> | Implement | Code, wiki pages, tool changes | N/A — per deliverable |
> | Test | Validation runs, pipeline post, operator review | N/A — per deliverable |

## Module Breakdown

<!-- Break the epic into modules. Each module becomes its own page.
     Format: Module name — what it delivers — estimated tasks.
     
     EXAMPLE (from E012 — Template Enrichment):
     | Module | Delivers | Est. Tasks |
     |--------|----------|-----------|
     | M1: Wiki Page Templates (18 templates) | Each of 18 page type templates enriched with inline example content | 18 |
     | M2: Methodology Templates (6 templates) | Each of 6 stage document templates enriched with example items | 6 |
     | M3: Validation | Scaffold every type, run pipeline post, verify 0 errors | 1 |
     
     EXAMPLE (from gateway epic):
     | Module | Delivers | Est. Tasks |
     |--------|----------|-----------|
     | M1: Query Operations | Queries for stages, domains, chains, templates, artifacts | 8 |
     | M2: Mutation Operations | Archive, move, backup, factory reset, agent write-back | 6 |
     | M3: MCP Integration | Wrap gateway as MCP server for cross-conversation access | 3 | -->

| Module | Delivers | Est. Tasks |
|--------|----------|-----------|
| {{module_1}} | {{deliverable}} | {{N}} |
| {{module_2}} | {{deliverable}} | {{N}} |

## Dependencies

<!-- Other epics, external factors, or blockers.
     For each: what it depends on + what happens if it's not ready. -->

## Open Questions

<!-- What's not yet decided? Each question should block a specific module or task.
     Resolve questions during Document/Design stages — not during Implement. -->

> [!question] {{question}}
> {{context for the question}}

## Relationships

- IMPLEMENTS: {{what_directive_or_model}}
- DEPENDS ON: {{dependency_epic_or_page}}
