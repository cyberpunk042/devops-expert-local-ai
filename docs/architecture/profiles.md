# Configuration Profiles

> Extracted from CLAUDE.md `## Configuration Profiles` 2026-04-25. CLAUDE.md keeps a one-line summary and routes here for the full profile listing, load order, activation precedence, and tuning guidance.

Named bundles coordinating backends + router + RAG + budget + cache + timeouts + Docker via single switch.

## Profiles (11 total)

| Profile | Primary | Failover | Use case |
|---------|---------|----------|----------|
| **default** | qwen3-8b | local→fleet→k2_6_openrouter→openrouter→claude | Balanced, audit-safe (pinned K2.6 mid-tier) |
| **personal** | kimi-k2.6 | local→ollama_cloud→k2_6_openrouter→openrouter→claude | Research/dev/non-monetizable — band 1 routes Ollama Cloud Pro (shared pool) |
| **quality** | qwen3-8b | local→k2_6_openrouter→openrouter→claude | Max reasoning per dollar — K2.6 widens, Opus reserved for top ~8% |
| **fast** | gemma4-e2b | local→openrouter | Low-latency, 53 tok/s, minimal RAG |
| **offline** | qwen3-8b | local→fleet | Air-gapped — no cloud backends |
| **thorough** | qwen3-8b | local→fleet→openrouter→claude | Full thinking, deep RAG, generous budgets |
| **code-review** | qwen3-8b | local→openrouter→claude | Code analysis, low temperature |
| **fleet-light** | gemma4-e2b | inherits default | Fleet heartbeat duty, zero RAG |
| **reliable** | qwen3-8b | inherits default | Production — aggressive breaker, auto-warmup, DLQ, reports |
| **dual-gpu** | qwen3-30b-a3b | inherits default | 19GB VRAM MoE — local-frontier expansion |
| **benchmark** | qwen3-8b | local only | Deterministic (temp=0, seed=42) for evals |

## Config load order

`config/default.yaml` → `config/profiles/<name>.yaml` → `~/.aicp/config.yaml` → `<project>/.aicp/config.yaml` → `--config <path>`.

## Activation (precedence)

1. `aicp --profile fast "..."` (CLI — highest)
2. `AICP_PROFILE=fast` (env var)
3. `make profile-use PROFILE=fast` (.env, lowest)

## Implementation

- Profiles can `extends:` other profiles (deep merge, circular detection).
- Implementation: [aicp/core/profiles.py](../../aicp/core/profiles.py).
- 58 profile tests at [tests/test_profiles.py](../../tests/test_profiles.py).

## When to use which

| If you... | Use |
|-----------|-----|
| Have audit/client/monetizable work | `default` (or `quality` for harder reasoning) |
| Are doing personal research / AICP dev | `personal` (Ollama Cloud Pro band 1) |
| Need offline-only operation | `offline` |
| Are running fleet heartbeats | `fleet-light` |
| Need production reliability (breaker + warmup + reports) | `reliable` |
| Want deterministic evals | `benchmark` |
| Have both GPUs free + want frontier MoE | `dual-gpu` |
| Need quick low-latency responses | `fast` |
| Are doing structured code review | `code-review` |
| Need maximum reasoning depth (full RAG) | `thorough` |
