# AICP Knowledge Base

Structured knowledge for the AI Control Platform. Research findings, model evaluations,
infrastructure decisions, and architectural knowledge stored here for:

1. **Human reference** — lookup during development sessions
2. **LocalAI collections** — sync to `/stores/` API for semantic search
3. **RAG injection** — feed into agent context when relevant
4. **Fleet KB sync** — mirror relevant entries to openclaw-fleet KB

## Structure

```
kb/
├── research/        — Investigation findings, evaluations, benchmarks
├── models/          — Model configs, benchmarks, VRAM maps, upgrade paths
├── infrastructure/  — Docker, GPU, networking, observability decisions
├── routing/         — Router logic, backend ranking, cost analysis
├── backends/        — Backend-specific knowledge (LocalAI, OpenRouter, Claude)
└── standards/       — Conventions, naming, config formats
```

## Conventions

- **One topic per file**, kebab-case naming
- **Metadata header**: Type, Date, Status, Sources
- **Status values**: RESEARCHED, VERIFIED, IMPLEMENTED, OUTDATED
- **Keep findings factual** — link to sources, include versions tested
- **Update, don't duplicate** — revise existing entries when things change
