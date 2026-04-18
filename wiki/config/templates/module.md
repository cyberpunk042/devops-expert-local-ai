---
title: "{{title}}"
type: module
domain: backlog
status: draft
priority: {{priority}}
task_type: module
current_stage: document
readiness: 0               # 0-100: derived from child tasks. Is this module DEFINED enough?
progress: 0                 # 0-100: derived from child tasks. How far is the WORK?
stages_completed: []
artifacts: []
epic: "{{epic_id}}"
depends_on: []
confidence: high
created: {{date}}
updated: {{date}}
sources: []
tags: []
---

# {{title}}

<!-- READINESS vs PROGRESS for modules:
     - readiness = AVERAGE of child task readiness (derived, never manual)
     - progress = AVERAGE of child task progress (derived, never manual)
     - Module readiness gates its children: if module design isn't done (readiness < 50),
       child tasks shouldn't start implementation
     See: wiki/domains/cross-domain/readiness-vs-progress.md -->

## Summary

<!-- 2-3 sentences: what this module delivers within its parent epic.
     A module is a scoped subsystem — independently reviewable with its own design.

     EXAMPLE (replace):
     "Update the 3 core models (Methodology, LLM Wiki, Quality) with all session
     knowledge. These models are referenced by everything else — they must be
     current before other models can reference them correctly." -->

## Tasks

<!-- List of child tasks (created separately in wiki/backlog/tasks/).
     Format: | Task ID | Title | Readiness | Progress | Status |
     Track both dimensions for each child.

     EXAMPLE Tasks table (replace with your content):

     | Task | Title | Readiness | Progress | Status |
     |------|-------|-----------|----------|--------|
     | T-042 | Enrich pattern.md template with examples | 100% | 100% | done |
     | T-043 | Enrich concept.md template with examples | 75% | 25% | in-progress |

     Readiness = is this task DEFINED enough to start (requirements, AC set)?
     Progress = how much WORK is done (scaffold→implement→test)?
     A task at 100% readiness / 0% progress is fully specified but not started
     — normal and healthy. A task at 0% readiness / 50% progress is being built
     without a clear definition — a red flag. -->

| Task | Title | Readiness | Progress | Status |
|------|-------|-----------|----------|--------|
| {{task_id}} | {{task_title}} | 0% | 0% | draft |

## Dependencies

<!-- Modules or epics this module blocks on (before its work can start/finish).
     Distinct from Impediments — Dependencies are STRUCTURAL (scheduling),
     Impediments are RUNTIME (currently blocking).
     Format: - [[target|title]] — what it provides that this module needs. -->

- [[{{dependency}}]] — {{what_it_provides}}

## Done When

<!-- Checklist. Module is done when ALL child tasks are done AND these criteria met.
     Format: - [ ] Specific verifiable statement
     99→100: requires human review (status ceiling = review, not done). -->

- [ ] All child tasks at status: done
- [ ] {{module_specific_criterion}}

## Impediments

<!-- Active RUNTIME blockers (distinct from structural Dependencies above).
     Remove entries when resolved.
     Types: technical, dependency, decision, environment, clarification,
     scope, external, quality. -->

## Relationships

- PART OF: [[{{epic_title}}]]
