---
name: pm-assess
description: Assess project state — what's built, pending, blocked, next actions
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# Project Management — Assess

Comprehensive assessment of where the project stands.

## Process

1. Read project state (.aicp/state.yaml), architecture doc, README
2. Scan codebase: what modules exist, what tests pass, what's stubbed
3. Read git log for recent activity
4. Compare against milestones and plan
5. Produce assessment:
   - **Accomplished**: what's done and working
   - **Current state**: what's in progress
   - **Blocked**: what's stuck and why
   - **Risks**: what could go wrong
   - **Next actions**: specific, prioritized steps
6. Update .aicp/state.yaml with assessment findings