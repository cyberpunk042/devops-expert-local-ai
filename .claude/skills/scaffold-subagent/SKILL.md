---
name: scaffold-subagent
description: Create a new sub-agent inside a fleet project
argument-hint: <agent-name> [fleet-project-path]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# Sub-Agent Scaffold

Create a new agent within an OpenClaw Fleet or similar multi-agent project.

## Input

- Agent name: `$0`
- Fleet project path: `$1` (default: current directory)

## Process

1. Read the fleet project's architecture and agent conventions
2. Create agent directory: `agents/<agent-name>/`
3. Generate agent files:
   - `README.md`: Agent mission, capabilities, architecture
   - `CLAUDE.md`: Instructions for working on this agent
   - `config.yaml`: Agent configuration (mission, capabilities, mode restrictions)
   - `mission.md`: Detailed mission definition
   - Source directory with stub implementation
   - Test directory
4. Register agent in fleet manifest (if one exists)
5. Create initial commit for the agent

## Agent Config Format

```yaml
name: <agent-name>
mission: <one-line mission>
capabilities:
  - <capability-1>
  - <capability-2>
mode: think  # or edit, act
backend_preference: local  # or claude, auto
budget:
  max_cost_usd: 1.0
  max_duration_seconds: 300
```

## Rules

- Agent must follow fleet conventions
- Mission must be clearly defined
- Capabilities must be specific and testable
- Agent must be independently runnable