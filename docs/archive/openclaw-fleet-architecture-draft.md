# OpenClaw Fleet — Architecture

## Core Principle

**openclaw-mission-control is the center.** It provides the operations surface: UI, API, task management, agent lifecycle, approvals, activity logging. Our code plugs into it as a **gateway** — receiving work, executing it through Claude Code, and reporting results back.

We don't rebuild what mission-control already does. We feed it and dance with it.

## Decisions

| Question | Decision |
|----------|----------|
| Tech stack | Python gateway + mission-control (FastAPI/Next.js/Postgres/Redis) |
| Agent execution | Mix: definition agents (on-demand) and persistent agents (services) |
| AI backend | Direct Claude Code CLI |
| Mission-control role | **Central operations surface** — the UI, the API, the brain |
| Our role | **Gateway** — execute work, provide AI capabilities |

## How It Works

```
User ──→ Mission Control (UI/API)
              │
              ├── Agent management (create, configure, monitor)
              ├── Task boards (assign, track, approve)
              ├── Activity log (audit trail)
              │
              └── Gateway dispatch ──→ OCF Gateway (our code)
                                          │
                                          ├── Claude Code CLI (complex work)
                                          ├── LocalAI (lightweight analysis)
                                          └── Agent logic (custom per-agent)
```

## Mission Control Already Has

From their codebase:

| Component | Files | What It Does |
|-----------|-------|-------------|
| Agent model | `models/agents.py` | Agent registration, state, lifecycle |
| Task system | `models/tasks.py`, `boards.py` | Task boards, groups, dependencies, custom fields |
| Gateway system | `services/openclaw/gateway_*.py` | Dispatch work to external runtimes |
| Approvals | `models/approvals.py` | Human-in-the-loop approval flows |
| Skills marketplace | `api/skills_marketplace.py` | Skill distribution and discovery |
| Activity log | `models/activity_events.py` | Full audit trail |
| Queue | `services/queue.py` | Background job processing (Redis/RQ) |
| Organizations | `models/organizations.py` | Multi-team support |
| Webhooks | `models/board_webhooks.py` | Event notifications |

**We don't rebuild any of this.**

## What We Build

### 1. OCF Gateway (Python)

A gateway service that mission-control dispatches work to. Implements the gateway protocol that mission-control expects (`gateway_rpc.py`, `gateway_dispatch.py`).

**Responsibilities:**
- Receive task assignments from mission-control
- Execute tasks through Claude Code CLI or LocalAI
- Report results, status updates, and costs back
- Manage local execution environment (worktrees, sessions)

### 2. Agent Definitions

Configuration and context for each agent. Stored in mission-control's agent model AND locally as files for Claude Code context.

**Per-agent:**
- `agent.yaml` — capabilities, constraints, budget, mode
- `context/` — files that give Claude Code project-specific knowledge
- `CLAUDE.md` — instructions when Claude Code works on this agent's tasks
- For persistent agents: source code, Dockerfile, tests

### 3. Custom Skills

OCF-specific skills registered in mission-control's skills marketplace AND as Claude Code skills locally.

- `add-subagent` — scaffold a new agent with mission-control registration
- `define-mission` — create a structured mission in mission-control's task format
- `execute-mission` — run a mission through the gateway

### 4. Mission-Control Configuration

Docker compose that brings up mission-control alongside our gateway.

## Directory Structure

```
openclaw-fleet/
├── README.md
├── CLAUDE.md
├── docker-compose.yaml           # mission-control + our gateway + postgres + redis
├── .env.example
├── .aicp/state.yaml              # AICP project tracking
├── .claude/skills/               # OCF-specific Claude Code skills
│
├── gateway/                      # Our gateway service (Python)
│   ├── __init__.py
│   ├── server.py                 # Gateway endpoint that mission-control talks to
│   ├── executor.py               # Claude Code CLI / LocalAI execution
│   ├── config.py                 # Gateway configuration
│   └── Dockerfile
│
├── agents/                       # Agent definitions
│   ├── accountability-generator/ # ocf-tag
│   │   ├── agent.yaml
│   │   ├── CLAUDE.md
│   │   ├── context/              # Agent-specific knowledge files
│   │   └── src/                  # Source (for persistent agents)
│   └── _template/                # Template for new agents
│       ├── agent.yaml
│       └── CLAUDE.md
│
├── config/
│   ├── fleet.yaml                # Fleet-wide settings
│   └── mission-control.env       # Mission-control environment config
│
├── tests/
└── docs/
    ├── idea.md
    └── architecture.md
```

## Docker Compose

```yaml
services:
  # Mission Control (their code, our central UI)
  db:
    image: postgres:16-alpine
  redis:
    image: redis:7-alpine
  mission-control-backend:
    image: openclaw-mission-control-backend  # or build from their repo
  mission-control-frontend:
    image: openclaw-mission-control-frontend

  # Our Gateway
  ocf-gateway:
    build: ./gateway
    environment:
      - MISSION_CONTROL_URL=http://mission-control-backend:8000
      - CLAUDE_CODE_PATH=/usr/local/bin/claude
    volumes:
      - ./agents:/agents
```

## Integration with AICP

- AICP builds OCF (uses skills to scaffold, develop, test)
- OCF runs independently (doesn't need AICP at runtime)
- AICP skills translate to OCF skills in mission-control's marketplace
- AICP's project registry tracks OCF as a managed project

## The Fleet — Agent Roster

OCF is a workforce, not a single tool. Agents specialize, collaborate, and their work compounds.

### Core Agents (required for the fleet to function)

| Agent | Role | Type | Mode | Description |
|-------|------|------|------|-------------|
| **Architect** | System design | Definition | Think | Designs architectures, reviews designs, proposes structure. Consults on every new component. |
| **Software Engineer** | Implementation | Definition/Persistent | Edit/Act | Writes code, implements features, fixes bugs, refactors. The workhorse. |
| **UX Designer** | Interface design | Definition | Think/Edit | Designs user flows, UI components, accessibility, interaction patterns. |
| **QA Engineer** | Quality | Definition | Think/Act | Writes tests, runs test suites, identifies regressions, validates acceptance criteria. |
| **DevOps** | Infrastructure | Definition | Act | CI/CD, Docker, deployment, monitoring, scaling, incident response. |
| **Technical Writer** | Documentation | Definition | Edit | API docs, user guides, architecture docs, changelogs, onboarding materials. |

### Mission Agents (specialized for specific initiatives)

| Agent | Role | Type | Mode | Description |
|-------|------|------|------|-------------|
| **Accountability Generator (ocf-tag)** | Civic accountability | Persistent | Think/Edit | Evidence-to-pressure system. 5 layers: Intake, Structuring, Mapping, Pressure Generation, Persistence. |
| *More mission agents added as initiatives grow* |

### Agent Collaboration Model

Agents don't work in isolation. They collaborate through mission-control's task system:

1. **Architect** designs a component → creates tasks for **Software Engineer**
2. **Software Engineer** implements → **QA Engineer** validates
3. **UX Designer** proposes interface → **Software Engineer** implements → **QA** tests
4. **DevOps** deploys → **QA** smoke tests → **Technical Writer** documents
5. **Accountability Generator** needs a data layer → **Architect** designs → **Engineer** builds

Mission-control tracks all of this: task dependencies, approvals, activity log.

### Agent Scaling

The fleet grows with need:
- **Security Analyst** — audit code, review dependencies, assess threats
- **Data Engineer** — data pipelines, transformations, storage optimization
- **Product Manager** — prioritization, roadmap, stakeholder communication
- **Code Reviewer** — dedicated review agent for PR quality
- **Performance Engineer** — profiling, optimization, benchmarking
- **Researcher** — investigate technologies, gather competitive intelligence

Each new agent is a `agents/<name>/` directory with config, context, and optionally source code. Registered in mission-control, executed through the gateway.

## First Initiative: The Accountability Generator (ocf-tag)

The first mission-specific agent. Registered in mission-control as a persistent agent with its own boards and task groups.

5 layers (each a mission-control board group):
1. **Intake** — collect claims, policies, actions, evidence
2. **Structuring** — normalize into actors, decisions, timelines
3. **Mapping** — build responsibility chains, knowledge graphs
4. **Pressure Generation** — reports, dashboards, contradiction flags
5. **Persistence** — nothing disappears, edits visible, claims linked to outcomes

Built by the core agents: Architect designs the layers, Engineer implements, QA validates, DevOps deploys, Writer documents.
