---
title: "Per-Backend Three-State Circuit Breaker with Failover-Chain Integration"
type: pattern
domain: backend-ai-platform-python
layer: 5
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "model-quality"
  - "4-tier-router-with-profiles-over-hardcoded-routing"
  - "profile-as-coordination-bundle"
instances:
  - page: "AICP controller failover (aicp/core/controller.py line 169-171, 431-483)"
    context: "Per-backend CircuitBreaker instances built once at controller init via build_breakers(); wrapped around backend.execute() at call time; CircuitBreakerOpen caught alongside generic Exception → enters failover chain (local → fleet → openrouter → claude). The breaker doesn't fight failover — it short-circuits the timeout wait so failover triggers in milliseconds, not after a full backend-call timeout."
  - page: "AICP reliable profile (config/profiles/reliable.yaml)"
    context: "Aggressive thresholds — failure_threshold: 2 (vs default 3), recovery_timeout: 20s (vs default 30s). Same breaker code, different config. Demonstrates that the pattern is profile-tunable: production-leaning workloads trip earlier and probe sooner; default-leaning workloads are more permissive."
  - page: "AICP DLQ integration (aicp/core/dlq.py via controller.py line 487-499)"
    context: "When ALL failover backends fail (or breakers are all open), the controller persists the failed task to JSONL via dlq.enqueue() before raising. Breaker + failover + DLQ form a three-layer reliability stack — fast-fail per backend, graceful failover across backends, durable persistence when the whole chain is exhausted."
created: 2026-04-19
updated: 2026-04-19
sources:
  - id: aicp-circuit-breaker
    type: file
    file: aicp/core/circuit_breaker.py
    description: "207-line implementation — State enum (CLOSED/OPEN/HALF_OPEN), CircuitBreaker class with thread-safe transitions, build_breakers() factory, CircuitBreakerOpen exception"
  - id: aicp-controller-failover
    type: file
    file: aicp/core/controller.py
    description: "Wires breakers per backend (line 170-171); wraps backend.execute() in breaker.call() (line 432-435); catches CircuitBreakerOpen with generic Exception to trigger failover (line 446)"
  - id: reliable-profile
    type: file
    file: config/profiles/reliable.yaml
    description: "Aggressive breaker config — failure_threshold: 2, recovery_timeout: 20, half_open_max: 1 — proves the pattern is profile-tunable per workload"
  - id: model-quality
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-quality.md
    description: "Second brain Quality model — 'fail-fast over fail-slow' principle for systems with retry budgets. Circuit breaker is the canonical fail-fast primitive."
tags: [pattern, reliability, circuit-breaker, failover, backend, state-machine, aicp, backend-ai-platform-python, transferable]
---

# Per-Backend Three-State Circuit Breaker with Failover-Chain Integration

## Summary

When a system orchestrates multiple interchangeable backends behind a failover chain (try local → fleet → cloud → escalation), the failure mode that ruins reliability isn't *individual* backend failure — it's **repeated synchronous waits on a known-bad backend** that block the failover chain from triggering. AICP's circuit breaker pattern solves this with a per-backend three-state machine (`CLOSED → OPEN → HALF_OPEN`) wired so that backend failures **count** toward a threshold (default 3 consecutive), tripping OPEN; OPEN state raises a specific `CircuitBreakerOpen` exception that the controller catches **alongside** generic exceptions, immediately advancing to the next failover backend; OPEN auto-transitions to HALF_OPEN after `recovery_timeout` (default 30s); HALF_OPEN allows ONE probe request through, and the probe's success/failure decides whether to close the breaker (recovered) or re-open it (still bad). The pattern's two non-obvious correctness properties: (a) the breaker raises a **distinct exception type** but is caught by the **same except clause** as generic failures — this is intentional, because the failover chain doesn't need to know whether the backend was slow-failing or fast-failing, only that it failed; (b) the breaker is **per-backend**, not per-controller — meaning a tripped local breaker doesn't affect the cloud breaker, so failover to a healthy backend works even when one is fully out. Implementation in `aicp/core/circuit_breaker.py` (207 lines, thread-safe, profile-configurable). The pattern composes with AICP's failover chain (controller line 446) and DLQ (controller line 487-499) into a three-layer reliability stack: per-backend fast-fail → cross-backend failover → durable persistence.

> [!info] Pattern Reference Card
>
> | Component | Role | Why it matters |
> |-----------|------|----------------|
> | State machine (CLOSED/OPEN/HALF_OPEN) | Tracks per-backend health | OPEN avoids the synchronous-wait failure mode; HALF_OPEN avoids permanent abandonment |
> | Per-backend instance (one breaker per backend name) | Isolates fault domains | A bad cloud doesn't trip the local breaker; a stuck local doesn't trip the fleet breaker |
> | `failure_threshold` (consecutive failures to trip) | Tunable sensitivity | Default 3 (permissive); reliable profile uses 2 (production-aggressive) |
> | `recovery_timeout` (seconds before HALF_OPEN probe) | Tunable forgiveness | Default 30s; reliable profile uses 20s; too short = oscillation, too long = abandonment |
> | `half_open_max` (concurrent probe slots) | Prevents thundering herd on recovery | Default 1; only one request tests recovery; others get OPEN |
> | `CircuitBreakerOpen` exception (subclass-able) | Distinguishes "fast-fail" from "slow-fail" for diagnostics | But controller catches it via generic Exception clause to trigger same failover path |
> | `breaker.call(fn)` wrapper | Single integration point | Controller wraps `backend.execute(...)` once; no per-call boilerplate |
> | `_on_state_change` / `_on_trip` callbacks | Metrics + alerting hooks | Wired to Prometheus collector for ops visibility |

## When to apply

Use this pattern when ALL of the following are true:

1. **Multiple interchangeable backends exist** behind a router/dispatcher with a defined failover order (not just a primary + spare).
2. **Backend failure modes include slow timeouts** (network hangs, model loading delays, container OOM-then-restart) — not just fast errors. If failures are always fast, a circuit breaker adds latency without adding value.
3. **Calls are issued frequently** (not once-per-day) — the breaker accumulates failure counts only when traffic is hitting it. For very-low-traffic systems, the threshold may never trip during a real outage.
4. **A configurable failover chain exists downstream** of the breaker. The breaker's job is to make failover trigger fast; it isn't useful if there's no failover to trigger.

Do NOT apply when:

- The "backends" are different *operations* on the same backend (e.g., read vs write on one database). Use a per-operation timeout instead — a breaker would over-isolate.
- Failures are always fast (network refused, immediate 4xx). A breaker adds detection latency without saving wait time.
- There's no failover. A tripped breaker that has nowhere to fail over to just produces faster errors, not better outcomes.

## Implementation shape

```
┌─────────────────────────────────────────────────────────────┐
│ Controller init (once)                                       │
│   build_breakers([local, fleet, openrouter, claude], cfg)    │
│     ↓                                                         │
│   { local: CircuitBreaker(threshold=3, timeout=30),          │
│     fleet: CircuitBreaker(threshold=3, timeout=30),          │
│     openrouter: CircuitBreaker(threshold=3, timeout=30),     │
│     claude: CircuitBreaker(threshold=3, timeout=30) }        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ per request
┌─────────────────────────────────────────────────────────────┐
│ Controller execute_local(task)                                │
│   try:                                                        │
│     breaker = self._breakers[task.backend_name]               │
│     result = breaker.call(lambda: backend.execute(prompt))    │
│   except (Exception, CircuitBreakerOpen):                     │
│     # Either real failure OR breaker said skip — same path:   │
│     for fb_name in self.failover_chain:                       │
│       if fb_name == task.backend_name: continue               │
│       try: result = backends[fb_name].execute(...); break     │
│       except Exception: continue                              │
│     if result is None: enqueue_to_dlq(task)                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ inside breaker.call()
┌─────────────────────────────────────────────────────────────┐
│ State machine                                                 │
│   CLOSED → fn() → success: count=0; failure: count++         │
│           if count >= threshold: → OPEN, _open_since=now      │
│   OPEN   → check (now - _open_since >= recovery_timeout)?    │
│           yes: → HALF_OPEN; no: raise CircuitBreakerOpen     │
│   HALF_OPEN → if half_open_active >= max: raise OPEN         │
│           else: increment, fn(), success: → CLOSED            │
│           failure: → OPEN                                     │
└─────────────────────────────────────────────────────────────┘
```

## Alternatives

### Alternative 1: No circuit breaker — let timeouts drive failover

Skip the breaker entirely. Wrap each backend call in a timeout (say, 60s); if it times out or errors, jump to the next failover backend.

> [!warning] Rejected: timeouts are necessary but insufficient. The failure mode this pattern prevents is *repeated synchronous timeout waits*: if the local backend takes 60s to time out and you have 1000 concurrent requests, you've burned 60,000 wait-seconds before the failover chain even starts. The breaker compresses this to: first 3 failures wait the full 60s each (bad), subsequent failures fail-fast in microseconds (good). For low-traffic systems this is overkill; for AICP's fleet integration (multiple agents pinging concurrently), it's load-bearing.

### Alternative 2: Single global circuit breaker (one breaker for all backends)

One shared breaker that trips when "the system" fails too much.

> [!warning] Rejected: this couples failure domains. If the cloud backend fails 3 times, a single global breaker trips, and now the local backend (which is healthy) is also blocked. Failover chains exist precisely because backends fail independently; a per-backend breaker preserves that independence. AICP's `build_breakers()` (line 183-206) explicitly takes a list of backend names and returns a dict — one per backend — encoding this isolation.

### Alternative 3: Closed/open-only breaker (no HALF_OPEN state)

Two states. Once OPEN, stay OPEN until manually reset.

> [!warning] Rejected: produces permanent abandonment. Backends recover (LocalAI container restarts after OOM, network blip resolves, cloud provider's transient outage ends) — a manually-reset breaker requires operator intervention for normal recovery. HALF_OPEN's auto-probe (one request goes through after `recovery_timeout`) is what makes the pattern operationally hands-off. The probe's outcome is the recovery decision; no human needed for normal operation.

### Alternative 4: Probabilistic / sliding-window breaker (fail rate over last N requests)

Trip the breaker on failure RATE, not consecutive count. E.g., open if >50% of last 20 requests failed.

> [!warning] Rejected (deferred): conceptually cleaner but operationally harder to reason about. Consecutive-failure thresholds give a clear "if you see 3 failures in a row, trip" rule that's easy to debug from logs. A sliding-window rate is sensitive to traffic pattern (low traffic + 1 failure = 100% rate). For AICP's current scale (single-operator, modest concurrency), consecutive-count is sufficient. Sliding-window may be revisited if AICP scales to high-concurrency multi-agent fleet operation where a single transient failure shouldn't dominate the rate.

### Alternative 5: Breaker that hides failures (return cached / default response on OPEN)

When OPEN, return a cached or fallback value instead of raising. Common in HTTP / microservices contexts.

> [!warning] Rejected for AICP: AICP's request semantics don't permit silent fallback. A model response cannot be "approximated" by a cached different model's response without changing the operation's correctness. The breaker's job here is to **fail fast so failover can choose a different backend** — not to substitute a fake answer. The HTTP-microservices pattern (return cached recommendation when recommender service is down) doesn't translate to AI-inference-routing.

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **CircuitBreakerOpen is caught alongside generic Exception — intentionally, not by accident.** `aicp/core/controller.py` line 446: `except (Exception, CircuitBreakerOpen) as local_err:`. The breaker exception type is distinct (helps logs/metrics distinguish "we short-circuited" from "the call actually failed"), but the recovery action is identical: enter failover. Making them share a clause means failover code doesn't branch on failure type. This is the cleanest integration point — one breaker call site, one failover handler, one DLQ fallback.
>
> 2. **Per-backend isolation matters more than a global health view.** `build_breakers()` (line 183-206) returns `{name: CircuitBreaker(...) for name in backend_names}`. Each backend gets its own state machine, its own counts, its own open/close transitions. When the cloud is having a bad day, the local breaker stays CLOSED; failover from local-failure to cloud is blocked by cloud's OPEN breaker, but local→fleet→openrouter (skipping cloud) still works. This is what "failover chain" means operationally — and a global breaker would defeat it.
>
> 3. **The state machine has only ONE auto-transition: OPEN → HALF_OPEN by elapsed time.** All other transitions (CLOSED → OPEN, HALF_OPEN → OPEN, HALF_OPEN → CLOSED) require a request to flow through the breaker. This is intentional: the breaker doesn't run a background timer that wakes up to test backends. It only acts when called. This makes the implementation simple (no thread, no scheduler) and correct under low-traffic conditions (no spurious transitions when nothing is happening). The auto-transition lives in the `state` property getter (line 79-84) — checked lazily on every `breaker.call()`.
>
> 4. **`half_open_max=1` is the thundering-herd guard.** Without it, when OPEN auto-transitions to HALF_OPEN, ALL concurrent waiting requests would proceed simultaneously to test recovery. If the backend is still bad, all of them fail, and the breaker re-opens — but you've wasted N concurrent backend calls. With `half_open_max=1`, exactly one probe goes; others see HALF_OPEN with `_half_open_active >= max` (line 102-104) and raise CircuitBreakerOpen → failover. The probe's outcome is then the basis for closing or re-opening.
>
> 5. **Profile-tunable thresholds are a hard requirement, not a nice-to-have.** `config/profiles/reliable.yaml` uses `failure_threshold: 2, recovery_timeout: 20` — strictly tighter than the default `(3, 30)`. The same code, different config. This matters because reliability targets are workload-specific: AICP's `default` profile (everyday work) tolerates more transient failures before tripping; the `reliable` profile (production / external-facing) trips earlier and probes sooner. Hardcoding thresholds would force one tradeoff for all profiles. Reading from `config["circuit_breaker"]` (line 192-204) makes this an operator decision per profile.
>
> 6. **Three-layer reliability composition (breaker + failover + DLQ).** Each layer handles a different failure scope: breaker handles per-backend repeated failure; failover handles per-request "this backend is unusable, try another"; DLQ handles "the whole chain failed, persist for retry". They're independent and stack additively. `controller.py` lines 432-499 contain all three in sequence: breaker.call() → on failure, walk failover_chain → on total failure, dlq.enqueue(). This is the complete production-reliability path; removing any layer leaves a known failure mode uncovered.

## Trade-offs

- **+** Failover triggers in microseconds (after threshold), not after timeout-per-call. Critical at scale.
- **+** Per-backend isolation preserves failover correctness when individual backends are unhealthy.
- **+** Profile-tunable thresholds let operators dial reliability vs permissiveness per workload.
- **+** Three-layer reliability composition (breaker + failover + DLQ) covers the full failure spectrum.
- **−** Adds detection latency under low-traffic conditions: if you only call once a minute, the threshold may never accumulate during an outage.
- **−** Operators must understand the state machine to debug "why is the breaker open?" — adds operational complexity vs naive timeout.
- **−** `half_open_max=1` means recovery is single-threaded — slow recovery probe blocks N waiting requests until the probe completes.
- **−** Per-backend statefulness means breakers must be process-resident; horizontal scaling requires either sticky routing or a shared store (AICP's controller is single-process so this is not yet a constraint).

## Detection / measurement

- **Trip rate**: how often does CLOSED → OPEN transition fire per backend per hour? Wire `_on_trip` callback to Prometheus (AICP does this in controller init line 172). High trip rate = unhealthy backend or threshold too tight.
- **Recovery rate**: HALF_OPEN → CLOSED frequency. Low recovery rate after trips suggests `recovery_timeout` is too short (probing before backend has recovered).
- **HALF_OPEN re-open rate**: HALF_OPEN → OPEN frequency. High = backend is flapping; investigate root cause not just tune threshold.
- **DLQ depth**: if breakers + failover are working, DLQ should be near-empty. Growing DLQ means the entire failover chain is failing — fix backends, don't tune the breaker.

## Related

- COMPLEMENTS: [profile-as-coordination-bundle](./profile-as-coordination-bundle.md) — circuit_breaker config is one of the ~12 settings switched together by profile activation
- COMPLEMENTS: [single-active-backend-with-lru-eviction](./single-active-backend-with-lru-eviction.md) — when a model swap times out (LRU evicts the wrong one), the breaker prevents repeated swap-attempt cascades
- ENABLES: [4-tier router with profiles](../../decisions/01_drafts/4-tier-router-with-profiles-over-hardcoded-routing.md) — the failover chain the router defines is operationally usable BECAUSE per-backend breakers make failover trigger fast
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-quality.md (the second brain's Quality model — "fail-fast over fail-slow" principle made concrete by this pattern)
- DEPENDS ON: A configurable failover chain downstream and a callable backend interface (`backend.execute(prompt, mode, project_path)`)

## Relationships

- INSTANCE OF: AICP's three-layer reliability stack (breaker + failover + DLQ in `aicp/core/controller.py`)
- INSTANCE OF: Profile-tunable reliability settings (`config/profiles/reliable.yaml` overrides default thresholds)
- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-quality.md
- COMPLEMENTS: [profile-as-coordination-bundle](./profile-as-coordination-bundle.md)
- COMPLEMENTS: [single-active-backend-with-lru-eviction](./single-active-backend-with-lru-eviction.md)
- ENABLES: [4-tier router with profiles](../../decisions/01_drafts/4-tier-router-with-profiles-over-hardcoded-routing.md)
