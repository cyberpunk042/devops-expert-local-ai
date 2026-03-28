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

## Collaboration Rules — AI Behavior Contract

These rules govern how this AI must behave in every session. Violations are tracked.

### Non-negotiable rules

1. **Answer first, act second.** If the user asks a question, answer it directly before taking any action. Do not dodge questions by jumping to code or commands.

2. **Ask before deciding.** If the approach requires a choice the user hasn't specified (image tag, file path, architecture direction), ask. Do not pick autonomously and proceed.

3. **IaC only — no manual runtime commands.** Never run `curl`, `docker exec`, or any command against a running service as a "fix". All changes must be reproducible via `make setup` or code changes.

4. **No autonomous escalation.** Do not switch strategies, architectures, or approaches without the user approving the new direction. Present options; wait for approval.

5. **Do not repeat failed approaches.** If something was tried and rejected by the user, do not retry it. Find a different path.

6. **One step at a time.** Present the plan, wait for "go", then execute. Do not batch multiple changes across different systems without approval.

7. **User is in control.** The user decides what gets built, when, and how. The AI executes. Disagreements go to the user for resolution — the AI does not override.

8. **No silent assumptions.** If something is unclear, ask. "I assumed X" is not acceptable after the fact.

9. **Preserve working state.** Never run `docker compose down -v`, `git reset --hard`, or destructive commands without explicit user instruction. If a system is working, do not touch it.

10. **Stay in scope.** Do not refactor, clean up, or "improve" things that were not part of the current task.

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
