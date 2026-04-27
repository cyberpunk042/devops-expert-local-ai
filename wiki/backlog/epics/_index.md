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
| 84 skills audit against Extension Standards | Stage 3 | planned | Surfaced from Extension Standards review |
| Empirical routing split measurement (Stage 3 hardware) | Stage 3 | planned | Open question on Local AI model in second brain |
| Cluster peering (Alpha ↔ Bravo) | Stage 4 | planned | LocalAI cluster topology from CLAUDE.md |
| MCP tool surface Phase 2b — hard removal | next milestone | planned | `wiki/decisions/00_inbox/aicp-mcp-tool-surface-audit-2026-04-19.md` (Phase 2a soft-deprecation done 2026-04-25) |

## Completed

| Epic | Completed | Evidence |
|------|-----------|----------|
| AGENTS.md creation (cross-tool universal layer) | 2026-04 | [AGENTS.md](../../../AGENTS.md) (162 lines, gold-standard split with [CLAUDE.md](../../../CLAUDE.md) + [TOOLS.md](../../../TOOLS.md)) |
| CLAUDE.md slim (gold-standard routing pattern) | 2026-04-25 | 307→184 lines; details extracted to [docs/architecture/](../../../docs/architecture/) (7 files, full data preserved with cross-references) |
| backend-ai-platform-python domain profile | 2026-04 | [wiki/config/domain-profiles/backend-ai-platform-python.yaml](../../config/domain-profiles/backend-ai-platform-python.yaml) |
| MCP tool surface Phase 2a — soft deprecation | 2026-04-25 | 21 of 22 migration-target tools annotated with stderr deprecation pointing at CLI/skill replacements; verified in `aicp/mcp/server.py` |
