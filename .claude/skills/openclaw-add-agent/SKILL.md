---
name: openclaw-add-agent
description: Add a new agent to an OpenClaw deployment
argument-hint: <agent-name> [workspace-path]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Add OpenClaw Agent

Add a new specialized agent to an OpenClaw deployment.

## Process

1. Create agent directory: `agents/<name>/`
2. Create `agent.yaml` with: name, type, description, mission, capabilities, mode
3. Create `CLAUDE.md` with agent instructions (role, how it works, rules)
4. Create `SOUL.md` (copy of CLAUDE.md for OpenClaw)
5. Create `AGENTS.md` with workspace startup instructions
6. Register in OpenClaw: `openclaw agents add <name> --workspace <path>`
7. Copy auth profiles from main agent if available
8. Verify: `openclaw agents list` shows the new agent

## Rules

- Agent name must be lowercase with hyphens
- CLAUDE.md and SOUL.md should be identical (SOUL.md is OpenClaw's name for it)
- Each agent needs clear role boundaries — don't overlap with existing agents