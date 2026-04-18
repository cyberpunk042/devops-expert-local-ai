---
title: "Milestone: {{title}}"
type: milestone
domain: backlog
status: draft
priority: {{priority}}
target_date: {{YYYY-MM-DD}}
readiness: 0               # 0-100: derived from child epics. Is the milestone DEFINED enough?
progress: 0                 # 0-100: derived from child epics. How far is the WORK?
epics:
  - "{{epic_id_1}}"
  - "{{epic_id_2}}"
acceptance_criteria:
  - "{{measurable_criterion_1}}"
  - "{{measurable_criterion_2}}"
confidence: high
created: {{date}}
updated: {{date}}
sources:
  - id: operator-directive
    type: file
    file: "{{directive_file}}"
tags: [milestone]
---

# Milestone: {{title}}

<!-- A milestone groups multiple epics into a delivery target — what ships TOGETHER.
     Use milestones for: version releases, phase transitions (POC→MVP), quarterly boundaries.
     Don't use milestones for single-epic deliveries — just use the epic directly. -->

## Summary

<!-- 2-3 sentences: what this milestone delivers and WHY these epics must coordinate.
     The summary defines the scope boundary — what's IN vs OUT of this milestone.
     
     EXAMPLE: "Transform the second brain from a collection of 279 knowledge pages
     into a complete, navigable, proven system. Every model updated, every standard
     exemplified, every template rich, every chain proven, every entry point
     browsable. This is not incremental improvement — it's the system-level
     integration that makes the whole greater than the parts. 12 epics, each with
     its own proper document-design-scaffold-implement-test cycle."
     
     EXAMPLE: "Ship the first external-facing integration: OpenArms consuming the
     methodology engine from the second brain. Proves the full chain end-to-end:
     identity detection, SDLC profile selection, stage routing, artifact validation,
     enforcement hook deployment. 4 epics must coordinate because the integration
     touches methodology, gateway, hooks, and validation." -->

## Operator Directive

<!-- Verbatim quote(s) that define this milestone target.
     STYLING: > blockquote for each directive. -->

> "{{verbatim operator directive}}"

## Delivery Target

<!-- When and what.
     STYLING: > [!info] with target table. -->

> [!info] Milestone Parameters
>
> | Parameter | Value |
> |-----------|-------|
> | **Target date** | {{YYYY-MM-DD}} |
> | **Phase** | {{POC / MVP / Staging / Production}} |
> | **Chain** | {{Simplified / Middle Ground / Full}} |
> | **Total epics** | {{N}} |
> | **Estimated total tasks** | {{N}} |

<!-- EXAMPLE (from Second Brain v2.0):
     > [!info] Milestone Parameters
     >
     > | Parameter | Value |
     > |-----------|-------|
     > | **Target date** | 2026-05-15 (tentative — operator confirms) |
     > | **Phase** | Production (the wiki itself) |
     > | **Chain** | Default (stage-gated with selected artifacts) |
     > | **Total epics** | 12 (first batch — second batch of ~8-10 follows) |
     > | **Estimated total tasks** | 80-120 | -->

## Epic Composition

<!-- Which epics are in this milestone, what each contributes, and their current state.
     STYLING: Table with readiness column updated from derived values. -->

| Epic | Contributes | Current Readiness | Status |
|------|------------|-------------------|--------|
| [[{{epic_1}}]] | {{what it delivers to this milestone}} | {{N}}% | {{status}} |
| [[{{epic_2}}]] | {{what it delivers to this milestone}} | {{N}}% | {{status}} |

<!-- EXAMPLE (from Second Brain v2.0):
     | Epic | Contributes | Current Readiness | Status |
     |------|------------|-------------------|--------|
     | [[E010 — Model Updates]] | Every model page reflects ALL session learnings | 10% | draft |
     | [[E011 — Standards Exemplification]] | Every standard shows WHAT good looks like with WHY annotations | 0% | draft |
     | [[E012 — Template Enrichment]] | Every template teaches through structure, not just placeholders | 70% | draft |
     | [[E013 — Super-Model Evolution]] | Goldilocks super-model, Enforcement super-model, Knowledge super-model | 0% | draft |
     | [[E014 — Goldilocks Navigable System]] | Identity protocol to action in continuous navigable flow | 0% | draft |
     | [[E016 — Integration Chain Proof]] | Full 17-step chain proven on OpenArms with documented results | 0% | draft | -->

## Acceptance Criteria

<!-- Measurable criteria that define "this milestone is DONE."
     Each criterion is verifiable — names a command, metric, or observable behavior.
     GOOD: "Agent stage violations < 5% across 10 autonomous runs"
     BAD: "System works well"
     
     EXAMPLE (from Second Brain v2.0):
     - [ ] Operator opens Obsidian, browses from any entry point, finds everything
           needed within 3 clicks
     - [ ] Operator runs `gateway navigate` and can drill into any branch
     - [ ] All 15 model pages confirmed current by operator (no outdated sections)
     - [ ] Full integration chain (17 steps) proven on OpenArms with documented results
     - [ ] `pipeline post` returns 0 errors, 0 lint issues
     - [ ] Global sweep: operator confirms quality on all validated lessons, patterns,
           principles -->

- [ ] {{measurable_criterion_1}}
- [ ] {{measurable_criterion_2}}
- [ ] All child epics at status: done (operator confirmed)

## Dependencies

<!-- External factors or cross-milestone dependencies.
     Format: what → impact if not ready → mitigation -->

## Impediments

<!-- Active blockers against this milestone. Each has a type.
     Types: technical, dependency, decision, environment, clarification, scope, external, quality
     Remove when resolved (move to Resolved Impediments section). -->

| Impediment | Type | Blocked Since | Escalated? | Resolution |
|-----------|------|---------------|-----------|------------|
| {{description}} | {{type}} | {{date}} | {{yes/no}} | {{pending / resolved: how}} |

## Relationships

- CONTAINS: [[{{epic_1}}]]
- CONTAINS: [[{{epic_2}}]]
- IMPLEMENTS: {{what_directive_or_vision}}
