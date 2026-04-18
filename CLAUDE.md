# CLAUDE.md — AI Control Platform (AICP)

## Project Overview

AICP is a personal AI control workspace that orchestrates local and cloud AI backends (LocalAI, Claude Code) through a unified controller. The user is always in control — AI backends are tools, not masters.

This is one of four projects in the fleet ecosystem:

| Project | Repo | Purpose |
|---------|------|---------|
| **AICP** | `devops-expert-local-ai` | AI Control Platform — backends, modes, guardrails, LocalAI independence |
| **Fleet** | `openclaw-fleet` | 10 autonomous AI agents via OpenClaw + Mission Control |
| **DSPD** | `devops-solution-product-development` | Project management via self-hosted Plane |
| **NNRT** | `Narrative-to-Neutral-Report-Transformer` | Report transformation NLP pipeline |

## Identity Profile

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Type** | product (backend AI platform) | CLI (`python -m aicp.cli`) + 4-tier router + MCP server (11 tools) + guardrails + 9 operational profiles |
| **Domain** | backend-ai-platform-python | Python 3.11+; 61 modules in `aicp/`; 94 test files / 1,758 tests; backend stack = LocalAI v4.1.3 (Docker, GPU via WSL2) + Claude Code subprocess |
| **Second-brain** | connected | Forwarder at [tools/gateway.py](tools/gateway.py) → `~/devops-solutions-research-wiki`. AICP is documented in `wiki/ecosystem/project_profiles/aicp/identity-profile.md`. Compliance currently Tier 0/4 — adoption underway. |
| **Phase** | production — Stage 2 routing operational; **Stage 3 hardware unlocked 2026-04-17** | LocalAI Stage 1 complete; 4-tier router with circuit breakers + DLQ + warmup deployed; hardware upgrade to **19GB VRAM** (RTX 2080 8GB + RTX 2080 Ti 11GB) confirmed today — unblocks Qwen3-30B-A3B MoE and Gemma 4 26B (dual-gpu profile becomes runnable) |
| **Scale** | medium | 61 Python modules, 94 test files, 1,758 tests, 78 skills (.claude/skills/), 9 profiles (config/profiles/), 14 model configs (config/models/) |

### Why these five fields and not others

The Identity Profile above declares AICP per the second brain's Project
Self-Identification Protocol (`wiki/domains/cross-domain/methodology-framework/project-self-identification-protocol.md`).
The protocol distinguishes three classes of properties — only the **stable**
(type, domain, second-brain) and **phase/scale state** classes belong here.
**Consumer/task properties** (execution mode, SDLC profile, methodology model,
current stage) are deliberately NOT hardcoded — declaring them in CLAUDE.md is
a documented drift failure (see
`wiki/lessons/01_drafts/execution-mode-is-consumer-property-not-project-property.md`).
They are decided per work unit by the consumer (solo Claude Code session,
harness, or fleet) at connection time.

### Consumer / task properties (NOT declared here)

These are per-work-unit choices the consumer makes — declaring them as project
properties conflates task-dependent state with project identity, a recurring
drift failure ("the project is frozen to a model"). The defaults below
apply when the consumer doesn't override them at MCP connect or task start.

| Property | Default | Where it's actually decided |
|----------|---------|-----------------------------|
| **Execution mode** | solo | The consumer's runtime — solo Claude Code session, harness (e.g., OpenArms v10), fleet orchestrator (e.g., OpenFleet). Non-default declared at MCP connect via the `runtime:` field in the consumer's `.mcp.json`. From inside this project we cannot detect who is consuming us elsewhere. |
| **SDLC profile** | default (Goldilocks — stage-gated, hooks-optional, gates enforced) | Per-task. A production project running a hotfix wants `simplified`; running an architecture review wants `full`. Selected at task start, not project setup. |
| **Methodology model** | task-dependent | One of 9 chains: feature-development, bug-fix, research, refactor, hotfix, integration, documentation, knowledge-evolution, project-lifecycle. Selected per task; menu via `python3 -m tools.gateway query --chains`. |
| **Current stage** | task-dependent | document → design → scaffold → implement → test (varies by chain). Set per task. |

### How to verify or refresh

```bash
python3 -m tools.gateway status        # second brain's view of AICP identity + SDLC profile
python3 -m tools.gateway compliance    # adoption tier (currently Tier 0/4 — adoption in progress)
python3 -m tools.gateway query --chains  # methodology chains menu (per-task selection)
python3 -m tools.gateway orient        # full orientation flow
```

Identity reviews quarterly or when phase/scale crosses a threshold. The phase
field changes when a stage in the Mission completes — that update belongs here.
Scale field changes when module/test counts cross an order-of-magnitude (medium
→ large at ~500 modules, etc.).

## The Mission

**LocalAI independence.** Progressive offload from Claude to LocalAI. 5 stages:

1. **Make LocalAI functional** — done (LocalAI v4.1.3 on Docker, 9 models loaded, OpenAI-compatible API on :8090)
2. **Route simple operations to LocalAI** — done (4-tier router with circuit breakers, DLQ, warmup, 9 profiles)
3. **Progressive offload** ← **CURRENT** — hardware unlocked 2026-04-17 (19GB VRAM, dual-gpu profile runnable). Open question: empirical routing split with the new capacity. Heartbeats, simple reviews, status checks moving to local.
4. **Reliability and failover** — graceful degradation, cluster peering (partial: circuit breakers + DLQ + reliable profile shipped; cluster peering pending)
5. **Near-independent operation** — 80%+ Claude token reduction (target)

> "Its important that the main first mission is to make localAI functional
> and then make it more and more reliable to offload as much as possible
> the work from claude till one day maybe even try to actually run
> independently as much as possible."

## Architecture

```
User → AICP Controller → Router → (LocalAI | Claude Code) → Project/Repo
                            │
                            ├── Does this need reasoning?
                            │   NO → LocalAI (local, free, fast)
                            │         ├── 3B model for structured responses
                            │         ├── MCP tool calls (direct HTTP, no LLM)
                            │         └── Template-based responses
                            │   YES → Claude (cloud, paid, powerful)
                            │         ├── opus for complex (architecture, security, planning)
                            │         └── sonnet for standard (implementation, review)
```

### Three Permission Modes

- **Think** — read, analyze, plan. No edits, no commands.
- **Edit** — modify files in a controlled scope. Produce patches/diffs.
- **Act** — run commands, workflows, tools. Highest power, most controlled.

### Two Backends

- **LocalAI** — fast, private, default for most tasks. OpenAI-compatible API on port 8090.
- **Claude Code** — stronger reasoning/coding, used for complex tasks and escalation.

## Tech Stack

- **Language**: Python 3.11+
- **Local AI Gateway**: LocalAI v4.1.3 (OpenAI-compatible API, Docker, GPU via WSL2)
- **Cloud Backend**: Claude Code CLI (invoked as subprocess)
- **Config**: YAML files in `config/`
- **Logging**: structured JSON logs
- **GPU**: NVIDIA via WSL2 `/dev/dxg`, 8GB VRAM
- **Model management**: Single-active backend (one GPU model at a time, swap on demand)

## Project Structure

```
aicp/                      # Main package (52 modules)
  core/                    # Controller, modes, router, session, pipeline, budget, metrics
    controller.py          # Central orchestrator — mode enforcement + backend dispatch + events
    router.py              # Backend routing — LocalAI vs Claude by task complexity
    modes.py               # Think/Edit/Act mode definitions and enforcement
    pipeline.py            # Request processing pipeline
    session.py             # Session management
    budget.py              # Token budget tracking
    metrics.py             # Performance metrics
    observability.py       # Tracing and monitoring
    context.py             # Context management
    tools.py               # Tool definitions + safety metadata + 3-stage pipeline
    skills.py              # Skill loading — model override, allowed-tools, scope
    worktree.py            # Git worktree management
    projects.py            # Project registry
    rag.py                 # Retrieval-augmented generation
    kb.py                  # Knowledge base
    stores.py              # Data stores
    db.py                  # Database operations
    gpu.py                 # GPU management
    cluster.py             # Multi-machine cluster support
    chunking.py            # Text chunking for embeddings
    history.py             # Conversation history (post-hoc task records)
    models.py              # Model info and configuration
    result.py              # Result types
    approval.py            # Approval workflows
    events.py              # Event emitter — lifecycle events for fleet integration
    tasks.py               # Task lifecycle state machine (pending→running→completed/failed)
    memory_relevance.py    # Embedding-based memory relevance scoring + aging
    memory_extract.py      # Auto-extraction of learnable facts from task history
    compaction.py          # Context compaction + microcompaction + image stripping
  backends/                # Backend integrations
    localai.py             # LocalAI client (OpenAI-compatible)
    claude_code.py         # Claude Code subprocess integration
    base.py                # Backend interface
  guardrails/              # Permission enforcement
    checks.py              # Pre/post execution checks
    paths.py               # Path protection rules
    response.py            # Response filtering
  config/                  # Configuration loading
    loader.py              # YAML config loader
  cli/                     # CLI entry point
    main.py                # CLI dispatcher
    control.py             # Control commands
    interactive.py         # Interactive mode
    dashboard.py           # Status dashboard
    display.py             # Output formatting
    project_ops.py         # Project operations
  agent/                   # Agent mode (fleet integration)
    client.py              # Agent client for fleet operations
    server.py              # Agent server — task lifecycle, away summary, progress events
  mcp/                     # MCP server
    server.py              # MCP tool server — 11 tools (chat, vision, route, health, profile, tasks, DLQ)
tests/                     # Test suite (77 test files, 1631 total tests)
config/                    # Default config files
  default.yaml             # Default AICP configuration
  fleet.yaml               # Fleet network topology
  models/                  # Model YAML configs (IaC source of truth, tracked in git)
    qwen3-8b.yaml          # Qwen3 8B (main reasoning model — recommended)
    qwen3-8b-fast.yaml     # Qwen3 8B fast mode (no thinking, structured tasks)
    qwen3-4b.yaml          # Qwen3 4B (lightweight fleet model — replaces hermes-3b)
    qwen3-30b-a3b.yaml     # Qwen3 30B MoE (dual GPU only: 8+11GB)
    hermes.yaml            # Hermes 2 Pro Mistral 7B (legacy)
    hermes-3b.yaml         # Hermes 3 Llama 3.2 3B (legacy)
    codellama.yaml         # CodeLlama 7B (code tasks)
    phi-2.yaml             # Phi-2 2.7B (CPU fallback)
    llava.yaml             # LLaVA 7B (vision)
    nomic-embed.yaml       # Nomic Embed (embeddings, CPU)
    whisper-1.yaml         # Whisper (speech-to-text)
    piper-tts.yaml         # Piper (text-to-speech)
    bge-reranker-v2-m3.yaml # BGE reranker (search)
    stablediffusion.yaml   # Stable Diffusion (image generation)
  profiles/                # Configuration profiles (operational presets)
    default.yaml           # Balanced defaults
    fast.yaml              # Low-latency, no thinking
    offline.yaml           # No cloud backends
    thorough.yaml          # Max quality, deep RAG
    code-review.yaml       # Code analysis, low temperature
    fleet-light.yaml       # Minimal footprint heartbeat duty
    dual-gpu.yaml          # Two GPUs, 30B MoE model
    benchmark.yaml         # Deterministic evaluation (temp=0)
models/                    # Runtime directory (gitignored entirely)
                           # Populated by: make setup (configs from config/models/ + binary downloads)
docs/                      # Architecture and planning documents
  kb/                      # Knowledge base (syncs to LocalAI collections)
    research/              # Investigation findings, model evaluations
    models/                # Model benchmarks, VRAM maps
    infrastructure/        # Docker, GPU, networking decisions
```

## LocalAI Assessment (Stage 1 — 2026-03-29)

LocalAI is running and functional on Docker with GPU acceleration.

### Models Available

#### Qwen3 (Recommended — 2025, next-gen)

| Model | Config | Size | VRAM | GPU Layers | Use Case |
|-------|--------|------|------|------------|----------|
| **qwen3-8b** | `qwen3-8b.yaml` | 4.9GB | 6GB+ | 33 | **Main reasoning** — thinking mode, 119 langs, native tool calling |
| qwen3-8b-fast | `qwen3-8b-fast.yaml` | 4.9GB | 6GB+ | 33 | Fast mode — no thinking, structured tasks |
| **qwen3-4b** | `qwen3-4b.yaml` | 3.3GB | 4GB+ | 33 | **Fleet lightweight** — replaces hermes-3b |
| qwen3-30b-a3b | `qwen3-30b-a3b.yaml` | 17GB | 18GB+ | 48 | MoE flagship — dual GPU (8+11GB) only |

#### Gemma 4 (Google — 2026, multimodal)

| Model | Config | Size | VRAM | GPU Layers | Use Case |
|-------|--------|------|------|------------|----------|
| gemma4-e2b | `gemma4-e2b.yaml` | 3.1GB | 4GB+ | 33 | Lightweight multimodal — text+image+audio, 128K context |
| gemma4-e4b | `gemma4-e4b.yaml` | 5.0GB | 6GB+ | 33 | Mid-range multimodal — could replace llava for vision tasks |
| gemma4-26b-a4b | `gemma4-26b-a4b.yaml` | 16.8GB | 18GB+ | 48 | MoE multimodal — dual GPU (8+11GB) only, 256K context |

#### Legacy Models

| Model | Config | Size | VRAM | GPU Layers | Use Case |
|-------|--------|------|------|------------|----------|
| hermes (7B) | `hermes.yaml` | 4.4GB | 6GB+ | 32 | Complex reasoning (legacy) |
| hermes-3b (3B) | `hermes-3b.yaml` | 2.0GB | 3GB+ | 32 | Fleet heartbeats (legacy) |
| codellama (7B) | `codellama.yaml` | 4.4GB | 6GB+ | 32 | Code generation |
| phi-2 (2.7B) | `phi-2.yaml` | 1.6GB | CPU | 0 | CPU fallback |

#### Specialized Models (CPU, no GPU needed)

| Model | Config | Use Case |
|-------|--------|----------|
| llava (7B) | `llava.yaml` | Vision + language |
| whisper | `whisper-1.yaml` | Speech-to-text |
| piper-tts | `piper-tts.yaml` | Text-to-speech |
| bge-reranker | `bge-reranker-v2-m3.yaml` | Search reranking |
| nomic-embed | `nomic-embed.yaml` | Embeddings |
| **sd35-medium** | `sd35-medium.yaml` | **Image gen (SD 3.5 Medium, default)** |
| stablediffusion | `stablediffusion.yaml` | Image gen (SD 1.5, legacy fallback) |

### Key Findings

- **API**: OpenAI-compatible chat completions working (`localhost:8090`)
- **Single-active backend**: Only one GPU model loaded at a time (8GB VRAM limit, `LOCALAI_SINGLE_ACTIVE_BACKEND=true`)
- **Cold start**: Model swap takes 10-80s depending on model size
- **Warm inference**: 1-1.2s for both 7B and 3B
- **Quality**: hermes correctly follows structured instructions
- **Watchdog**: Auto-recover stuck backends (`LOCALAI_WATCHDOG_IDLE=true`, 15m timeout)
- **GPU**: NVIDIA via WSL2 `/dev/dxg`, CUDA 12

### Routing Strategy (Implemented)

4-tier routing with confidence scoring and auto-escalation:

| Operation | Backend | Model | Why |
|-----------|---------|-------|-----|
| Heartbeat (no work) | Intercepted (0 tokens) | — | Template response, no LLM needed |
| Fleet ops (status, chat) | local | gemma4-e2b | 53 tok/s, 2.9GB, multimodal |
| Simple Q&A, format, translate | local | qwen3-8b-fast | No thinking mode, fewer tokens |
| Code tasks (implement, debug) | local | qwen3-8b | Thinking mode enabled |
| Medium complexity | openrouter | qwen3-8b:free | Free cloud fallback |
| Complex implementation | claude | opus | Deep reasoning needed |
| Architecture / security | claude | opus | Cannot compromise |
| Edit/Act modes | claude | opus | Configurable via `force_cloud_modes` |

Failover chain: configurable per profile (default: local → fleet → openrouter → claude)
Quality escalation: configurable threshold (default: score < 0.25 → auto-retry on next tier)
Complexity thresholds: configurable (default: [0.3, 0.6] → local/openrouter/claude)

### Infrastructure Target

```
Machine 1: Fleet Alpha
  ├── LocalAI Cluster 1 (GPU: 8GB VRAM)
  ├── OpenClaw Gateway + MC
  ├── Fleet Daemons
  └── 10 Agents (alpha-prefixed)

Machine 2: Fleet Bravo
  ├── LocalAI Cluster 2 (GPU: 8GB VRAM)
  ├── OpenClaw Gateway + MC
  ├── Fleet Daemons
  └── 10 Agents (bravo-prefixed)

Shared: Plane (one instance), GitHub, ntfy
LocalAI Peering: Cluster 1 ↔ Cluster 2 (load balance, failover)
```

## Development Conventions

- Python type hints on all public functions.
- Tests in `tests/` mirroring `aicp/` structure.
- Config files are YAML, loaded via `aicp/config/loader.py`.
- No secrets in code — use env vars or `.env` (gitignored).
- Keep modules small and focused. One responsibility per file.
- Prefer composition over inheritance.
- Error handling: fail loudly in dev, gracefully in production.
- Conventional commits: `type(scope): description`
- Model YAML configs tracked in git. Model binary files (*.gguf) gitignored.

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

## Reliability (Stage 4)

Production reliability infrastructure for fleet operation:

### Circuit Breaker (`aicp/core/circuit_breaker.py`)
Per-backend state machine (CLOSED → OPEN → HALF_OPEN). When a backend fails
`failure_threshold` times consecutively, the breaker OPENS and subsequent calls
fail fast — failover happens in milliseconds instead of waiting for timeouts.
After `recovery_timeout` seconds, one probe request is allowed through (HALF_OPEN).
Profile-configurable via `circuit_breaker:` section.

### Startup Warmup (`aicp/agent/server.py`)
Agent daemon pre-loads models from `warmup.models` list before accepting traffic.
Health endpoint returns `{"status": "warming"}` during load. Prevents cold-start
timeouts when fleet agents connect. Enabled per-profile (`warmup.enabled: true`).

### Deep Health Endpoint
`GET /health` checks actual backend availability (not just "agent is running").
Returns `{"status": "ok|degraded|warming", "backends": {"local": true/false}}`.
Fleet routing uses this to avoid nodes with dead LocalAI.

### Dead-Letter Queue (`aicp/core/dlq.py`)
Failed tasks (after full failover chain exhausted) are persisted to `~/.aicp/dlq/`
as JSONL. Retryable via `aicp --retry-dlq`. Profile-configurable: `dlq.max_retries`,
`dlq.retry_delay_seconds`.

### Persistent Metrics (`aicp/core/prometheus.py`)
MetricsCollector saves JSON snapshots to disk periodically. Counters survive
restarts. Configured via `metrics.persist: true`.

### Health Reports (`aicp/core/health_report.py`)
Periodic reports comparing current vs previous period stats. Detects trends
(latency increase, error rate growth, low offload). Optional ntfy notification.
Generate manually: `aicp --health-report`. Profile: `reports.enabled: true`.

### Reliability Profile
`make profile-use PROFILE=reliable` — aggressive breaker (threshold=2), auto-warmup
(qwen3-8b + nomic-embed), DLQ with 5 retries, health reports every 4 hours.

## Intelligent Infrastructure (Stage 5)

Patterns adopted from Claude Code's production architecture, adapted for AICP's
local-first, fleet-oriented design. Research: `docs/kb/research/claude-code-architecture-analysis.md`.

### Event Emitter (`aicp/core/events.py`)
Thread-safe fire-and-forget event bus. Controller emits `task_start`, `task_complete`,
`task_failed` on every task. Fleet agents can register callbacks (e.g., notify MC
dashboard, update metrics). Errors in callbacks never break the caller.

### Tool Safety Metadata (`aicp/core/tools.py`)
Every tool has fail-closed safety flags: `is_read_only`, `is_destructive`,
`is_concurrent_safe`, `requires_backend`, `requires_path`. 3-stage execution
pipeline: `validate_tool_input()` -> `check_tool_permissions()` -> `execute_tool()`.

### Task Lifecycle (`aicp/core/tasks.py`)
Real-time task tracking: `pending -> running -> completed/failed/killed`. Progress
tracking (tool use count, token count, recent activities). Agent server wraps all
`/task` requests with lifecycle management. `GET /tasks` returns active task list.

### Memory Relevance (`aicp/core/memory_relevance.py`)
Embedding-based memory selection using nomic-embed (local, free, deterministic).
Replaces loading all memories into prompt -- selects top-K most relevant per query.
Memory aging with staleness warnings for files >1 day old.

### Microcompaction (`aicp/core/compaction.py`)
Surgical pruning of old tool results while keeping conversation structure. Replaces
verbose file_read/grep/shell output with `[Tool result cleared]` markers. Time-based
clearing when >60min gap detected. Image stripping replaces vision content with
`[image]` markers.

### Skill Model Override (`aicp/core/skills.py`)
Skills can specify `model:` in frontmatter to override routing. Fleet heartbeat
skills use `gemma4-e2b` (53 tok/s), code review skills use `qwen3-8b` (thinking).
Also: `allowed-tools` (security boundary), `context: fork` (sub-agent isolation),
`paths` (scope restriction).

### Auto-Memory Extraction (`aicp/core/memory_extract.py`)
Heuristic extraction of learnable facts from task history. Scans for error fixes,
decisions, and discoveries. Saves as memory files with YAML frontmatter. Runs on
demand or as periodic background job.

### Away Summary (`aicp/agent/server.py`)
On agent shutdown, generates 1-3 sentence summary of recent work. On restart,
loads previous session context. `GET /away-summary` returns the summary.

### Extended MCP Tools (`aicp/mcp/server.py`)
11 MCP tools total: `aicp_chat`, `aicp_vision`, `aicp_transcribe`, `aicp_speak`,
`aicp_voice_pipeline`, `aicp_route` (full controller routing), `aicp_deep_health`,
`aicp_profile` (list/show/active), `aicp_kb_search_collection`, `aicp_task_status`,
`aicp_dlq_status` (list/count/retry).

## Collaboration Rules — AI Behavior Contract

These rules govern how this AI must behave in every session. Violations are tracked.

### Non-negotiable rules

1. **Answer first, act second.** If the user asks a question, answer it directly before taking any action.
2. **Ask before deciding.** If the approach requires a choice the user hasn't specified, ask.
3. **IaC only — no manual runtime commands.** All changes must be reproducible via `make setup` or code changes.
4. **No autonomous escalation.** Present options; wait for approval.
5. **Do not repeat failed approaches.** Find a different path.
6. **One step at a time.** Present the plan, wait for "go", then execute.
7. **User is in control.** The user decides what gets built, when, and how.
8. **No silent assumptions.** If something is unclear, ask.
9. **Preserve working state.** Never run destructive commands without explicit instruction.
10. **Stay in scope.** Do not refactor or "improve" things not part of the current task.

## Docker Configuration

LocalAI runs via `docker-compose.yaml`:

```yaml
# Key environment variables:
THREADS=4                          # CPU threads for inference
LLAMACPP_PARALLEL=2                # Parallel request slots
CONTEXT_SIZE=16384                 # Max context window (divided by PARALLEL)
LOCALAI_SINGLE_ACTIVE_BACKEND=false
LOCALAI_MAX_ACTIVE_BACKENDS=3      # LRU eviction (GPU model + embed + reranker)
LOCALAI_WATCHDOG_IDLE=true         # Auto-recover stuck backends
LOCALAI_WATCHDOG_IDLE_TIMEOUT=15m
LOCALAI_WATCHDOG_BUSY=true
LOCALAI_WATCHDOG_BUSY_TIMEOUT=10m
LOCALAI_AGENT_POOL_EMBEDDING_MODEL=nomic-embed  # For collections
```

Port: `8090` (host) → `8080` (container)

### Knowledge Base

KB content lives in **LocalAI Collections** (persistent, chromem-backed).
- Visible at: `http://localhost:8090/app/collections`
- Synced via: `make kb-sync` (or `make kb-sync-force` to reset + re-upload)
- Source files: `docs/kb/` (research) + `docs/knowledge-map/` (system/tool/module manuals)
- Collection name: `aicp-kb`
- Searchable via: `/api/agents/collections/aicp-kb/search`

### Observability Stack

Optional Prometheus + Grafana behind a Docker Compose profile:
```bash
make monitoring-up    # Prometheus :9090, Grafana :3000 (admin/aicp)
make monitoring-down
```
- AICP metrics: `aicp/core/prometheus.py` → `:9101/metrics`
- LocalAI metrics: built-in at `:8090/metrics`
- Alerting: `config/alerts.yaml` (7 rules: stuck model, latency, errors, swaps, quality, cost, memory)

## Configuration Profiles

Profiles are named configuration bundles that coordinate settings across backends,
router, RAG, budget, cache, timeouts, and Docker with a single switch. They sit
between `config/default.yaml` (base) and user/project overrides in the merge chain.

### Config Load Order

```
1. config/default.yaml             — repo defaults (committed)
2. config/profiles/<name>.yaml     — profile overlay (selected)
3. ~/.aicp/config.yaml             — user-level overrides
4. <project>/.aicp/config.yaml     — per-project overrides
5. --config <path>                 — explicit CLI override
```

### Available Profiles

| Profile | Primary Model | Failover | Use Case |
|---------|--------------|----------|----------|
| **default** | qwen3-8b | local→fleet→openrouter→claude | Balanced everyday use |
| **fast** | gemma4-e2b | local→openrouter | Quick responses, 53 tok/s |
| **offline** | qwen3-8b | local→fleet | No cloud, air-gapped environments |
| **thorough** | qwen3-8b | full chain | Architecture reviews, security audits |
| **code-review** | qwen3-8b | local→openrouter→claude | Code analysis, structured output |
| **fleet-light** | gemma4-e2b | local→fleet | Heartbeat node duty, 53 tok/s, 2.9GB |
| **reliable** | qwen3-8b | full chain | Production fleet — breaker, warmup, DLQ, reports |
| **dual-gpu** | qwen3-30b-a3b | full chain | Two GPUs, MoE model, expanded context |
| **benchmark** | qwen3-8b | local only | Deterministic evaluation (temp=0, seed=42) |

### What Profiles Control

Each profile can override: `backends`, `router` (complexity thresholds, failover chain,
force_cloud_modes), `mode_profiles` (sampling per mode), `rag`, `budget`, `cache`,
`quality` (escalation threshold), `timeouts` (request, cold start, retries),
`circuit_breaker`, `warmup`, `dlq`, `metrics`, `reports`,
`docker` (context size, threads, memory limit).

Profiles do NOT control: model internals (GGUF, gpu_layers), mode definitions (Think/Edit/Act),
guardrail rules, fleet topology, GPU detection, model binary downloads.

### Profile Activation (3 methods, in precedence order)

1. CLI flag: `aicp --profile fast "..."`
2. Environment variable: `AICP_PROFILE=fast`
3. `.env` file: set via `make profile-use PROFILE=fast`

### Profile Inheritance

Profiles can extend other profiles via `extends: default`. The extends chain is
resolved bottom-up with deep merge (derived overrides base). Circular extends are detected.

### Key Files

- `config/profiles/*.yaml` — profile definitions
- `aicp/core/profiles.py` — profile loader, validator, resolver, diff engine
- `tests/test_profiles.py` — 49 profile tests

## Commands

```bash
# Run tests
pytest tests/

# Run the CLI
python -m aicp.cli

# Lint
ruff check aicp/ tests/

# Format
ruff format aicp/ tests/

# Test LocalAI
curl http://localhost:8090/v1/models
curl http://localhost:8090/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"qwen3-8b","messages":[{"role":"user","content":"Hello"}]}'

# Profile management
make profile-list                              # List available profiles
make profile-show PROFILE=fast                 # Show resolved config for a profile
make profile-diff PROFILE_A=fast PROFILE_B=offline  # Compare two profiles
make profile-validate                          # Validate all profiles
make profile-use PROFILE=fast                  # Set active profile (writes .env + docker vars)

# Model management
make model-qwen3             # Download Qwen3-8B + Qwen3-4B (8GB GPU)
make model-qwen3-30b         # Download Qwen3-30B MoE (dual GPU 8+11GB only)
make model-gemma4            # Download Gemma 4 E2B + E4B (8GB GPU)
make model-gemma4-26b        # Download Gemma 4 26B MoE (dual GPU 8+11GB only)
make model-list-remote       # Show full model catalog with VRAM info
make benchmark-qwen3         # Benchmark Qwen3-8B

# Stable Diffusion 3.5 (auto-handled by make setup if CUDA + HF token available)
make build-libgosd           # Rebuild libgosd.so for SD 3.5 support (auto in setup)
make sd35-test               # Generate SD 3.5 image via LocalAI API
make model-sd35-safetensors  # Download SD 3.5 safetensors (needs HF token in .env)

# Knowledge Base (syncs to LocalAI Collections — visible at :8090/app/collections)
make kb-sync                 # Upload KB docs to LocalAI collection
make kb-sync-force           # Reset collection + re-upload everything

# Observability
make monitoring-up           # Start Prometheus (:9090) + Grafana (:3000)
make monitoring-down         # Stop monitoring stack

# Reliability (Stage 4)
aicp --health-report                   # Generate health report with trends
aicp --profile-cmd use --profile reliable  # Switch to production reliability profile

# Docker
docker compose up -d                    # Start LocalAI
docker compose restart localai          # Restart (picks up new model configs)
docker logs devops-expert-local-ai-localai-1 --tail 20  # Check logs
docker stats                            # Monitor resource usage
```

## AICP ↔ Fleet Connection

AICP provides LocalAI inference to the fleet ecosystem:
- `aicp/core/rag.py` — SQLite vector store, cosine similarity (fleet RAG)
- `aicp/core/kb.py` — Knowledge base, file ingestion, BGE reranker
- `aicp/core/stores.py` — LocalAI /stores/ API client
- `aicp/core/router.py` — Score-based routing with configurable thresholds
- `aicp/core/skills.py` — 3-layer skill system (78 skills in .claude/skills/)
- `aicp/core/circuit_breaker.py` — Prevents thundering herd from fleet agents
- `aicp/core/dlq.py` — Persists failed tasks for retry

Skills in AICP needed by fleet agents (18 skills referenced in fleet's
config/agent-tooling.yaml): architecture-propose, feature-implement,
quality-coverage, foundation-docker, pm-plan, ops-deploy, etc.

## Related Projects

- **OpenFleet**: `../openfleet/` (10-agent orchestration framework)
- **OpenArms**: `../openarms/` (AI assistant vendor/runtime)
- **DSPD**: `../devops-solution-product-development/` (project management via Plane)
- **NNRT**: `../Narrative-to-Neutral-Report-Transformer/` (report transformation)
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
