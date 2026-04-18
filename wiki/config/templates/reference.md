---
title: "{{title}}"
type: reference
domain: {{domain}}
status: synthesized
confidence: medium
maturity: seed
created: {{date}}
updated: {{date}}
sources: []
tags: []
---

# {{title}}

## Summary

<!-- 2-3 sentences: what this reference covers and who should use it.
     MIN 30 words. References are LOOKUP material — optimize for findability. -->

## Reference Content

<!-- The actual reference material. Structure depends on what's being referenced.
     Common patterns:
     - API reference: table with Function | Input | Output | Side effects
     - Configuration reference: table with Key | Type | Default | Description
     - Vocabulary reference: table with Term | Definition | Example
     - Checklist reference: numbered steps with validation criteria
     STYLING: Use > [!info] to wrap the main reference table.
     Use > [!tip] for usage guidance.
     Use > [!warning] for gotchas and common mistakes.

     EXAMPLE reference table with 3 rows (replace with your content):

     > [!info] Pipeline Post — Step Reference
     >
     > | Step | Command | What It Checks | Fails When |
     > |------|---------|---------------|-----------|
     > | 1. Index | auto | _index.md files current | Page in domain folder but missing from index |
     > | 2. Manifest | auto | manifest.json reflects all pages | New page not added to manifest |
     > | 3. Validate | tools.validate | YAML frontmatter schema | Required field missing or wrong type |
     >
     > **How to use this table:** When `pipeline post` fails, the step number in the error
     > output tells you which row to consult. The "Fails When" column tells you exactly
     > what to fix — no guesswork required.

     > [!warning] The most common mistake: running pipeline post from the wrong directory.
     > It must be run from the wiki root (where wiki/ and tools/ are siblings).
     > Running it from inside wiki/ causes all path resolutions to fail silently. -->

## Relationships

- RELATES TO: {{related_page}}
