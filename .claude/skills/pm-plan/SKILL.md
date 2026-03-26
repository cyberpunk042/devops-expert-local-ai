---
name: pm-plan
description: Generate or update project plan with milestones and dependencies
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# Project Management — Plan

Create or update a project plan.

## Process

1. Read idea doc, architecture doc, current state
2. Break the architecture into buildable milestones (5-10)
3. For each milestone: name, description, deliverables, dependencies, estimated effort
4. Identify critical path
5. Write to .aicp/state.yaml milestones
6. Present to user for review

## Rules

- Each milestone must produce something testable
- Dependencies must be explicit
- No milestone should take more than 2-3 sessions