---
title: "Skills Audit 2026-04-17 — 47% boilerplate against Extension Standards"
type: decision
domain: backend-ai-platform-python
status: synthesized
confidence: high
maturity: seed
created: 2026-04-17
updated: 2026-04-17
sources:
  - id: extension-standards
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-skills-commands-hooks-standards.md
    description: Extension Standards — what good skills/commands/hooks look like
  - id: claude-code-standards
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-claude-code-standards.md
    description: Claude Code Standards — skill quality bar
  - id: aicp-skills
    type: directory
    file: /home/jfortin/devops-expert-local-ai/.claude/skills/
    description: 78 skills inventory
tags: [audit, skills, extension-standards, anti-pattern, technical-debt, epic-b]
contribution_status: pending-review
---

# Skills Audit 2026-04-17 — 47% boilerplate against Extension Standards

## Summary

Quantitative audit of all 78 skills in `.claude/skills/` against the second brain's Extension Standards. **47% of skills (37/78) contain the IDENTICAL generic Process boilerplate** — the "instruction dump" anti-pattern explicitly called out in Extension Standards. **0/78 skills satisfy any of the 5 required structural elements** (trigger phrases, named operations, process per operation, quality bar, gotchas).

## Decision

Treat all 37 boilerplate skills as **technical debt**. Authoring skill-specific content for each is multi-day work tracked under Epic B. Until then: **do not create more skills using the boilerplate template**; the boilerplate trains agents in the wrong pattern (Quality Standards: "Methodology that the wiki documents but the agent doesn't follow is worse than no methodology — because the documentation creates false confidence").

## Audit results

### Quantitative

| Standard requirement | Skills meeting it | % |
|---------------------|-------------------|---|
| Trigger phrases section | 0/78 | 0% |
| Named operations (multiple per skill) | 0/78 | 0% |
| Process per operation | 78/78 (single Process) | 100% partial |
| Quality bar section | 0/78 | 0% |
| Gotchas section | 0/78 | 0% |
| Skill-specific content (NOT boilerplate) | 41/78 | 53% |

### Qualitative — three skill tiers

**Tier 3 — meets Extension Standards exemplars** (`model-builder` / `wiki-agent` quality): **0 skills** (none of AICP's 78 skills meets the bar set by the wiki's reference skills).

**Tier 2 — has skill-specific Process and inputs but lacks structural elements** (~41/78, 53%): examples include `architecture-propose`, `pm-plan`, `ops-deploy`, `foundation-docker`, `openclaw-fleet-status`, `idea-capture`, `idea-refine`. These have:
- Description that's specific (not boilerplate)
- argument-hint where applicable
- Process steps tailored to the skill's actual purpose
- Sometimes Input section
- Sometimes Output section

What they STILL lack per Standards: trigger phrases, multiple named operations, quality bar, gotchas, exit criteria.

**Tier 1 — boilerplate "instruction dump" anti-pattern** (37/78, 47%):

```
config-deploy, config-env, config-feature-flags, config-migrations, config-secrets,
evolve-api-version, evolve-integrate, evolve-internationalize, evolve-migrate,
evolve-plugin-system, evolve-scale, feature-document, feature-implement,
feature-iterate, feature-plan, feature-review, feature-test, infra-api, infra-cache,
infra-monitoring, infra-networking, infra-queue, infra-search, infra-security,
infra-storage, quality-accessibility, quality-audit, quality-coverage, quality-debt,
quality-lint, quality-performance, refactor-architecture, refactor-dependencies,
refactor-extract, refactor-patterns, refactor-rename, refactor-split
```

All 37 share the IDENTICAL Process section:

```markdown
## Process

1. Read the project context: architecture, current state, relevant code
2. Analyze what needs to be done for this specific operation
3. Plan the changes with the user
4. Execute: create/modify files, run commands as needed
5. Verify: tests pass, no regressions, output is correct
6. Update project state (.aicp/state.yaml) with what was accomplished
```

This is the "instruction dump skill" anti-pattern verbatim from Extension Standards line ~85: *"A skill that is a wall of text: 'When the user asks you to do X, first do Y, then Z, make sure to A, also B, and don't forget C...' No trigger phrases — the agent doesn't know WHEN to load it. No operations — the agent doesn't know WHAT it does. No quality bar — the agent doesn't know WHEN it's done."*

Worse: 37 different skill names point to the SAME generic process. An agent loading `quality-coverage` gets the same instructions as loading `feature-implement` — the skill name is a lie.

## Why this matters

Per Claude Code Standards: *"A skill is a system definition, not a text file. The difference between a good skill and a bad skill is the same as the difference between a good model page and a reading list."*

Per Extension Standards anti-pattern table:
| Anti-pattern | What goes wrong | Fix |
|-------------|----------------|-----|
| Instruction dump skill | Agent doesn't know when/how to use it | Trigger phrases, operations, process, quality bar, gotchas |

37 of AICP's 78 skills score across all three columns of the anti-pattern row.

## Alternatives considered

1. **Rewrite all 78 skills now** — rejected: multi-week effort, blocks current work
2. **Delete the 37 boilerplate skills** — rejected: skill names are referenced in fleet's `config/agent-tooling.yaml` (18 skills); deleting would break consumers
3. **Mark boilerplate skills as deprecated, prevent loading until rewritten** — rejected: same consumer-break problem
4. **Audit + technical debt + gradual rewrite** ← chosen: surface the gap with measurable pass-rate, prevent new boilerplate, prioritize rewrites by usage frequency

## Plan (Epic B execution)

**Phase 1 (immediate, this audit):** Document the gap. Add tag `boilerplate-anti-pattern` to all 37 skills (audit metadata, not blocking). Update SKILL.md template (if one exists) or block creation of new boilerplate skills.

**Phase 2 (weeks):** Rewrite the 18 fleet-referenced skills first — those are actually being loaded by fleet agents. Reference: `config/agent-tooling.yaml` in openfleet. Skills: architecture-propose, feature-implement, quality-coverage, foundation-docker, pm-plan, ops-deploy, etc.

**Phase 3 (months):** Rewrite remaining boilerplate skills as they're called for in real work, prioritized by frequency. The `model-builder` and `wiki-agent` skills in the second brain are the exemplars to match — multiple named operations + per-operation Process + Quality bar + Gotchas + Trigger phrases.

**Phase 4 (when 50+ rewritten):** Add a skill validation schema (per Extension Standards Open Question — "Should skills have a validation schema? Yes eventually, not until skill count grows beyond ~20" — we're past 20).

## Reversibility

Easy. Each rewrite is independent; the SKILL.md format is stable. Adding sections doesn't break existing consumers.

## Dependencies

- Epic B execution (Phase 2-3): touches `.claude/skills/` and references in CLAUDE.md / AGENTS.md / fleet's agent-tooling.yaml
- Phase 4 validation schema: new tooling in `tools/lint.py` (currently a structural stub — see [tools/lint.py](../../../tools/lint.py))

## Relationships

- DERIVED FROM: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-skills-commands-hooks-standards.md
- DERIVED FROM: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-claude-code-standards.md
- RELATES TO: structural-compliance-is-not-operational-compliance (this audit measures depth, not just presence)
- BLOCKS: future skill creation (no new boilerplate)
- ENABLES: meaningful skill loading by fleet agents (currently they get 47% identical instructions across different skill names)

## How to verify the audit

```bash
cd /home/jfortin/devops-expert-local-ai/.claude/skills
echo "Total skills:"
ls | wc -l
echo "Boilerplate skills (anti-pattern):"
grep -l "Read the project context: architecture" */SKILL.md | wc -l
echo "Skills with Trigger phrases:"
grep -l "## Trigger" */SKILL.md | wc -l
echo "Skills with Quality bar:"
grep -l "## Quality bar\|## Quality Bar\|## When done" */SKILL.md | wc -l
echo "Skills with Gotchas:"
grep -l "## Gotchas\|## Common failures" */SKILL.md | wc -l
```

Re-run after each rewrite phase to track pass-rate improvement.
