---
name: refactor-architecture
description: Restructure AICP at the package/module level without changing behavior — extract subsystems, split overlarge modules, consolidate duplicate logic across packages, realign with the layered architecture in AGENTS.md. The largest-scope refactor skill (smaller siblings: refactor-extract, refactor-split, refactor-rename). Loads when the operator says "refactor the architecture", "restructure aicp/core", "the layering is broken", "modules X and Y should merge".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
effort: high
---

# refactor-architecture

The highest-scope refactor skill. Restructures AICP at the **package and
inter-module** level — moving responsibilities between packages, splitting
overlarge packages, consolidating duplicated logic across packages, fixing
layering violations. Different from `refactor-extract` (extract one
function/class), `refactor-split` (split one module), `refactor-rename` (lexical
rename) — those are file-level. This is package-level.

Architecture refactors are HIGH cost and HIGH risk: they touch many files,
break import paths consumers depend on, and require comprehensive test
coverage to verify behavior is preserved. Per CLAUDE.md hard rule: "Add
complexity only when it earns its place" — and the inverse: don't refactor
architecture without earning the disruption.

## Trigger phrases (when to load this skill)

Load when the conversation matches any of:

- **Direct verb**: operator says "refactor the architecture", "restructure aicp/core", "the layering is broken", "modules X and Y should merge", "split package X"
- **Surfaced from quality-audit**: a `quality-audit` Convergent Problem identifies a package as the root of multiple issues (e.g., `aicp/core/` is hot in coverage gaps + lint violations + debt markers — symptom of structural problem)
- **Surfaced from architecture-review**: `architecture-review` identifies a layering violation, circular dependency, or responsibility drift
- **Pre-major-feature**: a planned feature would WORSEN existing architectural debt; refactor first to make the feature land cleanly
- **Post-incident retrospective**: an incident traced to "this package was doing too many things" — refactor surfaces in the postmortem actions

Do NOT load when:

- A single function/class needs extraction (load `refactor-extract`)
- A single module needs to be split (load `refactor-split`)
- A symbol needs renaming (load `refactor-rename`)
- A behavior change is needed (load `feature-implement` — refactor preserves behavior)
- Quality dimensions need measuring first (load `quality-audit` — measure before restructuring)

## Operations

This skill has 4 named operations. Execute in order. Each gate is a HARD STOP — architecture refactors abandoned mid-way leave AICP in worse shape than before.

### Operation 1: Establish baseline + scope the refactor

**Trigger**: skill loaded; problem identified.

**Process**:

1. Read the source quality-audit / architecture-review that surfaced the need (per Trigger criteria). Capture the SPECIFIC architectural concern in your own words. Examples: "aicp/core/router.py is 1200 lines and mixes scoring + dispatch + circuit breaker logic" or "aicp/backends/ and aicp/core/router.py have duplicated retry logic."
2. Define the BEHAVIOR PRESERVATION contract. What MUST work identically before and after?
   - Public API surfaces (CLI args, MCP tool signatures, controller interface)
   - All currently-passing tests
   - Performance budgets (refactor must not regress hot paths — load `quality-performance` for baseline if unsure)
3. Capture the baseline: full test suite count + result, lint count, coverage % per affected file, perf benchmarks. Write to `wiki/decisions/01_drafts/refactor-architecture-<slug>-<date>.md` (type=decision — this is a DECISION about restructuring, not a one-shot operation).
4. Define the SCOPE OF THE REFACTOR explicitly:
   - Files moved or renamed (specific list)
   - New packages created (specific list)
   - Old packages deleted (specific list)
   - Import changes (estimated count via grep)
5. Stop here. Present scope + behavior contract + baseline to operator. Wait for "go" before any code changes.

**Quality bar (Operation 1 done when)**:

- [ ] Concern stated specifically (not "improve aicp/core/")
- [ ] Behavior preservation contract has explicit list of what must not change
- [ ] Baseline numbers captured (tests, lint, coverage, perf)
- [ ] Refactor scope is explicit (specific file moves, package additions/removals, import-change estimate)
- [ ] Operator approved the scope before any code change

### Operation 2: Plan the migration as ordered steps

**Trigger**: Operation 1 scope approved.

**Process**:

1. Architecture refactors land in MULTIPLE COMMITS, not one giant commit. Plan the migration as ordered steps where each step:
   - Lands a partial structural change
   - Leaves the codebase in a buildable + testable state
   - Has a clear rollback (revert the step's commit)
2. Typical migration shape:
   - Step 1: Add NEW structure (new packages, new files) WITHOUT touching old structure. Old still works.
   - Step 2: Move logic from old structure to new structure. Old becomes thin shim that delegates to new.
   - Step 3: Update consumers (imports) to reference new structure directly. Shims still in place but unused.
   - Step 4: Delete shims. Old structure gone.
   - Each step ends with full test pass + lint pass.
3. For each step, specify the SAFETY MECHANISM:
   - **Pre-step**: full suite passes (no pre-existing failures)
   - **During step**: build still works (typecheck passes, imports resolve)
   - **Post-step**: full suite passes (count unchanged or increased)
   - **Rollback**: `git revert <step-commit>` returns to prior state cleanly
4. Write the migration plan to the decision page from Operation 1. Each step is a numbered subsection with: scope / commands / verification / rollback.
5. Operator approves the step plan before Step 1 commits.

**Quality bar (Operation 2 done when)**:

- [ ] Migration is N ordered steps (N ≥ 3 for any non-trivial architecture refactor)
- [ ] Each step has scope + commands + verification + rollback documented
- [ ] Each step leaves the codebase in a buildable + testable state
- [ ] Operator approved the full step plan

### Operation 3: Execute the migration step-by-step

**Trigger**: Operation 2 plan approved.

**Process**:

1. Execute Step 1. Run pre-step verification (full test suite must pass). Make the changes. Run post-step verification (full test suite must pass, count unchanged). If verification fails, STOP and rollback the step. Don't proceed to Step 2 with broken state.
2. Commit Step 1 with conventional format: `refactor(<scope>): step 1/N - <description>`. Reference the decision page in the commit body.
3. Repeat for Step 2..N. Each step is independently committable + revertable.
4. After EACH step's commit:
   - Re-run perf benchmarks if hot paths were touched (per the behavior contract)
   - Re-run lint (`ruff check + ruff format --check`)
   - Re-run wiki lint if wiki content was touched (paths references etc.)
5. If a step's verification fails AND the step can't be saved cleanly: rollback that step's commit, document what failed in the decision page, abandon the migration. **A half-done architecture refactor is worse than not starting one.**

**Quality bar (Operation 3 done when)**:

- [ ] All N steps committed with conventional format
- [ ] Each step's pre + post verification documented (test count + lint result + perf delta if applicable)
- [ ] Behavior preservation contract from Operation 1 verified at the end (all listed APIs unchanged, all tests still pass, perf within budget)
- [ ] No step left the codebase in broken state at any point

### Operation 4: Update wiki + close the decision

**Trigger**: Operation 3 migration complete.

**Process**:

1. Update the decision page from Operation 1:
   - Mark `status: synthesized` → `status: verified` (the decision was implemented and verified)
   - Add a `## Outcome` section: numbers BEFORE vs AFTER (test count, lint count, file count per package, perf delta if measured)
   - Document any deviations from the planned scope (a step had to be split, a step needed an extra commit, etc.)
2. Update AGENTS.md / CLAUDE.md if package-level structure changed (new packages, deleted packages, renamed packages). The "Project Structure" section MUST reflect reality.
3. Update the domain profile if the package layout changed (`wiki/config/domain-profiles/backend-ai-platform-python.yaml` references `aicp/**/*.py` etc.; major restructures may need updates).
4. If a SYSTEMIC pattern emerged (e.g., "extracting circuit breaker logic into its own package made 3 unrelated callers cleaner — circuit breaker should always have its own package"), contribute back as a lesson: `gateway contribute --type lesson`.
5. Re-run wiki lint on the decision page + AGENTS.md + CLAUDE.md.

**Quality bar (Operation 4 done when)**:

- [ ] Decision page Outcome section has before/after numbers
- [ ] AGENTS.md / CLAUDE.md reflect new structure
- [ ] Domain profile updated if package layout changed
- [ ] Lesson contributed if systemic
- [ ] Wiki lint passes for all updated pages

## Gotchas (known failure modes — read before doing)

### Gotcha 1: Refactor without behavior contract (silent regression)

The temptation: "I'll just restructure these files; it's all the same code, behavior preserves automatically." NO — moving code OFTEN changes behavior subtly (import side effects, module-level state, fixture setup order). Without an explicit behavior contract (Operation 1 step 2), regressions are detected only by users hitting bugs in production.

**Detection**: did Operation 1 produce a written contract listing what MUST not change?

**The rule**: every architecture refactor has an explicit behavior contract. Without it, you're refactoring blind.

### Gotcha 2: Single giant commit (un-revertable migration)

The temptation: do the entire migration in one commit because "it's all related." NO — a giant commit can't be partially reverted. If Step 3 of an undisclosed 5-step migration broke something, you can only revert the WHOLE migration, losing Steps 1-2 of work.

**Detection**: more than 50 files changed in a single commit on a refactor branch.

**The rule**: per Operation 2 — multiple commits, each independently revertable. Each commit ends in a buildable + testable state.

### Gotcha 3: "Improving while refactoring" (scope creep + bug introduction)

The temptation: while moving the file, you spot something that could be cleaner. Tempting to fix it. NO — refactor PRESERVES BEHAVIOR. Improvements (better algorithms, cleaner abstractions, additional features) are SEPARATE tasks. Mixing them means: if behavior breaks, you don't know if the refactor or the improvement caused it.

**Detection**: the diff for a refactor commit includes any logic change, not just code movement.

**The rule**: refactor commits are pure structural change. Move code, update imports, that's it. If you find an improvement worth making, file it as a separate task, don't slip it into the refactor commit.

### Gotcha 4: Refactor without perf baseline (silent regression)

The temptation: refactor doesn't change behavior, so perf must be the same. NOT TRUE — refactors can introduce perf regressions via new function call overhead, new attribute lookups, new module imports at startup, etc.

**Detection**: did Operation 1 capture perf baselines for hot paths? Did Operation 3 re-run them after?

**The rule**: any architecture refactor that touches hot paths runs `quality-performance` BEFORE (baseline) and AFTER (verify within budget). If the refactor regressed perf >5%, it needs investigation before merge.

### Gotcha 5: Half-done refactor (worse than not starting)

The temptation: 3 of 5 steps complete, the rest is "too hard right now," let's pause. The codebase is now in a TRANSITIONAL state — some modules use new structure, some use old, the architectural inconsistency is now LOCKED IN until someone finishes (probably never).

**Detection**: did the migration plan include a clear "abandon and rollback" path for incomplete migrations? Was that path used when stuck, or did the operator just commit partial state?

**The rule**: per Operation 3 — if you can't finish, ROLLBACK to the start. A consistent old structure is much better than a half-migrated one. Document why you stopped in the decision page so a future attempt has the lessons.

## Reference exemplars

Per Extension Standards, reference exemplars are the second brain's `model-builder` and `wiki-agent` skills. For the OUTPUT artifact:

- **Decision page for architecture refactor**: same shape as [4-tier router with profiles](../../../wiki/decisions/01_drafts/4-tier-router-with-profiles-over-hardcoded-routing.md) and [skills as primary extension pattern](../../../wiki/decisions/01_drafts/skills-as-primary-extension-pattern.md) — both are real AICP architecture decisions.
- **Migration step pattern**: see `Epic A — CLAUDE.md slim 646→265` (committed in this repo). That refactor was: Step 1 add AGENTS.md, Step 2 slim CLAUDE.md, Step 3 verify identity still parses. Three steps, each committable + revertable.

## Domain context

This skill operates in **backend-ai-platform-python** — see [wiki/config/domain-profiles/backend-ai-platform-python.yaml](../../../wiki/config/domain-profiles/backend-ai-platform-python.yaml). AICP-specific concerns: package boundaries currently are `aicp/{core,backends,cli,mcp,guardrails,agent,config}/` — refactors should preserve this top-level shape unless there's strong evidence to change it (see also [skills-as-primary-extension-pattern](../../../wiki/decisions/01_drafts/skills-as-primary-extension-pattern.md) for similar architectural-shape stability arguments).

## Related skills

| Skill | When | Why distinct |
|-------|------|--------------|
| refactor-extract | extract ONE function or class | File-level; this skill is package-level |
| refactor-split | split ONE module that's too big | File-level; this skill is package-level |
| refactor-rename | lexical rename of symbols | Mechanical; this skill is structural |
| refactor-patterns | apply a design pattern to existing code | Pattern-level; this skill is package-level |
| refactor-dependencies | dependency hygiene | Different scope (package deps); this skill is module-package layout |
| architecture-review | review existing architecture | Read-only; this skill changes structure |
| architecture-propose | propose a new architecture | Greenfield; this skill restructures existing |
| feature-implement | new behavior | Refactor preserves behavior; feature adds |
