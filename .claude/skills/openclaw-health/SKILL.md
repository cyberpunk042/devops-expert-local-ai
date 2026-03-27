---
name: openclaw-health
description: Check health of OpenClaw + Mission Control + agents
allowed-tools: Read, Bash, Glob, Grep
effort: low
---

# OpenClaw Health Check

Comprehensive health check of the OpenClaw ecosystem.

## Process

1. Check OpenClaw gateway: `openclaw status`
2. Check Mission Control backend: `curl http://localhost:8000/health`
3. Check Mission Control frontend: `curl http://localhost:3000`
4. Check Docker services: `docker compose ps`
5. List registered agents: `openclaw agents list`
6. Check for any error logs: gateway log, MC backend log
7. Report overall health status

## Output

A clear summary: what's running, what's not, what needs attention.