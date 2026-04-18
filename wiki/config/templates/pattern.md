---
title: "{{title}}"
type: pattern
domain: cross-domain
layer: 5
status: synthesized
confidence: medium
maturity: seed
derived_from:
  - "{{derived_page_1}}"
  - "{{derived_page_2}}"
instances:
  - page: "{{instance_1}}"
    context: "{{how_instance_1_shows_this_pattern}}"
  - page: "{{instance_2}}"
    context: "{{how_instance_2_shows_this_pattern}}"
created: {{date}}
updated: {{date}}
sources: []
tags: []
---

# {{title}}

## Summary

<!-- 2-3 sentences: what recurs and why it matters -->

<!-- STYLING: After Summary, add a reference card if the pattern has named stages/components:
     > [!info] Pattern Reference Card
     > | Component | Role | ... |
-->

## Pattern Description

<!-- What is this pattern? How do you recognize it? Min 100 words.
     STYLING: If the pattern has a core tradeoff or constraint, use > [!warning].
     If there is a taxonomy (types, tiers, modes), use > [!abstract] with a table.

     EXAMPLE (replace with your content):
     "Progressive Distillation is the pattern where raw, unprocessed knowledge is refined
     through successive stages until it reaches actionable, high-confidence form. Each
     stage has a gatekeeping criterion (evidence count, cross-validation, peer review)
     that prevents premature promotion. The pattern recurs wherever information asymmetry
     exists and the cost of acting on low-confidence knowledge is high.

     Recognition signal: when you see a system with numbered maturity tiers and explicit
     promotion criteria, Progressive Distillation is operating. The key diagnostic is
     whether demotion is possible — a true instance allows downgrading when evidence weakens."

     ANTI-PATTERN: Do not describe a one-time technique as a pattern. A pattern recurs
     across contexts with the same essential structure. If you can only name one instance,
     you have a lesson, not a pattern. -->

## Instances

<!-- 2+ specific examples from the wiki. Reference pages directly.
     STYLING: Use > [!example]- foldable per instance for detailed breakdowns.
     A summary table at the top (instance | how it implements pattern) is ideal.

     EXAMPLE table (replace with your content):

     | Instance | Domain | How it implements this pattern |
     |----------|--------|-------------------------------|
     | [[LLM Wiki Knowledge Layers]] | knowledge | L0→L6 progression with evidence gates at L4 and L5 |
     | [[Stage-Gate Methodology]] | methodology | 5 stages (0→100% readiness) with ALLOWED/FORBIDDEN per stage |

     The table matters: it forces you to articulate the common structure across instances.
     If you can't fill the third column with a parallel statement, the instances don't
     share a pattern — they're just similar-looking things. -->

## When To Apply

<!-- Conditions that make this pattern appropriate.
     STYLING: > [!tip] for the positive cases.

     EXAMPLE (replace with your content):
     > [!tip] Apply Progressive Distillation when:
     > - Knowledge is arriving faster than it can be validated (backlog of raw material)
     > - Acting on unvalidated knowledge has measurable cost (wrong architectural decisions, rework)
     > - Multiple independent sources exist that can cross-validate each other
     > - The audience is varied (some need summaries, some need depth) -->

## When Not To

<!-- Anti-patterns, conditions where this fails or is counterproductive.
     STYLING: > [!warning] for the negative cases.

     EXAMPLE (replace with your content):
     > [!warning] Do NOT apply when:
     > - The knowledge domain is small and stable (overhead of stages exceeds benefit)
     > - All knowledge comes from a single source (no cross-validation possible — skip to L3 max)
     > - Speed is the primary constraint and acting on low-confidence data is acceptable
     >
     > The most common mistake: applying every layer to every piece of knowledge.
     > Operational runbooks don't need L6 distillation. Use judgment on what earns depth. -->

## Relationships

- DERIVED FROM: {{derived_page_1}}
- DERIVED FROM: {{derived_page_2}}
