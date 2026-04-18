---
title: "Evolution: {{concept}}"
type: evolution
domain: {{domain}}
layer: spine
status: synthesized
confidence: medium
maturity: seed
created: {{date}}
updated: {{date}}
sources: []
tags: [evolution]
---

# Evolution: {{concept}}

## Summary

<!-- What evolved, through how many phases, and where it stands now.
     2-3 sentences covering the arc: from WHAT → through WHAT → to WHAT.
     Include the timespan and number of major versions/phases.
     
     EXAMPLE: "How the methodology system evolved from prose instructions to
     infrastructure-enforced stage gates. Tracks the journey from OpenArms v1
     (manual rules) through v9 (14 enforcement scripts + 4 hooks) and the
     research wiki's formalization into a portable methodology engine with artifact
     chains, domain profiles, and structural compliance patterns."
     
     EXAMPLE: "How the wiki's page schema evolved from a flat type list (5 types)
     to a layered knowledge architecture (17 types across 6 maturity-managed
     folders). Three phases over 12 days, driven by the need to distinguish
     constraining documents from explanatory documentation." -->

## Timeline

<!-- Chronological entries. EVERY entry must show SIGNIFICANCE, not just what happened.
     Format: **YYYY-MM-DD** — Event (significance: why this mattered)
     
     GOOD: "**2026-04-08** — Infrastructure enforcement hooks deployed (significance: violations dropped from 75% to 0% — first proof that instructions fail but infrastructure works)"
     BAD: "**2026-04-08** — Added hooks"
     
     MINIMUM: 5 dated entries with significance annotations.
     STYLING: Use > [!abstract] callout for the timeline to make it scannable. -->

> [!abstract] Evolution Timeline
>
> | Date | Event | Significance |
> |------|-------|-------------|
> | {{date}} | {{event}} | {{why this mattered}} |
> | {{date}} | {{event}} | {{why this mattered}} |

<!-- EXAMPLE (from Methodology Evolution):
     > [!abstract] Evolution Timeline
     >
     > | Date | Event | Significance |
     > |------|-------|-------------|
     > | 2026-04-01 | OpenArms v1: First CLAUDE.md with stage gate prose | Proof that the concept works even if enforcement doesn't |
     > | 2026-04-04 | OpenArms v2-v4: Iterative instruction refinement. ALLOWED/FORBIDDEN wording added. Violation rate ~75% | Proved instruction-based enforcement has a ceiling |
     > | 2026-04-08 | Research Wiki created. Methodology documented as reusable knowledge | Shift from project-specific config to portable knowledge |
     > | 2026-04-10 | Overnight run analysis: 75% stage boundary violations measured empirically | The tipping point — evidence that instruction-based enforcement doesn't work |
     > | 2026-04-10 | OpenArms v8-v9: 14 CJS scripts, 4 hooks, 3 commands. Harness owns git | Infrastructure enforcement achieves ~90% compliance |
     > | 2026-04-11 | Artifact Type System complete. 17 types, 9 model chains, 3 domain profiles | Generalized from project-specific to portable methodology engine | -->

## Key Shifts

<!-- Turning points that changed DIRECTION or UNDERSTANDING. Not incremental improvements.
     MINIMUM: 2 key shifts.
     
     Each shift: what was believed BEFORE → what evidence appeared → what changed AFTER.
     STYLING: > [!warning] for shifts that corrected dangerous assumptions.
     > [!tip] for shifts that unlocked new capabilities. -->

> [!warning] Shift 1: {{title}}
>
> **Before:** {{what was believed or practiced}}
> **Evidence:** {{what happened that challenged the assumption}}
> **After:** {{what changed as a result}}

> [!tip] Shift 2: {{title}}
>
> **Before:** {{previous state}}
> **Evidence:** {{what proved the shift was needed}}
> **After:** {{new state}}

<!-- EXAMPLE (from Methodology Evolution):
     > [!warning] Shift 1: Instructions to Infrastructure
     >
     > **Before:** Believed detailed CLAUDE.md instructions with ALLOWED/FORBIDDEN
     > tables would achieve compliance. 28 rules written across v1-v4.
     > **Evidence:** Overnight run analysis showed 75% stage boundary violations.
     > Agents violate scaffold-to-implement boundary most frequently (business logic
     > in scaffold files).
     > **After:** Moved enforcement from instructions to infrastructure. 4 hooks
     > (215 lines) achieved 0% violation rate. Same rules, different mechanism.
     
     > [!tip] Shift 2: Project-specific to Portable
     >
     > **Before:** OpenArms methodology.yaml was hardcoded to TypeScript/pnpm.
     > **Evidence:** Research wiki needed the same stage-gate system but for
     > Python/wiki tools. Copy-pasting would create drift.
     > **After:** Generalized into domain-agnostic models with domain profiles as
     > the customization layer. Any project can consume the base methodology. -->

## Current State

<!-- Where this concept/system stands TODAY. Honest assessment.
     Include: what works, what doesn't, what's next.
     Reference specific metrics or evidence — not claims.
     STYLING: > [!info] for the state summary table. -->

> [!info] Current State Assessment
>
> | Aspect | State | Evidence |
> |--------|-------|---------|
> | {{aspect}} | {{state}} | {{evidence}} |

<!-- EXAMPLE (from Methodology Evolution):
     > [!info] Current State Assessment
     >
     > | Aspect | State | Evidence |
     > |--------|-------|---------|
     > | Model completeness | v1.0 — first complete version | 9 named models with full artifact chains |
     > | Domain coverage | 3 profiles | TypeScript, Python/wiki, Infrastructure |
     > | Template coverage | 17 page types | All with styling directives, not yet all with inline examples |
     > | Enforcement | Documented, not yet universal | 4 hook patterns documented; only OpenArms has live hooks |
     > | Adoption | Self-consuming | Research wiki uses its own methodology; no external consumers yet | -->

## Next Frontiers

<!-- What evolution is expected or needed next.
     Each frontier: what problem it would solve + what evidence suggests it's needed. -->

## Relationships

- RELATES TO: {{related_model_or_system}}
- BUILDS ON: {{foundation_page}}
