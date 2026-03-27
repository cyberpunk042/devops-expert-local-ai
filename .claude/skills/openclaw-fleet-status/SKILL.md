---
name: openclaw-fleet-status
description: Check fleet operational status — tasks, agents, boards
allowed-tools: Read, Bash, Glob, Grep
effort: low
---

# Fleet Status

Check the operational status of an OpenClaw Fleet deployment.

## Process

1. Run `make status` in the fleet project directory
2. Check pending tasks in Mission Control
3. Check agent status and recent activity
4. Report: active tasks, completed tasks, agent health, any blockers