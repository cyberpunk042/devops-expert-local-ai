---
name: foundation-testing
description: Set up testing infrastructure with fixtures, mocking, and coverage
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: medium
---

# Foundation — Testing

Set up comprehensive testing infrastructure.

## Process

1. Install test framework (pytest, jest, cargo test, go test)
2. Configure:
   - Test runner with sensible defaults
   - Test directory structure mirroring source
   - Fixtures for common setup (database, auth, HTTP client)
   - Mocking utilities
   - Coverage reporting (minimum threshold)
   - Test database or in-memory alternatives
3. Create test helpers:
   - Factory functions for test data
   - Assertion helpers for common patterns
   - Test client for API testing
4. Write initial smoke tests that verify the project runs
5. Add test targets to Makefile: `test`, `test-coverage`, `test-watch`
6. Configure CI to run tests

## Rules

- Tests must be fast (mock external services)
- Every module gets a corresponding test file
- Coverage threshold: 80% minimum
- Tests must be independent (no order dependency)