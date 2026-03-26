---
name: foundation-docker
description: Generate Dockerfile, docker-compose, and container config
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Foundation — Docker

Containerize the project with proper Dockerfile and docker-compose.

## Process

1. Analyze the project structure and dependencies
2. Create `Dockerfile`:
   - Multi-stage build (builder + runtime)
   - Minimal runtime image
   - Non-root user
   - Health check
   - Proper layer caching (deps before code)
3. Create `docker-compose.yaml`:
   - Application service
   - Database service if needed
   - Volume mounts for development
   - Environment variables from .env
   - Port mappings
   - Network configuration
4. Create `.dockerignore`
5. Add docker targets to Makefile: `build`, `up`, `down`, `logs`
6. Test that `docker compose up` works

## Rules

- Production image must be as small as possible
- Dev compose must support hot reload / volume mounts
- Never bake secrets into images
- Always include health checks