---
title: "Decision: AICP active-state mechanism — `.aicp/state.yaml` per-repo with git-branch fallback"
type: decision
domain: backend-ai-platform-python
layer: 6
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "pretooluse-hooks-layered-approach"
  - "model-quality-failure-prevention"
reversibility: easy
created: 2026-04-18
updated: 2026-04-18
sources:
  - id: layer-a-decision
    type: file
    file: wiki/decisions/01_drafts/pretooluse-hooks-layered-approach.md
    description: Layer A decision enumerated 3 candidate state mechanisms; this decision picks among them
  - id: aicp-domain-profile
    type: file
    file: wiki/config/domain-profiles/backend-ai-platform-python.yaml
    description: Per-stage forbidden_zones that Layer B hooks will enforce
  - id: aicp-backlog-tasks
    type: directory
    file: wiki/backlog/tasks/
    description: Where active tasks will live (currently has _index.md placeholder; no live tasks yet)
tags: [decision, hooks, state, stage-gate, aicp, backend-ai-platform-python, transferable, pattern]
---

# Decision: AICP active-state mechanism — `.aicp/state.yaml` per-repo with git-branch fallback

## Summary

To enable Layer B PreToolUse stage-gate hooks (block writes to forbidden paths per the active task's `current_stage`), AICP needs a runtime mechanism that answers "what task + stage am I in right now?" Three candidates were considered (per the Layer A decision): a global `~/.aicp/active-task.json`, a per-repo `.aicp/state.yaml`, and git-branch-name inference. **AICP adopts `.aicp/state.yaml` per repo as the primary source of truth, with git-branch inference as an advisory fallback when state.yaml is absent.** This combination is correct because: (a) per-repo state cleanly handles multi-repo workflows (operator working on AICP + openfleet + other projects each with different active tasks), (b) branch-name fallback gives a sensible default with zero operator burden when `.aicp/state.yaml` is missing or stale, (c) the file format integrates with AICP's existing YAML config patterns (operator already reads `config/profiles/*.yaml` and `config/models/*.yaml` — adding `.aicp/state.yaml` doesn't introduce a new format), (d) `.aicp/` is gitignored so per-operator state doesn't pollute commits.

## Decision

> [!success] Adopt `.aicp/state.yaml` per-repo as primary; git-branch name as advisory fallback.
>
> | Layer | Source | When used |
> |-------|--------|-----------|
> | **Primary** | `.aicp/state.yaml` (gitignored, per repo) | Whenever the file exists |
> | **Fallback** | Git branch name pattern (e.g., `feat/T001-router-rewrite`) | When `.aicp/state.yaml` is missing or unreadable |
> | **Final fallback** | "no active task" sentinel (hooks default to no per-stage enforcement, only Layer A safety rules apply) | When neither primary nor branch-name yields a task ID |

`.aicp/state.yaml` schema (v1):

```yaml
# AICP runtime state — operator-managed, gitignored. Updated by:
# - `aicp task switch <id>` CLI command
# - feature-* skills as they advance task stages
# - manual edit (when CLI not available)
active_task: T001                      # task ID, matches wiki/backlog/tasks/T<N>-<slug>.md
active_stage: implement                # current_stage; mirrors task frontmatter for hook performance
mode: edit                             # Three Permission Mode (think | edit | act)
updated: 2026-04-18T12:34:56Z          # ISO 8601; helps detect stale state
```

A schema-validated example file ships at `.aicp/state.yaml.example` (committed). The active `.aicp/state.yaml` is gitignored (already covered by existing `.aicp/` ignore pattern).

## Alternatives

### Alternative 1: `~/.aicp/active-task.json` (global per-user)

Single file in user home. Hook reads it for ALL Claude Code sessions on this user account.

> [!warning] Rejected: AICP operator works on multiple repos (AICP itself, openfleet, second brain, NNRT). A global active-task makes sense ONLY if the operator is single-tasking across all projects, which isn't realistic. If the operator switches from AICP work to fleet work, the global state is now wrong for whichever repo they're in. Per-repo state correctly partitions the concern.

### Alternative 2: Pure git-branch-name inference (no state file)

Parse git HEAD branch name; require convention like `feat/T<id>-<slug>` or `fix/T<id>-<slug>`. Hook does `git symbolic-ref HEAD` → extract task ID → look up `wiki/backlog/tasks/T<id>-*.md` → read current_stage from frontmatter.

> [!warning] Rejected as primary: relies on naming convention (operators forget; auto-generated branches may not follow); doesn't capture per-task STAGE (current_stage lives in task frontmatter, not branch name); doesn't support multi-task branches (a branch covering 2 related tasks); doesn't support task-less work (exploratory branches with no formal task). KEPT as fallback because when no state.yaml exists, branch name is the BEST available heuristic.

### Alternative 3: `.aicp/state.yaml` only (no fallback)

Per-repo state file as the sole source. If missing, hooks behave as if no task is active.

> [!warning] Rejected (the primary is BETTER WITH a fallback): on a fresh checkout or after `rm .aicp/state.yaml`, the hook would have no signal at all. Branch-name fallback covers the common case ("operator started a branch but hasn't run `aicp task switch` yet") gracefully. The cost of adding the fallback is small (one extra check); the benefit is meaningful UX.

### Alternative 4: Embed state in `.env`

Use existing `.env` mechanism: `AICP_ACTIVE_TASK=T001`, `AICP_ACTIVE_STAGE=implement`.

> [!warning] Rejected: `.env` is for SECRETS and stable config (per the `config-secrets` skill), not transient runtime state that changes per task. Mixing transient state with `.env` invites accidental commits (e.g., if an operator deletes the gitignore for `.env` to share a snippet, suddenly the active task ID leaks). State has different lifecycle than secrets — separate file is cleaner.

### Alternative 5: SQLite or in-memory daemon

Run an aicp daemon that holds state in memory. Hook queries the daemon via local socket.

> [!warning] Rejected: huge complexity for the use case. SQLite would work but adds a database dependency for a single-record state. Daemon adds operational surface (must be running for hooks to work). Plain YAML file at known path is simpler, has zero runtime cost, and survives Claude Code restarts trivially.

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **Per-repo correctness for multi-repo operators.** AICP's operator works across 4 active projects (AICP + openfleet + second brain + NNRT). A global state can hold ONE active task; a per-repo state correctly holds one PER REPO. Operators routinely switch repos via cd; state.yaml moves with the directory.
>
> 2. **Branch-name fallback covers the bootstrap problem.** A fresh `git checkout` of a feature branch has no `.aicp/state.yaml`. Without fallback, the operator must remember to `aicp task switch <id>` before the hook gives any per-stage signal. With fallback, the branch name is checked first; many feature branches already follow `feat/T<id>-<slug>` per CLAUDE.md commit conventions, so the bootstrap is automatic.
>
> 3. **YAML integrates with existing AICP patterns.** AICP operators already read `config/profiles/*.yaml`, `config/models/*.yaml`, `wiki/config/methodology.yaml`, `wiki/config/wiki-schema.yaml`. Adding `.aicp/state.yaml` doesn't introduce a new format. Tools like `make profile-show` already pretty-print YAML, so `aicp task show` follows naturally.
>
> 4. **Gitignored = per-operator clean.** `.aicp/` is already in the standard ignore patterns. Operator-specific state never lands in commits. Multi-developer scenarios (each operator working on different tasks in the same repo) work without state collisions.
>
> 5. **Layer A hook can be extended in-place.** `tools/hooks/pretool_safety.py` already exists with R01-R04 deny rules. Layer B adds a `check_stage_gate(path, mode)` function that reads state.yaml + domain profile + applies forbidden_zones. Same hook script, additional rules — no second hook process to register.
>
> 6. **Reversibility is trivial.** Delete `.aicp/state.yaml` → hook falls back to branch-name → if branch doesn't match → only Layer A rules apply (which is the current state without Layer B). Removing the mechanism removes the per-stage signal; baseline safety stays.

## Reversibility

**Easy** — three layers of fallback mean removal is graceful at any point:

- Stop using state.yaml: delete the file. Hook falls back to git-branch inference.
- Disable git-branch inference too: edit hook to skip the fallback. Hook returns to Layer A behavior only.
- Remove Layer B entirely: delete the `check_stage_gate` function from the hook. Layer A rules still operational.

No dependencies break either direction.

## Dependencies

If reversed (remove Layer B):

- `.aicp/state.yaml` and `.aicp/state.yaml.example` become unused (can stay as harmless artifacts or be deleted)
- `tools/hooks/pretool_safety.py` loses the stage-gate check (Layer A R01-R04 still active)
- `aicp task` CLI subcommand (if implemented) becomes orphan tooling
- Skill rewrites (feature-implement, feature-test, etc.) reference state.yaml updates — those references become advisory rather than enforced

If extended (add more state fields):

- `state.yaml` schema v2 could add: `active_milestone`, `active_epic`, `active_module` for hierarchy traversal; `last_committed_at` for staleness detection; `operator` for multi-developer tracking
- Each new field is additive; old hooks ignore unknown fields gracefully

If integrated with skills:

- `feature-implement`'s Operation 4 (Update task state) already plans to write `current_stage: test` to the task frontmatter; the same operation can ALSO write `active_stage: test` to `.aicp/state.yaml` so the hook sees the transition immediately
- `feature-test`'s Operation 4 same pattern: stage transition in frontmatter mirrored in state.yaml

## Implementation (this decision)

### Files

- **NEW**: `.aicp/state.yaml.example` — committed template + comments
- **VERIFY**: `.gitignore` — confirms `.aicp/` already ignored (or add if not)
- **NEW**: `aicp/cli/state.py` — `state read()`, `state write()`, `state switch(task_id)` helpers (small, ~60 lines)
- **NEW**: `aicp/cli/task.py` — `aicp task` subcommand surface: `aicp task switch <id>`, `aicp task show`, `aicp task list` (~80 lines)
- **MODIFIED**: `tools/hooks/pretool_safety.py` — add `check_stage_gate(tool_name, tool_input)` function; new `R05_STAGE_GATE` rule that reads state + applies per-stage forbidden_zones
- **MODIFIED**: `aicp/cli/main.py` — register the `task` subcommand
- Tests: `tests/test_state.py` for state read/write; `tests/test_task_cli.py` for the CLI; extension to existing `tools/hooks` tests for stage-gate behavior

### Branch-name parsing pattern

Inferred task ID matches `^(feat|fix|refactor|docs|chore|test)/T(\d+)-`. Extracted task ID is `T<N>`. Hook then opens `wiki/backlog/tasks/T<N>-*.md` (glob match for the slug suffix) and reads `current_stage` from frontmatter.

If the branch doesn't match OR the task file doesn't exist, fallback fails gracefully → no Layer B enforcement, only Layer A.

### Stage-gate forbidden_zones lookup

`wiki/config/domain-profiles/backend-ai-platform-python.yaml` defines per-stage `forbidden_zones`. Hook reads it once on startup (cached), then for each Write/Edit/MultiEdit checks: does the file_path match any pattern in the active stage's forbidden_zones? If yes, deny with reason "Stage `<stage>` forbids writes to `<zone>` per backend-ai-platform-python domain profile."

## Relationships

- BUILDS ON: [PreToolUse hooks layered approach](./pretooluse-hooks-layered-approach.md) — Layer A decision enumerated this design space; this decision resolves it
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/standards/model-standards/model-quality-failure-prevention-standards.md (the 60→98% enforcement evidence motivating Layer B)
- IMPLEMENTS: per-repo runtime state pattern (transferable to any project that needs hook-readable session state)
- ENABLES: Layer B PreToolUse stage-gate enforcement — closes the per-stage compliance gap that AGENTS.md hard rules currently leave at instruction-only level
- RELATES TO: [Three Permission Modes](../../patterns/01_drafts/three-permission-modes-think-edit-act.md) — state.yaml's `mode` field is where the Three Permission Mode lives at runtime; hook can also enforce mode-based rules
- RELATES TO: [Profile as Coordination Bundle](../../patterns/01_drafts/profile-as-coordination-bundle.md) — `.aicp/state.yaml` is operator-state; profiles are deployment-state; both are coordination bundles at different layers
- RELATES TO: feature-* skills — feature-implement / feature-test / feature-review's Operation 4 already updates task frontmatter; this decision adds `state.yaml` as a parallel update destination for hook performance
