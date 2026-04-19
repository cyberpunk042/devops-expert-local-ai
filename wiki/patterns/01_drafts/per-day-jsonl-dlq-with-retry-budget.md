---
title: "Per-Day JSONL Dead-Letter Queue with Retry Budget and Status Tracking"
type: pattern
domain: backend-ai-platform-python
layer: 5
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "model-quality"
  - "per-backend-circuit-breaker-with-failover-chain"
instances:
  - page: "AICP controller failure path (aicp/core/controller.py line 487-499)"
    context: "When breaker + failover chain are exhausted, the controller calls dlq.enqueue() with full task context (prompt, mode, backend, project, error, failover_chain). The enqueue happens inside an except clause, so DLQ failures don't mask the original exception — the original failure still raises after persistence."
  - page: "AICP CLI --retry-dlq + MCP dlq_status tool"
    context: "Operator-driven retry surface (`aicp --retry-dlq` invokes `dlq.retry_pending(controller, max_items=10)` per CLAUDE.md `## Reliability` table). MCP server exposes `dlq_status` as a tool for fleet agents and external observers (per CLAUDE.md `## Intelligent Infrastructure` 11-tool MCP listing). Same DLQ store; two distinct invocation surfaces."
  - page: "AICP reliable profile dlq config (config/profiles/reliable.yaml)"
    context: "Production-leaning workloads override defaults — `dlq.max_retries: 5` (vs default 3), `retry_delay_seconds` typically reduced. Same DLQ code path; different operational policy. Profile system (per profile-as-coordination-bundle) makes this one switch among ~12 settings."
created: 2026-04-19
updated: 2026-04-19
sources:
  - id: aicp-dlq
    type: file
    file: aicp/core/dlq.py
    description: "260-line implementation — enqueue/list_entries/count/retry_pending/_prune_oldest/_mark_entry/status; per-day JSONL files in ~/.aicp/dlq/ keyed by UTC date"
  - id: aicp-controller-failure-path
    type: file
    file: aicp/core/controller.py
    description: "Lines 487-499 — DLQ persistence inside except clause AFTER failover exhaustion; original error still propagates upstream after DLQ write"
  - id: reliable-profile
    type: file
    file: config/profiles/reliable.yaml
    description: "dlq.max_retries: 5 — production tuning; demonstrates profile-tunable retry budget"
  - id: claude-md-reliability
    type: file
    file: CLAUDE.md
    description: "## Reliability section — DLQ entry: 'Failed tasks → ~/.aicp/dlq/ JSONL; retry via aicp --retry-dlq'; MCP server section lists dlq_status as one of 11 tools"
  - id: model-quality
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-quality.md
    description: "Second brain Quality model — durability and graceful-degradation principles. DLQ instantiates 'never lose work' for the AI inference domain."
tags: [pattern, reliability, dlq, dead-letter-queue, persistence, retry, jsonl, aicp, backend-ai-platform-python, transferable]
---

# Per-Day JSONL Dead-Letter Queue with Retry Budget and Status Tracking

## Summary

When a layered reliability stack (per-backend circuit breakers → failover chain → final fallback) can still fail end-to-end — because every backend in the chain is unavailable, or the failure is structurally irrecoverable in the moment (network partition, all credentials expired, throttle ceiling hit) — the workload that triggered the cascade is **about to be lost** unless something captures it. AICP's pattern: **append a JSONL line per failed task to `~/.aicp/dlq/<UTC-date>.jsonl`** with full reconstruction context (prompt, mode, backend, project_path, error string, failover_chain that was attempted, retry_count starting at 0, status="pending", timestamp). One file per UTC date (auto-rotation, matches the existing history pattern), append-only writes (no locks needed for single-writer single-process), per-line independent JSON (corrupt lines don't poison the file). Reads are lazy: `list_entries()` walks files newest-first and parses on demand, capping at `max_count`. Retry is a separate operator-invoked or scheduler-invoked operation: `retry_pending(controller, max_items=10)` filters entries that are (a) status="pending", (b) retry_count < max_retries (default 3, profile-tunable to 5+), (c) older than `retry_delay_seconds` (default 300s = 5min — gives transient failures time to clear); each retry runs through the same controller path that originally failed, and the entry's status flips to "succeeded" or its retry_count increments. A bounded queue (`max_entries`, default 1000) with `_prune_oldest` keeps disk usage bounded. The pattern's distinctive choice is **per-day JSONL files instead of a single growing file or a database**: rotation is implicit in the filename, archival is `tar` on yesterday's files, querying recent failures is `tail -100 today.jsonl`, and operators can edit the file directly to mark stuck entries — no schema migrations, no DB connection, no daemon. The trade-off accepted: no built-in indexing (can't query "all DLQ entries for backend=X" without scanning); the trade-off rejected: SQLite, which would add a dependency for what is fundamentally an append log.

> [!info] Pattern Reference Card
>
> | Component | Role | Why this shape |
> |-----------|------|----------------|
> | Per-day file (`~/.aicp/dlq/<UTC-date>.jsonl`) | Storage with implicit rotation | No rotation daemon; date encoded in filename; matches history pattern in same dir tree |
> | Append-only JSONL | Concurrency-safe-enough for single-writer | No locks needed for AICP's single-process controller; corrupt line doesn't poison file |
> | Full task context per entry | Enables faithful retry | prompt + mode + backend + project_path + failover_chain — no external state needed |
> | `status` field (pending/succeeded) + `retry_count` | Tracks retry history per entry | Status flips during retry; retry_count caps at `max_retries` |
> | `enqueued_at` (epoch float) + `retry_delay_seconds` filter | Prevents tight-loop retry on transient failures | Entries become eligible only after delay; permits backoff without separate scheduler |
> | `max_entries` + `_prune_oldest` | Bounded disk usage | When full, evicts oldest half (not oldest one — amortized O(1) per insert) |
> | Profile-configurable (`config["dlq"]`) | Per-workload tuning | reliable profile overrides max_retries; default profile uses conservative values |
> | Two invocation surfaces (CLI + MCP) | Operator AND programmatic access | `aicp --retry-dlq` for humans; `dlq_status` MCP tool for agents |

## When to apply

Use this pattern when ALL of the following are true:

1. **Workloads are bounded and replayable** — each unit of work has finite context that can be serialized and re-run. AI inference requests fit (prompt + mode + project = enough). Streaming sessions don't fit (state grows unboundedly during the stream).
2. **A reliability stack already exists** that handles the common-case retries (circuit breaker for fast-fail, failover chain for cross-backend). DLQ catches what the stack missed; it's not the first line of defense.
3. **Single-writer (or coordinated multi-writer)** — append-only JSONL is concurrency-safe for one writer per file. Multi-process writers would need fcntl locks or a different store.
4. **Operators want to inspect / surgically edit** the failed-work store. JSONL is `cat`-able, `grep`-able, and `jq`-able. SQLite needs a client.

Do NOT apply when:

- **Real high-throughput** (>100 failed tasks/second): JSONL becomes a hot file; switch to a real queue (Redis Streams, Kafka).
- **Strong ordering / exactly-once** is required: JSONL doesn't enforce ordering across files; retry doesn't dedupe across runs.
- **Multi-process writers without coordination**: race conditions on append are possible (rare with O_APPEND but not zero); use a real queue.

## Implementation shape

```
┌──────────────────────────────────────────────────────────────────────┐
│ Failure path (controller exception handler)                            │
│   except (Exception, CircuitBreakerOpen) as e:                        │
│     # ... try failover chain ...                                       │
│     if all backends failed:                                            │
│       try:                                                             │
│         dlq.enqueue(prompt=..., mode=..., backend=...,                 │
│                     project=..., error=str(e), failover_chain=...,    │
│                     config=self.config)                                │
│       except Exception:                                                │
│         pass  # DLQ persistence failure shouldn't mask original error │
│       raise e from None                                                │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Storage (~/.aicp/dlq/2026-04-19.jsonl)                                │
│   {"timestamp":"2026-04-19T14:32:11Z", "enqueued_at":1745079131.4,    │
│    "prompt":"...", "mode":"edit", "backend":"local", "project":"...", │
│    "error":"CircuitBreakerOpen: backend 'local' open for 32.4s",      │
│    "failover_chain":["local","fleet","openrouter","claude"],          │
│    "retry_count":0, "status":"pending"}                                │
│   {"timestamp":"...", ...}                                             │
│   ...                                                                  │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Retry (operator-invoked OR scheduler-invoked)                          │
│   retry_pending(controller, max_items=10):                            │
│     entries = list_entries() where status==pending                    │
│                  AND retry_count < max_retries                         │
│                  AND now - enqueued_at >= retry_delay_seconds         │
│     for entry in entries[:max_items]:                                  │
│       try: controller.run(reconstruct_task(entry))                     │
│             mark status=succeeded                                      │
│       except: increment retry_count, status stays pending             │
└──────────────────────────────────────────────────────────────────────┘
```

## Alternatives

### Alternative 1: SQLite DLQ table

Store entries in a SQLite database with proper indexes (backend, status, retry_count).

> [!warning] Rejected: adds dependency on a SQL store for what is fundamentally an append log + occasional scan. AICP avoids long-running daemons / external services where a flat file works (this is the same principle behind LocalAI v4.1.3's choice over distributed services for inference). SQLite would give: indexed queries (real benefit), schema migrations (unwanted complexity), connection management (unwanted complexity), `.db` file that operators can't `cat`/`grep` (operational regression). The query patterns AICP actually uses (most-recent-first, count-by-status, filter-by-retry-delay) are well-served by linear scans of files capped at 1000 entries.

### Alternative 2: Single growing JSONL file (no per-day rotation)

One `dlq.jsonl` that grows forever (or until manually truncated).

> [!warning] Rejected: rotation is the operationally-expensive part to skip. With per-day files: archival is `mv 2026-04-12.jsonl /backup/` — no daemon, no `logrotate` config. With one growing file: rotation requires a separate logrotate-style mechanism, copy-then-truncate races, etc. The per-day filename also lets operators answer "what failed yesterday?" with `cat 2026-04-18.jsonl | jq` — no SQL, no parsing. The cost of rotation: zero (date is in `_today_file()` line 35-36). The cost of NOT rotating: operational debt that will accumulate.

### Alternative 3: In-memory ring buffer (no persistence)

Keep failed tasks in a deque in the controller process. No disk, no JSON.

> [!warning] Rejected: defeats the whole point. Process restart loses the queue. AICP's controller restarts during config reload, after OOM, after model swaps that hang the watchdog. A DLQ that loses entries on restart is worse than no DLQ — operators expect persistence. The disk cost of a 1000-entry JSONL DLQ is ~500KB; the durability benefit is total. In-memory might be appropriate as a *cache layer* in front of the JSONL DLQ for very-high-throughput scenarios, but the JSONL is the source of truth.

### Alternative 4: Real message queue (Redis Streams / Kafka / RabbitMQ)

A purpose-built persistent queue with consumer groups, ack/nack, exactly-once semantics.

> [!warning] Rejected at AICP's current scale: real queues are correct for high-throughput multi-consumer workloads. AICP's DLQ throughput is "occasional failure" — single-digit entries per day in normal operation, dozens during a backend outage. The operational cost of running Redis (process to manage, port to expose, persistence to configure, AOF to tune) dwarfs the benefit at this scale. The pattern is intentionally chosen for the operational scale; if AICP graduates to multi-process / multi-machine fleet operation, the DLQ should migrate to a real queue. The migration is straightforward because the entry shape is JSON.

### Alternative 5: Re-raise without persistence (just let the exception propagate)

Don't capture the failed task. The caller deals with it (e.g., the user re-types the prompt).

> [!warning] Rejected: caller-side recovery is fine for interactive use but breaks for any automated invocation. Fleet agents calling AICP via MCP can't re-type a prompt; their orchestrator would need to capture failures separately. By centralizing persistence in AICP itself, every caller gets the same durability guarantee without coordinating across invocation paths (CLI, MCP, agent server). The CLI user can use `aicp --retry-dlq` later; the fleet agent's orchestrator can poll `dlq_status` MCP tool. Both work because the entry exists.

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **DLQ persistence happens AFTER failover exhaustion, BEFORE re-raise.** `aicp/core/controller.py` line 485-499 wraps the entire backend-call-and-failover block in a final except. Inside that except: write to DLQ, then re-raise the original error. This ordering matters — the DLQ captures what the user/agent will see fail; the upstream still gets the exception so it knows to surface the failure. A pre-failover DLQ would over-capture (entries for tasks that succeeded on failover); a post-success DLQ would under-capture (entries lost on re-raise paths that bypass the handler).
>
> 2. **Per-line independent JSON survives partial corruption.** `enqueue` writes one JSON object per line via `f.write(json.dumps(entry) + "\n")` (line 81). If a line is truncated by a power loss, `list_entries` (line 91-100) skips the bad line via `try/except json.JSONDecodeError` — every other entry remains parseable. A single-document JSON file (one giant array) would lose ALL entries on corruption. JSONL is the correct serialization for append-only event logs precisely because of this property.
>
> 3. **Retry-delay filter prevents tight-loop retry on transient failures.** A backend that's been failing might recover in 30 seconds. Retrying immediately after enqueue (or after every operator invocation) would re-fail and burn the retry budget. The `now - enqueued_at >= retry_delay_seconds` filter (line 153) holds entries until the delay has elapsed. Default 300s = 5min — long enough for most transient causes (model reload, container restart, network blip) to clear, short enough that operators can still see retries succeed within a working session.
>
> 4. **Retry budget capped at `max_retries` prevents infinite reprocessing.** An entry that fails 3 times (default; 5 in reliable profile) is effectively poisoned and should be inspected manually. The status counts in `status()` (line 247-251) report this as `exhausted`. Exhausted entries stay on disk (still parseable, still inspectable) but `retry_pending` excludes them from the ready queue. This makes dead poison-pill entries visible in dashboards without polluting active retry attempts. Operators can `jq 'select(.retry_count >= 3)' today.jsonl` to find them.
>
> 5. **Two invocation surfaces (CLI `--retry-dlq` + MCP `dlq_status`) share one store.** AICP exposes the DLQ via two distinct entry points: humans use `aicp --retry-dlq` (per CLAUDE.md `## Reliability` row), agents use the `dlq_status` MCP tool (per CLAUDE.md `## Intelligent Infrastructure` 11-tool listing). Both paths read from the same `~/.aicp/dlq/` store. This is what makes the DLQ a stable contract — the storage shape is the API, not the function signatures. Adding a third surface (e.g., HTTP endpoint, scheduler integration) doesn't change the store, only adds a new reader.
>
> 6. **Profile-tunable budgets follow the same pattern as circuit breaker / router.** `dlq.max_retries`, `dlq.retry_delay_seconds`, `dlq.max_entries`, `dlq.enabled` all live in `config["dlq"]` (line 53-58) and are overridden in `config/profiles/reliable.yaml` (max_retries: 5). The reliability stack is consistently profile-tunable across all three layers (breaker, failover, DLQ) — operators tune the WHOLE stack with one profile switch, not piecewise.

## Trade-offs

- **+** Durability across process restarts, OOMs, container redeploys (disk persists).
- **+** No external dependencies (no Redis, no DB, no daemon).
- **+** Operator-inspectable with standard tools (`cat`, `grep`, `jq`, `tail`).
- **+** Per-line independence — corruption is local, not catastrophic.
- **+** Two retry surfaces (CLI + MCP) with one store — stable contract.
- **−** No indexing — "find all entries for backend X" requires scan (acceptable at <1000 entries; broken at 10K+).
- **−** Single-writer assumption — multi-process writers would race on append (mitigated by O_APPEND but not bulletproof).
- **−** Retry counter is best-effort — `_mark_entry` rewrites the whole file (line 207); a crash mid-rewrite could lose the file. (AICP has not seen this in practice but it's a known risk.)
- **−** No exactly-once delivery — a successful retry that crashes before `_mark_entry` will retry again. Workloads must tolerate at-least-once.
- **−** Bounded queue silently drops oldest entries on overflow (`_prune_oldest`). High-failure scenarios lose oldest history.

## Detection / measurement

- **`dlq.count()`**: total entries on disk. Healthy = near-zero. Sustained growth = upstream failure not being addressed.
- **`dlq.status()` returns** `pending / succeeded / exhausted` — track ratios. High `exhausted` = real failures (not transient); investigate root cause. High `succeeded` = retry policy is working.
- **Time-since-oldest-pending**: if oldest pending entry is >24h old, retries aren't running (broken scheduler or operator forgot `--retry-dlq`).
- **`exhausted` count crossing alert threshold**: wire to ntfy / Prometheus alert. Indicates a class of work is structurally unable to complete; needs human triage.
- **DLQ growth rate during incidents**: a working DLQ should show a spike during outage and a decay after recovery (as retries clear pending). Flat-high after recovery = retries aren't being invoked.

## Related

- COMPLEMENTS: [Per-Backend Circuit Breaker with Failover Chain](./per-backend-circuit-breaker-with-failover-chain.md) — DLQ is the third layer in the reliability stack (breaker fast-fails → failover crosses backends → DLQ persists when chain exhausts)
- COMPLEMENTS: [profile-as-coordination-bundle](./profile-as-coordination-bundle.md) — `dlq.max_retries`/`retry_delay_seconds` are part of the ~12 settings switched together by profile activation
- ENABLES: Operator-driven incident recovery (`aicp --retry-dlq` after backend recovery) and agent-driven recovery (MCP `dlq_status` polling)
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-quality.md (Quality model — durability and graceful-degradation principles)
- DEPENDS ON: A bounded, replayable workload shape (prompt + mode + project_path is enough to reconstruct the AI inference call)

## Relationships

- INSTANCE OF: AICP's three-layer reliability stack (`aicp/core/dlq.py` invoked from `controller.py` line 487-499 after breaker + failover exhaustion)
- INSTANCE OF: Operator-and-agent dual-invocation surface (`aicp --retry-dlq` CLI + `dlq_status` MCP tool, same store)
- INSTANCE OF: Profile-tunable reliability budgets (`config/profiles/reliable.yaml` `dlq.max_retries: 5` overriding default 3)
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-quality.md
- COMPLEMENTS: [Per-Backend Circuit Breaker with Failover Chain](./per-backend-circuit-breaker-with-failover-chain.md)
- COMPLEMENTS: [profile-as-coordination-bundle](./profile-as-coordination-bundle.md)
