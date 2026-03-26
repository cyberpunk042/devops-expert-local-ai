---
name: foundation-auth
description: Implement authentication and authorization
argument-hint: [auth-type: token|session|oauth]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# Foundation — Authentication

Implement auth system: user model, login, token management, middleware, roles.

## Input

Auth type: `$ARGUMENTS` (default: detect from project needs or ask)

## Process

1. Read architecture for auth requirements
2. Implement:
   - User model/schema
   - Registration and login endpoints/handlers
   - Token generation and validation (JWT or session-based)
   - Auth middleware that protects routes
   - Role-based access control (if needed)
   - Password hashing (bcrypt/argon2)
3. Configuration: token expiry, secret keys, allowed origins
4. Tests for: registration, login, token validation, protected routes, role checks
5. Document the auth flow in README or architecture doc

## Rules

- Never store plaintext passwords
- Tokens must expire
- Secret keys from environment, never hardcoded
- Rate limit auth endpoints
- Log auth events (login, failed login, token refresh)