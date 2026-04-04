# AICP Module Manual — Core Python Modules

Condensed reference for all modules in `aicp/`. Each entry: purpose, key functions, connections.

---

## Core Modules (`aicp/core/`)

### controller.py — Central Orchestrator
Routes tasks to backends with mode enforcement, failover, caching, quality escalation, and budget tracking.
- `Controller.run(task)` — main entry: preflight → cache check → intercept → fleet route → execute → quality check → save
- `ResponseCache` — TTL-based cache, skips inference for repeated prompts
- Failover chain: local → fleet peer → openrouter → claude
- Quality escalation: score < 0.25 → retry on next tier

### router.py — Backend & Model Selection
Classifies tasks by complexity and routes to the optimal backend/model.
- `classify_task_with_reason()` — 4-tier routing (local/openrouter/claude) with reason string
- `recommend_model()` — select LocalAI model (fleet→qwen3-4b, simple→qwen3-8b-fast, code→qwen3-8b)
- `analyze_complexity()` — weighted scoring (0.0-1.0) with signals: mode, length, keywords, multi-step
- `score_response_quality()` — heuristic quality check (0.0-1.0): length, refusal, repetition, structure
- `estimate_cost()` — per-backend cost estimation

### modes.py — Permission Model
Three modes: THINK (read-only), EDIT (scoped writes), ACT (controlled commands).
- `Mode` enum: THINK, EDIT, ACT

### pipeline.py — YAML Pipeline Execution
Execute multi-step YAML pipelines with budget enforcement and conditional steps.
- `run_pipeline()` — load YAML, iterate steps, enforce budget per step

### session.py — Conversation Persistence
Store/load LocalAI conversation history as JSON files.
- `load_session(name)` / `save_session(name, messages)` — `~/.aicp/sessions/<name>.json`

### budget.py — Token Budget Tracking
Track and enforce token/cost/time budgets across tasks.
- `BudgetLimits` dataclass: max_tokens, max_cost_usd, max_duration_seconds, max_steps

### metrics.py — History Aggregation
Aggregate metrics from task history JSON files.
- `aggregate()` — per-backend stats: requests, tokens, cost, latency, errors

### history.py — Task Persistence
Save every task execution to JSONL history.
- `save_task()` — append to `~/.aicp/history/` with prompt, response, usage, route

### context.py — Project Context Builder
Build text summary of project structure + key files for backend system prompts.
- `build_project_context(path, max_chars)` — dir tree + README/CLAUDE.md content

### tools.py — Built-in Tool Definitions
13 tools for function-calling: file_read, file_list, grep, shell, vision, audio, KB, stores.
- `execute_tool(name, args, project_path)` — dispatch to tool implementation
- `get_tools_for_mode(mode)` — filter tools by permission mode

### skills.py — Skill System
3-layer skill discovery: global (~/.aicp/skills.yaml), project (.aicp/skills/), Claude (.claude/skills/).
- `load_skills()` — merge all layers, return skill definitions
- 85 skills documented in `docs/aicp-skills-inventory.md`

### rag.py — Vector Store + RAG Pipeline
SQLite-backed vector store with cosine similarity search.
- `VectorStore` — add, search, delete chunks with embeddings
- `RAGPipeline` — ingest_file → chunk → embed → store → retrieve → augment_prompt
- Note: persistent KB now uses LocalAI Collections (`make kb-sync`), not SQLite

### kb.py — Knowledge Base Manager
High-level wrapper over RAG pipeline with cross-encoder reranking.
- `KnowledgeBase.search()` — embed → retrieve → rerank (BGE reranker)
- `KnowledgeBase.ingest_directory()` — bulk file ingestion

### lightrag.py — Unified Search
Bridges persistent KB (SQLite) and ephemeral LocalAI /stores/ with merged reranking.
- `LightRAG.search()` — query both, merge, rerank

### indexer.py — Auto-Indexing
Background file watcher that re-embeds changed files (mtime-based polling).
- `AutoIndexer.start()` — daemon thread, polls every 30s

### stores.py — LocalAI /stores/ Client
Client for LocalAI's in-memory vector key-value store.
- `EmbeddingStore.remember()` / `.recall()` — high-level text-in/text-out

### navigator.py — Knowledge Map Engine
Reads map metadata, matches intent, selects injection profile, assembles context.
- `Navigator.match_intent()` — two-pass: keywords first, complexity second
- `Navigator.select_profile()` — opus-1m / sonnet-200k / localai-8k / heartbeat
- `Navigator.assemble_context()` — augment prompt with KB results

### compaction.py — Context Compaction
Manage conversation history within model context windows.
- `compact_messages()` — summarize old turns, keep recent, fit budget
- `should_compact()` — check if history exceeds model context threshold

### prometheus.py — Metrics Exporter
Thread-safe Prometheus metrics collector + HTTP server.
- `MetricsCollector` — per-backend: requests, errors, tokens, cost, latency, quality, cache, escalations
- `start_metrics_server(collector, port=9101)` — background `/metrics` endpoint
- Warm pool tracking: `record_model_load()` / `record_model_unload()`

### observability.py — LocalAI Metrics Scraper
Scrape and parse LocalAI's built-in /metrics endpoint.
- `scrape_prometheus(base_url)` — parse Prometheus text format
- `get_loaded_models()` / `get_system_info()` — query LocalAI status

### gpu.py — GPU Detection
Detect NVIDIA GPUs via nvidia-smi, calculate optimal model config.
- `detect_gpus()` → list of GpuInfo (name, VRAM total/used/free)
- `calculate_optimal_config()` → gpu_layers, context_size, threads

### cluster.py — Multi-Machine Federation
Load fleet topology, health-check nodes, route tasks to best node.
- `load_cluster_config()` — from config/fleet.yaml
- `find_best_node()` — prefer: has model, most free VRAM, online
- `execute_remote()` — send task to remote AICP agent

### db.py — SQLite Metrics Store
Queryable index over task history for dashboards.
- `record_task()` / `query_tasks()` — SQLite with backend/date filters

### models.py — Model Management CLI
List, install, unload, benchmark models via LocalAI API.

### chunking.py — Text Chunking
Split text/files into chunks for embedding.
- `chunk_file()` / `chunk_text()` — with configurable size and overlap

### result.py — Result Types
`TaskResult` + `TokenUsage` dataclasses.

### approval.py — Approval Workflows
Two-phase approval: plan then execute with interactive confirmation.

### worktree.py — Git Worktree Isolation
Create isolated git worktrees for safe parallel execution.

### projects.py — Project Registry
Auto-discover and register projects from git repos.

---

## Backends (`aicp/backends/`)

### localai.py — LocalAI Client (3400 LOC)
Full OpenAI-compatible API client. Chat, embed, vision, audio, tools, streaming. Qwen3 reasoning field support via `_extract_content()`. Mode-aware sampling profiles. Auto-routing between models.

### openrouter.py — OpenRouter Client
Cloud LLM gateway. 200+ models, 29 free. OpenAI-compatible API. Cost estimation. Free model catalog.

### claude_code.py — Claude Code CLI Wrapper
Subprocess invocation of `claude` CLI. Session management, mode mapping, streaming via stream-json.

### base.py — Backend ABC
Abstract interface: `execute()`, `execute_stream()`, `is_available()`, `status_detail()`.

---

## Guardrails (`aicp/guardrails/`)

### checks.py — Preflight Checks
Validates project path, mode compatibility, forbidden paths before execution.

### paths.py — Path Protection
Glob-based allowlist/denylist for file operations.

### response.py — Response Scanning
Post-execution: detect secrets (AWS keys, JWTs, private keys, GitHub PATs), block shell patterns in think mode.

---

## CLI (`aicp/cli/`)

### main.py — CLI Entry Point (2700 LOC)
50+ argparse subcommands. Backend construction, routing, execution, all feature flags.

### interactive.py — REPL (1600 LOC)
40+ slash commands. Streaming, vision, audio, KB, fleet, tools.

### dashboard.py — Live TUI
GPU/model/metrics dashboard with refresh loop.

### control.py — Terminal Controls
Cross-project view, milestone tracking.

### display.py — Output Formatting
Rich console: spinners, tables, colors.

### project_ops.py — Project Operations
Auto-config, skill discovery, model management.

---

## Agent (`aicp/agent/`)

### server.py — Agent HTTP Daemon
Lightweight HTTP server: /health, /status, /task. Bearer token auth.

### client.py — Agent HTTP Client
Client for remote AICP agent instances.

---

## MCP (`aicp/mcp/`)

### server.py — MCP Tool Server (1400 LOC)
64 tools via FastMCP protocol. See tool-manual.md for complete reference.
