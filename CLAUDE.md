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

## The Mission

**LocalAI independence.** Progressive offload from Claude to LocalAI. 5 stages:

1. **Make LocalAI functional** ← CURRENT (assessment done, models working)
2. **Route simple operations to LocalAI** — inference router
3. **Progressive offload** — heartbeats, simple reviews, status checks
4. **Reliability and failover** — graceful degradation, cluster peering
5. **Near-independent operation** — 80%+ Claude token reduction

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
- **Local AI Gateway**: LocalAI (OpenAI-compatible API, Docker, GPU via WSL2)
- **Cloud Backend**: Claude Code CLI (invoked as subprocess)
- **Config**: YAML files in `config/`
- **Logging**: structured JSON logs
- **GPU**: NVIDIA via WSL2 `/dev/dxg`, 8GB VRAM
- **Model management**: Single-active backend (one GPU model at a time, swap on demand)

## Project Structure

```
aicp/                      # Main package (46 modules)
  core/                    # Controller, modes, router, session, pipeline, budget, metrics
    controller.py          # Central orchestrator — mode enforcement + backend dispatch
    router.py              # Backend routing — LocalAI vs Claude by task complexity
    modes.py               # Think/Edit/Act mode definitions and enforcement
    pipeline.py            # Request processing pipeline
    session.py             # Session management
    budget.py              # Token budget tracking
    metrics.py             # Performance metrics
    observability.py       # Tracing and monitoring
    context.py             # Context management
    tools.py               # Tool definitions
    skills.py              # Skill loading and execution
    worktree.py            # Git worktree management
    projects.py            # Project registry
    rag.py                 # Retrieval-augmented generation
    kb.py                  # Knowledge base
    stores.py              # Data stores
    db.py                  # Database operations
    gpu.py                 # GPU management
    cluster.py             # Multi-machine cluster support
    chunking.py            # Text chunking for embeddings
    history.py             # Conversation history
    models.py              # Model info and configuration
    result.py              # Result types
    approval.py            # Approval workflows
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
    server.py              # Agent server (MCP)
  mcp/                     # MCP server
    server.py              # MCP tool server for AICP
tests/                     # Test suite (67 test files)
config/                    # Default config files
  default.yaml             # Default AICP configuration
  fleet.yaml               # Fleet network topology
  *.yaml.template          # Model config templates
models/                    # LocalAI model files (gitignored binaries, tracked YAML configs)
  hermes.yaml              # Hermes 2 Pro Mistral 7B (complex reasoning)
  hermes-3b.yaml           # Hermes 3 Llama 3.2 3B (fleet heartbeats target)
  codellama.yaml           # CodeLlama 7B (code tasks)
  phi-2.yaml               # Phi-2 2.7B (CPU fallback)
  llava.yaml               # LLaVA 7B (vision)
  whisper-1.yaml           # Whisper (speech-to-text)
  piper-tts.yaml           # Piper (text-to-speech)
  bge-reranker-v2-m3.yaml  # BGE reranker (search)
  stablediffusion.yaml     # Stable Diffusion (image generation)
docs/                      # Architecture and planning documents
```

## LocalAI Assessment (Stage 1 — 2026-03-29)

LocalAI is running and functional on Docker with GPU acceleration.

### Models Available

| Model | Config | Size | Cold Start | Warm | GPU Layers | Use Case |
|-------|--------|------|------------|------|------------|----------|
| hermes (7B) | `hermes.yaml` | 4.4GB | ~80s | ~1s | 24 | Complex reasoning, multi-step |
| **hermes-3b (3B)** | `hermes-3b.yaml` | 2.0GB | **~10s** | **~1.2s** | 32 | **Fleet heartbeats** (target) |
| codellama (7B) | `codellama.yaml` | 4.4GB | ~80s | ~1s | GPU | Code generation, completion |
| phi-2 (2.7B) | `phi-2.yaml` | 1.6GB | fast | fast | 0 (CPU) | Fallback, light tasks |
| llava (7B) | `llava.yaml` | 4.4GB | ~80s | ~1s | GPU | Vision + language |
| whisper | `whisper-1.yaml` | — | — | — | — | Speech-to-text |
| piper-tts | `piper-tts.yaml` | — | — | — | — | Text-to-speech |
| bge-reranker | `bge-reranker-v2-m3.yaml` | — | — | — | — | Search reranking |
| stablediffusion | `stablediffusion.yaml` | — | — | — | — | Image generation |

### Key Findings

- **API**: OpenAI-compatible chat completions working (`localhost:8090`)
- **Single-active backend**: Only one GPU model loaded at a time (8GB VRAM limit, `LOCALAI_SINGLE_ACTIVE_BACKEND=true`)
- **Cold start**: Model swap takes 10-80s depending on model size
- **Warm inference**: 1-1.2s for both 7B and 3B
- **Quality**: hermes correctly follows structured instructions
- **Watchdog**: Auto-recover stuck backends (`LOCALAI_WATCHDOG_IDLE=true`, 15m timeout)
- **GPU**: NVIDIA via WSL2 `/dev/dxg`, CUDA 12

### Routing Strategy (Stage 2 target)

| Operation | Backend | Why |
|-----------|---------|-----|
| Heartbeat (no work) | hermes-3b (LocalAI) | Just read context + HEARTBEAT_OK, 0 Claude tokens |
| fleet_read_context | Direct HTTP (no LLM) | Just API calls to MC |
| fleet_agent_status | Direct HTTP (no LLM) | Same |
| fleet_chat post | hermes-3b (LocalAI) | Posting a message ≠ reasoning |
| Simple task acceptance | hermes-3b (LocalAI) | Structured plan output |
| Simple review (test pass/fail) | hermes-3b (LocalAI) | Pattern matching |
| Complex implementation | Claude (opus) | Deep reasoning needed |
| Architecture design | Claude (opus) | Creative thinking needed |
| Security analysis | Claude (opus) | Cannot compromise |
| Sprint planning | Claude (opus) | Strategic thinking needed |

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
LLAMACPP_PARALLEL=4                # Parallel request handling
CONTEXT_SIZE=8192                  # Max context window
LOCALAI_SINGLE_ACTIVE_BACKEND=true # One GPU model at a time (8GB VRAM)
LOCALAI_WATCHDOG_IDLE=true         # Auto-recover stuck backends
LOCALAI_WATCHDOG_IDLE_TIMEOUT=15m
LOCALAI_WATCHDOG_BUSY=true
LOCALAI_WATCHDOG_BUSY_TIMEOUT=5m
```

Port: `8090` (host) → `8080` (container)

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
  -d '{"model":"hermes-3b","messages":[{"role":"user","content":"Hello"}]}'

# Docker
docker compose up -d                    # Start LocalAI
docker compose restart localai          # Restart (picks up new model configs)
docker logs devops-expert-local-ai-localai-1 --tail 20  # Check logs
docker stats                            # Monitor resource usage
```

## AICP ↔ Fleet Connection

AICP modules that fleet will connect to (NOT yet wired):
- `aicp/core/rag.py` — SQLite vector store, cosine similarity (fleet RAG)
- `aicp/core/kb.py` — Knowledge base, file ingestion, BGE reranker
- `aicp/core/stores.py` — LocalAI /stores/ API client
- `aicp/core/router.py` — Backend routing (AICP version → fleet bridge)
- `aicp/core/skills.py` — 3-layer skill system (78 skills in .claude/skills/)

Skills in AICP needed by fleet agents (18 skills referenced in fleet's
config/agent-tooling.yaml): architecture-propose, feature-implement,
quality-coverage, foundation-docker, pm-plan, ops-deploy, etc.

## Related Projects

- **Fleet navigation**: `../openclaw-fleet/docs/README.md` (start here for fleet docs)
- **Fleet architecture**: `../openclaw-fleet/docs/ARCHITECTURE.md`
- **Fleet work backlog**: `../openclaw-fleet/docs/WORK-BACKLOG.md`
- **DSPD mission**: `../devops-solution-product-development/config/mission.yaml`
- **LocalAI strategic vision**: `../openclaw-fleet/docs/milestones/active/strategic-vision-localai-independence.md`