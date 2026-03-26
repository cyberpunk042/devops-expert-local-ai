# AICP — AI Control Platform

A personal AI control workspace that lets you choose a backend, choose a project, choose a mode, and run tasks under your control.

## What is this?

AICP is a controller layer that orchestrates AI backends — local models via LocalAI and cloud models via Claude Code — through a single interface with strict permission boundaries.

```
You → AICP → (LocalAI | Claude Code) → Your Project
```

## Core Concepts

### Modes (permission levels)

| Mode | Can Do | Cannot Do |
|------|--------|-----------|
| **Think** | Read files, analyze, plan | Edit files, run commands |
| **Edit** | Modify allowed files, produce diffs | Run commands, touch protected paths |
| **Act** | Run commands, workflows, tools | Bypass guardrails |

### Backends

| Backend | Use When |
|---------|----------|
| **LocalAI** | Default. Fast, private, most tasks. |
| **Claude Code** | Complex reasoning, coding, escalation. |

## Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd devops-expert-local-ai
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run
python -m aicp.cli --mode think --backend local "analyze this project"
```

## Project Status

**v0.1 — Foundation** (in progress)

- [ ] Project structure and core interfaces
- [ ] Mode enforcement (Think/Edit/Act)
- [ ] LocalAI backend integration
- [ ] Claude Code backend integration (subprocess)
- [ ] CLI entry point
- [ ] Basic guardrails

## Principles

1. You are in control, not the AI
2. Backends are tools, not masters
3. Local-first, cloud when needed
4. Keep v1 simple and usable
5. Add complexity only when it earns its place

## License

Private — personal project.
