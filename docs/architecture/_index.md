# AICP Architecture — Detail Index

This directory holds the per-topic detail pages extracted from CLAUDE.md to keep the every-message hot path lean. CLAUDE.md routes here when a topic is needed in depth; otherwise, only the one-line summary in CLAUDE.md is loaded into context.

## Pages

| Page | Topic | Read when... |
|------|-------|--------------|
| [post-anthropic-mission.md](post-anthropic-mission.md) | The 2026-04-22 → 2026-04-25 mission shift, full strategic-shift table, original LocalAI-independence stages, sacrosanct operator quotes | Mission context / why we're on this path / what changed |
| [project-structure.md](project-structure.md) | Top-level packages + module-level breakdown + MCP tool surface (64 tools) | Navigating the codebase / understanding the MCP surface |
| [localai-routing.md](localai-routing.md) | LocalAI model inventory, key findings, default + personal profile routing tables, multi-host fleet target | Configuring LocalAI / picking models / understanding routing decisions |
| [profiles.md](profiles.md) | All 11 profiles + load order + activation precedence + when-to-use guide | Picking a profile / building a new profile / debugging profile precedence |
| [intelligent-infrastructure.md](intelligent-infrastructure.md) | Stage 5 components — events, tool safety, task lifecycle, memory relevance, microcompaction | Working on controller internals / runtime patterns |
| [reliability.md](reliability.md) | Stage 4 components — circuit breaker, warmup, deep health, DLQ, metrics, health reports | Reliability tuning / failover debugging |
| [fleet-integration.md](fleet-integration.md) | AICP ↔ Fleet shared modules + 18 skills used by fleet agents | Fleet integration work / multi-host topology |

## Pattern

CLAUDE.md is the every-message hot path (loaded into the agent's context every turn). Detail files are loaded on demand when the operator's task requires that depth. See `wiki/spine/standards/model-standards/model-claude-code-standards.md` for the gold-standard rationale.
