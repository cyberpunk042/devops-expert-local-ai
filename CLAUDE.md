# CLAUDE.md — AI Control Platform (AICP)

> **Read [AGENTS.md](AGENTS.md) first** — universal cross-tool context (hard rules, stage gates, methodology models, quality gates, commands, conventions, where to find things). This file is the **Claude Code-specific layer** plus the **gateway-parseable Identity Profile**. Detail-heavy sections route to [docs/architecture/](docs/architecture/) so every-message context stays lean.

## Project Overview

AICP is a personal AI control workspace that orchestrates local and cloud AI backends through a unified controller. The user is always in control — AI backends are tools, not masters.

One of four projects in the fleet ecosystem:

| Project | Repo | Purpose |
|---------|------|---------|
| **AICP** | `devops-expert-local-ai` | AI Control Platform — backends, modes, guardrails, post-Anthropic routing |
| **Fleet** | `openfleet` | 10 autonomous AI agents via OpenClaw + Mission Control |
| **DSPD** | `devops-solution-product-development` | Project management via self-hosted Plane |
| **NNRT** | `Narrative-to-Neutral-Report-Transformer` | Report transformation NLP pipeline |

## Identity Profile

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Type** | product (backend AI platform) | CLI (`python -m aicp.cli`) + 5-band tier_map router + MCP server (64 tools — audit pending, see [docs/architecture/project-structure.md](docs/architecture/project-structure.md)) + guardrails + 11 operational profiles |
| **Domain** | backend-ai-platform-python | Python 3.11+; 64 modules in `aicp/`; 97 test files / 1,840 tests; backend stack = LocalAI v4.1.3 (Docker) + llama.cpp (local K2.6 sovereignty) + OpenRouter + Ollama Cloud + Claude Code subprocess |
| **Second-brain** | connected | Forwarder at [tools/gateway.py](tools/gateway.py) → `~/devops-solutions-research-wiki`. Compliance currently **Tier 4/4 STRUCTURAL** (`python3 -m tools.gateway compliance`). |
| **Phase** | production — **Post-Anthropic milestone functionally reached 2026-04-25** (2 days early on the 2026-04-27 P0 deadline) | LocalAI Stage 1-2 complete; Stage 3 hardware unlocked 2026-04-17 (19GB VRAM + 64GB RAM); Stage 5 reached via Post-Anthropic milestone |
| **Scale** | medium | 64 Python modules, 97 test files, 1,840 tests, 84 skills, 11 profiles, 19 model configs |

**Consumer/task properties NOT declared here** (per the consumer-property doctrine — `wiki/lessons/01_drafts/execution-mode-is-consumer-property-not-project-property.md`): execution mode (default solo), SDLC profile (default Goldilocks), methodology model (per-task), current stage (per-task). Full table + commands in [AGENTS.md](AGENTS.md).

## The Mission

**Post-Anthropic self-autonomous AI stack** — functionally reached 2026-04-25. Kimi K2.6 via OpenRouter (audit-safe, pinned-provider) + Ollama Cloud Pro (personal/research, shared pool) replaces the prior Claude-Opus-as-default habit. Local K2.6 Q2 GGUF runs on operator hardware via llama.cpp as sovereignty fallback (slow, opt-in). Realistic monthly cost: ~$30-60 CAD blended vs prior ~$540 CAD baseline.

> "I dont want to have to deal with Anthropic and Claude and Opus in the future......" (operator, 2026-04-22)

Full mission shift table, original 5-stage independence arc, brain-epic links, and operator quotes: **[docs/architecture/post-anthropic-mission.md](docs/architecture/post-anthropic-mission.md)**.

## Architecture

```
User → AICP Controller → Router → 5 backends → Project/Repo
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
- **local** — LocalAI on `localhost:8090` (Qwen3 / Gemma4 family). Default for low-complexity work.
- **k2_6_openrouter** — Kimi K2.6 via OpenRouter, pinned provider (audit-safe). Default agentic tier.
- **ollama_cloud** — Ollama Cloud Pro (~$27 CAD/mo flat). `personal` profile only — shared inference pool.
- **openrouter** — Generic catalog (Opus 4.7 / GPT-5.4 / Gemini etc.). Premium fallback.
- **claude** — Claude Code direct subprocess. Hard-gated last resort.
- **k2_6_local** *(sovereignty-only, not in default routing)* — llama.cpp + Unsloth Q2 GGUF on `:8091`. Opt-in via `--backend k2_6_local`. Slow (0.045–0.10 tok/s on Tier 0).

Full LocalAI model inventory, per-profile routing tables, and infrastructure target: **[docs/architecture/localai-routing.md](docs/architecture/localai-routing.md)**.

## Tech Stack

Python 3.11+ • LocalAI v4.1.3 (Docker, GPU via WSL2) • Claude Code CLI subprocess • llama.cpp (CUDA, b8920+, for local K2.6 sovereignty) • OpenRouter HTTP • Ollama Cloud HTTP • YAML config • structured JSON logs • NVIDIA dual-GPU via WSL2 `/dev/dxg` (8GB + 11GB = 19GB) • 64GB DDR4-2666 quad-channel (X299) • Single-active GPU model with LRU eviction (MAX_ACTIVE_BACKENDS=3).

## Project Structure

| Package | Responsibility |
|---------|---------------|
| [aicp/core/](aicp/core/) | Controller + router + modes + reliability + intelligent infra |
| [aicp/backends/](aicp/backends/) | All backend clients (base, localai, claude_code, openrouter, k2_6_local, ollama_cloud) |
| [aicp/guardrails/](aicp/guardrails/) | Permission enforcement (checks, paths, response) |
| [aicp/cli/](aicp/cli/) | CLI dispatcher + interactive + dashboard |
| [aicp/agent/](aicp/agent/) | Agent server (fleet integration, task lifecycle, away summary) |
| [aicp/mcp/](aicp/mcp/) | MCP server — 64 tools (audit pending) |
| [config/](config/) | Default config + 11 profiles + 19 model YAMLs + alerts |
| [tests/](tests/) | 97 test files / 1,840 tests |
| [wiki/](wiki/) | AICP knowledge wiki (per second-brain standards) |
| [docs/](docs/) | Architecture detail + planning + KB content |
| [.claude/skills/](.claude/skills/) | 84 skills (conditional, just-in-time) |

Full module-level breakdown + MCP tool inventory: **[docs/architecture/project-structure.md](docs/architecture/project-structure.md)**.

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

## Configuration Profiles (one-liner)

11 profiles. `default` + `personal` are the post-mission canonicals (audit-safe vs research/dev). `quality`, `fast`, `offline`, `thorough`, `code-review`, `fleet-light`, `reliable`, `dual-gpu`, `benchmark` extend or specialize.

Full profile table + load order + activation precedence + when-to-use guide: **[docs/architecture/profiles.md](docs/architecture/profiles.md)**.

## Reliability (Stage 4)

Per-backend circuit breakers, startup warmup, deep health endpoint, dead-letter queue with retry budget, persistent metrics, optional ntfy health reports. Reliability profile (`make profile-use PROFILE=reliable`) tightens breaker thresholds + auto-warmup + DLQ retries.

Component map: **[docs/architecture/reliability.md](docs/architecture/reliability.md)**.

## Intelligent Infrastructure (Stage 5)

Patterns adopted from Claude Code's production architecture, adapted for AICP's local-first, fleet-oriented design: event emitter, tool safety metadata, task lifecycle, memory relevance scoring, microcompaction, skill model overrides, auto-memory extraction, away summary.

Component map: **[docs/architecture/intelligent-infrastructure.md](docs/architecture/intelligent-infrastructure.md)**.

## Docker (LocalAI)

Port `8090` (host) → `8080` (container). Key envs in [docker-compose.yaml](docker-compose.yaml): `THREADS=4`, `LLAMACPP_PARALLEL=2`, `CONTEXT_SIZE=16384`, `LOCALAI_MAX_ACTIVE_BACKENDS=3`, watchdog 15m idle / 10m busy, `LOCALAI_AGENT_POOL_EMBEDDING_MODEL=nomic-embed`. KB content lives in LocalAI Collections (`localhost:8090/app/collections`, collection `aicp-kb`, sync via `make kb-sync`). Optional Prometheus + Grafana via `make monitoring-up` → `:9090` + `:3000` admin/aicp; AICP own metrics at `:9101/metrics`; LocalAI built-in at `:8090/metrics`. Alerts: [config/alerts.yaml](config/alerts.yaml) (7 rules).

## AICP ↔ Fleet Connection

AICP provides LocalAI inference + cloud routing + skill library to the fleet ecosystem. 18 of the 84 skills are referenced by fleet's `config/agent-tooling.yaml`.

Module map + skill inventory: **[docs/architecture/fleet-integration.md](docs/architecture/fleet-integration.md)**.

## Pointers to depth

| Topic | File |
|-------|------|
| Why this mission, what changed, full strategic-shift table | [docs/architecture/post-anthropic-mission.md](docs/architecture/post-anthropic-mission.md) |
| Codebase navigation, MCP tool surface | [docs/architecture/project-structure.md](docs/architecture/project-structure.md) |
| LocalAI model inventory, routing tables | [docs/architecture/localai-routing.md](docs/architecture/localai-routing.md) |
| All 11 profiles, when to use which | [docs/architecture/profiles.md](docs/architecture/profiles.md) |
| Stage 4 reliability components | [docs/architecture/reliability.md](docs/architecture/reliability.md) |
| Stage 5 intelligent-infrastructure components | [docs/architecture/intelligent-infrastructure.md](docs/architecture/intelligent-infrastructure.md) |
| Fleet integration modules + skills | [docs/architecture/fleet-integration.md](docs/architecture/fleet-integration.md) |
| Storage tiers (T0 NVMe / T1 SATA / T2 archive) | [docs/STORAGE.md](docs/STORAGE.md) |
| Why local K2.6 is on llama.cpp (not KTransformers) | [docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md](docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md) |
| Empirical Tier 0 K2.6 throughput numbers | [docs/EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md](docs/EXPLORATION-LOG-LOCAL-K26-EMPIRICAL-2026-04-24.md) |
| Cloud spend math + 5-year projection | [docs/CLOUD-SPEND-SCENARIOS-2026-04-24.md](docs/CLOUD-SPEND-SCENARIOS-2026-04-24.md), [docs/SCALING-PROJECTION-5YR-2026-04-24.md](docs/SCALING-PROJECTION-5YR-2026-04-24.md) |
| Detail index | [docs/architecture/_index.md](docs/architecture/_index.md) |

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
