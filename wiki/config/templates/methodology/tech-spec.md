---
title: "{{title}} — Tech Spec"
type: reference
domain: {{domain}}
status: synthesized
confidence: high
maturity: seed
created: {{date}}
updated: {{date}}
sources:
  - id: design-doc
    type: file
    file: "{{design_doc_path}}"
tags: [methodology, tech-spec, {{epic_tag}}]
---

# {{title}} — Tech Spec

## Summary

<!-- 2-3 sentences: what this spec defines and for whom.
     A tech spec is LOOKUP material — API tables, interface definitions,
     algorithm pseudocode. Produced during the DESIGN stage. -->

## Reference Content

### Component Specifications

<!-- Per component: responsibility, location, dependencies, consumers.
     STYLING: > [!info] per component with table:
     > | Attribute | Value |
     > |-----------|-------|
     > | Responsibility | ... |
     > | Location | ... |
     > | Dependencies | ... |
     > | Consumers | ... |
-->

<!--
EXAMPLE:

### Component: ValidationEngine

> [!info] ValidationEngine
>
> | Attribute | Value |
> |-----------|-------|
> | Responsibility | Validate a single wiki page's frontmatter against wiki-schema.yaml; return structured result |
> | Location | tools/validate.py — class ValidationEngine (new), extracted from existing validate_page() function |
> | Dependencies | wiki/config/wiki-schema.yaml (read once at init), PyYAML |
> | Consumers | tools/pipeline.py post-chain (step 3), tools/lint.py (quality checks), CLI `python3 -m tools.validate` |

**API:**

> [!info] API Reference — ValidationEngine
>
> | Method | Input | Output | Side Effects |
> |--------|-------|--------|--------------|
> | `__init__(schema_path)` | Path to wiki-schema.yaml | ValidationEngine instance | Loads and parses YAML schema once |
> | `validate_page(path)` | Path to .md file | `ValidationResult` | None (pure — no writes, no network) |
> | `validate_all(wiki_root)` | Path to wiki/ directory | `list[ValidationResult]` | None (pure) |

**ValidationResult contract:**
```python
@dataclass
class ValidationResult:
    path: Path
    ok: bool                     # True = no errors
    errors: list[FieldError]     # Empty list when ok=True
    warnings: list[FieldError]   # Non-blocking issues (deprecated fields, etc.)
```
-->


### API

<!-- Function/method reference table.
     > [!info] API Reference
     > | Function | Input | Output | Side Effects |
     > |----------|-------|--------|-------------|
-->

### Data Contracts

<!-- File formats, JSON/YAML structures, state file formats.
     Use code blocks with concrete examples, not placeholders. -->

### Algorithm

<!-- Pseudocode or step-by-step for key logic.
     Code blocks for pseudocode. Numbered steps for process. -->

### Error Handling

<!-- Error case → response mapping.
     > | Error Case | Response | Recovery |
     > |-----------|----------|----------|
-->

## Relationships

- IMPLEMENTS: {{design_doc_title}}
- PART OF: [[{{epic_title}}]]
