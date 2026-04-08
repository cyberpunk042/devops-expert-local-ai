# OpenArms Architecture Analysis — AICP Integration Paths

**Date:** 2026-04-07
**Source:** /home/jfortin/openarms (v2026.4.1, Node.js/TypeScript)
**Codebase size:** ~150K+ LOC, 55 skills, 23+ channels, plugin SDK, multi-agent ACP

## Executive Summary

OpenArms is a personal AI assistant runtime that connects to 23+ messaging channels
(WhatsApp, Telegram, Discord, Slack, Signal, iMessage, IRC, Teams, Matrix, etc.)
and routes messages through AI agents. It has a WebSocket Gateway as control plane,
a plugin system for providers (LLM, TTS, vision, image gen), and an ACP (Agent
Client Protocol) subsystem for multi-agent orchestration.

AICP provides the local inference layer that OpenArms needs for privacy-first,
always-on operation. This document maps the three integration paths and the
multimodal capability alignment.

---

## System Architecture

```
Messaging Channels (23+)              IDE Clients (Zed, Claude Code)
  WhatsApp, Telegram, Discord...         ACP stdio/NDJSON
           │                                    │
           ▼                                    ▼
┌──────────────────────────────────────────────────────────┐
│              OpenArms Gateway (ws://localhost:18789)       │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Routing  │  │ Sessions │  │ Agents   │  │ Plugins  │ │
│  │ Bindings │  │ SQLite   │  │ Multi-   │  │ Provider │ │
│  │ Resolve  │  │ Store    │  │ agent    │  │ Registry │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
└───────┼──────────────┼──────────────┼──────────────┼──────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
   Channel        Session        Agent           Provider
   Adapters       Management     Execution       Plugins
                                    │
                      ┌─────────────┼─────────────┐
                      ▼             ▼             ▼
                  Anthropic      OpenAI       AICP (LocalAI)
                  (cloud)       (cloud)       (local, free)
```

---

## Three Integration Paths

### Path A: ACP Runtime Backend (Deepest Integration)

**What:** Register AICP as a native ACP runtime backend. OpenArms' session manager
routes agent turns directly to AICP.

**Interface:** `src/acp/runtime/types.ts`

```typescript
interface AcpRuntime {
  ensureSession(input: AcpRuntimeEnsureInput): Promise<AcpRuntimeHandle>;
  runTurn(input: AcpRuntimeTurnInput): AsyncIterable<AcpRuntimeEvent>;
  cancel(input: { handle: AcpRuntimeHandle; reason?: string }): Promise<void>;
  close(input: { handle: AcpRuntimeHandle; reason: string }): Promise<void>;
  getCapabilities?(input): Promise<AcpRuntimeCapabilities>;
  getStatus?(input): Promise<AcpRuntimeStatus>;
  doctor?(): Promise<AcpRuntimeDoctorReport>;
}
```

**Registration:** `src/acp/runtime/registry.ts`

```typescript
registerAcpRuntimeBackend({
  id: "aicp",
  runtime: new AicpAcpRuntime({ baseUrl: "http://localhost:9100" }),
  healthy: () => fetch("http://localhost:9100/health").then(r => r.json()).then(h => h.status !== "degraded")
});
```

**AICP mapping:**
- `ensureSession()` → create session via AICP task manager
- `runTurn()` → POST /task + stream events via EventEmitter
- `cancel()` → kill task via task manager
- `close()` → cleanup session
- `getStatus()` → GET /health (deep health with backend status)
- `doctor()` → self-test + health report

**Effort:** Medium — needs a TypeScript adapter in OpenArms that calls AICP's HTTP API.

**Best for:** Native multi-agent support, session isolation, full lifecycle management.

---

### Path B: Provider Plugin (Model Catalog)

**What:** Register AICP as a model provider. OpenArms agents can select AICP models
by name (e.g., `aicp/qwen3-8b`, `aicp/gemma4-e2b`).

**Interface:** `src/plugin-sdk/provider-entry.ts`

```typescript
defineSingleProviderPluginEntry({
  id: "aicp-provider",
  provider: {
    id: "aicp",
    label: "AICP (LocalAI)",
    envVars: ["AICP_AGENT_SECRET", "AICP_BASE_URL"],
    auth: [{ methodId: "api_key", label: "Agent Token", envVar: "AICP_AGENT_SECRET" }],
    catalog: {
      order: "simple",
      run: async (ctx) => ({
        models: [
          { id: "qwen3-8b", label: "Qwen3 8B (reasoning)", capabilities: ["tool_use"] },
          { id: "gemma4-e2b", label: "Gemma 4 E2B (fast)", capabilities: ["vision", "tool_use"] },
          { id: "gemma4-e4b", label: "Gemma 4 E4B (vision)", capabilities: ["vision", "tool_use"] },
          { id: "qwen3-8b-fast", label: "Qwen3 8B Fast", capabilities: ["tool_use"] },
        ]
      })
    }
  }
});
```

**Agent config:**
```yaml
agents:
  list:
    - id: main
      model: aicp/qwen3-8b
    - id: heartbeat
      model: aicp/gemma4-e2b
```

**Effort:** Medium — needs OpenArms extension plugin + OpenAI-compatible adapter.

**Best for:** Model selection, auth rotation, fallback chains.

---

### Path C: MCP Server (Lowest Effort)

**What:** OpenArms already supports MCP servers. AICP's MCP server (`aicp/mcp/server.py`)
exposes 11 tools. OpenArms can consume them directly.

**Current AICP MCP tools:**
- `aicp_chat` — prompt to local LLM
- `aicp_route` — full controller routing (score-based, failover, circuit breaker)
- `aicp_vision` — image analysis (LLaVA/Gemma4)
- `aicp_transcribe` — speech-to-text (Whisper)
- `aicp_speak` — text-to-speech (Piper)
- `aicp_voice_pipeline` — full voice loop
- `aicp_deep_health` — backend health status
- `aicp_profile` — profile management
- `aicp_kb_search_collection` — semantic KB search
- `aicp_task_status` — task lifecycle status
- `aicp_dlq_status` — dead-letter queue management

**OpenArms MCP config:**
```yaml
mcp:
  enabled: true
  servers:
    aicp:
      command: "python"
      args: ["-m", "aicp.mcp.server"]
      transport: "stdio"
```

**Effort:** Low — MCP server already exists, just needs OpenArms config.

**Best for:** Immediate integration, tool exposure, gradual adoption.

---

## Multimodal Capability Mapping

### Provider Registry Alignment

| OpenArms Provider Interface | Method | AICP Model | MCP Tool |
|---|---|---|---|
| `MediaUnderstandingProvider` | `transcribeAudio()` | Whisper (whisper-1) | `aicp_transcribe` |
| `MediaUnderstandingProvider` | `describeImage()` | Gemma4-E4B + mmproj | `aicp_vision` |
| `ImageGenerationProvider` | `generateImage()` | Stable Diffusion | `aicp_chat` (image_generate tool) |
| `SpeechProvider` | `synthesize()` | Piper TTS | `aicp_speak` |
| `PluginWebSearchProvider` | `execute()` | nomic-embed + BGE reranker | `aicp_kb_search_collection` |
| Model Provider | `chat.send()` | qwen3-8b / gemma4-e2b | `aicp_route` |

### OpenArms Skills That Overlap With AICP

| OpenArms Skill | AICP Equivalent | Notes |
|---|---|---|
| `openai-whisper` (CLI) | LocalAI Whisper (API) | AICP adds routing + failover |
| `sherpa-onnx-tts` (ONNX) | Piper TTS (LocalAI) | Same underlying engine |
| `coding-agent` | qwen3-8b + tool calling | AICP adds score-based routing |
| `video-frames` | None | OpenArms-only (ffmpeg extraction) |
| `voice-call` | aicp_voice_pipeline | AICP has full STT→LLM→TTS loop |

---

## Message Flow: WhatsApp → AICP → WhatsApp

```
1. User sends WhatsApp message "What's in this photo?"
   + attached image

2. OpenArms WhatsApp channel adapter normalizes message
   → { text: "What's in this photo?", attachments: [image.jpg] }

3. Routing resolves agent + session
   → agentId: "main", sessionKey: "agent:main:wa:+1234567890"

4. Agent config: model: "aicp/gemma4-e4b" (vision-capable)

5. Provider plugin calls AICP agent daemon
   → POST http://localhost:9100/task
   → { prompt: "What's in this photo?", mode: "think", backend: "local" }
   + image attachment via multimodal API

6. AICP controller:
   → Circuit breaker: CLOSED (healthy)
   → Route: local (score 0.15, below threshold)
   → Model: gemma4-e4b (vision model from skill override)
   → Execute: LocalAI /v1/chat/completions with image

7. Response streams back:
   → AICP → EventEmitter("task_complete") → Provider plugin
   → Gateway → WhatsApp channel adapter → WhatsApp API
   → User sees: "The photo shows a red car parked on a street..."
```

---

## Gateway Protocol Details

### Connection
- WebSocket: `ws://localhost:18789`
- Auth: token, password, or device fingerprint
- Protocol: JSON frames (RequestFrame/ResponseFrame/EventFrame)

### Key Methods
- `chat.send` — execute a prompt (→ AICP POST /task)
- `chat.abort` — cancel active run (→ AICP task kill)
- `sessions.list` — list sessions (→ AICP GET /tasks)
- `sessions.resolve` — get session by key
- `config.*` — runtime configuration
- `agents.*` — multi-agent operations

### Session Key Format
```
"acp:<uuid>"                    — Isolated ACP session
"agent:main:main"               — Agent "main", default session
"agent:main:wa:+1234567890"     — Agent "main", WhatsApp peer
"agent:heartbeat:fleet:alpha-1" — Heartbeat agent, fleet node
```

---

## OpenArms Extension Plugin Design

The natural integration is a single OpenArms extension that registers all AICP capabilities:

```
extensions/aicp-inference/
├── openarms.plugin.json    — manifest
├── package.json            — deps (@agentclientprotocol/sdk)
├── index.ts                — plugin entry (registers all providers)
├── provider.ts             — model catalog (qwen3-8b, gemma4-e2b, etc.)
├── media.ts                — vision + transcription providers
├── speech.ts               — TTS provider (Piper via AICP)
├── image-gen.ts            — Stable Diffusion provider
└── health.ts               — AICP health check integration
```

**Plugin entry:**
```typescript
export default definePluginEntry({
  id: "aicp-inference",
  name: "AICP Local Inference",
  description: "LocalAI inference via AICP — free, private, GPU-accelerated",
  register(api) {
    api.registerModelProvider(buildAicpModelProvider());
    api.registerMediaUnderstandingProvider(buildAicpVisionProvider());
    api.registerSpeechProvider(buildAicpSpeechProvider());
    api.registerImageGenerationProvider(buildAicpImageGenProvider());
    api.registerWebSearchProvider(buildAicpKbSearchProvider());
  }
});
```

---

## Architecture Parallels

| Concept | OpenArms | AICP |
|---------|----------|------|
| Control plane | Gateway (ws://18789) | Agent daemon (http://9100) |
| Session management | Session keys + SQLite | Session files + history.py |
| Task lifecycle | TaskRecord (queued→running→succeeded) | TaskState (pending→running→completed) |
| Event system | Gateway EventFrames | EventEmitter (events.py) |
| Tool permissions | Approval gates + hooks | Mode enforcement (Think/Edit/Act) |
| Context compaction | Context engine + token budgets | compaction.py + microcompaction |
| Model failover | Auth profile rotation + fallbacks | Failover chain + circuit breaker |
| Plugin/Skill system | 55 skills + plugin SDK | 78 skills + 4-layer discovery |
| MCP | Channel bridge + plugin tools | FastMCP server (11 tools) |
| Multi-agent | ACP sessions + agent spawning | Fleet agent daemon + cluster |

---

## Recommended Integration Order

### Phase 1: MCP (immediate, no OpenArms code changes)
- Configure AICP MCP server in OpenArms config
- OpenArms agents can use AICP tools (vision, TTS, STT, KB search)
- Zero code changes to either project

### Phase 2: Provider Plugin (when OpenFleet integrates)
- Create `extensions/aicp-inference/` in OpenArms
- Register AICP models in catalog
- Agents can select `model: "aicp/qwen3-8b"`
- AICP handles routing, failover, circuit breaking

### Phase 3: ACP Runtime Backend (fleet production)
- Register AICP as native ACP runtime
- Multi-agent session management
- Progress streaming to OpenArms dashboard
- Away summary integration

### Phase 4: Full Multimodal (when tested)
- Vision provider (Gemma4-E4B)
- TTS provider (Piper)
- STT provider (Whisper)
- Image gen provider (Stable Diffusion)
- All routed through AICP's reliability layer
