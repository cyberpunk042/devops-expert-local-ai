# AICP Project Structure — Top-Level Packages

> Extracted from CLAUDE.md `## Project Structure (top-level packages)` 2026-04-25. CLAUDE.md keeps a 1-line-per-package summary and routes here for full module breakdown including the MCP tool surface inventory.

## Packages

| Package | Responsibility | Key modules |
|---------|---------------|-------------|
| [aicp/core/](../../aicp/core/) | Controller + router + modes + reliability + intelligent infra | controller, router, modes, pipeline, session, budget, metrics, observability, tools, skills, rag, kb, gpu, cluster, history, models, approval, events, tasks, memory_relevance, memory_extract, compaction, circuit_breaker, dlq, prometheus, health_report |
| [aicp/backends/](../../aicp/backends/) | All backend clients | base, localai, claude_code, openrouter, k2_6_local, ollama_cloud |
| [aicp/guardrails/](../../aicp/guardrails/) | Permission enforcement | checks, paths, response |
| [aicp/cli/](../../aicp/cli/) | CLI dispatcher + interactive + dashboard | main, control, interactive, dashboard, display, project_ops |
| [aicp/agent/](../../aicp/agent/) | Agent server (fleet integration) | client, server (task lifecycle, away summary, progress events) |
| [aicp/mcp/](../../aicp/mcp/) | MCP server — **64 tools (audit pending)** | server.py — see MCP tool surface below |
| [config/](../../config/) | Default config + 11 profiles + 19 model YAMLs + alerts | default.yaml, fleet.yaml, alerts.yaml, profiles/, models/ |
| [tests/](../../tests/) | 97 test files, 1,840 tests | mirrors aicp/ structure |
| [wiki/](../../wiki/) | AICP knowledge wiki (per second brain standards) | config/, backlog/, lessons/, patterns/, decisions/ |
| [docs/](../../docs/) | Architecture and planning + KB content | kb/research/, kb/models/, kb/infrastructure/, knowledge-map/ |
| [.claude/skills/](../../.claude/skills/) | 84 skills (conditional, just-in-time) | per skill: SKILL.md + scripts/ + references/ |

## MCP tool surface (64 tools, audit pending)

The MCP server at `aicp/mcp/server.py` exposes 64 tools. Audit findings live at `wiki/lessons/00_inbox/aicp-mcp-server-tool-surface-drift-from-claude-md.md` and the canonical decision is `wiki/decisions/00_inbox/aicp-mcp-tool-surface-audit-2026-04-19.md` (21 deprecated, replacement skills in `.claude/skills/aicp-*`).

**Tools by category:**

| Category | Tools |
|----------|-------|
| Inference | chat, vision, transcribe, speak, voice_pipeline, imagine, embed, multimodal, bestof, complete\* |
| Knowledge base | kb_search, kb_ingest, kb_stats, kb_augment, kb_search_collection |
| Stores | store_set, store_find |
| Models | models, model_\*, lora_\* |
| Audio | tts, tts_voices, transcribe_detailed, sound, vad |
| Tokenization | tokenize, tokenize_batch, detokenize, token_count |
| Embeddings | embed, embed_typed, embed_typed_batch, embed_dims, embed_image, similarity, nearest_neighbors |
| Operational | route, deep_health, profile, task_status, dlq_status, metrics, warmup, models_loaded, system, server_config, backends_list, p2p_status |
| Fleet | fleet_status, fleet_run, agent |
| Advanced | grammar, rerank, json, seed, infill, batch, edit, detect, logprobs, complete_logprobs, complete_n, tools_stream |

**Audit framing** (per the second brain's `cli-tools-beat-mcp-for-token-efficiency` lesson): which tools are external-bridge (justified MCP) vs operational (should migrate to CLI + Skills). The 21 deprecated tools have CLI/skill replacements documented in `wiki/decisions/00_inbox/aicp-mcp-tool-surface-audit-2026-04-19.md`.
