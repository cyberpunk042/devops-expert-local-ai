# Claude Code Architecture Analysis — Patterns for AICP

**Date:** 2026-04-07
**Source:** Claude Code source (leaked via npm sourcemap, March 31 2026)
**Codebase size:** ~40K LOC TypeScript, 785KB main.tsx, 44 tools, ~22 services

## Executive Summary

Claude Code is a production-grade AI coding CLI with sophisticated infrastructure
for tool execution, memory management, context compaction, multi-agent orchestration,
MCP integration, plugin extensibility, cost tracking, and voice I/O. Many patterns
directly map to AICP's architecture and can be adopted to improve fleet reliability,
context efficiency, and skill management.

This document maps their patterns to our codebase, identifies gaps, and proposes
concrete adaptations ordered by value-to-effort ratio.

---

## 1. Tool Architecture

### What They Have

Each of their 44 tools lives in its own directory with:
- Schema definition (Zod)
- `call()` implementation
- `checkPermissions()` — per-tool permission logic
- `validateInput()` — pre-execution validation
- UI rendering (React/Ink)
- Safety flags: `isConcurrencySafe()`, `isReadOnly()`, `isDestructive()`

**3-stage execution pipeline:**
```
validateInput(input, context)     → abort if invalid
checkPermissions(input, context)  → abort if denied
call(input, context, onProgress)  → execute with streaming
```

**Factory pattern with fail-closed defaults:**
```typescript
buildTool(def) → {
  isConcurrencySafe: false,   // assume NOT safe
  isReadOnly: false,           // assume WRITES
  isDestructive: false,        // opt-in
  ...def                       // user overrides
}
```

**Dependency injection via ToolUseContext:**
- Tools access other tools, state, permissions, messages through one context object
- No globals — everything flows through the context
- Enables agent nesting (subagent context is distinct from parent)

### What We Have (aicp/core/tools.py)

- 12 tools defined as OpenAI function-calling dicts
- Two registries: `_TOOL_REGISTRY` (basic) + `_MULTIMODAL_REGISTRY` (LocalAI-dependent)
- `execute_tool(name, arguments, project_path, backend)` dispatcher
- `get_tools_for_mode(mode)` returns tool set by Think/Edit/Act
- No per-tool validation, no per-tool permissions, no streaming progress

### Gap Analysis

| Feature | Claude Code | AICP | Effort to Add |
|---------|-------------|------|---------------|
| Per-tool validation | `validateInput()` | None | Low |
| Per-tool permissions | `checkPermissions()` | Mode-level only | Medium |
| Safety flags | `isConcurrencySafe`, `isReadOnly`, `isDestructive` | Implicit in mode sets | Low |
| Progress streaming | `onProgress(data)` callback | None | Medium |
| Tool-as-directory | Each tool in own folder | All in one file | Refactor (not needed yet) |
| Dependency injection | ToolUseContext | `backend` param only | Medium |

### Recommended Adaptation

**Phase 1 (Low effort, high value):** Add safety metadata to tool definitions.

```python
# In tools.py — extend each tool dict
TOOL_SHELL = {
    "type": "function",
    "function": { ... },
    # New safety metadata
    "_meta": {
        "is_read_only": False,
        "is_destructive": True,
        "is_concurrent_safe": False,
        "requires_backend": False,
    }
}
```

**Phase 2 (Medium effort):** Add `validate_tool_input(name, arguments)` pre-check
before `execute_tool()`. Catches malformed paths, missing required args, etc.

**Phase 3 (When fleet needs it):** Add progress callbacks for long-running tools
(shell commands, image generation). Fleet agents can stream progress to MC dashboard.

---

## 2. Memory System

### What They Have (memdir/)

Their persistent memory is architecturally identical to ours — MEMORY.md index +
topic files with YAML frontmatter. But they add several layers:

**AI-powered relevance scoring (findRelevantMemories.ts):**
1. Scan all memory files → extract frontmatter (name, description, type, mtime)
2. Format as manifest: `- [type] filename (timestamp): description`
3. Call Sonnet (small/fast model) with user query + manifest
4. Model returns top 5 most relevant filenames
5. Load only those 5 files into context

**Memory aging (memoryAge.ts):**
- `memoryAgeDays(mtime)` — floor-rounded days since modification
- Staleness warning for memories >1 day old: "claims about code behavior
  or file:line citations may be outdated — verify against current code"

**Auto-extraction (extractMemories.ts):**
- Background subagent runs after each complete query (no tool calls in response)
- Reads last ~30 messages, extracts notable facts
- Creates/updates memory files with learned information
- Limited tool access (read-only Bash, Grep, Glob — no destructive ops)
- Prevents duplicates by scanning existing memories first

**Session memory (sessionMemory.ts):**
- Per-conversation summary, distinct from persistent memory
- Updated when context grows >5K tokens or >3 tool calls since last update
- Runs as forked subagent sharing parent's prompt cache
- Stored at `.claude_session_memory.md`

**Away summary (awaySummary.ts):**
- Generated on session end: "You were debugging X. Next step: Y"
- Used as context when user returns to resume work
- 1-3 sentences, high-level task + concrete next step

**Team memory (teamMemPaths.ts):**
- Shared `team/` subdirectory with symlink protection
- Security: rejects relative paths, null bytes, URL-encoded traversals, symlink escapes
- Synced across project contributors

**Guardrails:**
- Max 200 memory files, 25KB index
- Only first 30 lines read during scan (frontmatter extraction)
- 256 token budget for relevance scoring call

### What We Have

- MEMORY.md + topic files (same structure)
- 4 memory types: user, feedback, project, reference (same taxonomy)
- YAML frontmatter with name, description, type (same format)
- Manual creation only (no auto-extraction)
- No relevance scoring (all loaded into prompt)
- No aging/staleness
- No session memory
- No team memory

### Gap Analysis

| Feature | Claude Code | AICP | Value for Fleet |
|---------|-------------|------|-----------------|
| AI relevance scoring | Sonnet call, top 5 | Load all | HIGH — reduces prompt bloat |
| Memory aging | Staleness warnings | None | MEDIUM — prevents stale info |
| Auto-extraction | Background subagent | Manual | HIGH — fleet agents learn |
| Session memory | Per-conversation summary | None | MEDIUM — long sessions |
| Away summary | Resume context | None | HIGH — fleet agent restarts |
| Team memory | Shared subdirectory | None | MEDIUM — fleet-wide knowledge |
| File cap | 200 files, 25KB | Uncapped | LOW — preventive |

### Recommended Adaptation

**Phase 1 — Embedding-based relevance (our advantage: nomic-embed is local):**

Claude Code calls Sonnet (cloud) for relevance scoring. We can do better — we
already have `nomic-embed` running on CPU. Instead of an LLM call, use embeddings:

```python
# In a new memory_relevance.py
def select_relevant_memories(query: str, memory_dir: str, top_k: int = 5) -> list[str]:
    """Use nomic-embed to find most relevant memories for a query."""
    # 1. Scan memory files, extract descriptions
    headers = scan_memory_files(memory_dir)
    
    # 2. Embed query
    query_embedding = embed(query)  # nomic-embed, local, free
    
    # 3. Embed descriptions (cache these — they rarely change)
    desc_embeddings = [embed(h.description) for h in headers]
    
    # 4. Cosine similarity, return top_k
    scores = [cosine_sim(query_embedding, d) for d in desc_embeddings]
    return sorted(zip(headers, scores), key=lambda x: x[1], reverse=True)[:top_k]
```

This is strictly better than their approach:
- **Free** (local nomic-embed vs cloud Sonnet call)
- **Fast** (embedding lookup vs LLM inference)
- **Deterministic** (cosine similarity vs LLM judgment)
- We already have `nomic-embed` loaded and the `cosine_similarity` function in `rag.py`

**Phase 2 — Memory aging:**

Add `mtime` check when loading memories. If >24h old, append staleness note.
Trivial to implement — `os.path.getmtime()` + human-readable age string.

**Phase 3 — Away summary for fleet agents:**

When an agent daemon restarts or reconnects, generate a 1-3 sentence summary
of what it was doing. Use the local model (gemma4-e2b, fast) to summarize
the last N task history entries. Store at `~/.aicp/away_summary.txt`.

**Phase 4 — Auto-extraction (fleet-only):**

For fleet agents running 24/7, automatically extract learnings from task history
into memory files. Run as a periodic background job (every N tasks or every hour).
Use the local model to decide what's worth remembering.

---

## 3. Context Compaction

### What They Have (services/compact/)

Four-layer compaction strategy:

**Layer 1 — Auto-compact (threshold-based):**
- Triggers at `effectiveContextWindow - 13K tokens`
- Forked agent summarizes full conversation chronologically
- Produces `<analysis>` block (drafting) + `<summary>` block (final)
- Replaces old messages with compact boundary marker
- Circuit breaker: stops after 3 consecutive failures

**Layer 2 — Microcompact (tool result pruning):**
- Clears old results from: file reads, bash output, grep, glob, web search
- Replaces with `[Old tool result content cleared]`
- Keeps conversation structure, drops verbose tool output
- Non-compactable: API calls, MCP tools, agents

**Layer 3 — Time-based clearing:**
- If >60min gap between messages, server prompt cache likely expired
- Clear old tool results before next API call (shrinks context for rewrite)
- Only runs on main thread (subagents have short lifetimes)

**Layer 4 — Image stripping:**
- On compaction, replace images/documents with `[image]` markers
- Prevents prompt-too-long on image-heavy sessions

### What We Have (aicp/core/compaction.py)

- `estimate_tokens(messages)` — chars/4 heuristic
- `compact_messages(messages, max_tokens, keep_recent_turns)` — keeps system + recent N turns, summarizes older
- `should_compact(messages, model)` — threshold check
- `_summarize_messages()` — heuristic: first sentence per turn, last 20 points
- No microcompaction, no time-based clearing, no image stripping

### Gap Analysis

| Feature | Claude Code | AICP | Value |
|---------|-------------|------|-------|
| LLM-based summary | Forked agent | Heuristic (first sentence) | MEDIUM |
| Microcompact | Clear old tool results | None | HIGH for fleet |
| Time-based clearing | >60min gap | None | MEDIUM |
| Image stripping | `[image]` markers | None | LOW |
| Circuit breaker | 3 failures → stop | None | LOW |

### Recommended Adaptation

**Phase 1 — Microcompaction (high value for fleet):**

Fleet agents run 24/7. Tool results (especially file reads and grep output) are
the largest context consumers. After N turns, replace old tool results:

```python
def microcompact(messages: list[dict], keep_recent: int = 5) -> list[dict]:
    """Clear old tool results while keeping conversation structure."""
    compactable_tools = {"file_read", "file_list", "grep", "shell", "kb_search"}
    
    # Find tool result messages older than keep_recent turns
    tool_results = [m for m in messages if m.get("role") == "tool"]
    old_results = tool_results[:-keep_recent] if len(tool_results) > keep_recent else []
    
    for msg in old_results:
        if msg.get("name") in compactable_tools:
            msg["content"] = "[Tool result cleared — re-run if needed]"
    
    return messages
```

**Phase 2 — LLM-based summary (when local model is warm):**

Instead of the heuristic summarizer, use the already-warm local model to produce
a proper conversation summary. Since we have single-active-backend, this only
works when the reasoning model is already loaded (no cold start penalty).

---

## 4. Skill System

### What They Have (skills/)

**Frontmatter fields (superset of ours):**
```yaml
---
name: commit
description: Create a git commit
allowed-tools: Bash, FileRead, Glob, Grep  # SECURITY BOUNDARY
model: sonnet                               # MODEL OVERRIDE
context: inline | fork                      # EXECUTION CONTEXT
agent: worker                               # AGENT TYPE
effort: low | medium | high                 # COMPLEXITY HINT
hooks: { ... }                              # LIFECYCLE HOOKS
paths: [src/, tests/]                       # SCOPE RESTRICTION
---
```

**Key additions beyond ours:**
- `allowed-tools` — restrict which tools a skill can access (security boundary)
- `model` — override which model runs the skill
- `context: fork` — skill runs as sub-agent with isolated context
- `agent` — specify agent type (worker, coordinator)
- `paths` — restrict file access scope
- `hooks` — lifecycle hooks (pre/post execution)

**Skill-as-MCP-tool:** Skills can be discovered and invoked via MCP servers,
enabling cross-project skill sharing.

### What We Have (aicp/core/skills.py + .claude/skills/)

- 78 skills across `.claude/skills/` directories
- 4-layer discovery: AICP global → AICP project → Claude Code global → Claude Code project
- Frontmatter: name, description, allowed-tools, effort, argument-hint
- `resolve_params()` + `apply_params()` for template substitution
- `generate_claude_skill()` — convert AICP YAML to Claude Code SKILL.md
- No model override, no fork context, no scope restriction, no hooks

### Gap Analysis

| Feature | Claude Code | AICP | Value |
|---------|-------------|------|-------|
| Model override per skill | `model: sonnet` | None | HIGH — fleet optimization |
| Fork context | `context: fork` | None | MEDIUM — isolation |
| Scope restriction | `paths: [src/]` | None | LOW — security |
| Lifecycle hooks | `hooks: {...}` | None | MEDIUM — extensibility |
| MCP skill discovery | Skills via MCP | None | MEDIUM — fleet sharing |

### Recommended Adaptation

**Phase 1 — Model override per skill (immediate fleet value):**

Add `model` field to skill frontmatter. Fleet heartbeat skills should use
`gemma4-e2b` (53 tok/s), code review skills should use `qwen3-8b` (thinking mode).

```yaml
# .claude/skills/fleet-heartbeat/SKILL.md
---
name: fleet-heartbeat
description: Fleet agent heartbeat response
allowed-tools: Read
model: gemma4-e2b          # Fast model for heartbeats
effort: low
---
```

Implementation: In `skills.py`, parse `model` from frontmatter.
In `controller.py`, if skill specifies model, override the routing decision.

**Phase 2 — Scope restriction per skill:**

Skills that operate on specific directories (e.g., `ops-deploy` only touches
`infrastructure/`) should declare their scope. The controller checks file access
against the skill's `paths` list.

---

## 5. Agent Orchestration

### What They Have

**Agent spawning:**
- `AgentTool` — spawns sub-agents with isolated context
- Sync (blocking) or async (backgrounded) based on `run_in_background`
- Fork subagent shares parent's prompt cache (cache-safe params)
- Coordinator mode: spawn workers, receive `<task-notification>` XML results

**Task management (Task.ts + framework.ts):**
- `TaskType`: local_bash, local_agent, remote_agent, in_process_teammate, workflow, monitor, dream
- `TaskStatus`: pending → running → completed/failed/killed
- Task ID: prefix + 8 random chars (e.g., `a1k3m5n7` for agent task)
- `registerTask()` → `updateTaskState()` → `completeAgentTask()`/`failAgentTask()`
- Atomic updates via immutable state + updater functions

**Progress tracking:**
- Per-turn: tool use count, token counts (latest input, cumulative output)
- Recent activities: last 5 tool calls with descriptions
- Background summarization: every 30s, a forked agent summarizes agent progress
- Summary: 3-5 words, present tense, file-specific (e.g., "Editing auth middleware tests")

**Key patterns:**
- `createChildAbortController()` — parent abort propagates to subagents
- `CleanupRegistry` — ensures background tasks abort on shutdown
- Eviction grace period: 30s before GC of completed tasks (UI retention)

### What We Have

- `aicp/agent/server.py` — agent daemon (HTTP server)
- `aicp/agent/client.py` — fleet client for remote nodes
- `aicp/core/cluster.py` — multi-machine cluster support
- No sub-agent spawning (single execution thread)
- No task lifecycle management
- No progress tracking
- No background summarization

### Gap Analysis

| Feature | Claude Code | AICP | Fleet Value |
|---------|-------------|------|-------------|
| Sub-agent spawning | AgentTool with sync/async | None | HIGH |
| Task lifecycle | Full state machine | None | HIGH |
| Progress tracking | Per-turn metrics | None | HIGH |
| Background summarization | 30s polling | None | MEDIUM |
| Child abort propagation | AbortController chain | None | MEDIUM |
| Cleanup registry | Ensures shutdown cleanup | None | MEDIUM |

### Recommended Adaptation

**Phase 1 — Task lifecycle for fleet agents:**

Fleet agents (via OpenFleet) submit tasks to AICP. Currently these are
fire-and-forget requests to `/v1/chat/completions`. Adding a task wrapper:

```python
@dataclass
class TaskState:
    id: str                    # a<8 random chars>
    status: str                # pending|running|completed|failed
    prompt: str
    mode: str
    backend: str
    created_at: float
    completed_at: float | None = None
    result: str | None = None
    error: str | None = None
    token_count: int = 0
    tool_use_count: int = 0
```

This maps directly to our DLQ (failed tasks) and history (completed tasks)
but adds real-time status tracking during execution.

**Phase 2 — Progress streaming to fleet MC:**

During task execution, emit progress events to OpenFleet's event bus.
MC dashboard can show: "Agent alpha-3: Editing auth middleware tests (3 tools, 1.2K tokens)"

---

## 6. Cost Tracking

### What They Have (cost-tracker.ts)

**Formula:**
```
cost = (input_tokens / 1M) × input_price
     + (output_tokens / 1M) × output_price
     + (cache_read_tokens / 1M) × cache_read_price
     + (cache_write_tokens / 1M) × cache_write_price
     + web_search_requests × search_price
```

**Per-model breakdown:** Accumulates by canonical model name (e.g., "sonnet" not
"claude-3-5-sonnet-20241022"). Tracks: input/output/cache_read/cache_write tokens + cost.

**Session persistence:** Saves to project config before exit, restores on resume.
Includes: total cost, API duration, cache stats, session ID.

**Recursive tracking:** Subagent/advisor costs roll up to parent session total.

**OpenTelemetry integration:** Cost counter, token counter, session counter as OTel metrics.

### What We Have (aicp/core/budget.py + prometheus.py)

- `BudgetLimits` — tracks max_cost_usd, max_steps, max_file_changes, max_duration
- `MetricsCollector` — tracks per-backend: requests, errors, tokens, cost, latency
- `history.py` — stores estimated_cost_usd per task record
- No cache-aware pricing (we use local models — no cache pricing needed)
- No per-model breakdown in budget (only in metrics)
- Snapshot persistence exists (Stage 4, Phase 5)

### Gap Analysis

Our cost tracking is simpler because local inference is free. The main cost
is cloud backends (Claude, OpenRouter). Their patterns are most valuable for:

1. **Cloud cost breakdown** — when we route to Claude/OpenRouter, track per-model costs
2. **Session cost persistence** — survive restarts (we already have this via snapshots)
3. **Budget enforcement** — their `maxBudgetUsd` maps to our `BudgetLimits.max_cost_usd`

### Recommended Adaptation

**Enhance cloud cost tracking in MetricsCollector:**

Add per-model cost breakdown for cloud backends. When a task routes to Claude or
OpenRouter, record the model-specific cost using their pricing formula. The local
backend cost is always $0.

---

## 7. MCP Integration

### What They Have (services/mcp/)

- **22 files** for MCP alone
- Multi-scope config: local → project → user → enterprise → plugins → claude.ai
- Transport types: stdio, SSE, HTTP, WebSocket, SDK
- OAuth + PKCE authentication for remote servers
- Channel gating (MCP servers control access by channel)
- Auto-reconnect with exponential backoff (max 5 attempts)
- Tool/prompt/resource discovery with LRU caching
- MCP tools appear as native tools in the tool pool

### What We Have (aicp/mcp/server.py)

- Single FastMCP server exposing 5 tools (chat, transcribe, speak, vision, voice_pipeline)
- stdio transport only (Claude Code integration)
- No client-side MCP consumption
- No auth, no reconnection, no resource discovery

### Gap Analysis

| Feature | Claude Code | AICP | Fleet Value |
|---------|-------------|------|-------------|
| MCP server | Full tool exposure | 5 basic tools | MEDIUM |
| MCP client | Consume external MCP servers | None | HIGH |
| Multi-transport | stdio, SSE, HTTP, WS | stdio only | MEDIUM |
| Auth | OAuth + PKCE | None | LOW for local |
| Auto-reconnect | Exponential backoff | None | HIGH for fleet |
| Resource discovery | List + read MCP resources | None | MEDIUM |

### Recommended Adaptation

**Phase 1 — Expose more AICP capabilities via MCP:**

Our MCP server only exposes 5 tools. Add:
- `aicp_route` — route a prompt through the full controller (with score-based routing)
- `aicp_health` — deep health check (backends, circuit breaker, warming)
- `aicp_profile` — get/set active profile
- `aicp_kb_search` — semantic search in knowledge base
- `aicp_task_status` — check task status (when task lifecycle is added)
- `aicp_dlq_status` — DLQ status and retry

**Phase 2 — MCP client for fleet integration:**

AICP could consume OpenFleet's MCP server to:
- Receive task assignments
- Report progress
- Query fleet status
- Share knowledge across nodes

---

## 8. Plugin System

### What They Have

Plugins bundle: MCP servers + LSP servers + hooks + skills + agents.
Lifecycle: install → enable → disable → update → uninstall.
Sources: builtin, marketplace, git repos.

### Applicability to AICP

Not immediately needed. AICP is a single-purpose platform, not an extensible IDE.
However, the pattern of "capability bundles" (MCP + skills + hooks) could be how
fleet agents discover and load AICP capabilities. File for future reference.

---

## 9. Hook System

### What They Have

Event-driven extensibility at lifecycle points:
- `permission_request` — before tool execution
- `post_sampling` — after API call
- `session_start/end` — session lifecycle
- `task_created` — when tasks are registered

Hook types: shell command, agent prompt, HTTP call.
Configuration: `.claude/hooks.json` with JSON schema validation.

### Applicability to AICP

Our circuit breaker, DLQ, and warmup already handle the reliability hooks.
But adding an event hook system would enable:

- `on_task_complete` → notify OpenFleet event bus
- `on_model_swap` → log to metrics, update dashboard
- `on_circuit_open` → alert via ntfy
- `on_dlq_enqueue` → notify operator

**Recommended:** Add a lightweight event emitter to the controller.
Not a full hook system — just `emit(event_name, data)` with registered callbacks.

---

## 10. Unique Claude Code Features

### MagicDocs (auto-updating documentation)
Files marked with `# MAGIC DOC: [title]` are automatically updated by a background
agent based on conversation context. Interesting for our KB — documents that
self-update based on what the system learns.

### Buddy (terminal Tamagotchi)
Deterministic gacha system using Mulberry32 PRNG seeded from userId.
Pure fun, not applicable, but delightful engineering.

### Voice Pipeline
Multi-tier audio: native cpal → arecord (ALSA) → SoX (fallback).
STT via WebSocket streaming. Keyterm boosting from project context.
We already have Whisper + Piper — their STT streaming pattern could improve latency.

### BoundedUUIDSet (ring buffer deduplication)
O(capacity) memory deduplication using ring buffer + Set.
Useful for fleet message deduplication (OpenFleet event bus).

### Feature Latches
Sticky-on flags that prevent mid-session cache busts. Once a prompt cache
header is set, it stays for the session even if the feature toggles off.
Interesting for our profile system — avoid cache invalidation on profile switch.

---

## Summary: Adoption Roadmap

### Immediate (Low effort, High value)

| # | Feature | Files to Modify | Effort |
|---|---------|----------------|--------|
| 1 | Tool safety metadata | `aicp/core/tools.py` | 1h |
| 2 | Memory aging/staleness | New: `aicp/core/memory_relevance.py` | 2h |
| 3 | Skill model override | `aicp/core/skills.py`, frontmatter parsing | 2h |

### Short-term (Medium effort, High value)

| # | Feature | Files to Modify | Effort |
|---|---------|----------------|--------|
| 4 | Embedding-based memory relevance | New: `aicp/core/memory_relevance.py` + `rag.py` | 4h |
| 5 | Microcompaction | `aicp/core/compaction.py` | 3h |
| 6 | Extended MCP tools | `aicp/mcp/server.py` | 3h |
| 7 | Controller event emitter | `aicp/core/controller.py` | 2h |

### Medium-term (Higher effort, Fleet-dependent)

| # | Feature | Files to Modify | Effort |
|---|---------|----------------|--------|
| 8 | Task lifecycle state machine | New: `aicp/core/tasks.py` | 6h |
| 9 | Away summary for agent restart | `aicp/agent/server.py` | 4h |
| 10 | Auto-memory extraction | New: `aicp/core/memory_extract.py` | 8h |
| 11 | Progress streaming to fleet | `aicp/agent/server.py` + `client.py` | 6h |

### Future (When fleet is production)

| # | Feature | Notes |
|---|---------|-------|
| 12 | Team memory | Shared memory across fleet nodes |
| 13 | MCP client | Consume OpenFleet's MCP server |
| 14 | Hook system | Event-driven fleet notifications |
| 15 | Fork subagent | Parallel execution with shared cache |

---

## Architecture Comparison

```
Claude Code (TypeScript)              AICP (Python)
========================              =============
Tool.ts (base)                   →    tools.py (flat registry)
tools.ts (registry/assembly)     →    tools.py (get_tools_for_mode)
tools/*/ (44 dirs)               →    tools.py (12 functions)
skills/ (bundled + file-based)   →    skills.py (4-layer discovery)
memdir/ (6 files)                →    MEMORY.md + manual topic files
compact/ (5 files)               →    compaction.py (basic)
cost-tracker.ts                  →    budget.py + prometheus.py
Task.ts + tasks/                 →    history.py (post-hoc only)
services/mcp/ (22 files)         →    mcp/server.py (5 tools)
query.ts (execution loop)        →    controller.py (orchestrator)
state/AppState                   →    session.py + config
hooks/ (extensibility)           →    circuit_breaker.py + dlq.py
AgentTool/ (sub-agents)          →    agent/server.py (daemon)
services/analytics/ (9 files)    →    prometheus.py (metrics)
```

**Key insight:** Claude Code has ~10x more code than AICP for similar functionality.
Much of that is UI rendering (React/Ink), cloud auth (OAuth/PKCE), and IDE integration.
The core patterns (tool pipeline, memory, compaction, orchestration) are transferable
at ~1/5 the code size in Python.

---

## What They Do Better

1. **Memory relevance** — selecting which memories matter instead of loading all
2. **Microcompaction** — surgical context pruning instead of wholesale summarization
3. **Tool safety** — fail-closed defaults, per-tool permissions
4. **Agent orchestration** — real task lifecycle with progress tracking
5. **Skill flexibility** — model override, fork context, scope restriction

## What We Do Better

1. **Local-first** — their memory relevance costs a Sonnet call; ours uses free embeddings
2. **Profile system** — they have no equivalent to our 9-profile configuration system
3. **Circuit breaker** — they rely on rate limits; we have per-backend state machines
4. **DLQ** — they lose failed tasks; we persist and retry
5. **Score-based routing** — they route by hardcoded rules; we score with configurable thresholds
6. **Multi-backend** — they have one backend (Claude); we orchestrate local + 3 cloud tiers
7. **GPU management** — they don't manage hardware; we handle VRAM, model swaps, KV cache
8. **Health reports** — they have no proactive trend detection; we do

## Honest Assessment

Their codebase is a masterpiece of production engineering. The tool permission system,
memory relevance scoring, context compaction layers, and agent orchestration represent
years of iteration. AICP is younger and simpler, but has architectural advantages
they don't: local inference, multi-backend routing, GPU management, and fleet-oriented
reliability (circuit breaker, DLQ, warmup).

The best path forward is surgical adoption: take the patterns that fill our gaps
(memory relevance, microcompaction, tool safety, task lifecycle) while keeping our
strengths (local-first, profile system, score-based routing, reliability hardening).
