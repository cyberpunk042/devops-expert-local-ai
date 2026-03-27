# AICP — AI Control Platform

A personal AI control workspace that orchestrates local and cloud AI backends under your control — not theirs.

```
You → AICP → (LocalAI | Claude Code) → Your Project
```

## Quick Start

```bash
# Full setup: venv, deps, model download, LocalAI build (one command)
make setup

# Check everything is working
make check           # or: aicp --check

# Ask a question
aicp "What does this project do?"

# Run interactively
make                 # shows all available targets
```

## One-Command Setup

```bash
make setup                    # auto-selects model by VRAM (6 GB+)
make setup-low-vram           # phi3-mini (3 GB VRAM)
make setup-claude-only        # Python + Claude Code, no LocalAI
make setup-force              # re-run all steps even if already done
make check-prereqs            # check Python / Docker / GPU before setup
```

### GPU Acceleration (NVIDIA)

If `make setup` reports *GPU passthrough NOT working*, run:

```bash
make install-nvidia-toolkit   # installs NVIDIA Container Toolkit (requires sudo)
make setup-force              # rebuilds LocalAI image + regenerates model YAML with CUDA backend
make check                    # verify GPU passthrough now passes
```

This is a one-time step. After that, inference runs fully on your GPU.

## CLI Reference

```bash
# Single-shot query
aicp "your prompt"                          # think + local (defaults)
aicp "fix the auth bug" -m edit -b claude   # edit mode, Claude Code
aicp "your prompt" -b auto                  # smart backend routing

# Permission modes: think (read-only), edit (file changes), act (run commands)
aicp "explain this" -m think
aicp "refactor this" -m edit
aicp "run the tests" -m act

# Backends
aicp "explain" -b local                     # LocalAI (fast, private)
aicp "complex refactor" -b claude           # Claude Code (stronger reasoning)
aicp "help me" -b auto                      # auto-route by prompt complexity

# Streaming (real-time output)
aicp "explain quantum computing" --stream
aicp "explain" --stream -b local            # LocalAI streaming (SSE)
aicp "explain" --stream -b claude           # Claude Code streaming

# Conversation sessions — persist history across single-shot calls
aicp --session myfeature "What files are in auth?"
aicp --session myfeature "Show me the login function"
aicp --session-list                         # list saved sessions
aicp --session-delete myfeature             # delete a session

# Interactive REPL (LocalAI, streaming by default)
aicp -i
aicp -i -m edit --stream

# Continue Claude Code sessions
aicp -c                                     # continue last session
aicp -c "keep going"
aicp -r my-session "resume"                 # resume by name/ID

# System health
aicp --check                                # config + backend + GPU
aicp --check --router-debug "explain X"    # show routing decision table

# Task history and replay
aicp --history                              # last 20 tasks
aicp --history 5                            # last 5
aicp --replay <ID>                          # replay full output

# Metrics
aicp --stats                                # summary + per-backend table (local vs. claude)

# Dashboard (live TUI, Ctrl+C to exit)
aicp --dashboard

# Control plane (project overview)
aicp --control                              # all registered projects
aicp --control myproject                    # deep dive into one project

# Router debug — see why a backend was chosen
aicp --router-debug "refactor the auth module" -b auto

# Approval workflow
aicp --approval "deploy to staging" -m act  # plan first, execute on approval

# Pipeline
aicp --pipeline workflow.yaml               # run multi-step pipeline

# Model management
aicp --models list                          # local models
aicp --models info hermes                   # model config
aicp --models benchmark --models-arg hermes # latency benchmark
aicp --auto-config                          # GPU-aware config optimiser

# Skills
aicp --skill list
aicp --skill run --skill-name code-review
aicp --skill create --skill-name my-skill

# Project management
aicp --project-cmd register -d /path/to/project --project-name myapp
aicp --project-cmd list
aicp --project-cmd status -d /path/to/project

# Targeting a project directory
aicp "analyze" -d /path/to/project
```

## Modes

| Mode | Can Read | Can Edit Files | Can Run Commands |
|------|----------|---------------|-----------------|
| **think** | ✓ | — | — |
| **edit** | ✓ | ✓ (allowed paths only) | — |
| **act** | ✓ | ✓ | ✓ |

## Backends

| Backend | Speed | Privacy | Mode Enforcement |
|---------|-------|---------|-----------------|
| **local** (LocalAI) | Fast | 100% local | Advisory (system prompt) |
| **claude** (Claude Code) | Slower | Cloud | Hard (CLI flags) |
| **auto** | — | — | Routes by prompt complexity |

## Environment Variables

```bash
# Defaults
export AICP_DEFAULT_MODE=think
export AICP_DEFAULT_BACKEND=local
export AICP_PROJECT_PATH=/my/project

# Storage
export AICP_HOME=~/.aicp                    # base dir for history, sessions, config
export AICP_HISTORY_DIR=~/.aicp/history     # override history location

# Observability
export AICP_LOG_FILE=~/.aicp/events.jsonl   # append JSONL event log per task
export AICP_DB_FILE=~/.aicp/metrics.db      # SQLite metrics (query with sqlite3)
```

## Shell Aliases

```bash
make install-aliases   # adds these to ~/.bashrc / ~/.zshrc automatically

alias think='aicp -m think -b local'
alias ask='aicp -m think -b claude'
alias edit='aicp -m edit -b claude'
alias act='aicp -m act -b claude'
alias chat='aicp -i'
alias thinkauto='aicp -m think -b auto'
```

## LocalAI Commands

```bash
make local-up          # start LocalAI container
make local-down        # stop
make local-status      # container + API status
make local-logs        # tail container logs
make local-up-multi    # multi-GPU (docker-compose.multi-gpu.yaml)

# Model management
make model-list-remote            # curated catalog (7 models) with VRAM/size
make models-list                  # models currently loaded in running LocalAI
make model-download MODEL=f.gguf URL=https://...
```

## Development

```bash
make test              # unit tests (fast, no live backends needed)
make test-all          # all tests including integration
make lint              # ruff check
make format            # ruff format
make type-check        # mypy static analysis
make check             # aicp --check (live backend health)
make benchmark         # model latency benchmark
make db-rebuild        # rebuild SQLite metrics DB from history JSON files
```

## Agent Daemon

```bash
make agent-up          # start aicp-agent on port 9100 (PID-tracked)
make agent-down        # stop
make install-service   # install as systemd user service (auto-start on login)
make uninstall-service # remove service
```

## Guardrails

- **Think mode** — read-only; response scanner warns if local model outputs shell commands or file writes
- **Edit/Act mode** — blocked on forbidden paths (`.env`, `*.key`, `*secret*`, `.ssh/`) and optional `guardrails.allowed_paths` whitelist
- **Secret-leak detection** — all responses scanned for AWS keys, JWTs, private key blocks, GitHub PATs, bearer tokens
- **VRAM-aware setup** — `make setup` auto-selects the largest model that fits your GPU

## SQLite Metrics

```bash
export AICP_DB_FILE=~/.aicp/metrics.db
make db-rebuild        # import existing history

# Query examples
sqlite3 ~/.aicp/metrics.db "SELECT backend, COUNT(*), AVG(duration_seconds) FROM tasks GROUP BY backend;"
sqlite3 ~/.aicp/metrics.db "SELECT DATE(timestamp) AS day, SUM(total_tokens) FROM tasks GROUP BY day;"
```

## Principles

1. You are in control, not the AI
2. Backends are tools, not masters
3. Local-first, cloud when needed
4. Keep it simple and usable
5. Add complexity only when it earns its place
