---
title: "{{title}}"
type: task
domain: backlog
status: draft
priority: {{priority}}
task_type: {{task_type}}
current_stage: document
readiness: 0               # 0-100: definition completeness. Is this READY to work on?
progress: 0                 # 0-100: execution completeness. How far is the WORK?
stages_completed: []
artifacts: []
estimate: {{estimate}}
epic: "{{epic_id}}"
module: "{{module_id}}"
depends_on: []
confidence: high
created: {{date}}
updated: {{date}}
sources: []
tags: []
---

# {{title}}

<!-- READINESS vs PROGRESS:
     - readiness: advances through document/design stages (requirements defined, plan confirmed)
     - progress: advances through scaffold/implement/test stages (work done, tests passing)
     - readiness gates progress: don't start building until readiness ≥ threshold
     - 99→100 on EITHER dimension = human review required
     See: wiki/domains/cross-domain/readiness-vs-progress.md -->

## Summary

<!-- 1-2 sentences: what this task produces.
     A task is the atomic work unit — it goes through stages.
     Reference the parent module/epic for context. -->

## Done When

<!-- Checklist of verifiable completion criteria.
     Format: - [ ] Specific verifiable statement
     CRITICAL: At least one item must name a specific file or output.
     For code tasks: name the runtime file that imports new code.
     For wiki tasks: name the wiki page that must pass validation.
     Generic boilerplate lets agents cheat — be specific.
     
     GOOD: "- [ ] `wiki/lessons/new-lesson.md` passes pipeline post with 0 errors"
     BAD: "- [ ] Task is complete" -->

<!-- EXAMPLE Done When items (replace with your content):
     - [ ] `wiki/lessons/03_validated/new-lesson.md` passes `pipeline post` with 0 errors
     - [ ] `src/hooks/event-firing.ts` imports and calls workspace-coordinator
     - [ ] `pnpm tsgo` passes with 0 type errors
     Specific files and commands — never "it works" or "it's done"

     WHY specific file paths matter:
     - Generic: "- [ ] Lesson page is created and validated" — an agent can claim this done
       by creating any file in any location with any content.
     - Specific: "- [ ] `wiki/lessons/02_synthesized/lessons-from-batch-ingestion.md` passes
       `python3 -m tools.pipeline post` with 0 errors" — there is exactly one way to satisfy
       this criterion and it requires the right file in the right location passing real checks.
     The Done When section is your protection against plausible-but-wrong completion. -->

- [ ] {{specific_criterion_naming_a_file}}
- [ ] {{specific_criterion_naming_a_command}}

## Relationships

- PART OF: [[{{epic_title}}]]
