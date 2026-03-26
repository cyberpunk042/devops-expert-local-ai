---
name: idea-capture
description: Capture a raw idea and produce a structured idea document
argument-hint: [idea text or "interactive" for guided mode]
allowed-tools: Read, Write, Bash, Glob, Grep
effort: high
---

# Idea Capture

Take the user's raw input and produce a structured idea document.

## Input

$ARGUMENTS

If no arguments provided, ask the user to describe their idea interactively.

## Process

1. Read and understand the raw idea
2. Identify: core vision, target users, key differentiators, constraints, unknowns
3. Ask clarifying questions if critical information is missing
4. Structure into a formal idea document

## Output

Write a file at `docs/idea.md` with this structure:

```markdown
# [Project Name] — Idea Document

## Vision
One-line description of what this is.

## Problem
What problem does this solve? Who has this problem?

## Core Concepts
- Concept 1: explanation
- Concept 2: explanation

## Target Users
Who will use this and why.

## Key Differentiators
What makes this different from existing solutions.

## Constraints
- Technical constraints
- Resource constraints
- Timeline constraints

## Open Questions
Things that need to be decided before building.

## Success Criteria
How do we know this worked?
```

After writing, show the user the document and ask if anything needs adjustment.