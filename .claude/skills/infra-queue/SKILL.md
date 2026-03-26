---
name: infra-queue
description: Infra Queue — project lifecycle skill
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Infra Queue

Execute the queue operation for the infra phase of the project lifecycle.

## Process

1. Read the project context: architecture, current state, relevant code
2. Analyze what needs to be done for this specific operation
3. Plan the changes with the user
4. Execute: create/modify files, run commands as needed
5. Verify: tests pass, no regressions, output is correct
6. Update project state (.aicp/state.yaml) with what was accomplished

## Rules

- Follow existing project patterns and conventions
- Ask before making destructive changes
- Leave the project in a working state
- Document non-obvious decisions
