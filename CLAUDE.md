# CLAUDE.md — AI Control Platform (AICP)

## Project Overview

AICP is a personal AI control workspace that orchestrates local and cloud AI backends (LocalAI, Claude Code) through a unified controller. The user is always in control — AI backends are tools, not masters.

## Architecture

```
User → AICP Controller → (LocalAI | Claude Code) → Project/Repo
```

### Three Permission Modes

- **Think** — read, analyze, plan. No edits, no commands.
- **Edit** — modify files in a controlled scope. Produce patches/diffs.
- **Act** — run commands, workflows, tools. Highest power, most controlled.

### Two Backends

- **LocalAI** — fast, private, default for most tasks.
- **Claude Code** — stronger reasoning/coding, used for complex tasks and escalation.

## Tech Stack

- **Language**: Python 3.11+
- **Local AI Gateway**: LocalAI (OpenAI-compatible API)
- **Cloud Backend**: Claude Code CLI (invoked as subprocess)
- **UI (planned)**: Open WebUI or custom TUI
- **Config**: YAML files
- **Logging**: structured JSON logs

## Project Structure

```
aicp/                  # Main package
  core/                # Controller, mode enforcement, backend routing
  backends/            # LocalAI and Claude Code integrations
  guardrails/          # Permission enforcement, path protection
  config/              # Configuration loading and validation
  cli/                 # CLI entry point
tests/                 # Test suite
config/                # Default config files
docs/                  # Documentation
```

## Development Conventions

- Use Python type hints everywhere.
- Tests go in `tests/` mirroring `aicp/` structure.
- Config files are YAML, loaded via `aicp/config/`.
- No secrets in code — use env vars or `.env` (gitignored).
- Keep modules small and focused. One responsibility per file.
- Prefer composition over inheritance.
- Error handling: fail loudly in dev, gracefully in production.

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
```
