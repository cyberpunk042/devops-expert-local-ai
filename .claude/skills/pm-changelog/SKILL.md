---
name: pm-changelog
description: Generate changelog from git history
argument-hint: [since: tag or commit hash]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Project Management — Changelog

Generate a human-readable changelog from git history.

## Process

1. Read git log since `$ARGUMENTS` (or last tag, or last changelog entry)
2. Group commits by: features, fixes, breaking changes, other
3. Write human-readable entries (not raw commit messages)
4. Link to relevant PRs/issues if available
5. Append to CHANGELOG.md (or create if doesn't exist)