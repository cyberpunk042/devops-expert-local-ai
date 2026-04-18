---
title: "{{title}} — Gap Analysis"
type: concept
domain: {{domain}}
status: synthesized
confidence: high
maturity: seed
created: {{date}}
updated: {{date}}
sources:
  - id: infrastructure-analysis
    type: file
    file: "{{infrastructure_analysis_path}}"
tags: [methodology, gap-analysis, {{epic_tag}}]
---

# {{title}} — Gap Analysis

## Summary

<!-- 2-3 sentences: what's missing between current state and target state.
     Built on top of the infrastructure analysis. -->

## Key Insights

<!-- Top gaps and their implications. What's the biggest risk? What's the
     highest-impact gap to close? -->

## Deep Analysis

### Gap Inventory

<!-- Numbered gaps. Each gap has:
     | Aspect | Details |
     |--------|---------|
     | Current state | What exists today |
     | Required state | What needs to exist |
     | Impact | What breaks or is blocked without this |
     | Affected scope | Files, components, systems affected |
     | Complexity | S/M/L/XL effort estimate |

     Group related gaps by module or epic.
     STYLING: > [!warning] for critical/blocking gaps. -->

<!--
EXAMPLE:

> [!warning] Gap 1 — Missing frontmatter validation in post-chain (BLOCKING)
>
> | Aspect | Details |
> |--------|---------|
> | Current state | `tools/pipeline.py post` runs lint and manifest but does NOT validate frontmatter fields against wiki-schema.yaml |
> | Required state | Every page saved to wiki/ is validated on the next `pipeline post` run; invalid pages produce exit code 1 with field-level errors |
> | Impact | HIGH — malformed pages (wrong type enum, missing confidence field) silently enter the manifest, corrupt search index, and break export profiles |
> | Affected scope | tools/pipeline.py, tools/validate.py, wiki/config/wiki-schema.yaml, all 267 wiki pages |
> | Complexity | LOW — `tools/validate.py` already exists; gap is a missing function call in the post-chain at pipeline.py:~142 |

Gap 2 — No per-type required-field enforcement

| Aspect | Details |
|--------|---------|
| Current state | wiki-schema.yaml lists required fields globally but not per page type (e.g., lessons require `evidence_count`, decisions require `alternatives`) |
| Required state | Validator checks type-specific required fields in addition to global ones |
| Impact | MEDIUM — evolved page types (lesson, pattern, decision) pass validation while missing critical quality fields |
| Affected scope | tools/validate.py, wiki/config/wiki-schema.yaml |
| Complexity | S — extend validator to branch on `type` field, read type-specific rules from schema |

**Summary table:**

| Gap | Current State | Required State | Impact | Complexity |
|-----|--------------|----------------|--------|------------|
| No frontmatter validation | Pages accepted without field checks | All pages validated on save | HIGH — errors propagate | LOW — one function call |
| No per-type field enforcement | Global fields only | Type-specific required fields | MEDIUM — quality gaps in evolved types | S |
-->


### Dependency Graph

<!-- How gaps relate to each other. Which must be filled first?
     STYLING: > [!abstract] with ordering or dependency tree. -->

### Complexity and Effort Assessment

<!-- Summary table of all gaps with effort estimates.
     STYLING: > [!info] with table: Gap | Complexity | Dependencies -->

## Open Questions

<!-- Questions about gaps that need research or design decisions. -->

## Relationships

- BUILDS ON: {{infrastructure_analysis_title}}
- FEEDS INTO: {{requirements_spec_title}}
