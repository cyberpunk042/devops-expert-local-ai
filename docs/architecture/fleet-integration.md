# AICP ↔ Fleet Connection

> Extracted from CLAUDE.md `## AICP ↔ Fleet Connection` 2026-04-25. CLAUDE.md keeps a one-line summary and routes here for the module table.

AICP provides LocalAI inference + cloud routing + skill library to the fleet ecosystem.

## Modules

| Module | Purpose |
|--------|---------|
| [aicp/core/rag.py](../../aicp/core/rag.py) | SQLite vector store, cosine similarity (fleet RAG) |
| [aicp/core/kb.py](../../aicp/core/kb.py) | Knowledge base, file ingestion, BGE reranker |
| [aicp/core/stores.py](../../aicp/core/stores.py) | LocalAI /stores/ API client |
| [aicp/core/router.py](../../aicp/core/router.py) | Score-based routing with configurable thresholds |
| [aicp/core/skills.py](../../aicp/core/skills.py) | 3-layer skill system (84 skills in `.claude/skills/`) |
| [aicp/core/circuit_breaker.py](../../aicp/core/circuit_breaker.py) | Prevents thundering herd from fleet agents |
| [aicp/core/dlq.py](../../aicp/core/dlq.py) | Persists failed tasks for retry |

## Skills shared with fleet

Skills used by fleet agents (18 referenced in fleet's `config/agent-tooling.yaml`): `architecture-propose`, `feature-implement`, `quality-coverage`, `foundation-docker`, `pm-plan`, `ops-deploy`, etc.

## Related

- See `docs/aicp-fleet-architecture.md` for the broader fleet topology.
- LocalAI cluster peering (Stage 4 reliability) is the planned next integration step — currently pending.
