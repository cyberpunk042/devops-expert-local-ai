---
title: Decisions
type: index
domain: backend-ai-platform-python
status: active
created: 2026-04-17
updated: 2026-04-17
---

# Decisions (Layer 5-6)

Decisions document what was chosen and what was rejected. Each decision requires ≥2 alternatives with concrete rejection reasons (per second brain's Knowledge Evolution Standards).

## Maturity Pipeline

| Stage | Folder |
|-------|--------|
| 0 | [00_inbox/](00_inbox/) |
| 1 | [01_drafts/](01_drafts/) |
| 2 | [02_reviewed/](02_reviewed/) |
| 3 | [03_validated/](03_validated/) |
| 4 | [04_principles/](04_principles/) |

## AICP Decisions (to be populated)

Candidate decisions to formalize as ADRs:
- **LocalAI v4.1.3 over alternatives (Ollama, vLLM)** — OpenAI-compatible API, GPU via WSL2, single-active backend
- **4-tier router with profiles over hardcoded routing** — config-driven thresholds, failover chain configurable per profile
- **Qwen3-8B as main reasoning model** — thinking mode, 119 languages, native tool calling, 4.9GB / 6GB VRAM
- **Dual-GPU asymmetric KV cache** — RTX 2080 (8GB) + RTX 2080 Ti (11GB), 19GB total, unblocks Qwen3-30B-A3B MoE
- **Skills as primary extension pattern** — 78 skills in .claude/skills/ vs MCP-everywhere
- **Configuration profiles as named bundles** — coordinate backend + router + RAG + budget + Docker via single switch
