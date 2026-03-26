---
name: pm-handoff
description: Generate handoff documentation for new team members or future sessions
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# Project Management — Handoff

Generate everything someone needs to pick up this project.

## Process

1. Read all project docs, architecture, state, recent activity
2. Generate handoff document:
   - Project overview (what and why)
   - Architecture summary (how it's built)
   - How to run locally
   - How to deploy
   - Current state (what's done, what's in progress)
   - Known issues and workarounds
   - Key decisions and their rationale
   - Tribal knowledge (things not in the code)
3. Write to docs/handoff.md