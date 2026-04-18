---
title: "{{title}}"
type: concept
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

<!-- 2-3 sentences: what this concept IS and why it matters.
     MIN 30 words. This is used as the LightRAG description — make it self-contained.
     
     EXAMPLE (replace with your content):
     "This concept defines how projects adapt their SDLC process based on context —
     project phase, codebase scale, and organizational needs. Three pre-built chains
     (simplified, default, full) cover the spectrum from POC exploration to production governance." -->

## Key Insights

<!-- 3-8 numbered insights. Each should be self-contained — if someone reads ONLY
     this section, they should be able to explain the concept to a colleague.
     STYLING: If an insight contains a comparison or taxonomy, use a table.
     If an insight is a critical constraint, wrap in > [!warning].
     
     EXAMPLE insights (replace with your content):

     EXAMPLE of a self-contained insight (notice: bold claim + specific mechanism + implication):
     "1. **Readiness and progress are orthogonal dimensions, not a single scale.**
     A task at 100% readiness / 0% progress is fully specified but unstarted — healthy.
     A task at 0% readiness / 50% progress is being built without a clear definition — a red flag.
     The two dimensions must be tracked separately because readiness gates progress: you should
     not start building (advance progress) until the task is defined (readiness ≥ threshold)."

     WHAT MAKES THIS GOOD: It's self-contained (no prior context needed), it has a specific
     mechanism (orthogonal dimensions, gating relationship), and it has a concrete implication
     (don't build without definition). Compare to BAD: "Readiness and progress are different
     things and both matter." True but not actionable — adds zero transferable knowledge. -->

1. **{{First insight as bold statement.}}** Explanation with specific data or mechanism. Not vague — name numbers, sources, or concrete examples.

2. **{{Second insight.}}** If comparing options, use a table:

> [!abstract] {{Comparison or taxonomy title}}
>
> | Dimension | Option A | Option B | Option C |
> |-----------|----------|----------|----------|
> | {{criterion}} | {{value}} | {{value}} | {{value}} |

3. **{{Third insight.}}** If this is a constraint or risk:

> [!warning] {{Constraint title}}
>
> {{What can go wrong and why. Specific, not vague.}}

## Deep Analysis

<!-- MIN 100 words. Break into subsections (### headings) — never one long essay.
     Each subsection defines a concrete mechanism, pattern, or dimension.
     STYLING: Use > [!info] for reference data (tables, definitions).
     Use > [!abstract] for taxonomies or selection criteria.
     Use > [!warning] for constraints and failure modes.
     Use > [!example]- foldable for detailed worked examples. -->

### {{First Subsection — Name the Mechanism}}

<!-- Explain ONE specific mechanism, dimension, or component.
     Use tables for structured data. Use callouts for typed information.

     EXAMPLE subsection (replace with your content):

### The Three-Chain Model: Simplified, Default, Full

<!-- This subsection explains the taxonomy — three things to compare.
     The table makes the comparison scannable; the prose below explains the selection logic. -->

> [!info] SDLC Profile Comparison
>
> | Profile | Stages | Enforced gates | Best for |
> |---------|--------|----------------|---------|
> | simplified | document → implement → test | 2 (doc→impl, impl→test) | POC, solo, fast iteration |
> | default | document → design → scaffold → implement → test | 4 | Most projects, production-bound work |
> | full | adds milestone, review, and sign-off gates | 6+ | Regulated, team, high-risk |
>
> Selection criterion: use the simplest profile that catches the failure modes you've actually
> experienced. Defaulting to "full" adds ceremony without adding safety for small projects. -->

> [!info] {{Reference data title}}
>
> | {{Column 1}} | {{Column 2}} | {{Column 3}} |
> |-------------|-------------|-------------|
> | {{data}} | {{data}} | {{data}} |

### {{Second Subsection — Another Dimension}}

<!-- Each subsection should be independently valuable — a reader can
     jump to any subsection and understand it without reading the others.

     EXAMPLE: if your first subsection explained WHAT the mechanism is,
     the second subsection should explain HOW to select or apply it (decision logic),
     and the third should explain WHERE it fails (edge cases, constraints). -->

## Open Questions

<!-- Optional but encouraged. Specific, testable questions — not vague.
     Format: > [!question] Question text (Requires: what would answer it) -->

> [!question] {{Specific question about this concept}}
> {{What evidence or testing would answer it. Not "we need to think about this" but "measuring X would resolve this."}}

### How This Connects — Navigate From Here

> [!abstract] From This Page → Related Knowledge
>
> | Direction | Go To |
> |-----------|-------|
> | **What principle governs this?** | [[Principle: Right Process for Right Context — The Goldilocks Imperative]] |
> | **What is my identity?** | [[Project Self-Identification Protocol — The Goldilocks Framework]] |
> | **System map** | [[Methodology System Map]] |

## Relationships

- RELATES TO: {{related_page}}
