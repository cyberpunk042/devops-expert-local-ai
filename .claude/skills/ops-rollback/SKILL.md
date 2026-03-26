---
name: ops-rollback
description: Rollback deployment to last known good state
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# Operations — Rollback

Rollback to the last known good state.

## Process

1. Identify current broken state and last good deployment
2. Execute rollback (revert deploy, restore database if needed)
3. Verify the rollback succeeded (smoke tests)
4. Generate post-mortem template
5. Update deployment log

## Rules

- Verify the rollback target is actually good before rolling back
- Preserve logs and state from the failed deployment for post-mortem
- Notify stakeholders of the rollback