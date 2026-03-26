---
name: scaffold
description: Create a new project from an architecture document
argument-hint: <project-name> [path-to-architecture-doc]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# Project Scaffold

Create a fully structured project from an architecture document.

## Input

- Project name: `$0`
- Architecture doc: `$1` (default: `docs/architecture.md`)

## Process

1. Read the architecture document
2. Create the directory structure from the architecture
3. Generate all boilerplate files:
   - **README.md**: Project overview, setup, usage
   - **CLAUDE.md**: AI assistant instructions, conventions, architecture reference
   - **.gitignore**: Appropriate for the tech stack
   - **Package manifest**: pyproject.toml / package.json / Cargo.toml / go.mod
   - **Config files**: linter, formatter, editor config
   - **Docker**: Dockerfile + docker-compose.yaml if applicable
   - **CI**: GitHub Actions workflow (lint, test, build)
   - **Test structure**: test directory mirroring source
   - **.aicp/state.yaml**: Project state for AICP tracking
4. For each component in the architecture:
   - Create the module/package directory
   - Create `__init__.py` or equivalent with docstring
   - Create a stub implementation with the right interfaces
   - Create a corresponding test file
5. Initialize git repository
6. Create initial commit

## Rules

- Every file must have real content, not just placeholders
- Follow the conventions described in the architecture
- README must include working setup instructions
- CLAUDE.md must describe the architecture accurately
- Tests must actually run (even if trivially)
- The project must be immediately runnable after scaffold

## Output

A working project directory that can be cloned, set up, and run.
Report what was created and what the user should do next.