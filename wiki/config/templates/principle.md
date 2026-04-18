---
title: "Principle: {{title}}"
type: principle
domain: cross-domain
layer: 5
status: synthesized
confidence: medium
maturity: seed
derived_from:
  - "{{lesson_1}}"
  - "{{lesson_2}}"
  - "{{lesson_3}}"
created: {{date}}
updated: {{date}}
sources: []
tags: [principle]
---

# Principle: {{title}}

<!-- A PRINCIPLE is distilled from multiple VALIDATED LESSONS.
     A lesson says "we learned X from incident Y."
     A principle says "ALWAYS do X because the mechanism is Z, and here are N lessons that prove it."
     
     Promotion criteria: ≥3 validated lessons converge on the same mechanism.
     Principles are the highest knowledge layer — they govern behavior across all contexts. -->

## Summary

<!-- 1-2 sentences: the principle as an actionable rule.
     A reader should be able to FOLLOW this principle from the summary alone.
     
     EXAMPLE: "For any process rule that can be checked at the tool-call level,
     infrastructure enforcement (hooks, commands, harness, immune system) achieves
     categorically higher compliance than instruction-based enforcement (CLAUDE.md
     rules, skill text, prompts). This is not a marginal improvement — it is a
     categorical shift proven independently across three systems with quantified data."
     
     EXAMPLE: "No single methodology fits all projects — the right process depends on
     the project's identity (type, scale, phase, domain, execution mode). A POC with
     one developer needs a different SDLC profile than a production fleet with 12 agents.
     The Goldilocks Framework provides the selection mechanism." -->

## Statement

<!-- The principle stated formally. One sentence. Unambiguous.
     STYLING: > [!tip] for the principle statement.
     
     GOOD: "Infrastructure enforcement achieves categorically higher compliance than instruction-based enforcement for any process rule that can be checked at the tool-call level."
     BAD: "Infrastructure is better than instructions." (no mechanism, no scope) -->

> [!tip] The Principle
>
> {{formal statement with mechanism and scope}}

<!-- EXAMPLE (Infrastructure Over Instructions):
     > [!tip] The Principle
     >
     > **Any process rule that can be expressed as "allow or block this tool call
     > based on the current stage/state" MUST be enforced through infrastructure
     > (hooks, commands, harness), not through instructions (CLAUDE.md, skills,
     > prompts).** Instructions achieve ~25% compliance for stage boundaries.
     > Infrastructure achieves 100%. The mechanism: instructions compete with the
     > agent's objective function (complete the task); infrastructure removes the
     > competition by making violation physically impossible. However, enforcement
     > must be MINDFUL — every block must explain why, and every system must offer
     > justified bypass.
     
     EXAMPLE (Goldilocks Imperative):
     > [!tip] The Principle
     >
     > **The right methodology for a project is determined by its identity profile
     > (type, scale, phase, domain, execution mode), not by a one-size-fits-all
     > prescription.** A solo-developer POC uses a simplified profile with 3 stages.
     > A production fleet uses the full profile with 5 stages, enforcement hooks, and
     > immune system. The mechanism: under-process creates chaos; over-process
     > creates paralysis. The Goldilocks Framework finds the zone between them. -->

## Derived From

<!-- The lessons that converge to prove this principle.
     MINIMUM 3 validated lessons, each providing independent evidence.
     STYLING: Table with lesson → what it contributes to the principle. -->

> [!abstract] Evidence Chain
>
> | Lesson | What It Contributes |
> |--------|-------------------|
> | [[{{lesson_1}}]] | {{specific evidence from this lesson}} |
> | [[{{lesson_2}}]] | {{specific evidence from this lesson}} |
> | [[{{lesson_3}}]] | {{specific evidence from this lesson}} |

<!-- EXAMPLE (from Infrastructure Over Instructions):
     > [!abstract] Evidence Chain — 5 Converging Lessons
     >
     > | Lesson | What It Contributes |
     > |--------|-------------------|
     > | [[Infrastructure Enforcement Proves Instructions Fail]] | **The quantified proof.** OpenArms v4-v8: 28 CLAUDE.md rules, 75% violations. v9-v10: 4 hooks (215 lines), 0% violations. |
     > | [[Harness Ownership Converges Independently Across Projects]] | **Independent convergence.** Three systems discovered this principle independently. Convergence = structural, not preferential. |
     > | [[Agent Failure Taxonomy — Seven Classes]] | **The boundary.** Infrastructure solves PROCESS failures (stage violations). Behavioral failures (7 classes, 80% rate) persist. The principle has a scope. |
     > | [[Context Compaction Is a Reset Event]] | **Why instructions fail specifically.** After compaction, instruction-based corrections are lost. Infrastructure survives because it reads state from files, not context. |
     > | [[Enforcement Must Be Mindful]] | **The constraint.** Blind enforcement creates its own failures. The principle requires mindful implementation: explain why, offer bypass, log overrides. | -->

## Application

<!-- How to apply this principle in practice.
     STYLING: Table mapping contexts to application.
     Include: which identity profiles benefit, which SDLC profiles, which PM levels. -->

> [!abstract] Application by Context
>
> | Context | How to Apply |
> |---------|-------------|
> | {{context_1}} | {{how}} |
> | {{context_2}} | {{how}} |

<!-- EXAMPLE (from Infrastructure Over Instructions):
     > [!abstract] Application by Context (Goldilocks)
     >
     > | Identity Profile | How to Apply This Principle |
     > |-----------------|---------------------------|
     > | **Solo agent, POC, L1** | Add 4 hooks (pre-bash, pre-write, post-write, post-compact). ~215 lines. 1 day. |
     > | **Solo agent, MVP+, L2** | Add harness-owned loop + commands. Agent never touches git or frontmatter. |
     > | **Fleet, Production, L2-L3** | MCP tool blocking per stage. Immune system (30s doctor cycle). Contribution gating. |
     > | **Sub-agents** | Accept non-compliance (33% rate). Verify output instead of constraining input. | -->

## Boundaries

<!-- Where this principle does NOT apply. What breaks it.
     A principle without boundaries is a dogma.
     STYLING: > [!warning] for the boundary conditions. -->

> [!warning] Boundaries
>
> - {{condition where this principle doesn't apply}}
> - {{what would change the principle if discovered}}

<!-- EXAMPLE (from Infrastructure Over Instructions):
     > [!warning] Where This Principle Does NOT Apply
     >
     > - **Judgment-level quality** — Infrastructure can check "did the agent write
     >   to src/ during document stage?" (boolean). It CANNOT check "is this
     >   requirements spec good enough?" (judgment).
     > - **Exploratory/research work** — Hard blocks constrain exploration. Research
     >   model should have fewer hooks, not more.
     > - **Human-supervised interactive sessions** — The human IS the infrastructure.
     >   Adding hooks between human and agent adds latency without safety.
     > - **Over-enforcement threshold** — When >10% of legitimate actions are blocked.
     >   The Goldilocks principle: enough enforcement to prevent violations, not so
     >   much that correct work is blocked. -->

## How This Connects — Navigate From Here

> [!abstract] From This Principle → Related Knowledge
>
> | Direction | Go To |
> |-----------|-------|
> | **Lessons that prove this** | See Derived From above |
> | **Patterns that implement this** | {{related patterns}} |
> | **Models that embed this** | {{which models use this principle}} |
> | **Goldilocks application** | [[Project Self-Identification Protocol — The Goldilocks Framework]] |

## Relationships

- DERIVED FROM: [[{{lesson_1}}]]
- DERIVED FROM: [[{{lesson_2}}]]
- DERIVED FROM: [[{{lesson_3}}]]
