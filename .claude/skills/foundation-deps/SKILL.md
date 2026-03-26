---
name: foundation-deps
description: Install and configure all project dependencies
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Foundation — Dependencies

Analyze the project and set up all required dependencies.

## Process

1. Read the project manifest (pyproject.toml, package.json, Cargo.toml, go.mod)
2. Read the architecture doc to understand what's needed
3. Install all dependencies with proper version pinning
4. Resolve any version conflicts
5. Set up lock files
6. Verify everything imports/compiles correctly
7. Create virtual environment if Python (and add to .gitignore)

## Rules

- Pin versions for reproducibility
- Separate dev/test dependencies from production
- Document why non-obvious dependencies are included
- Run a basic smoke test after installation