---
name: ops-incident
description: Incident response — diagnose, fix, report
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: max
---

# Operations — Incident Response

Gather diagnostics, identify root cause, propose fix, generate report.

## Process

1. Gather: logs, error messages, metrics, recent changes (git log)
2. Identify: what broke, when, what changed before it broke
3. Root cause analysis: trace from symptom to cause
4. Propose fix: specific code/config changes
5. Generate incident report: timeline, root cause, fix, prevention

## Rules

- First priority: restore service
- Second priority: understand why
- Third priority: prevent recurrence
- Document everything, even if it seems obvious