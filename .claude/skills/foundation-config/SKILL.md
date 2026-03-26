---
name: foundation-config
description: Set up configuration management with multi-environment support
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Foundation — Configuration

Set up config management: environment files, loaders, secrets, multi-env support.

## Process

1. Read the project architecture for config requirements
2. Create configuration structure:
   - `.env.example` with all required variables (no secrets)
   - Config loader that reads env vars with fallbacks
   - Multi-environment support (dev, staging, prod)
   - Config validation on startup
3. Add `.env` to .gitignore
4. Document all configuration options in README

## Rules

- Never commit real secrets
- Every config option must have a default or explicit error
- Validate config at startup, not at first use
- Use typed config objects, not raw string dicts