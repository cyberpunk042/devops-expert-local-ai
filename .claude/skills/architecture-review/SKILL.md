---
name: architecture-review
description: Review an architecture document for gaps, risks, and improvements
allowed-tools: Read, Write, Edit, Glob, Grep
effort: high
---

# Architecture Review

Critically review an existing architecture document.

## Process

1. Read `docs/architecture.md` and `docs/idea.md`
2. Evaluate against these criteria:
   - **Completeness**: Does every requirement from the idea doc have a home in the architecture?
   - **Over-engineering**: Is anything more complex than needed for the current stage?
   - **Under-engineering**: Will anything obviously break at moderate scale?
   - **Security**: Are there exposed attack surfaces?
   - **Dependencies**: Are there risky or unnecessary external dependencies?
   - **Testability**: Can each component be tested independently?
   - **Deployability**: Can this be deployed incrementally?
   - **Missing pieces**: What's not addressed?
3. For each issue found, propose a specific fix
4. Rate overall readiness: Ready to build / Needs revision / Major rethink

## Output

Write findings inline as review comments in the architecture doc, or produce a separate `docs/architecture-review.md` if the user prefers.