---
name: openclaw-setup
description: Set up OpenClaw in a project — install, configure, verify
argument-hint: [project-path]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# OpenClaw Setup

Set up OpenClaw in a project workspace.

## Process

1. Check if OpenClaw is installed (`openclaw --version`). Install if missing.
2. Check if the project has a `setup.sh`. If so, run it.
3. If no setup.sh, run `openclaw onboard` with the project as workspace.
4. Configure gateway settings (bind mode, auth, control UI).
5. Verify: `openclaw status` shows healthy.
6. If Mission Control docker-compose exists, start it.
7. Verify all components are running.

## Rules

- Never overwrite existing OpenClaw config without backing up
- Auth configuration may require user interaction — detect and guide
- All config changes should be scripted, not manual
- Verify each step before proceeding to the next