# LocalAI Models + Routing Strategy

> Extracted from CLAUDE.md `## LocalAI Assessment` 2026-04-25. CLAUDE.md keeps a one-line "LocalAI on :8090" reference and routes here for the model inventory, key findings, and routing tables.

LocalAI is running and functional on Docker with GPU acceleration. API on `localhost:8090`.

## Models — Qwen3 (recommended) + Gemma 4 (multimodal) + legacy

| Model | Config | Size | VRAM | Use case |
|-------|--------|------|------|----------|
| **qwen3-8b** | `qwen3-8b.yaml` | 4.9GB | 6GB+ | Main reasoning — thinking mode, tool calling |
| qwen3-8b-fast | `qwen3-8b-fast.yaml` | 4.9GB | 6GB+ | No thinking, structured tasks |
| **qwen3-4b** | `qwen3-4b.yaml` | 3.3GB | 4GB+ | Fleet lightweight |
| qwen3-30b-a3b | `qwen3-30b-a3b.yaml` | 17GB | 18GB+ | MoE — **dual GPU only (now runnable)** |
| gemma4-e2b | `gemma4-e2b.yaml` | 3.1GB | 4GB+ | Multimodal (text+image+audio), 53 tok/s |
| gemma4-e4b | `gemma4-e4b.yaml` | 5.0GB | 6GB+ | Mid-range multimodal |
| gemma4-26b-a4b | `gemma4-26b-a4b.yaml` | 16.8GB | 18GB+ | MoE multimodal — **dual GPU only (now runnable)** |
| codellama / hermes / phi-2 | (legacy) | varies | varies | Code gen / legacy reasoning / CPU fallback |
| llava / whisper / piper-tts / nomic-embed / bge-reranker / sd35-medium | (specialized) | CPU/small | — | Vision / STT / TTS / embeddings / reranking / image gen |

## Key findings

- **Cold start**: 10-80s per swap (model size dependent). **Warm inference**: 1-1.2s for 7B/3B.
- **Single-active backend**: 8GB VRAM constraint (now 19GB with dual GPU — dual-gpu profile activates). LRU eviction at `MAX_ACTIVE_BACKENDS=3`.
- **Watchdog**: auto-recovers stuck backends (15m idle / 10m busy).
- **API**: OpenAI-compatible chat completions (`localhost:8090`). Routes `aicp_route` MCP tool wraps the controller's full routing decision.

## Routing strategy (5-tier, post-mission)

### Default profile (audit-safe; client/monetizable work)

| Operation | Backend | Model | Why |
|-----------|---------|-------|-----|
| Heartbeat (no work) | intercepted | — | Template, 0 tokens |
| Fleet ops (status, chat) | local | gemma4-e2b | 53 tok/s, multimodal |
| Simple Q&A / format / translate | local | qwen3-8b-fast | No thinking, fewer tokens |
| Code (implement, debug) | local | qwen3-8b | Thinking enabled |
| Medium / agentic | k2_6_openrouter | moonshotai/kimi-k2.6 | Audit-safe pinned provider |
| Premium fallback | openrouter | opus / gpt-5.4 / gemini-3.1-pro | When K2.6 not enough |
| Last resort | claude | opus | Hard-gated |

### Personal profile (research/dev/non-monetizable; shared pool acceptable)

| Band | Backend | Why |
|------|---------|-----|
| Medium | **ollama_cloud** | Subscription-flat (~$27 CAD/mo), faster than per-token |
| Higher | k2_6_openrouter | Spillover when Ollama caps hit |
| Premium | openrouter | Opus / GPT fallback |
| Last resort | claude | Hard-gated |

**Configurable per profile**: failover chain, escalation threshold, complexity thresholds, `force_cloud_modes` per mode. See `config/profiles/*.yaml` (11 profiles total — `default`, `personal` are post-mission canonical; `fast`, `quality`, `reliable`, `dual-gpu`, etc. inherit and override). Full per-profile detail at [profiles.md](profiles.md).

## Infrastructure target (multi-host fleet)

```
Machine 1: Fleet Alpha    Machine 2: Fleet Bravo
├── LocalAI Cluster 1     ├── LocalAI Cluster 2
├── OpenClaw + MC         ├── OpenClaw + MC
├── Fleet Daemons         ├── Fleet Daemons
└── 10 Agents (alpha-*)   └── 10 Agents (bravo-*)

Shared: Plane, GitHub, ntfy
LocalAI peering: Cluster 1 ↔ Cluster 2 (load balance, failover) — pending (Stage 4 reliability blocker)
```
