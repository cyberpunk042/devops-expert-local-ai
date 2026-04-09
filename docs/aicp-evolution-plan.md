# AICP Evolution Plan

**Date:** 2026-04-03 (updated 2026-04-08)
**Status:** Partially implemented — see DONE markers below
**Scope:** Everything AICP needs to evolve — models, router, backends, knowledge map, infrastructure, quality

---

## Evolution Areas

### Area 1: Model Upgrades (No Qwen, No Next-Gen Models)

Current models are 2024-era. Better models exist that fit our 8GB VRAM.

| What | Current | Target | Why |
|------|---------|--------|-----|
| Main reasoning model | hermes 7B (Mistral) | **Qwen3-8B** (~5-6GB VRAM) | 2.5x better than hermes-3b, fits 8GB |
| Lightweight model | hermes-3b (Llama 3.2 3B) | **Qwen3.5-9B** or keep 3B | Beats models 13x its size |
| Code model | codellama 7B | **Qwen3-8B** (code-capable) or **Phi-4** 14B | Phi-4 beats GPT-4o-mini on code/math |
| Future dual-GPU | N/A | **Qwen3-30B-A3B** (MoE, 19GB) | 30B total / 3B active, needs 2nd GPU |
| Embedding model | nomic-embed | Evaluate newer options | May improve RAG quality |

**Milestones:**

- **E-M01**: ~~Qwen3-8B model YAML config + GGUF download + benchmark vs hermes~~ **DONE** — qwen3-8b is the current main model
- **E-M02**: Qwen3.5-9B evaluation (if it fits 8GB VRAM as fleet lightweight) — superseded by Qwen3-4B + Gemma 4 E2B
- **E-M03**: Phi-4 evaluation for code tasks (14B — may need quantization)
- **E-M04**: ~~Model benchmark pipeline~~ **DONE** — `make benchmark-qwen3` implemented
- **E-M05**: ~~Update `config/default.yaml` and router to use new best models~~ **DONE** — default profile uses qwen3-8b, 9 profiles available
- **E-M06**: Embedding model evaluation (nomic-embed vs newer alternatives)

---

### Area 2: Router Evolution (Too Simplistic)

`aicp/core/router.py` is regex keyword matching. No intelligence.

| What | Current | Target |
|------|---------|--------|
| Classification | Regex keywords | Confidence scoring + prompt analysis |
| Backend ranking | Binary (local or claude) | Ranked list with fallback chain |
| Cost awareness | None | $/token tracking, cost-optimal routing |
| Quality feedback | None | Response quality scoring → learn what LocalAI handles well |
| Model selection | Hardcoded per-type | Dynamic based on task + model capabilities |

**Milestones:**

- **E-M07**: ~~Confidence-scored routing~~ **DONE** — router.py has 10+ dimension scoring
- **E-M08**: ~~Cost-aware routing~~ **DONE** — $/token tracking per backend in router
- **E-M09**: ~~Quality feedback loop~~ **DONE** — quality scoring + auto-escalation in controller
- **E-M10**: ~~Dynamic model selection~~ **DONE** — recommend_model() picks by task type
- **E-M11**: ~~Prompt complexity analyzer~~ **DONE** — multi-dimension complexity scoring

---

### Area 3: OpenRouter as 3rd Backend

200+ models, 29 free. Zero-cost middle tier between LocalAI and Claude.

```
Task → Router
  ├── Direct/MCP (no LLM)        → $0
  ├── LocalAI (if available)      → $0, local
  ├── OpenRouter free (if avail)  → $0, cloud
  ├── OpenRouter paid             → $, cloud
  └── Claude                      → $$$, cloud
```

**Milestones:**

- **E-M12**: OpenRouter backend implementation (`aicp/backends/openrouter.py`)
- **E-M13**: OpenRouter model catalog + free tier discovery
- **E-M14**: Router updated to 4-tier ranking (local → free cloud → paid cloud → Claude)
- **E-M15**: Failover chain: LocalAI → OpenRouter free → OpenRouter paid → Claude
- **E-M16**: Config schema updated (`config/default.yaml` + `backends.openrouter`)

---

### Area 4: Claw Code Parity Investigation

From `group-03-claw-code-parity-knowledge-map.md`: Claude Code has 184 tools,
207 commands. We have 33 built-in + 29 fleet MCP. 122 tools unaccounted for.

| Area | Claude Code | AICP | Gap |
|------|-------------|------|-----|
| Tools | 184 | 62 (33+29) | 122 unclassified |
| Commands | 207 | 50+ | ~157 unclassified |
| Hooks | PreToolUse/PostToolUse | 26 hook types | AICP has MORE |
| Skills | SKILL.md loading | 85 skills | AICP has MORE |
| Sessions | JSONL persistence | JSON sessions | Different model |

**Milestones:**

- **E-M17**: Extract full 184-tool list from claw-code-parity surface snapshots
- **E-M18**: Classify 122 missing tools (internal/UI vs capabilities we need)
- **E-M19**: Identify tools that AICP's router should handle or agents should know
- **E-M20**: Extract 207-command list, classify relevance
- **E-M21**: Gap analysis document — what's worth building vs what's Claude-internal

---

### Area 5: Fleet Knowledge Map Architecture

The foundational metadata/map system for ALL fleet knowledge. Adaptive injection
based on model context window. This is ~50+ milestones on its own.

**The tree:**
```
Fleet Knowledge Map (root)
├── SYSTEM MANUALS (22 systems) — full/condensed/minimal versions
├── AGENT MANUALS (10 agents) — role-specific knowledge
├── MODULE MANUALS (94 modules) — code documentation
├── TOOL MANUALS (62+ tools) — usage chains
├── SKILL MANUALS (85+ skills) — invocation guides
├── PLUGIN MANUALS — evaluated plugins
├── COMMAND MANUALS (50+ commands)
├── STANDARDS MANUAL (8 standards + 13 artifact types)
├── METHODOLOGY MANUAL — per-stage instructions
└── RAG INDEX (the navigator)
    ├── cross-references.yaml
    ├── intent-map.yaml
    └── injection-profiles/
        ├── opus-1m.yaml      (full detail)
        ├── sonnet-200k.yaml  (condensed)
        ├── localai-8k.yaml   (minimal for cheap models)
        └── heartbeat.yaml    (just enough for idle check)
```

**Key innovation:** Same agent, same task, different model = different injection depth.

**Milestones (phase 1 — foundation):**

- **E-M22**: Map metadata schema (`_map.yaml` format definition)
- **E-M23**: Injection profile schema (opus/sonnet/localai/heartbeat)
- **E-M24**: Intent-map rules (situation → what to inject)
- **E-M25**: System manuals — condensed + minimal versions of 22 existing docs
- **E-M26**: Agent manuals — 10 agent specs in full/condensed/minimal
- **E-M27**: Tool manuals — 62+ tools documented with chains

**Milestones (phase 2 — integration):**

- **E-M28**: Navigator module — brain reads map, selects content, assembles chain
- **E-M29**: Integration with `autocomplete.py` (map-driven, not hardcoded)
- **E-M30**: Integration with `preembed.py` (map-driven injection)
- **E-M31**: Integration with `context_writer.py` (profile-based assembly)
- **E-M32**: Integration with LightRAG (map = structured index)
- **E-M33**: Integration with `session_manager.py` (map decides what to keep/dump)

**Milestones (phase 3 — validation):**

- **E-M34**: Test with real agents — verify right content reaches agents
- **E-M35**: LocalAI 8K injection testing — minimal profile works with cheap models
- **E-M36**: Cross-session knowledge — map + claude-mem + memory working together

---

### Area 6: RAG / LightRAG Evolution

RAG is `enabled: false` by default. Not wired to fleet. No LightRAG.

| What | Current | Target |
|------|---------|--------|
| RAG state | Disabled, SQLite vector store | Enabled, production-ready |
| Embedding | nomic-embed (CPU) | Evaluate + upgrade |
| Reranking | bge-reranker (CPU) | Wired + tested |
| LightRAG | Not integrated | Map-driven semantic search |
| Fleet connection | None | Agents query AICP RAG via MCP |
| Auto-indexing | None | Project files auto-indexed on change |

**Milestones:**

- **E-M37**: Enable RAG by default, test with real project data
- **E-M38**: Auto-indexing pipeline (watch project files → re-embed on change)
- **E-M39**: LightRAG integration with knowledge map
- **E-M40**: Fleet RAG bridge — agents query AICP RAG via MCP server
- **E-M41**: Embedding model upgrade evaluation

---

### Area 7: Infrastructure Evolution

Docker, observability, multi-machine.

| What | Current | Target |
|------|---------|--------|
| Docker health check | None in compose | Proper healthcheck directive |
| Resource limits | None | Memory + CPU caps per container |
| Prometheus | LocalAI exposes /metrics, AICP doesn't scrape | Full pipeline |
| Grafana | None | Dashboards for inference latency, VRAM, token usage |
| Alerting | None | Model stuck, VRAM full, inference slow |
| Cluster peering | Code exists, not tested | Two LocalAI instances load-balancing |
| Agent auto-discovery | Manual IPs | mDNS/Avahi zero-config |

**Milestones:**

- **E-M42**: Docker compose healthcheck + resource limits
- **E-M43**: AICP Prometheus `/metrics` endpoint
- **E-M44**: Grafana dashboard stack (docker-compose addition)
- **E-M45**: Alerting rules (stuck model, high latency, VRAM pressure)
- **E-M46**: Cluster peering tested between two machines
- **E-M47**: Agent auto-discovery via mDNS/Avahi

---

### Area 8: Quality & Escalation Logic

Controller has failover but no quality assessment.

| What | Current | Target |
|------|---------|--------|
| Response quality | No assessment | Score responses (coherence, completeness) |
| Auto-escalation | Only on error | LocalAI garbage → auto-retry with Claude |
| Response caching | None | Same prompt = cached answer, skip inference |
| Token budget at router | None | Enforce budget before routing |
| Warm pool | None | Keep frequent models loaded, track cold-start cost |

**Milestones:**

- **E-M48**: Response quality scorer (heuristic: length, structure, relevance)
- **E-M49**: Auto-escalation on low quality (not just errors)
- **E-M50**: Response cache layer (prompt hash → cached response, TTL)
- **E-M51**: Token budget enforcement at routing level
- **E-M52**: Warm pool management (track loaded models, minimize swaps)

---

## Dependency Graph

```
Area 1 (Models) ──────────────────────────────┐
  E-M01..06                                   │
                                              ▼
Area 2 (Router) ──► Area 3 (OpenRouter) ──► Area 8 (Quality)
  E-M07..11          E-M12..16               E-M48..52
                                              │
Area 4 (Claw Code Parity) ───────────────────►│
  E-M17..21                                   │
                                              ▼
Area 5 (Knowledge Map) ──► Area 6 (RAG) ──► PRODUCTION
  E-M22..36                 E-M37..41
                                              ▲
Area 7 (Infrastructure) ─────────────────────►│
  E-M42..47
```

**Critical path:** Models (Area 1) → Router (Area 2) → Quality (Area 8)
**Parallel track:** Knowledge Map (Area 5) + Claw Code (Area 4)
**Foundation:** Infrastructure (Area 7) can start anytime

---

## Priority Order

| Priority | Area | Why |
|----------|------|-----|
| **P0** | Area 1: Model Upgrades | Can't evolve without better models. Qwen first. |
| **P0** | Area 7: Infrastructure (healthcheck, limits) | Basic production hygiene |
| **P1** | Area 2: Router Evolution | Intelligence before adding more backends |
| **P1** | Area 4: Claw Code Parity | Understanding what we're missing informs everything |
| **P2** | Area 3: OpenRouter Backend | Free middle tier, but needs router first |
| **P2** | Area 5: Knowledge Map (phase 1) | Foundation for adaptive injection |
| **P2** | Area 8: Quality & Escalation | Needs router + models first |
| **P3** | Area 6: RAG / LightRAG | Needs knowledge map first |
| **P3** | Area 5: Knowledge Map (phases 2-3) | Integration + validation |
| **P3** | Area 7: Infrastructure (Grafana, peering) | Nice-to-have at scale |

---

## Total Milestone Count

| Area | Milestones |
|------|-----------|
| 1. Model Upgrades | 6 |
| 2. Router Evolution | 5 |
| 3. OpenRouter Backend | 5 |
| 4. Claw Code Parity | 5 |
| 5. Knowledge Map | 15 |
| 6. RAG / LightRAG | 5 |
| 7. Infrastructure | 6 |
| 8. Quality & Escalation | 5 |
| **Total** | **52** |

Plus ~50+ from Knowledge Map manual creation (per-system, per-agent, per-tool, per-skill docs).

**Grand total: ~100+ milestones to production.**
