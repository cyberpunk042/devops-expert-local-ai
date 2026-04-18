---
title: "ADR-{{adr_number}}: {{title}}"
aliases:
  - "ADR-{{adr_number}}: {{title}}"
  - "{{title}}"
type: decision
domain: {{domain}}
layer: 6
status: proposed
confidence: medium
maturity: seed
methodology_doc_type: ADR
derived_from:
  - "{{derived_page_1}}"
reversibility: moderate
created: {{date}}
updated: {{date}}
sources: []
tags: [adr, architecture-decision, methodology-doc]
---

# ADR-{{adr_number}}: {{title}}

<!-- Architecture Decision Record — a FORMAL structural variant of a decision page.
     Produced during methodology's DESIGN stage. Uses type: decision but follows
     the classic ADR section structure (Context / Decision / Consequences).
     Maps to methodology's design-plan or tech-spec artifacts.

     Use an ADR when:
     - Decision affects system architecture (not just implementation detail)
     - You need durable provenance (future engineers ask WHY this was chosen)
     - Decision is HARD to reverse (infrastructure, data model, protocol)

     Use a plain decision page when:
     - Decision is operational or policy (not architectural)
     - Reversibility is easy (swap implementation without migration)

     Status progression: proposed → accepted → deprecated → superseded -->

## Status

<!-- One of: proposed, accepted, deprecated, superseded
     If superseded, add: "Superseded by ADR-XXX: <title>"
     EXAMPLE:
     **proposed** — awaiting review and acceptance -->

**{{status}}**

## Context

<!-- The forces at play. What problem needs solving? What constraints apply?
     Min 100 words. State the situation factually before proposing a choice.

     EXAMPLE: "The wiki has 300+ pages and grows weekly. Manual maintenance
     of the manifest.json (page catalog) is infeasible at this scale.
     Automation is required. Two approaches were evaluated:
     (a) regenerate manifest on every commit via pre-commit hook, (b)
     regenerate via scheduled pipeline post. The trade-off is latency
     (hook = immediate but blocks commit) vs. reliability (scheduled =
     may lag but doesn't break commit flow). Scale expected to 1000+
     pages within 6 months. Current CI runs ~30s; adding manifest
     regeneration would double this." -->

## Decision

<!-- What was decided. Clear imperative statement.
     STYLING: Wrap the decision statement in a > [!success] callout.

     EXAMPLE:
     > [!success] We will regenerate the manifest via `pipeline post`
     > (scheduled, not pre-commit).
     >
     > This decouples manifest freshness from commit latency. Pipeline
     > post runs after every wiki change and before any push. The
     > manifest is always fresh before external consumption. -->

## Consequences

<!-- What happens as a result. Both positive and negative.
     STYLING: Use two tables — Benefits and Costs.

     EXAMPLE:
     ### Benefits
     | Benefit | Impact |
     |---------|--------|
     | Commits stay fast | No pre-commit regeneration |
     | Single validation chain | pipeline post is the one gate |
     | Easy to trigger manually | `python3 -m tools.pipeline post` |

     ### Costs
     | Cost | Impact |
     |------|--------|
     | Manifest may lag intra-commit | Mitigated by running post before push |
     | Requires discipline | Easy to skip post locally |
     | No CI enforcement yet | Planned: GitHub Action runs pipeline post on PR |
     -->

## Alternatives Considered

<!-- What else was on the table. Min 2 alternatives with rejection rationale.
     STYLING: Each alternative as a subsection with > [!warning] for rejection.

     EXAMPLE:
     ### Alternative 1: Pre-commit hook regeneration
     Run `pipeline post` as a pre-commit hook. Manifest always current at commit.
     > [!warning] Rejected: doubles commit latency for every change. At current
     > 30s post time, every wiki commit would block for 1 minute. Friction
     > outweighs benefit — most commits don't need immediate manifest refresh.

     ### Alternative 2: Manifest-on-read
     Regenerate manifest lazily when first read per session.
     > [!warning] Rejected: incompatible with cross-tool consumers (gateway,
     > MCP server, Obsidian). Manifest is read by many tools, not just one. -->

## Reversibility

<!-- How hard to reverse this decision.
     State: easy / moderate / hard. Explain what would be required to reverse.

     EXAMPLE: "Moderate. Switching to pre-commit regeneration is a 5-line
     change in .git/hooks/pre-commit. No data migration, no schema change.
     The decision is reversible at any time if friction proves acceptable." -->

## Related ADRs

<!-- Other ADRs this depends on or supersedes.
     Format:
     - Depends on: ADR-XXX (brief reason)
     - Supersedes: ADR-YYY (brief reason)
     - Related to: ADR-ZZZ (non-binding relationship)
     -->

## Relationships

- DERIVED FROM: {{derived_page_1}}
