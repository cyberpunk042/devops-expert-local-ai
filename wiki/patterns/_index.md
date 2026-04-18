---
title: Patterns (Layer 4-5)
type: index
domain: backend-ai-platform-python
status: active
confidence: high
created: 2026-04-17
updated: 2026-04-17
sources: []
tags: [knowledge, index, patterns, aicp]
---

# Patterns (Layer 4-5)

Patterns are reusable structural solutions. Each pattern requires ≥2 concrete instances with page references (per second brain's Knowledge Evolution Standards).

## Maturity Pipeline

| Stage | Folder |
|-------|--------|
| 0 | [00_inbox/](00_inbox/) |
| 1 | [01_drafts/](01_drafts/) |
| 2 | [02_reviewed/](02_reviewed/) |
| 3 | [03_validated/](03_validated/) |
| 4 | [04_principles/](04_principles/) |

## AICP Patterns (to be populated)

Candidate patterns AICP demonstrates — to author as deep-dives:
- **Autocomplete Web** — three-layer pipeline (static map + LightRAG graph + claude-mem) — already implemented in fleet
- **4-tier router with confidence scoring** — local → fleet → openrouter → claude with quality escalation
- **Single-active backend with LRU eviction** — GPU model swap on demand under VRAM constraint
- **Profile-as-coordination-bundle** — single switch coordinates backend + router + RAG + budget + cache + timeouts + Docker
