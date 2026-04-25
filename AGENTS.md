# AGENTS.md — AICP (universal cross-tool agent context)

This file is the **universal layer** of AICP's three-layer agent context (per the second brain's [Three-Layer Agent Context Architecture](wiki/config/wiki-schema.yaml) pattern, validated by ETH Zurich Feb 2026 research). Any AI agent — Claude Code, Codex CLI, Copilot, Cursor, Gemini, MCP clients from other projects — reads this first. Tool-specific overrides live in [CLAUDE.md](CLAUDE.md) (Claude Code) and similar `*.md` files.

## Identity (canonical)

Source of truth: [CLAUDE.md `## Identity Profile`](CLAUDE.md). The brain's view: `python3 -m tools.gateway status`.

Stable: type=product (backend AI platform); domain=backend-ai-platform-python; second-brain=connected.
State: phase=production — **Post-Anthropic mission functionally reached 2026-04-25** (Ollama Cloud Pro + OpenRouter K2.6 pinned + local K2.6 sovereignty fallback; Anthropic gated last-resort); Stage 3 hardware unlocked 2026-04-17 (19GB VRAM + 64GB RAM); scale=medium (64 modules / 97 test files / 1,840 tests / 84 skills / 11 profiles).

**Consumer/task properties NOT declared here** (per the consumer-property doctrine — `wiki/lessons/01_drafts/execution-mode-is-consumer-property-not-project-property.md`): execution mode (default solo), SDLC profile (default), methodology model (per-task). Set these per task at the consumer's runtime.

## Sacrosanct operator directives (verbatim — non-negotiable)

> "Its important that the main first mission is to make localAI functional and then make it more and more reliable to offload as much as possible the work from claude till one day maybe even try to actually run independently as much as possible."

> "User is in control. Backends are tools, not masters."

## Hard rules (MANDATORY — apply to every AI tool reading this project)

1. **Answer first, act second.** Question → answer directly before acting.
2. **Ask before deciding.** Approach choice the user hasn't specified → ask.
3. **IaC only.** All changes reproducible via `make setup` or code changes. No manual runtime commands.
4. **No autonomous escalation.** Present options; wait for approval.
5. **Do not repeat failed approaches.** Find a different path.
6. **One step at a time.** Plan → "go" → execute.
7. **User is in control.** User decides what gets built, when, and how.
8. **No silent assumptions.** Unclear → ask.
9. **Preserve working state.** No destructive commands without explicit instruction.
10. **Stay in scope.** No refactoring beyond the current task.

## Stage gates (per second brain methodology)

Methodology config: [wiki/config/methodology.yaml](wiki/config/methodology.yaml). Domain profile: [wiki/config/domain-profiles/backend-ai-platform-python.yaml](wiki/config/domain-profiles/backend-ai-platform-python.yaml).

| Stage | Readiness | ALLOWED (AICP backend domain) | FORBIDDEN |
|-------|-----------|-------------------------------|-----------|
| **document** | 0-25 | `wiki/**/*.md`, `docs/**/*.md` (understanding, gap analysis) | `aicp/`, `tests/`, `config/profiles/` |
| **design** | 25-50 | `wiki/decisions/**/*.md`, `wiki/domains/**/*.md`, ADRs, tech specs | `aicp/`, `tests/`, `config/profiles/` |
| **scaffold** | 50-80 | Type aliases, Protocols, YAML configs, pytest stubs, templates | Business logic, real assertions |
| **implement** | 80-95 | `aicp/**/*.py` business logic; new code MUST be wired (imported by ≥1 existing file or exposed via CLI/MCP) | Test modifications |
| **test** | 95-100 | `tests/test_*.py`, integration tests | Source modifications |

**Never skip stages.** "Continue" = advance within current stage, not skip ahead.

## Methodology models (9 chains via gateway)

Selected per task by the consumer. Menu via `python3 -m tools.gateway query --chains`.

| Model | Chain | When |
|-------|-------|------|
| feature-development | document → design → scaffold → implement → test | New capability |
| bug-fix | document → implement → test | Fix something broken |
| hotfix | implement → test | Urgent fix, design known |
| research | document → design | Investigate, no implementation |
| refactor | document → scaffold → implement → test | Restructure existing code |
| integration | scaffold → implement → test | Wire up pre-designed pieces |
| documentation | document | Knowledge artifacts only |
| knowledge-evolution | document → implement | Promote existing content/code |
| project-lifecycle | scaffold → foundation → infrastructure → features | SFIF for whole projects |

## Quality gates (per stage, AICP-specific)

Defined in [wiki/config/domain-profiles/backend-ai-platform-python.yaml](wiki/config/domain-profiles/backend-ai-platform-python.yaml):

- **document/design**: `ruff check --select F,E aicp/ tests/` (syntax + undefined names)
- **scaffold**: `ruff check aicp/ tests/` + `ruff format --check`
- **implement**: ruff check + format + `pytest tests/ -x --tb=short` (fail fast)
- **test**: ruff check + format + full `pytest tests/` + test count drift check

Three-layer defense (per Quality Standards):
- **Structural prevention** (≈98% compliance): backend guardrails (`aicp/guardrails/`), CI ruff/pytest, IaC enforcement
- **Teaching** (≈60%): this file + CLAUDE.md + skills + memory
- **Review** (100% when engaged): user reviews approval-gated actions

## Where to find things

| Need | Path |
|------|------|
| Tool-specific behavior (Claude Code) | [CLAUDE.md](CLAUDE.md) |
| Mission + roadmap | [CLAUDE.md `## The Mission`](CLAUDE.md) |
| Architecture | [CLAUDE.md `## Architecture`](CLAUDE.md) |
| Backend/router internals | [aicp/core/](aicp/core/) — controller, router, modes, profiles, circuit_breaker, dlq, etc. |
| Operational profiles (11) | [config/profiles/](config/profiles/) |
| Model configs (19) | [config/models/](config/models/) |
| Skills (84, conditional) | [.claude/skills/](.claude/skills/) |
| Knowledge wiki | [wiki/](wiki/) — config, backlog, lessons, patterns, decisions |
| Second brain (canonical methodology) | `python3 -m tools.gateway` (forwards to `~/devops-solutions-research-wiki`) |
| Adoption status | `python3 -m tools.gateway compliance` (Tier 4/4 STRUCTURAL as of 2026-04-17) |

## How to operate the project

```bash
# Tests
pytest tests/                    # full suite (1,840 tests)
pytest tests/ -x --tb=short      # fail-fast for active dev

# Lint + format
ruff check aicp/ tests/
ruff format aicp/ tests/

# CLI
python -m aicp.cli               # interactive
python -m aicp.cli --help        # subcommands

# LocalAI
docker compose up -d             # start LocalAI on :8090
curl http://localhost:8090/v1/models

# Profiles
make profile-list
make profile-use PROFILE=fast    # writes .env + restarts containers
make profile-show PROFILE=reliable
make profile-diff PROFILE_A=fast PROFILE_B=offline

# Models
make model-qwen3                 # Qwen3-8B + Qwen3-4B (8GB GPU)
make model-list-remote           # full catalog with VRAM info

# Knowledge base (LocalAI Collections)
make kb-sync                     # sync docs/kb/ to LocalAI
make kb-sync-force               # reset + re-upload

# Observability
make monitoring-up               # Prometheus :9090 + Grafana :3000

# Reliability
aicp --health-report             # trend report
aicp --retry-dlq                 # retry failed tasks

# Second brain
python3 -m tools.gateway status     # identity + SDLC profile
python3 -m tools.gateway compliance # adoption tier
python3 -m tools.gateway orient     # full orientation flow
```

## Conventions

- Python type hints on all public functions
- Tests mirror `aicp/` structure
- YAML configs via `aicp/config/loader.py`
- No secrets in code (use `.env`, gitignored)
- One responsibility per file; small focused modules; composition over inheritance
- Conventional commits: `type(scope): description`
- Model YAML configs tracked in git; `*.gguf` binaries gitignored

## Related projects

- **OpenFleet** [`../openfleet/`](../openfleet/) — 10-agent orchestration framework consuming AICP backends
- **OpenArms** [`../openarms/`](../openarms/) — AI assistant vendor/runtime
- **DSPD** [`../devops-solution-product-development/`](../devops-solution-product-development/) — project management via Plane
- **NNRT** [`../Narrative-to-Neutral-Report-Transformer/`](../Narrative-to-Neutral-Report-Transformer/) — report transformation
- **Second brain (research wiki)** [`~/devops-solutions-research-wiki/`](file:///home/jfortin/devops-solutions-research-wiki/) — methodology + standards + patterns + lessons

## Reading order for a new agent

1. This file (universal rules + stage gates + where to find things)
2. [CLAUDE.md](CLAUDE.md) Identity Profile + Mission (project-specific context)
3. [wiki/backlog/_index.md](wiki/backlog/_index.md) (current work tracking)
4. Tool-specific overrides if applicable (CLAUDE.md for Claude Code; future: CODEX.md, COPILOT.md, etc.)
5. Skills loaded conditionally on demand from `.claude/skills/`

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
