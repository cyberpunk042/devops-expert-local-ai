---
name: ops-maintenance
description: Routine maintenance — dependency updates, cleanup, certificate renewal
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Operations — Maintenance

Routine maintenance tasks to keep the system healthy.

## Process

1. Check for dependency updates (security patches, minor versions)
2. Run security audit on dependencies
3. Clean up logs, temp files, old artifacts
4. Check certificate expiry
5. Review and rotate secrets if due
6. Update documentation if anything changed