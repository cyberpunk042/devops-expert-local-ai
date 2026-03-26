---
name: ops-deploy
description: Execute deployment with pre-flight checks, deploy, smoke test, rollback plan
argument-hint: [environment: dev|staging|prod]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# Operations — Deploy

Execute a deployment with safety checks.

## Process

1. Pre-flight: verify tests pass, lint clean, no uncommitted changes, correct branch
2. Build the deployment artifact
3. Deploy to target environment
4. Run smoke tests against the deployed version
5. If smoke tests fail, execute rollback
6. Update deployment log

## Rules

- Never deploy with failing tests
- Always have a rollback plan before deploying
- Smoke test immediately after deploy
- Log every deployment with timestamp, version, deployer, status