---
title: "{{epic_id}} {{title}} — Design Document"
type: concept
domain: {{domain}}
status: synthesized
confidence: high
maturity: seed
created: {{date}}
updated: {{date}}
sources:
  - id: requirements-spec
    type: file
    file: "{{requirements_spec_path}}"
tags: [methodology, design, {{epic_tag}}]
---

# {{epic_id}} {{title}} — Design Document

## Summary

<!-- 2-3 sentences: design decisions and architecture for this epic/module.
     Resolves open questions from the requirements spec. Every decision
     includes rationale and reversibility. Produced during the DESIGN stage. -->

## Key Insights

<!-- Top design insights that shaped the decisions. -->

## Deep Analysis

<!-- Each major design decision gets its own subsection.
     Structure per decision:

### Decision N: {{decision_title}}

     STYLING: > [!success] Decision: {{statement}}
     > | Scenario | Action |
     > |----------|--------|

     Then: rationale, evidence, rejected alternatives.
     STYLING: > [!warning] Rejected Alternative: {{name}}
     > Why rejected: {{specific reason}}

     Reversibility assessment for each decision. -->

<!--
EXAMPLE:

### Decision 1: Configuration Format for Validation Rules

> [!success] Decision: Define validation rules in YAML (wiki-schema.yaml), not in code
> | Scenario | Action |
> |----------|--------|
> | New field added to schema | Add entry to wiki-schema.yaml — no code change required |
> | Field type constraint changes | Update yaml — validator auto-reads on next run |
> | New page type introduced | Add type entry + required fields — deploy is a file copy |

**Rationale:** Validation rules change with wiki structure, not with tool releases.
Keeping them in YAML lets operators extend the schema without touching Python.
Evidence: existing `wiki-schema.yaml` already defines type enums; extending it is
lower friction than adding a new code branch per field.

> [!warning] Rejected Alternative: Hardcode validation in tools/validate.py
> Why rejected: Every schema change requires a code edit, review, and redeploy.
> Schema evolves weekly; coupling it to code creates unnecessary release pressure.

> [!warning] Rejected Alternative: JSON Schema
> Why rejected: YAML is already the project standard for config; JSON Schema adds a
> second format without meaningfully improving expressiveness for this use case.

**Reversibility:** LOW risk — YAML can be replaced with code later if performance
becomes a concern. The interface (validate_page → ValidationResult) stays the same.

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| YAML config | Machine-readable, validatable, operator-editable | Verbose, harder to author ad-hoc | CHOSEN — validation outweighs authoring cost |
| Hardcoded rules | Simple, fast to write | Couples schema to releases, brittle | REJECTED |
| JSON Schema | Industry standard, tooling support | Second format, no benefit here | REJECTED |
-->


### Module Plan

<!-- Refined module/task breakdown with implementation order.
     STYLING: > [!abstract] with table: Order | Module | Scope | Estimate | Depends On -->

## Open Questions

<!-- Design-level questions remaining. Should be few — design stage resolves
     most questions from requirements. Any remaining questions are implementation
     details, not design choices. -->

## Relationships

- IMPLEMENTS: [[{{epic_title}}]]
- BUILDS ON: {{requirements_spec_title}}
