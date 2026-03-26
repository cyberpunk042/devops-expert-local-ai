---
name: foundation-ci
description: Generate CI/CD pipeline tailored to the project stack
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Foundation — CI/CD

Generate a CI/CD pipeline appropriate for this project.

## Process

1. Detect the project's tech stack from manifests and source
2. Generate `.github/workflows/ci.yml` with:
   - Trigger on push and PR to main
   - Matrix testing if multiple versions needed
   - Lint step (ruff, eslint, clippy, etc.)
   - Test step with coverage
   - Build step
   - Optional: deploy step (commented out, ready to enable)
3. Add status badge to README
4. Create `Makefile` targets that mirror CI steps (so devs can run locally)

## Rules

- CI must pass on the current codebase before committing
- Keep pipeline fast — fail fast on lint before running tests
- Cache dependencies for speed
- Use specific action versions, not @latest