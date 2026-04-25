# CLAUDE.md — AI Control Platform (AICP)

> **Read [AGENTS.md](AGENTS.md) first** — universal cross-tool context (hard rules, stage gates, methodology models, quality gates, commands, conventions, where to find things). This file is the **Claude Code-specific layer** plus the **gateway-parseable Identity Profile**.

## Project Overview

AICP is a personal AI control workspace that orchestrates local and cloud AI backends (LocalAI, Claude Code) through a unified controller. The user is always in control — AI backends are tools, not masters.

This is one of four projects in the fleet ecosystem:

| Project | Repo | Purpose |
|---------|------|---------|
| **AICP** | `devops-expert-local-ai` | AI Control Platform — backends, modes, guardrails, LocalAI independence |
| **Fleet** | `openfleet` | 10 autonomous AI agents via OpenClaw + Mission Control |
| **DSPD** | `devops-solution-product-development` | Project management via self-hosted Plane |
| **NNRT** | `Narrative-to-Neutral-Report-Transformer` | Report transformation NLP pipeline |

## Identity Profile

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Type** | product (backend AI platform) | CLI (`python -m aicp.cli`) + 4-tier router + MCP server (**64 tools — audit pending**, see lesson `wiki/lessons/00_inbox/aicp-mcp-server-tool-surface-drift-from-claude-md.md`) + guardrails + 9 operational profiles |
| **Domain** | backend-ai-platform-python | Python 3.11+; 61 modules in `aicp/`; 94 test files / 1,758 tests; backend stack = LocalAI v4.1.3 (Docker, GPU via WSL2) + Claude Code subprocess |
| **Second-brain** | connected | Forwarder at [tools/gateway.py](tools/gateway.py) → `~/devops-solutions-research-wiki`. AICP is documented in `wiki/ecosystem/project_profiles/aicp/identity-profile.md`. Compliance currently **Tier 4/4 STRUCTURAL** (see `python3 -m tools.gateway compliance`). |
| **Phase** | production — Stage 2 routing operational; **Stage 3 hardware unlocked 2026-04-17** | LocalAI Stage 1 complete; 4-tier router with circuit breakers + DLQ + warmup deployed; hardware upgrade to **19GB VRAM** (RTX 2080 8GB + RTX 2080 Ti 11GB) — unblocks Qwen3-30B-A3B MoE and Gemma 4 26B (dual-gpu profile becomes runnable) |
| **Scale** | medium | 61 Python modules, 94 test files, 1,758 tests, 78 skills, 9 profiles, 14 model configs |

**Consumer/task properties NOT declared here** (per the consumer-property doctrine — `wiki/lessons/01_drafts/execution-mode-is-consumer-property-not-project-property.md`): execution mode (default solo), SDLC profile (default Goldilocks), methodology model (per-task), current stage (per-task). Full table + commands in [AGENTS.md](AGENTS.md).

## The Mission

**Post-Anthropic self-autonomous AI stack** by 2026-04-27 (P0 milestone, brain-assigned 2026-04-22 — see `wiki/log/2026-04-22-k2-6-directive-and-post-anthropic-pivot.md`). **Status as of 2026-04-25: functionally reached, 2 days early.** Kimi K2.6 (Moonshot, MIT-licensed, 1T/32B-active MoE) is now the primary cloud tier via OpenRouter (pinned-provider, $0.745/$4.655 per M, audit-safe) and via Ollama Cloud Pro (subscription-flat ~$27 CAD/mo, personal/research only — shared pool). Local K2.6 Q2 GGUF runs on operator's Tier 0 hardware via llama.cpp (sovereignty fallback only — empirically 0.045–0.10 tok/s, not interactive).

**Mission shift** (2026-04-22 → 2026-04-25):

| Tier | Before | After |
|------|--------|-------|
| Primary cloud agentic | Claude Opus 4.7 (Anthropic API) | **Kimi K2.6** via OpenRouter (audit-safe) + **Ollama Cloud Pro** (personal/research) |
| Anthropic role | Default escalation target | Hard-gated last-resort fallback only |
| Local frontier | Qwen3-30B-A3B (dual-GPU) | + **K2.6 Q2 via llama.cpp** (318GB Unsloth UD-Q2_K_XL GGUF) — sovereignty-only on Tier 0; opt-in via `--backend k2_6_local` |
| Router tiers (default profile) | 4 (local → fleet → openrouter → claude) | **4** (local → k2_6_openrouter → openrouter → claude); `personal` profile inserts `ollama_cloud` between local and k2_6_openrouter |
| Hardware ceiling | 19GB VRAM | + **64GB RAM** (sufficient for llama.cpp mmap of 318GB Q2 GGUF; sglang+kt-kernel datacenter path rejected — see `docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md`) |
| Realistic monthly cost | ~$540 CAD (prior Anthropic) | ~$30–60 CAD blended (Ollama Pro flat + occasional OpenRouter spillover) |

AICP owns brain epic **E011 — Routing Integration** (5 modules, 15-20 tasks). Authoritative scope at `~/devops-solutions-research-wiki/wiki/backlog/epics/pre-milestone/E011-routing-integration-aicp-tiers.md`.

**Original LocalAI-independence stages remain the long arc**:

1. **Make LocalAI functional** — done (LocalAI v4.1.3 on Docker, 9 models loaded, OpenAI-compatible API on :8090)
2. **Route simple operations to LocalAI** — done (4-tier router with circuit breakers, DLQ, warmup, 9 profiles)
3. **Progressive offload** — hardware unlocked 2026-04-17 (19GB VRAM, dual-gpu profile runnable). Now sits ALONGSIDE the K2.6 tier work.
4. **Reliability and failover** — partial (circuit breakers + DLQ + reliable profile shipped; cluster peering pending)
5. **Near-independent operation** — **functionally reached 2026-04-25** via Post-Anthropic milestone (Ollama Cloud Pro + OpenRouter K2.6 pinned + local K2.6 sovereignty fallback; Anthropic gated to last resort)

> "I dont want to have to deal with Anthropic and Claude and Opus in the future......" (operator, 2026-04-22)

> "Its important that the main first mission is to make localAI functional and then make it more and more reliable to offload as much as possible the work from claude till one day maybe even try to actually run independently as much as possible."

## Architecture

```
User → AICP Controller → Router → (5 backends below) → Project/Repo
                            │
                            ├── Score-banded routing via tier_map
                            │   0.00–0.25  local            (LocalAI Qwen3/Gemma4)
                            │   0.25–0.45  k2_6_openrouter  (Kimi K2.6, audit-safe pinned)
                            │              [or ollama_cloud under `personal` profile]
                            │   0.45–0.70  k2_6_openrouter  (Kimi K2.6 cont.)
                            │   0.70–0.90  openrouter       (Opus 4.7 / GPT-5.4 fallback)
                            │   0.90–1.00  claude           (Anthropic direct, last resort)
                            │
                            └── Sovereignty fallback: --backend k2_6_local
                                (llama.cpp + Unsloth Q2 GGUF, opt-in)
```

### Three Permission Modes
- **Think** — read, analyze, plan. No edits, no commands.
- **Edit** — modify files in a controlled scope. Produce patches/diffs.
- **Act** — run commands, workflows, tools. Highest power, most controlled.

### Backends (5 active, 1 sovereignty-only)
- **local** — LocalAI (Docker, port 8090). Qwen3/Gemma4 family, OpenAI-compat. Default for low-complexity work.
- **k2_6_openrouter** — Kimi K2.6 via OpenRouter, pinned-provider, audit-safe. Default agentic tier ($0.745/$4.655 per M).
- **ollama_cloud** — Ollama Cloud Pro subscription (~$27 CAD/mo flat). Personal/research only — shared inference pool. Activated under `personal` profile.
- **openrouter** — OpenRouter generic catalog (Opus 4.7, GPT-5.4, Gemini, etc.). Fallback for premium models.
- **claude** — Claude Code direct subprocess (Anthropic API). Hard-gated last resort.
- **k2_6_local** *(sovereignty-only, not in default routing)* — llama.cpp serving Unsloth K2.6 Q2 GGUF on localhost:8091. Opt-in via `--backend k2_6_local`. Empirical 0.045–0.10 tok/s on Tier 0, 60–90 min cold reload — proves independence, not interactive.

## Tech Stack

Python 3.11+ • LocalAI v4.1.3 (Docker, GPU via WSL2) • Claude Code CLI subprocess • llama.cpp (CUDA, b8920+, for local K2.6 sovereignty) • OpenRouter HTTP • Ollama Cloud HTTP • YAML config • structured JSON logs • NVIDIA dual-GPU via WSL2 `/dev/dxg` (8GB + 11GB = 19GB) • 64GB DDR4-2666 quad-channel (X299) • Single-active GPU model with LRU eviction (MAX_ACTIVE_BACKENDS=3).

## Project Structure (top-level packages)

| Package | Responsibility | Key modules |
|---------|---------------|-------------|
| [aicp/core/](aicp/core/) | Controller + router + modes + reliability + intelligent infra | controller, router, modes, pipeline, session, budget, metrics, observability, tools, skills, rag, kb, gpu, cluster, history, models, approval, events, tasks, memory_relevance, memory_extract, compaction, circuit_breaker, dlq, prometheus, health_report |
| [aicp/backends/](aicp/backends/) | All backend clients | base, localai, claude_code, openrouter, k2_6_local, ollama_cloud |
| [aicp/guardrails/](aicp/guardrails/) | Permission enforcement | checks, paths, response |
| [aicp/cli/](aicp/cli/) | CLI dispatcher + interactive + dashboard | main, control, interactive, dashboard, display, project_ops |
| [aicp/agent/](aicp/agent/) | Agent server (fleet integration) | client, server (task lifecycle, away summary, progress events) |
| [aicp/mcp/](aicp/mcp/) | MCP server — **64 tools (audit pending)** | server.py — chat, vision, transcribe, speak, voice_pipeline, imagine, embed, models, grammar, rerank, system, agent, store_*, kb_*, route, deep_health, profile, task_status, dlq_status, model_*, lora_*, tts*, transcribe_detailed, tokenize*, embed_typed*, similarity, nearest_neighbors, fleet_*, multimodal, bestof, logprobs, json, seed, infill, batch, metrics, warmup, models_loaded, complete*, vad, detect, p2p_status, sound, edit, model_gallery/install/status/unload/delete/config*, embed_image/dims, server_config, tools_stream, backends_list — see `wiki/lessons/00_inbox/aicp-mcp-server-tool-surface-drift-from-claude-md.md` for audit findings |
| [config/](config/) | Default config + 9 profiles + 14 model YAMLs + alerts | default.yaml, fleet.yaml, alerts.yaml, profiles/, models/ |
| [tests/](tests/) | 94 test files, 1,758 tests | mirrors aicp/ structure |
| [wiki/](wiki/) | AICP knowledge wiki (per second brain standards) | config/, backlog/, lessons/, patterns/, decisions/ |
| [docs/](docs/) | Architecture and planning + KB content | kb/research/, kb/models/, kb/infrastructure/, knowledge-map/ |
| [.claude/skills/](.claude/skills/) | 78 skills (conditional, just-in-time) | per skill: SKILL.md + scripts/ + references/ |

## LocalAI Assessment (operational state)

LocalAI is running and functional on Docker with GPU acceleration. API on `localhost:8090`.

### Models — Qwen3 (recommended) + Gemma 4 (multimodal) + legacy

| Model | Config | Size | VRAM | Use case |
|-------|--------|------|------|----------|
| **qwen3-8b** | `qwen3-8b.yaml` | 4.9GB | 6GB+ | Main reasoning — thinking mode, tool calling |
| qwen3-8b-fast | `qwen3-8b-fast.yaml` | 4.9GB | 6GB+ | No thinking, structured tasks |
| **qwen3-4b** | `qwen3-4b.yaml` | 3.3GB | 4GB+ | Fleet lightweight |
| qwen3-30b-a3b | `qwen3-30b-a3b.yaml` | 17GB | 18GB+ | MoE — **dual GPU only (now runnable)** |
| gemma4-e2b | `gemma4-e2b.yaml` | 3.1GB | 4GB+ | Multimodal (text+image+audio), 53 tok/s |
| gemma4-e4b | `gemma4-e4b.yaml` | 5.0GB | 6GB+ | Mid-range multimodal |
| gemma4-26b-a4b | `gemma4-26b-a4b.yaml` | 16.8GB | 18GB+ | MoE multimodal — **dual GPU only (now runnable)** |
| codellama / hermes / phi-2 | (legacy) | varies | varies | Code gen / legacy reasoning / CPU fallback |
| llava / whisper / piper-tts / nomic-embed / bge-reranker / sd35-medium | (specialized) | CPU/small | — | Vision / STT / TTS / embeddings / reranking / image gen |

### Key findings

- **Cold start**: 10-80s per swap (model size dependent). **Warm inference**: 1-1.2s for 7B/3B.
- **Single-active backend**: 8GB VRAM constraint (now 19GB with dual GPU — dual-gpu profile activates). LRU eviction at `MAX_ACTIVE_BACKENDS=3`.
- **Watchdog**: auto-recovers stuck backends (15m idle / 10m busy).
- **API**: OpenAI-compatible chat completions (`localhost:8090`). Routes `aicp_route` MCP tool wraps the controller's full routing decision.

### Routing strategy (5-tier, post-mission)

Default profile (audit-safe; client/monetizable work):

| Operation | Backend | Model | Why |
|-----------|---------|-------|-----|
| Heartbeat (no work) | intercepted | — | Template, 0 tokens |
| Fleet ops (status, chat) | local | gemma4-e2b | 53 tok/s, multimodal |
| Simple Q&A / format / translate | local | qwen3-8b-fast | No thinking, fewer tokens |
| Code (implement, debug) | local | qwen3-8b | Thinking enabled |
| Medium / agentic | k2_6_openrouter | moonshotai/kimi-k2.6 | Audit-safe pinned provider |
| Premium fallback | openrouter | opus / gpt-5.4 / gemini-3.1-pro | When K2.6 not enough |
| Last resort | claude | opus | Hard-gated |

`personal` profile (research/dev/non-monetizable; shared pool acceptable):

| Band | Backend | Why |
|------|---------|-----|
| Medium | **ollama_cloud** | Subscription-flat (~$27 CAD/mo), faster than per-token |
| Higher | k2_6_openrouter | Spillover when Ollama caps hit |
| Premium | openrouter | Opus / GPT fallback |
| Last resort | claude | Hard-gated |

**Configurable per profile**: failover chain, escalation threshold, complexity thresholds, `force_cloud_modes` per mode. See `config/profiles/*.yaml` (10 profiles total — `default`, `personal` are post-mission canonical; `fast`, `quality`, `reliable`, `dual-gpu`, etc. inherit and override).

### Infrastructure target

```
Machine 1: Fleet Alpha    Machine 2: Fleet Bravo
├── LocalAI Cluster 1     ├── LocalAI Cluster 2
├── OpenClaw + MC         ├── OpenClaw + MC
├── Fleet Daemons         ├── Fleet Daemons
└── 10 Agents (alpha-*)   └── 10 Agents (bravo-*)

Shared: Plane, GitHub, ntfy
LocalAI peering: Cluster 1 ↔ Cluster 2 (load balance, failover) — pending
```

## Key Principles

1. **User is in control**, not the AI.
2. **Backends are tools**, not masters.
3. **Local-first**, cloud when needed.
4. **Keep v1 simple and usable.**
5. **Add complexity only when it earns its place.**

## Guardrails

- Think mode → no writes allowed.
- Edit mode → only allowed files/paths.
- Act mode → controlled command allowlist.
- Protect secrets and forbidden paths always.
- Control when cloud backends are allowed.

Implementation: [aicp/guardrails/](aicp/guardrails/) — checks, paths, response.

## Reliability (Stage 4)

| Component | File | Purpose |
|-----------|------|---------|
| Circuit breaker | [aicp/core/circuit_breaker.py](aicp/core/circuit_breaker.py) | Per-backend state machine (CLOSED → OPEN → HALF_OPEN); failover in milliseconds |
| Startup warmup | [aicp/agent/server.py](aicp/agent/server.py) | Pre-loads models from `warmup.models` before accepting traffic |
| Deep health | `GET /health` | Returns `{status: ok|degraded|warming, backends: {...}}` |
| Dead-letter queue | [aicp/core/dlq.py](aicp/core/dlq.py) | Failed tasks → `~/.aicp/dlq/` JSONL; retry via `aicp --retry-dlq` |
| Persistent metrics | [aicp/core/prometheus.py](aicp/core/prometheus.py) | JSON snapshots; counters survive restarts |
| Health reports | [aicp/core/health_report.py](aicp/core/health_report.py) | Trend deltas; `aicp --health-report`; optional ntfy |
| Reliability profile | `make profile-use PROFILE=reliable` | Aggressive breaker (threshold=2), auto-warmup, DLQ retries=5, reports every 4h |

## Intelligent Infrastructure (Stage 5)

Patterns adopted from Claude Code's production architecture, adapted for AICP's local-first, fleet-oriented design. Research: [docs/kb/research/claude-code-architecture-analysis.md](docs/kb/research/claude-code-architecture-analysis.md).

| Component | File | Purpose |
|-----------|------|---------|
| Event emitter | [aicp/core/events.py](aicp/core/events.py) | Thread-safe fire-and-forget bus; controller emits task_start/complete/failed |
| Tool safety metadata | [aicp/core/tools.py](aicp/core/tools.py) | Fail-closed flags: is_read_only, is_destructive, is_concurrent_safe; 3-stage pipeline |
| Task lifecycle | [aicp/core/tasks.py](aicp/core/tasks.py) | pending → running → completed/failed/killed; tool/token/activity tracking |
| Memory relevance | [aicp/core/memory_relevance.py](aicp/core/memory_relevance.py) | Embedding-based selection via nomic-embed; aging warnings |
| Microcompaction | [aicp/core/compaction.py](aicp/core/compaction.py) | Surgical pruning; replaces tool results with markers; image stripping |
| Skill model override | [aicp/core/skills.py](aicp/core/skills.py) | Skills specify `model:` in frontmatter; `allowed-tools`, `context: fork`, `paths` |
| Auto-memory extraction | [aicp/core/memory_extract.py](aicp/core/memory_extract.py) | Heuristic extraction of learnable facts from task history |
| Away summary | [aicp/agent/server.py](aicp/agent/server.py) | 1-3 sentence summary on shutdown; loaded on restart |
| Extended MCP tools | [aicp/mcp/server.py](aicp/mcp/server.py) | **64 tools registered** (was claimed 11 — drift discovered 2026-04-19, see `wiki/lessons/00_inbox/aicp-mcp-server-tool-surface-drift-from-claude-md.md`). Categories: inference (chat, vision, transcribe, speak, voice_pipeline, imagine, embed, multimodal, bestof, complete*), KB (kb_search, kb_ingest, kb_stats, kb_augment, kb_search_collection), stores (store_set, store_find), models (models, model_*, lora_*), audio (tts, tts_voices, transcribe_detailed, sound, vad), tokenization (tokenize, tokenize_batch, detokenize, token_count), embeddings (embed, embed_typed, embed_typed_batch, embed_dims, embed_image, similarity, nearest_neighbors), operational (route, deep_health, profile, task_status, dlq_status, metrics, warmup, models_loaded, system, server_config, backends_list, p2p_status), fleet (fleet_status, fleet_run, agent), advanced (grammar, rerank, json, seed, infill, batch, edit, detect, logprobs, complete_logprobs, complete_n, tools_stream). Per the second brain's `cli-tools-beat-mcp-for-token-efficiency` lesson, this surface needs an audit: which tools are external-bridge (justified MCP) vs operational (should be CLI+Skills). |

## Configuration Profiles

Named bundles coordinating backends + router + RAG + budget + cache + timeouts + Docker via single switch.

### Profiles

| Profile | Primary | Failover | Use case |
|---------|---------|----------|----------|
| **default** | qwen3-8b | local→fleet→openrouter→claude | Balanced everyday |
| **fast** | gemma4-e2b | local→openrouter | Quick, 53 tok/s |
| **offline** | qwen3-8b | local→fleet | Air-gapped |
| **thorough** | qwen3-8b | full chain | Architecture/security audits |
| **code-review** | qwen3-8b | local→openrouter→claude | Code analysis, low temp |
| **fleet-light** | gemma4-e2b | local→fleet | Heartbeat duty |
| **reliable** | qwen3-8b | full chain | Production — breaker, warmup, DLQ, reports |
| **dual-gpu** | qwen3-30b-a3b | full chain | 19GB VRAM MoE (now runnable) |
| **benchmark** | qwen3-8b | local only | Deterministic (temp=0, seed=42) |

### Config load order

`config/default.yaml` → `config/profiles/<name>.yaml` → `~/.aicp/config.yaml` → `<project>/.aicp/config.yaml` → `--config <path>`.

### Activation (precedence)

1. `aicp --profile fast "..."` (CLI)
2. `AICP_PROFILE=fast` (env var)
3. `make profile-use PROFILE=fast` (.env)

Profiles can `extends:` other profiles (deep merge, circular detection). Implementation: [aicp/core/profiles.py](aicp/core/profiles.py); 49 profile tests in [tests/test_profiles.py](tests/test_profiles.py).

## Docker (LocalAI)

Port `8090` (host) → `8080` (container). Key envs in [docker-compose.yaml](docker-compose.yaml): `THREADS=4`, `LLAMACPP_PARALLEL=2`, `CONTEXT_SIZE=16384`, `LOCALAI_MAX_ACTIVE_BACKENDS=3`, watchdog 15m idle / 10m busy, `LOCALAI_AGENT_POOL_EMBEDDING_MODEL=nomic-embed`.

### Knowledge Base

KB content lives in **LocalAI Collections** (chromem-backed, persistent at `localhost:8090/app/collections`). Synced via `make kb-sync` (or `make kb-sync-force`). Collection: `aicp-kb`. Searchable via `/api/agents/collections/aicp-kb/search`. Sources: [docs/kb/](docs/kb/) + [docs/knowledge-map/](docs/knowledge-map/).

### Observability

Optional Prometheus + Grafana behind a Docker compose profile (`make monitoring-up` → `:9090` + `:3000` admin/aicp). AICP metrics: `aicp/core/prometheus.py` → `:9101/metrics`. LocalAI built-in: `:8090/metrics`. Alerts: [config/alerts.yaml](config/alerts.yaml) (7 rules: stuck model, latency, errors, swaps, quality, cost, memory).

## AICP ↔ Fleet Connection

AICP provides LocalAI inference + skill library to the fleet ecosystem.

| Module | Purpose |
|--------|---------|
| [aicp/core/rag.py](aicp/core/rag.py) | SQLite vector store, cosine similarity (fleet RAG) |
| [aicp/core/kb.py](aicp/core/kb.py) | Knowledge base, file ingestion, BGE reranker |
| [aicp/core/stores.py](aicp/core/stores.py) | LocalAI /stores/ API client |
| [aicp/core/router.py](aicp/core/router.py) | Score-based routing with configurable thresholds |
| [aicp/core/skills.py](aicp/core/skills.py) | 3-layer skill system (78 skills in `.claude/skills/`) |
| [aicp/core/circuit_breaker.py](aicp/core/circuit_breaker.py) | Prevents thundering herd from fleet agents |
| [aicp/core/dlq.py](aicp/core/dlq.py) | Persists failed tasks for retry |

Skills used by fleet agents (18 referenced in fleet's `config/agent-tooling.yaml`): `architecture-propose`, `feature-implement`, `quality-coverage`, `foundation-docker`, `pm-plan`, `ops-deploy`, etc.

<!-- SECOND-BRAIN-CONNECTION -->
## Second Brain Connection

This project is connected to the **second brain** (research wiki) — a shared
knowledge system holding methodology, standards, validated lessons, patterns,
and decisions across the ecosystem.

**Your brain** (this CLAUDE.md/AGENTS.md + skills + hooks) is YOUR agent.
**The second brain** is a SEPARATE system. The goal is NOT runtime dependency —
it's to ADOPT what fits your identity and EVOLVE your own brain.

**Adoption tiers** — check where you are: `python3 -m tools.gateway compliance`
- Tier 1: Agent foundation (schema + templates)
- Tier 2: Stage-gate process (methodology + backlog + enforcement)
- Tier 3: Evolution pipeline (maturity lifecycle + scoring)
- Tier 4: Hub integration (bidirectional sync + export + contribute)

**First step for any fresh session:** `python3 -m tools.gateway orient`

**Browse the second brain's knowledge:**
```
python3 -m tools.view spine          # all 16 models, standards, sub-models
python3 -m tools.view standards      # what "good" looks like per artifact type
python3 -m tools.view model <name>   # one model in full
python3 -m tools.view lessons        # 44 validated operational lessons
python3 -m tools.view search <query> # search across all knowledge
```

**Contribute learnings back:** `python3 -m tools.gateway contribute --type lesson --title "..."`
<!-- SECOND-BRAIN-CONNECTION -END -->
