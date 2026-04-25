---
title: Epics
type: index
domain: backend-ai-platform-python
status: active
confidence: high
created: 2026-04-17
updated: 2026-04-17
sources: []
tags: [backlog, index, epics, aicp]
---

# Epics

Multi-week initiatives. Each epic belongs to a milestone and contains modules and tasks.

## Active

| Epic | Milestone | Status | Source |
|------|-----------|--------|--------|
| **E011 — Routing Integration (K2.6 + Local Stack)** | Post-Anthropic Self-Autonomous Stack | **P0 active** (brain-assigned 2026-04-22, target 2026-04-27) | Brain authoritative at `~/devops-solutions-research-wiki/wiki/backlog/epics/pre-milestone/E011-routing-integration-aicp-tiers.md` — 5 modules, 15-20 tasks |

E011 modules (detail in brain):

| Module | Delivers |
|--------|----------|
| E011-m001 | AICP config: 7-tier stack with K2.6-cheap-online primary agentic |
| E011-m002 | K2.6 OpenRouter backend adapter (`aicp/backends/`) |
| E011-m003 | K2.6 local backend adapter (llama.cpp + Unsloth Q2 GGUF, sovereignty-fallback) |
| E011-m004 | Per-backend circuit breakers + fallback chain doc |
| E011-m005 | Routing-split metric + weekly review ritual |

Related brain epics (NOT AICP-owned but AICP depends on):

| Epic | Owner | Why AICP cares |
|------|-------|----------------|
| E007 — OpenRouter deadline de-risk | brain/operator | E011-m002 requires OpenRouter K2.6 route working |
| E008 — Local K2.6 offline frontier tier | brain/operator | E011-m003 delivered via llama.cpp + Unsloth Q2 GGUF (KTransformers/sglang+kt-kernel path rejected on consumer hardware — see `docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md`) |
| E010 — Storage and hardware enablement | operator | 64GB RAM + /dev/sdd mount required for E011-m003 |

## Planned

| Epic | Milestone | Status | Source |
|------|-----------|--------|--------|
| Second Brain Adoption (8-step + 4 epics) | Stage 3 | in-progress | Adoption plan started 2026-04-17 |
| CLAUDE.md slim (660→<200 lines) | Stage 3 | planned | Surfaced from Claude Code Standards review |
| 78 skills audit against Extension Standards | Stage 3 | planned | Surfaced from Extension Standards review |
| AGENTS.md creation (cross-tool universal layer) | Stage 3 | planned | Surfaced from Claude Code Standards review |
| backend-ai-platform-python domain profile | Stage 3 | planned | Surfaced from Methodology Standards review |
| Empirical routing split measurement (Stage 3 hardware) | Stage 3 | planned | Open question on Local AI model in second brain |
| Cluster peering (Alpha ↔ Bravo) | Stage 4 | planned | LocalAI cluster topology from CLAUDE.md |
