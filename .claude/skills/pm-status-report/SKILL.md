---
name: pm-status-report
description: Generate status report — progress, upcoming, blockers, metrics
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Project Management — Status Report

Generate a status report for stakeholders.

## Process

1. Read project state, recent git history, task history, metrics
2. Generate report:
   - **Progress**: what was completed since last report
   - **Upcoming**: what's planned next
   - **Blockers**: what's stuck
   - **Metrics**: tests passing, coverage, cost, token usage
   - **Decisions needed**: what needs user input
3. Write to docs/status/ with date-stamped filename