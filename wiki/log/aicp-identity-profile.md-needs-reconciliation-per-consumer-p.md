---
title: "AICP identity-profile.md needs reconciliation per consumer-property doctrine + outdated facts"
type: note
domain: log
note_type: session
status: synthesized
confidence: medium
created: 2026-04-17
updated: 2026-04-17
sources: []
tags: [contributed, correction]
contributed_by: "aicp-self"
contribution_source: "~/devops-expert-local-ai"
contribution_date: 2026-04-17
contribution_status: pending-review
contribution_reason: "Brain's identity-profile.md predates the consumer-property doctrine (2026-04-15) and needs reconciliation. Also has outdated scale/phase facts. AICP now declares identity per latest doctrine in its CLAUDE.md."
---

# AICP identity-profile.md needs reconciliation per consumer-property doctrine + outdated facts

## Summary

Target page: wiki/ecosystem/project_profiles/aicp/identity-profile.md (created 2026-04-13).

DOCTRINE VIOLATIONS (post-doctrine 2026-04-15):

1. The Identity table at lines 26-38 hardcodes 'Execution Mode: Solo' as a project field. This violates wiki/lessons/01_drafts/execution-mode-is-consumer-property-not-project-property.md (created 2026-04-15) which establishes that execution mode is a CONSUMER property, not a project property. Solo is the default for any project; harness/fleet declares non-default at MCP connect via the runtime field.

2. The same Identity table hardcodes 'SDLC Profile: Simplified'. Same doctrine violation — SDLC profile is per-task. Also questionable on its merits: a production-phase + medium-scale project would default to 'default' (Goldilocks), not 'simplified'.

OUTDATED FACTS:

3. Scale: profile says 'Medium (~60 modules)'. Current count as of 2026-04-17: 61 Python modules in aicp/, 94 test files, 1,758 tests (was 1,631 in profile), plus 78 skills, 9 profiles, 14 model configs.

4. Phase: profile says 'Stage 1 (LocalAI functional) complete, Stage 2 (routing) implemented'. Current state: Stage 2 routing operational (4-tier router with circuit breakers + DLQ + warmup deployed); Stage 3 hardware unlocked 2026-04-17 (19GB VRAM dual-GPU). See companion remark.

ADOPTION STATUS UPDATE:

5. The 'Integration with Second Brain' table at lines 92-101 says 'Wiki knowledge base: Partial' and 'Feed-back TO second brain: Minimal'. As of 2026-04-17, AICP has formal gateway forwarder at tools/gateway.py and has reached Tier 4/4 STRUCTURAL compliance per gateway compliance check (CLAUDE.md identity declared, wiki/config/{wiki-schema.yaml,templates,methodology.yaml,export-profiles.yaml}, wiki/backlog/, wiki/{lessons,patterns,decisions}/ with maturity dirs, tools/{evolve.py,lint.py} stubs, .mcp.json). Operational compliance is Tier 2+ (honest reporting per Structural Compliance Is Not Operational Compliance).

NEW KNOWLEDGE GAP TO ADD:

6. The 'Knowledge Gaps' section at lines 105-113 should add: 'Empirical routing split with 19GB hardware (Stage 3 hardware just unlocked, measurements pending).' This connects to the open question on Model — Local AI.

CORRECTED IDENTITY (declared by AICP per consumer-property doctrine):

Stable: type=product (backend AI platform); domain=backend-ai-platform-python; second-brain=connected.
State: phase=production — Stage 2 routing operational, Stage 3 hardware unlocked 2026-04-17; scale=medium (61 modules / 94 test files / 1,758 tests / 78 skills / 9 profiles / 14 model configs).
Consumer/task properties (NOT in CLAUDE.md): execution mode default solo, SDLC profile default 'default' (Goldilocks), methodology model task-dependent.

Source: AICP CLAUDE.md Identity Profile section (added 2026-04-17), parsed by gateway query_identity().

## Relationships

- RELATES TO: [[model-registry|Model Registry]]
