---
title: "{{title}} — Infrastructure Analysis"
type: concept
domain: {{domain}}
status: synthesized
confidence: high
maturity: seed
created: {{date}}
updated: {{date}}
sources: []
tags: [methodology, infrastructure-analysis, {{epic_tag}}]
---

# {{title}} — Infrastructure Analysis

## Summary

<!-- 2-3 sentences: what exists today in the area this epic/module will change.
     Produced during the DOCUMENT stage. Maps existing infrastructure before
     any design or implementation. -->

## Key Insights

<!-- Top findings from the infrastructure survey. What's strong, what's weak,
     what's surprising. -->

## Deep Analysis

### Existing Infrastructure

<!-- Complete mapping of what exists today.
     STYLING: > [!info] with inventory table:
     > | Component | Count | Location | Quality |
     > |-----------|-------|----------|---------|
     Verify every referenced file/component actually exists. -->

<!--
EXAMPLE:

> [!info] Post-Chain Components (verified 2026-04-13)
>
> | Component | File | Lines | Purpose | Dependencies |
> |-----------|------|-------|---------|--------------|
> | Post-chain runner | tools/pipeline.py | 142–198 | Orchestrates 6-step validation chain | tools/validate.py, tools/lint.py |
> | Schema validator | tools/validate.py | 1–87 | Checks frontmatter fields exist and are non-empty | wiki/config/wiki-schema.yaml |
> | Lint runner | tools/lint.py | 1–210 | 14 health checks across all pages | tools/manifest.py |
> | Manifest builder | tools/manifest.py | 1–156 | Regenerates wiki/manifest.json from page frontmatter | All wiki/ .md files |
> | Wiki schema | wiki/config/wiki-schema.yaml | 1–94 | Defines required fields, type enums, status enums | Read by tools/validate.py |
> | Obsidian sync step | tools/pipeline.py | 201–218 | Writes Obsidian-compatible link index | tools/manifest.py |

All 6 components exist and are callable. tools/validate.py is invoked independently
but NOT wired into the post-chain at pipeline.py:142–198 — that call is missing (see Gap Analysis).
-->


### How It Works Today

<!-- Data flow, dependencies, integration points.
     How the existing components interact.
     Include file:line references where applicable. -->

### What Works Well

<!-- Strengths of the current system. Evidence-backed. -->

### What's Weak

<!-- Problems, limitations, technical debt.
     STYLING: > [!warning] for critical weaknesses. -->

## Open Questions

<!-- Questions about the existing infrastructure that need answers. -->

## Relationships

- FEEDS INTO: {{gap_analysis_title}}
- FEEDS INTO: {{requirements_spec_title}}
