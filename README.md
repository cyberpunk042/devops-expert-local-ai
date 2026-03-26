# AICP — AI Control Platform

A personal AI control workspace that lets you choose a backend, choose a project, choose a mode, and run tasks under your control.

## What is this?

AICP is a controller layer that orchestrates AI backends — local models via LocalAI and cloud models via Claude Code — through a single interface with strict permission boundaries.

```
You → AICP → (LocalAI | Claude Code) → Your Project
```

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Start LocalAI
make local-up

# Check everything works
aicp --check

# Ask a question
aicp "What does this project do?" -m think -b local

# Interactive chat
aicp -i
```

## CLI Reference

```bash
# Single query
aicp "your prompt"                          # think mode, local backend (defaults)
aicp "fix the bug" -m edit -b claude        # edit mode, claude backend

# Modes: think (read-only), edit (file changes), act (commands)
aicp "analyze" -m think
aicp "refactor" -m edit
aicp "run tests" -m act

# Backends: local (LocalAI), claude (Claude Code)
aicp "explain" -b local
aicp "complex refactor" -b claude

# Interactive chat (LocalAI, keeps conversation history)
aicp -i
aicp -i -m edit

# Continue Claude Code session
aicp -c
aicp -c "keep going"

# System check
aicp --check

# Task history
aicp --history          # last 20 tasks
aicp --history 5        # last 5
aicp --replay <ID>      # replay full output

# Project targeting
aicp "analyze" -d /path/to/project
```

## Environment Variables

```bash
export AICP_DEFAULT_MODE=think       # default --mode
export AICP_DEFAULT_BACKEND=local    # default --backend
export AICP_PROJECT_PATH=/my/project # default --project
export AICP_HISTORY_DIR=~/.aicp/history  # history location
```

## Shell Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias think='aicp -m think -b local'
alias ask='aicp -m think -b claude'
alias edit='aicp -m edit -b claude'
alias act='aicp -m act -b claude'
alias chat='aicp -i'
```

## Modes

| Mode | Can Do | Cannot Do |
|------|--------|-----------|
| **Think** | Read files, analyze, plan | Edit files, run commands |
| **Edit** | Modify allowed files, produce diffs | Run commands, touch protected paths |
| **Act** | Run commands, workflows, tools | Bypass guardrails |

## Backends

| Backend | Use When | Enforcement |
|---------|----------|-------------|
| **LocalAI** | Default. Fast, private. | Advisory (system prompt) |
| **Claude Code** | Complex reasoning, coding. | Hard (CLI flags) |

## LocalAI Setup

```bash
# Build and start (requires Docker + NVIDIA GPU)
make local-up

# Check status
make local-status

# View logs
make local-logs

# Stop
make local-down
```

## Principles

1. You are in control, not the AI
2. Backends are tools, not masters
3. Local-first, cloud when needed
4. Keep v1 simple and usable
5. Add complexity only when it earns its place
