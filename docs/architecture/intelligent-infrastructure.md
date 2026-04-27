# Intelligent Infrastructure (Stage 5)

> Extracted from CLAUDE.md `## Intelligent Infrastructure (Stage 5)` 2026-04-25. CLAUDE.md keeps a one-line summary and routes here for the component table.

Patterns adopted from Claude Code's production architecture, adapted for AICP's local-first, fleet-oriented design. Research: [docs/kb/research/claude-code-architecture-analysis.md](../kb/research/claude-code-architecture-analysis.md).

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Event emitter | [aicp/core/events.py](../../aicp/core/events.py) | Thread-safe fire-and-forget bus; controller emits task_start/complete/failed |
| Tool safety metadata | [aicp/core/tools.py](../../aicp/core/tools.py) | Fail-closed flags: is_read_only, is_destructive, is_concurrent_safe; 3-stage pipeline |
| Task lifecycle | [aicp/core/tasks.py](../../aicp/core/tasks.py) | pending → running → completed/failed/killed; tool/token/activity tracking |
| Memory relevance | [aicp/core/memory_relevance.py](../../aicp/core/memory_relevance.py) | Embedding-based selection via nomic-embed; aging warnings |
| Microcompaction | [aicp/core/compaction.py](../../aicp/core/compaction.py) | Surgical pruning; replaces tool results with markers; image stripping |
| Skill model override | [aicp/core/skills.py](../../aicp/core/skills.py) | Skills specify `model:` in frontmatter; `allowed-tools`, `context: fork`, `paths` |
| Auto-memory extraction | [aicp/core/memory_extract.py](../../aicp/core/memory_extract.py) | Heuristic extraction of learnable facts from task history |
| Away summary | [aicp/agent/server.py](../../aicp/agent/server.py) | 1-3 sentence summary on shutdown; loaded on restart |
| Extended MCP tools | [aicp/mcp/server.py](../../aicp/mcp/server.py) | 64 tools registered (audit pending — see [project-structure.md](project-structure.md)) |
