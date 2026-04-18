---
title: AICP Backlog
type: index
domain: backend-ai-platform-python
status: active
confidence: high
created: 2026-04-17
updated: 2026-04-17
sources: []
tags: [backlog, index, aicp]
---

# AICP Backlog

Hierarchical work tracking per the second brain's methodology framework.

## Hierarchy

| Level | Folder | Purpose |
|-------|--------|---------|
| Milestones | [milestones/](milestones/) | Multi-month strategic goals (Stage 3, Stage 4, Stage 5 of LocalAI Independence) |
| Epics | [epics/](epics/) | Multi-week initiatives within a milestone |
| Modules | [modules/](modules/) | Multi-day scoped deliverables within an epic |
| Tasks | [tasks/](tasks/) | Atomic work units (hours-to-days) |

## Stages (per task)

`document` → `design` → `scaffold` → `implement` → `test`

Readiness ranges (cumulative): 0-25 (document) → 25-50 (design) → 50-80 (scaffold) → 80-95 (implement) → 95-100 (test).

## Methodology

Defined in [../config/methodology.yaml](../config/methodology.yaml) — 9 chains, 5 stages, 8 execution modes, 5 end conditions. Baseline copied from second brain on 2026-04-17; AICP-specific adaptations (pytest gates, ruff lint, Docker stage commands) to follow.
