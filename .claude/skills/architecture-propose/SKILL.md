---
name: architecture-propose
description: Propose a system architecture from an idea document
argument-hint: [path to idea doc]
allowed-tools: Read, Write, Edit, Glob, Grep
effort: high
---

# Architecture Proposal

Analyze the idea document and propose a concrete, buildable architecture.

## Input

Read the idea document at `$ARGUMENTS` (default: `docs/idea.md`).
Also read README.md and CLAUDE.md if they exist for additional context.

## Process

1. Understand the core requirements from the idea doc
2. Identify system boundaries and components
3. Choose appropriate technologies
4. Design the layer/component structure
5. Map data flows between components
6. Identify external dependencies and integrations
7. Consider deployment model

## Output

Write `docs/architecture.md` with:

```markdown
# [Project Name] — Architecture

## Overview
One paragraph: what the system does and how it's structured.

## Components
For each component:
- **Name**: What it is
- **Responsibility**: What it does (single responsibility)
- **Interfaces**: How other components talk to it
- **Technology**: What it's built with and why

## Layer Structure
How components are organized (e.g., layers, services, modules).
Include a directory structure proposal.

## Data Flow
How data moves through the system. Key pathways.

## Technology Stack
| Layer | Technology | Rationale |
|-------|-----------|-----------|

## External Dependencies
What this system depends on and why.

## Deployment Model
How this runs: containers, serverless, bare metal, etc.

## Security Considerations
Auth, data protection, access control.

## Scalability Path
How this grows from MVP to production scale.

## First 5 Milestones
Ordered steps to build this, each producing something testable.
```

Present to user for review. Incorporate feedback before finalizing.