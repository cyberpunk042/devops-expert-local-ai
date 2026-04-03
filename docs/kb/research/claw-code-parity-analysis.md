# Claw Code Parity Analysis — AICP vs Claude Code

**Type:** Research Finding
**Date:** 2026-04-03
**Status:** RESEARCHED — inventory complete, gaps classified
**Source:** group-03-claw-code-parity-knowledge-map.md (openclaw-fleet)

---

## Inventory Summary

| Category | Claude Code | AICP | Coverage |
|----------|------------|------|----------|
| **Tools** | 184 | 64 MCP + 13 built-in = **77** | 42% |
| **Commands** | 207 | 50+ slash commands | ~25% |
| **Skills** | SKILL.md loading | 85 skills + ecosystem | AICP > CC |
| **Hooks** | PreToolUse/PostToolUse | 26 hook types | AICP > CC |
| **Backends** | Anthropic API only | Local + OpenRouter + Claude | AICP > CC |
| **Cost control** | None | Budget, routing, caching | AICP > CC |

---

## AICP MCP Tools (64 total)

### Chat & Inference (9)
aicp_chat, aicp_complete, aicp_agent, aicp_grammar, aicp_json,
aicp_edit, aicp_infill, aicp_bestof, aicp_complete_n

### Embedding & Search (10)
aicp_embed, aicp_embed_dims, aicp_embed_image, aicp_embed_typed,
aicp_embed_typed_batch, aicp_similarity, aicp_nearest_neighbors,
aicp_rerank, aicp_store_set, aicp_store_find

### Knowledge Base (4)
aicp_kb_search, aicp_kb_ingest, aicp_kb_stats, aicp_kb_augment

### Tokenization (6)
aicp_tokenize, aicp_tokenize_batch, aicp_detokenize,
aicp_token_count, aicp_complete_logprobs, aicp_logprobs

### Model Management (9)
aicp_models, aicp_models_loaded, aicp_model_gallery,
aicp_model_install, aicp_model_status, aicp_model_unload,
aicp_model_delete, aicp_model_config, aicp_model_config_update

### Multimodal (8)
aicp_vision, aicp_multimodal, aicp_imagine, aicp_sound,
aicp_transcribe, aicp_transcribe_detailed, aicp_speak, aicp_tts

### Audio & Voice (4)
aicp_voice_pipeline, aicp_tts_voices, aicp_vad, aicp_detect

### System & Observability (7)
aicp_system, aicp_health, aicp_metrics, aicp_backends_list,
aicp_server_config, aicp_p2p_status, aicp_fleet_status

### Advanced (7)
aicp_batch, aicp_seed, aicp_warmup, aicp_lora_load,
aicp_lora_list, aicp_tools_stream, aicp_fleet_run

### Built-in Tools (13)
file_read, file_list, grep, shell, image_analyze,
audio_transcribe, text_to_speech, image_generate,
kb_search, store_remember, store_recall, system_info

---

## Claude Code Tool Categories (184 tools, estimated breakdown)

Based on claw-code-parity surface snapshots:

| Category | Count | Relevance to AICP |
|----------|-------|-------------------|
| **File operations** (Read, Write, Edit, Glob, Grep) | ~15 | Covered by built-in tools |
| **Shell/Bash execution** | ~5 | Covered by built-in shell |
| **Git operations** (status, diff, log, commit, push) | ~15 | Not in AICP (uses Claude CLI) |
| **Notebook operations** (Jupyter cells) | ~5 | Not relevant for fleet |
| **MCP client** (connect, list, call) | ~10 | AICP is MCP server, not client |
| **Agent orchestration** (spawn, message, plan) | ~15 | Fleet handles via OpenClaw |
| **UI/IDE tools** (VS Code, JetBrains) | ~30 | Not relevant (IDE-specific) |
| **Web tools** (fetch, search) | ~5 | Not in AICP, could add |
| **Memory/context** (compaction, ILM) | ~10 | AICP has different model |
| **Skill/hook execution** | ~10 | AICP has 85 skills |
| **Analytics/telemetry** | ~10 | AICP has Prometheus |
| **Session management** | ~10 | AICP has sessions |
| **Image/multimodal** | ~10 | Covered by MCP tools |
| **Internal/framework** | ~34 | Not relevant (CC internals) |

---

## Gap Classification

### Already covered by AICP (no action needed)
- File operations → built-in tools
- Shell execution → built-in shell
- Embeddings/search → 10 MCP tools
- Multimodal → 8 MCP tools
- Model management → 9 MCP tools
- Tokenization → 6 MCP tools
- Analytics → Prometheus metrics
- Skills → 85 skills

### Not relevant for AICP (skip)
- UI/IDE tools (~30) → Claude Code is IDE-integrated, AICP is CLI/API
- Internal framework (~34) → CC implementation details
- Notebook operations (~5) → not a fleet use case

### Worth investigating (potential additions)
| Tool Category | Count | Why | Priority |
|--------------|-------|-----|----------|
| **Git operations** | ~15 | Agents need to commit, diff, branch | Medium — fleet agents use Claude CLI for this |
| **Web fetch/search** | ~5 | KB ingestion from URLs, API calls | Low — can add as MCP tools |
| **Agent spawn/message** | ~15 | Fleet coordination | Low — OpenClaw handles this |
| **MCP client** | ~10 | AICP calling other MCP servers | Medium — enables tool chaining |

### Gap: ~45 tools potentially useful

Of the 122 "missing" tools:
- ~65 are IDE/internal/irrelevant → **skip**
- ~45 could add value → **investigate in future milestones**
- ~12 already partially covered → **no action**

---

## Key Insight

**AICP is not trying to replicate Claude Code.** Claude Code is a single-backend
IDE tool. AICP is a multi-backend control platform for fleet operations.

Where Claude Code has 184 tools for one user in one IDE, AICP has:
- 64 MCP tools + 13 built-in tools for inference/embedding/search
- 85 skills for development workflows
- 4-tier routing with cost optimization
- Quality scoring and auto-escalation
- Fleet clustering and peering
- Persistent KB with auto-indexing

The real gap is not tool count — it's **git operations** and **MCP client
capabilities** (calling external MCP servers). These are the most impactful
additions for fleet agents.

---

## Recommended Next Steps

1. **Git MCP tools** — add aicp_git_status, aicp_git_diff, aicp_git_commit
2. **Web fetch tool** — add aicp_web_fetch for URL ingestion into KB
3. **MCP client** — enable AICP to call external MCP servers (tool chaining)
4. These are not urgent — fleet agents use Claude Code for git, and web
   fetch can be done via shell
