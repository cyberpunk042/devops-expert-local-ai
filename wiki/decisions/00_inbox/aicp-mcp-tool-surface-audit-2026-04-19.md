---
title: "Decision: AICP MCP Tool Surface Audit — Categorize 69 Tools, Migrate Operational + Model-Mgmt to CLI+Skills (~22 tools), Keep Inference + KB + Fleet as MCP (~47 tools)"
type: decision
domain: ai-agents
layer: 6
status: synthesized
confidence: medium
maturity: seed
derived_from:
  - "cli-tools-beat-mcp-for-token-efficiency"
  - "mcp-vs-cli-for-tool-integration"
  - "model-mcp-cli-integration"
  - "aicp-mcp-server-tool-surface-drift-from-claude-md"
reversibility: moderate
created: 2026-04-19
updated: 2026-04-19
sources:
  - id: aicp-mcp-server
    type: file
    file: aicp/mcp/server.py
    description: "1727-line MCP server, 69 tools registered (verified 2026-04-19 via `grep -E '^def aicp_'`)"
  - id: drift-lesson
    type: file
    file: wiki/lessons/00_inbox/aicp-mcp-server-tool-surface-drift-from-claude-md.md
    description: "Sister lesson — documents how the count drifted from claimed 11 to actual 69 without governance"
  - id: cli-beats-mcp-lesson
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/lessons/03_validated/tools-architecture/cli-tools-beat-mcp-for-token-efficiency.md
    description: "Validated L4 lesson — explicit guidance: 'AICP and devops-control-plane: ... Establish the CLI-first default now before MCP proliferates'"
  - id: mcp-vs-cli-decision
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/decisions/02_validated/tools/mcp-vs-cli-for-tool-integration.md
    description: "L6 validated decision in second brain — provides the categorization criteria applied here"
tags: [decision, mcp, cli, audit, tool-surface, migration, aicp, ai-agents, transferable]
---

# Decision: AICP MCP Tool Surface Audit — Categorize 69 Tools, Migrate Operational + Model-Mgmt to CLI+Skills (~22 tools), Keep Inference + KB + Fleet as MCP (~47 tools)

## Summary

AICP's MCP server registers 69 tools (verified 2026-04-19 via `grep -E '^def aicp_' aicp/mcp/server.py`), far exceeding the 11 claimed in CLAUDE.md and well past the second brain's flagged threshold (the wiki-tools MCP server itself questioned whether 17 was too many). Per the `cli-tools-beat-mcp-for-token-efficiency` validated lesson, schema overhead loads on every consumer turn — 69 tools = substantial per-turn cost paid by every Claude Code session, every fleet agent, every external integration that connects. Applying the second brain's `mcp-vs-cli-for-tool-integration` decision criteria (MCP wins for: cross-conversation discoverability, OAuth, interactive workflows with rapid iteration, external service bridges; CLI+Skills wins for: project-internal operational tooling, specific-workflow tools, when schema overhead matters), this audit categorizes the 69 tools into 5 groups and assigns a disposition: **(A) Inference + multimodal + token utilities (36 tools) → KEEP MCP** — AICP IS the external service these consumers need a bridge to; **(B) Knowledge base + vector stores (7 tools) → KEEP MCP** — cross-agent KB access is exactly the discoverability case MCP serves; **(C) Fleet / P2P / agent coordination (4 tools) → KEEP MCP** — multi-agent state needs cross-conversation visibility; **(D) Operational status + diagnostics (13 tools) → MIGRATE TO CLI+Skills** — `route`, `deep_health`, `profile`, `task_status`, `dlq_status`, `metrics`, `warmup`, `models_loaded`, `system`, `server_config`, `backends_list`, `models`, `health` are project-internal operational tooling, used during specific workflows (debugging, profiling, ops), not on every turn — exactly the case the lesson identifies as "default winner" for CLI; **(E) Model lifecycle management (9 tools) → MIGRATE TO CLI+Skills** — `model_gallery`, `model_install`, `model_status`, `model_unload`, `model_delete`, `model_config`, `model_config_update`, `lora_load`, `lora_list` are administrative, low-frequency, batch-oriented — never needed on every turn. Total migration target: **22 tools (32% reduction)**, dropping the per-consumer per-turn schema cost by approximately a third while preserving all functionality (CLI subcommands + companion SKILL.md per migrated tool). The decision is medium-reversibility because each tool has consumers (CLI flag changes, MCP client library calls) that need a deprecation path; not high-reversibility (one config flag) because the migration changes the public surface. Phased approach: Phase 1 = audit (this doc, done); Phase 2 = migrate operational tools (13) — highest-value, lowest-risk; Phase 3 = migrate model lifecycle (9) — admin tooling; Phase 4 = re-measure schema cost on consumers, decide if further trimming needed.

## Decision

> [!success] Categorize all 69 AICP MCP tools by MCP-vs-CLI fit. Migrate the 22 operational + model-mgmt tools to CLI+Skills. Keep the 47 inference/KB/fleet tools as MCP.
>
> | # | Category | Count | Disposition | Reasoning |
> |---|----------|-------|-------------|-----------|
> | A | **Inference + multimodal + token utilities** | 36 | **KEEP MCP** | AICP is THE external service consumers bridge to for inference. The whole point of the MCP is to expose local-AI inference with cross-conversation discoverability. |
> | B | **Knowledge base + vector stores** | 7 | **KEEP MCP** | Cross-agent KB access; same discoverability rationale as inference. Fleet agents query KB without per-conversation setup. |
> | C | **Fleet / P2P / agent coordination** | 4 | **KEEP MCP** | Multi-agent state coordination requires cross-conversation visibility. CLI per-process can't share fleet state. |
> | D | **Operational status + diagnostics** | 13 | **MIGRATE TO CLI+Skills** | Project-internal operational tooling used in specific workflows (debugging, profiling, ops). Schema cost on every turn for tools used <1% of turns is the textbook anti-pattern in the lesson. |
> | E | **Model lifecycle management** | 9 | **MIGRATE TO CLI+Skills** | Administrative, low-frequency, batch-oriented. Operators install/unload/delete models in deliberate sessions, not per-turn during routine work. |

### Per-tool disposition (canonical list)

**KEEP MCP — Category A (Inference, 36 tools):**
`aicp_chat`, `aicp_complete`, `aicp_complete_logprobs`, `aicp_complete_n`, `aicp_bestof`, `aicp_logprobs`, `aicp_json`, `aicp_grammar`, `aicp_infill`, `aicp_batch`, `aicp_seed`, `aicp_edit`, `aicp_tools_stream`, `aicp_vision`, `aicp_multimodal`, `aicp_imagine`, `aicp_transcribe`, `aicp_transcribe_detailed`, `aicp_speak`, `aicp_voice_pipeline`, `aicp_sound`, `aicp_tts`, `aicp_tts_voices`, `aicp_vad`, `aicp_detect`, `aicp_embed`, `aicp_embed_image`, `aicp_embed_typed`, `aicp_embed_typed_batch`, `aicp_embed_dims`, `aicp_similarity`, `aicp_nearest_neighbors`, `aicp_tokenize`, `aicp_tokenize_batch`, `aicp_detokenize`, `aicp_token_count`, `aicp_rerank`

**KEEP MCP — Category B (KB + Stores, 7 tools):**
`aicp_kb_search`, `aicp_kb_search_collection`, `aicp_kb_ingest`, `aicp_kb_stats`, `aicp_kb_augment`, `aicp_store_set`, `aicp_store_find`

**KEEP MCP — Category C (Fleet + P2P, 4 tools):**
`aicp_fleet_status`, `aicp_fleet_run`, `aicp_agent`, `aicp_p2p_status`

**Audit correction 2026-04-19** (post-Phase-2 sample): `aicp_route` was incorrectly listed as Category D in the original draft. On re-examination, `aicp_route` actually EXECUTES a routed prompt (returns inference result), making it inference-path (Category A KEEP MCP), not status query. Recategorized to A. Net Category D reduces from 13 → 12 tools to migrate.

**MIGRATE TO CLI+Skills — Category D (Operational, 12 tools):**
`aicp_deep_health` → `aicp --deep-health` + `deep-health` skill (already partial in `aicp --health-report`);
`aicp_health` → consolidate with deep_health (deduplicate);
`aicp_profile` → `aicp --profile-cmd show/list/use` + `profile` skill (extends existing `--profile`);
`aicp_task_status` → `aicp --task-cmd status` + `task` skill (extends existing `--task-cmd switch/show/list/clear`);
`aicp_dlq_status` → `aicp --dlq-status` + `dlq` skill (already partial in `aicp --retry-dlq`);
`aicp_metrics` → `aicp --metrics` + `metrics` skill;
`aicp_warmup` → `aicp --warmup` + `warmup` skill;
`aicp_models_loaded` → `aicp --models loaded` + `models` skill;
`aicp_models` → `aicp --models list` + `models` skill;
`aicp_system` → `aicp --system-info` + `system` skill;
`aicp_server_config` → `aicp --config-show` + `config` skill;
`aicp_backends_list` → `aicp --backends-list` + `backends` skill.

**MIGRATE TO CLI+Skills — Category E (Model lifecycle, 9 tools):**
`aicp_model_gallery` → `aicp --model-cmd gallery [--search X]` + `model-mgmt` skill;
`aicp_model_install` → `aicp --model-cmd install <id>` + `model-mgmt` skill;
`aicp_model_status` → `aicp --model-cmd status <id>` + `model-mgmt` skill;
`aicp_model_unload` → `aicp --model-cmd unload <name>` + `model-mgmt` skill;
`aicp_model_delete` → `aicp --model-cmd delete <name>` + `model-mgmt` skill (with confirmation prompt);
`aicp_model_config` → `aicp --model-cmd config <name>` + `model-mgmt` skill;
`aicp_model_config_update` → `aicp --model-cmd update <name> --param <k=v>` + `model-mgmt` skill;
`aicp_lora_load` → `aicp --lora-cmd load <name> <adapter>` + `lora` skill;
`aicp_lora_list` → `aicp --lora-cmd list` + `lora` skill.

## Alternatives

### Alternative 1: Keep all 69 tools as MCP (status quo)

Don't migrate. Accept the schema overhead. The MCP server is feature-complete; consumers know how to use it.

> [!warning] Rejected: contradicts the second brain's validated lesson which explicitly named AICP as the project that should "establish the CLI-first default now before MCP proliferates." The lesson is L4 validated maturity (highest validation tier short of "principle"); ignoring it after explicitly reading and acknowledging it would be a documented adherence failure. The schema cost compounds across every consumer connection — every Claude Code session, every fleet agent, every CLI invocation of the MCP. The migration cost is small per tool (decorator → CLI subcommand + SKILL.md); the cumulative consumer benefit (~32% schema reduction) is real and persistent.

### Alternative 2: Migrate ALL 69 tools to CLI+Skills

Maximum adherence to the CLI-first default. No exceptions.

> [!warning] Rejected: the lesson itself documents WHEN MCP wins — cross-conversation discoverability, external service bridges, multi-agent coordination. Inference (Category A) is the textbook external-service-bridge case: AICP IS the inference service that consumers need a discoverable bridge to. KB access (Category B) is the textbook cross-conversation discoverability case. Fleet coordination (Category C) is the textbook multi-agent state case. Migrating these to CLI would force every consumer to teach itself how to invoke AICP per session — defeating the discoverability MCP provides. The audit applies the lesson's CRITERIA, not its surface conclusion ("CLI is better"). Where MCP genuinely wins, MCP stays.

### Alternative 3: Migrate operational tools (13) but keep model lifecycle (9) as MCP

Half measure. Move only the obvious operational tooling.

> [!warning] Rejected: model lifecycle management is administrative work — `aicp model install qwen3-8b-fast`, `aicp model unload`, `aicp model delete`. These are run by operators in deliberate sessions, not by agents during routine inference. They have ZERO need for cross-conversation discoverability (operator who installs a model knows they're installing it; no agent needs to discover the install API mid-conversation). Keeping them as MCP wastes the schema cost on every consumer for tools that 99% of consumers will never call. The full migration of both Categories D and E is consistent — both are admin/operational, both fail the discoverability test, both pass the "low frequency, specific workflow" CLI test.

### Alternative 4: Add MCP "selective tool exposure" instead of migrating

Wait for / use MCP's selective tool exposure feature (the model's "Thin or unverified" section flags this as upcoming). Selectively expose only the tools each consumer needs.

> [!warning] Rejected (deferred fallback): selective tool exposure may eventually solve the schema-cost problem at the protocol level. But (a) it's not a feature AICP can use today (status: upcoming, not implemented), (b) even when available, it shifts the cost from "AICP server exposes everything" to "consumer client must declare needed tools" — adding consumer-side complexity that AICP currently absorbs. Migration to CLI+Skills is a strictly-better solution because it eliminates the schema cost AND the discoverability decision (operator runs `aicp --help`; no MCP negotiation). If MCP selective exposure lands and proves better than CLI+Skills for some category, that's a future decision that doesn't block this one.

### Alternative 5: Build a doc-generator for CLAUDE.md and skip the audit

Treat the drift as a documentation problem only. Generate CLAUDE.md tool counts from the source. Don't migrate any tools.

> [!warning] Rejected: this addresses the drift symptom (CLAUDE.md was wrong) without addressing the root cause (MCP proliferation against ecosystem guidance). The drift lesson (`wiki/lessons/00_inbox/aicp-mcp-server-tool-surface-drift-from-claude-md.md`) explicitly distinguishes "the symptom" (drift) from "the root cause" (no proliferation guard). Doc-generation would freeze the wrong shape in code. The audit + migration addresses the cause; doc-generation is a complementary defense (still recommended) but not a substitute.

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **The second brain's lesson explicitly named AICP.** `cli-tools-beat-mcp-for-token-efficiency` line 95 (under "Domains where this lesson applies directly"): "AICP and devops-control-plane: Any future agent in the ecosystem faces the same tradeoff. Establish the CLI-first default now before MCP proliferates as the default integration pattern." AICP did not establish that default. This audit is the corrective action the lesson predicted would be needed.
>
> 2. **The categorization criteria are NOT subjective — they're in the source decision page.** The second brain's `mcp-vs-cli-for-tool-integration` L6 validated decision specifies WHEN MCP wins (cross-conversation discoverability, OAuth, interactive iteration, external service bridges) and WHEN CLI+Skills wins (project-internal, specific-workflow, schema-overhead matters). Applying these to AICP's 69 tools produces the categorization deterministically; reasonable reviewers should arrive at the same disposition for each tool because the criteria are codified.
>
> 3. **Migration cost per tool is low.** Each migration replaces `@mcp.tool()` with: (a) a CLI subcommand (one block in `aicp/cli/main.py`), (b) a SKILL.md teaching the agent when/how to invoke the CLI subcommand. AICP already has the CLI dispatcher pattern (`--task-cmd switch/show/list/clear` per the recent state-mgmt work) and the skills system (.claude/skills/, 78 skills). The migration is well-trodden ground — not greenfield.
>
> 4. **Consumer benefit compounds.** Each connected consumer (Claude Code session, fleet agent, external client) loads AICP's MCP schema on connect. 22 fewer tools = ~32% smaller schema = lower cost per turn forever, for every consumer. AICP's expected consumer count grows as the fleet matures (10 agents per machine target, multi-machine fleet planned per CLAUDE.md `## Infrastructure target`). The savings scale with fleet adoption.
>
> 5. **Operational tools are the WORST MCP fit and the BEST migration candidates.** `aicp_metrics`, `aicp_warmup`, `aicp_dlq_status`, `aicp_deep_health` are called during specific workflows — debugging an issue, tuning performance, recovering from incident. They're not called on every turn. The schema cost is paid every turn; the value is delivered <1% of turns. This is the EXACT cost/value mismatch the lesson identifies as the structural anti-pattern. Operational tools are first to migrate because they have the worst frequency-vs-cost ratio.
>
> 6. **Inference tools are the BEST MCP fit and stay.** `aicp_chat`, `aicp_vision`, `aicp_embed` ARE the service. They're called frequently. They need cross-conversation discoverability (a fresh Claude Code session opens, sees `aicp_chat` in the MCP listing, knows it can route inference). They benefit from JSON schema (typed parameters help the agent get the call right first try). Migrating these would defeat the MCP's purpose. The audit RESPECTS what MCP is for; it just removes what MCP isn't for.
>
> 7. **The audit produces a phased migration plan, not a flag day.** Migration is staged: Phase 2 = 13 operational tools, Phase 3 = 9 model lifecycle tools. Each phase can be reviewed, deployed, measured. The reversibility per phase is medium (consumer code referencing `aicp_metrics` MCP tool would need updating to call `aicp --metrics` CLI instead — but the deprecation path is straightforward: keep the MCP tool as a thin wrapper around the CLI for one release cycle, mark deprecated, remove next cycle).

## Reversibility

**Moderate.** Per-tool migration is straightforward but each migrated tool has potential consumers (other AICP tooling, fleet agents, external integrations) that need a deprecation path. Recommended approach:

- Phase migration over 2-3 release cycles per category
- During deprecation: keep the MCP tool as a thin wrapper that calls the CLI subcommand internally (zero functional change for consumers, full migration on the AICP side)
- Add deprecation warnings in the MCP tool's response: `{"warning": "aicp_metrics MCP tool deprecated; use 'aicp --metrics' CLI. Removal in next release."}`
- After 2 release cycles: remove the MCP tool. Consumers that didn't migrate get an obvious failure with a clear message about the CLI alternative.

The cost of full reversal (re-add 22 tools as MCP after removing them): hours per tool to restore. Higher than zero because the CLI+Skills implementations would also need to remain (parallel surfaces) or be removed first (which would ALSO need a deprecation path). The decision should be deliberate; reversal is not free.

## Dependencies

If executed (proceed with phased migration):

- `aicp/cli/main.py` — extend with new CLI flags per Category D and E migrations (pattern: `--<category>-cmd <action> [--<arg> <value>]` matching the recent `--task-cmd` precedent)
- `.claude/skills/` — author SKILL.md per migrated tool group (route, deep-health, profile, task, dlq, metrics, warmup, models, system, config, backends, model-mgmt, lora) — ~13 new skills
- `aicp/mcp/server.py` — first phase: convert migrated tools into thin wrappers calling the CLI; second phase: remove
- `CLAUDE.md` — re-update tool count after each phase
- Consumer-side: any external code calling `aicp_metrics` etc. via MCP needs to migrate to CLI; deprecation period gives them time
- Tests: integration tests in `tests/test_mcp_server.py` need migration (test the CLI surface alongside / instead of MCP for migrated tools)

If reversed (rollback after partial migration):

- Restore `@mcp.tool()` decorators for rolled-back tools
- Skills can stay (they teach a useful workflow regardless of invocation surface)
- Consumers that already migrated to CLI invocation continue working; new consumers see both options

## Relationships

- BUILDS ON: ~/devops-solutions-research-wiki/wiki/lessons/03_validated/tools-architecture/cli-tools-beat-mcp-for-token-efficiency.md (validated L4 lesson — explicitly named AICP)
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/decisions/02_validated/tools/mcp-vs-cli-for-tool-integration.md (validated L6 decision — categorization criteria)
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/ecosystem/model-mcp-cli-integration.md (model — eager vs deferred loading mechanism)
- BUILDS ON: [aicp-mcp-server-tool-surface-drift](../../lessons/00_inbox/aicp-mcp-server-tool-surface-drift-from-claude-md.md) (sister lesson — discovered the drift; this is the corrective action)
- IMPLEMENTS: AICP's adherence to the second brain's CLI-first guidance (corrects the prior failure to establish the default)
- ENABLES: ~32% schema cost reduction for every consumer of AICP's MCP server
- DEPENDS ON: AICP's CLI dispatcher pattern (`--task-cmd switch/show/list/clear` precedent at `aicp/cli/main.py`) being extensible to Category D and E migrations
- RELATES TO: [skills-as-primary-extension-pattern](../01_drafts/skills-as-primary-extension-pattern.md) (the migration strengthens this — every migrated tool gains a SKILL.md that's lazy-loaded vs eager-loaded)
- RELATES TO: [pretooluse-hooks-layered-approach](../01_drafts/pretooluse-hooks-layered-approach.md) (CLI surface migration means hooks can also intercept these operations — improved safety surface)

## Phase 2a status — soft-deprecation layer added 2026-04-25

21 of 21 migration-target tools (12 Category D + 9 Category E; `aicp_route` excluded per the audit correction above) annotated with `_deprecation_warning(...)` call in `aicp/mcp/server.py`. Helper function defined near the top of the module.

**Pattern**: tool function still responds normally (no consumer breakage), but emits a single stderr warning per session on first invocation pointing at the CLI/skill replacement. Idempotent via `_DEPRECATED_TOOLS_WARNED: set[str]` — log spam under fleet-agent traffic is bounded to one line per tool per process.

**Tools annotated** (verified 2026-04-25 via `grep '_deprecation_warning(' aicp/mcp/server.py | grep -v 'def _deprecation' | wc -l` → 21):

| Cat | Tools |
|-----|-------|
| D (operational, 12) | `aicp_models`, `aicp_system`, `aicp_health`, `aicp_backends_list`, `aicp_server_config`, `aicp_metrics`, `aicp_warmup`, `aicp_models_loaded`, `aicp_deep_health`, `aicp_profile`, `aicp_task_status`, `aicp_dlq_status` |
| E (model lifecycle, 9) | `aicp_model_gallery`, `aicp_model_install`, `aicp_model_status`, `aicp_model_unload`, `aicp_model_delete`, `aicp_model_config`, `aicp_model_config_update`, `aicp_lora_load`, `aicp_lora_list` |

**Phase 2b (hard removal)** — deferred to next milestone after consumers cut over to the CLI/skill replacements. The hard cutover removes the `@mcp.tool()` decorators and the function bodies, dropping the schema cost permanently.

**Verification**: helper is one-shot (verified 2026-04-25 via direct invocation — first call emits to stderr, second is silent). All 21 tools still pass their existing test mocks (no behavior change beyond the stderr line).
