---
title: "Decision: LocalAI v4.1.3 over Ollama / vLLM for multi-model orchestration under a VRAM constraint"
type: decision
domain: backend-ai-platform-python
layer: 6
status: synthesized
confidence: high
maturity: seed
derived_from:
  - "model-local-ai"
reversibility: hard
created: 2026-04-18
updated: 2026-04-18
sources:
  - id: aicp-compose
    type: file
    file: docker-compose.yaml
    description: LocalAI v4.1.3 container config with watchdog + single-active + embeddings pool
  - id: aicp-models
    type: directory
    file: config/models/
    description: 14 model YAML configs (chat + embed + rerank + vision + STT + TTS + image-gen) all consumed by LocalAI's single OpenAI-compatible API
  - id: aicp-localai-backend
    type: file
    file: aicp/backends/localai.py
    description: AICP's LocalAI HTTP client — assumes OpenAI-compatible chat completions + embeddings + audio endpoints
  - id: model-local-ai
    type: wiki
    file: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-local-ai.md
    description: Second brain's Local AI ($0 Target) model — routing framework agnostic to runtime stack
tags: [decision, localai, ollama, vllm, runtime, infrastructure, aicp, backend-ai-platform-python, transferable, ecosystem]
---

# Decision: LocalAI v4.1.3 over Ollama / vLLM for multi-model orchestration under a VRAM constraint

## Summary

AICP uses **LocalAI v4.1.3** as the single runtime for all local inference — chat (qwen3-8b / gemma4), embeddings (nomic-embed), reranker (bge-reranker-v2-m3), vision (llava / gemma4-e4b), speech (whisper / piper-tts), and image generation (sd35-medium). The alternative runtimes considered were Ollama (popular, simple) and vLLM (high-throughput, production-grade for single large models). LocalAI wins for AICP specifically because: (a) ONE OpenAI-compatible API handles all capability types (not just chat), (b) LRU backend eviction under a VRAM ceiling fits AICP's 8GB→19GB hardware reality, (c) built-in watchdog auto-recovers stuck backends, (d) the Collections endpoint provides RAG storage without a separate vector DB. Ollama can't serve non-chat modalities uniformly; vLLM requires one-model-per-instance which breaks the single-active-backend pattern. This decision is tightly coupled to the routing design (4-tier router assumes a swap-on-demand local runtime) and switching away is genuinely hard.

## Decision

> [!success] Use LocalAI v4.1.3 as the unified local-inference runtime. Consume it via its OpenAI-compatible HTTP API.
>
> | Capability | LocalAI endpoint | Model |
> |------------|-----------------|-------|
> | Chat completion | `POST /v1/chat/completions` | qwen3-8b (main), qwen3-8b-fast, qwen3-4b, gemma4-e2b/e4b, qwen3-30b-a3b (dual-GPU) |
> | Embeddings | `POST /v1/embeddings` | nomic-embed (CPU, batch 2048) |
> | Reranker | LocalAI-specific | bge-reranker-v2-m3 |
> | Vision | `POST /v1/chat/completions` (multimodal) | llava, gemma4-e4b |
> | Speech-to-text | `POST /v1/audio/transcriptions` | whisper |
> | Text-to-speech | `POST /v1/audio/speech` | piper-tts |
> | Image generation | `POST /v1/images/generations` | sd35-medium |
> | RAG store | `POST /api/agents/collections/<name>/search` | Collections backed by chromem |

All consumption goes through `aicp/backends/localai.py`, which speaks the OpenAI-compatible shape. Changes to the runtime stack would require this backend class to be rewritten.

## Alternatives

### Alternative 1: Ollama

Ollama is the most popular local-LLM runtime. Simple CLI (`ollama run qwen3:8b`), solid chat completions, growing ecosystem.

> [!warning] Rejected: Ollama's scope is **chat models**. It does not natively serve embeddings in the OpenAI-compatible shape (recent versions add partial embed support but not reranker, TTS, STT, or image-gen). AICP needs all 7 capability types through ONE runtime to keep the backend layer simple. Going with Ollama would force a multi-runtime stack (Ollama for chat + separate TEI for embeddings + separate Whisper container for STT + separate Coqui for TTS + separate ComfyUI for SD) — each with its own API shape, its own lifecycle, its own failure mode. AICP tried TEI for embeddings (see operational memory: "TEI ONNX hangs on WSL2") and reverted to LocalAI. Unified runtime is structurally better under AICP's operational constraints.

### Alternative 2: vLLM

vLLM is the high-throughput production runtime for large single models. PagedAttention, continuous batching, state-of-the-art serving performance on a single GPU.

> [!warning] Rejected: vLLM serves ONE model per instance. AICP's single-active-backend pattern (one GPU model at a time under 8GB VRAM, swap on demand) is directly opposed to vLLM's "load the model once, serve it for the process lifetime" model. Running AICP's 9 models via vLLM would require 9 containers with orchestration on top — or one vLLM instance that's restarted for each swap (10-80s cold start × frequent swaps = unusable). vLLM is the right choice for a production chat service with a fixed model; it's the wrong choice for AICP's multi-model swap pattern under VRAM constraint. vLLM also doesn't serve embeddings/reranker/vision/audio/image-gen uniformly — same Alternative 1 problem at higher scale.

### Alternative 3: Text Generation Inference (TGI, HuggingFace)

HuggingFace's TGI is production-grade for chat + embeddings. Similar tradeoffs to vLLM but with broader capability support.

> [!warning] Rejected on two grounds: (a) same one-model-per-instance problem as vLLM — doesn't fit single-active-backend. (b) TGI is heavily Docker/GPU-first; AICP's CPU fallback path (phi-2, nomic-embed) benefits from LocalAI's uniform handling of GPU vs CPU models in the same API, which TGI doesn't prioritize.

### Alternative 4: Build a custom orchestrator (direct llama.cpp + transformers + custom glue)

Skip all runtimes; use llama.cpp directly for GGUF models, HuggingFace transformers for everything else, custom Python to swap them.

> [!warning] Rejected: reinventing what LocalAI provides. LocalAI v4.x IS this orchestrator, maintained by a community, OpenAI-compatible, battle-tested. AICP's mission is NOT "build a local inference runtime" — it's "orchestrate AI backends" at a higher level. Building custom glue duplicates what LocalAI does well and diverts effort from AICP's actual mission (progressive offload from Claude to local). Per AICP's CLAUDE.md key principle: "Keep v1 simple and usable. Add complexity only when it earns its place."

## Rationale

> [!info] Evidence-backed reasons
>
> 1. **AICP requires 7 capability types through ONE API.** Chat + embeddings + reranker + vision + STT + TTS + image-gen — documented in `config/models/` (14 model YAMLs) and consumed by `aicp/backends/localai.py` through a single HTTP client. No other runtime unifies all 7 under OpenAI-compatible shape.
>
> 2. **Single-active backend under VRAM ceiling is the operational reality.** 8GB VRAM (yesterday) → 19GB (today with dual GPU) forces `LOCALAI_SINGLE_ACTIVE_BACKEND=false` + `LOCALAI_MAX_ACTIVE_BACKENDS=3` — LRU eviction across GPU model + embed (CPU) + reranker (CPU). Dual-GPU profile (`config/profiles/dual-gpu.yaml`) now lets the 30B MoE run while still swap-eviction-friendly. LocalAI's MAX_ACTIVE_BACKENDS is the exact knob needed; Ollama doesn't have a semantic equivalent.
>
> 3. **Watchdog auto-recovery is load-bearing.** `LOCALAI_WATCHDOG_IDLE=true` (15m timeout) + `LOCALAI_WATCHDOG_BUSY=true` (10m timeout) auto-kills stuck backends and respawns them. AICP's reliability profile depends on this — without it, a stuck model swap freezes all inference until a human restarts the container. Ollama + Docker compose restart is manual.
>
> 4. **Collections endpoint replaces a separate vector DB.** `POST /api/agents/collections/aicp-kb/search` provides RAG storage/retrieval backed by chromem. AICP syncs `docs/kb/` + `docs/knowledge-map/` into Collections via `make kb-sync`. No separate Qdrant / Weaviate / Milvus / pgvector container to operate. For a 225-entry KB at AICP's scale, this is materially simpler than running a dedicated vector DB.
>
> 5. **OpenAI-compatible surface is the integration abstraction.** `aicp/backends/localai.py` uses the OpenAI Python SDK shape (`openai.ChatCompletion.create(...)` with `base_url=http://localhost:8090/v1`). If LocalAI proved insufficient for a specific capability, AICP could point the SDK at a different provider for that one capability (e.g., Claude backend for chat + LocalAI for embeddings). Custom orchestrator or non-OpenAI runtimes foreclose this flexibility.
>
> 6. **The \$0 target (second brain's Local AI model) is achievable via LocalAI.** Per the Local AI ($0 Target) model, ~80% of operations should route local once Stage 3 is operational. LocalAI's pricing is \$0 (self-hosted, no per-token cost). Any cloud-inference alternative (AWS Bedrock local, Azure OpenAI) defeats the \$0 target.

## Reversibility

**Hard** — the decision is load-bearing for:

- `aicp/backends/localai.py` (entire module assumes LocalAI's OpenAI-compatible API with LocalAI-specific extensions like Collections)
- `config/models/*.yaml` (14 YAML files in LocalAI's native format — not directly portable to Ollama's `Modelfile` or vLLM's launch args)
- `docker-compose.yaml` (LocalAI container + env vars are the runtime definition)
- `Makefile` targets (`make setup`, `make model-*`, `make kb-sync`, `make sd35-test`) all assume LocalAI
- `.mcp.json` (AICP's MCP server routes through the LocalAI backend)

Switching away requires: rewriting `aicp/backends/localai.py` against the new runtime's API, re-extracting 14 model configs to the new format, rewriting Docker compose, rewriting Makefile IaC, potentially adding a separate vector DB to replace Collections. Multiple weeks of work. Easier path: add a second backend alongside LocalAI (e.g., `aicp/backends/ollama.py`) if a specific capability needs Ollama-specific features — but DON'T replace LocalAI outright.

## Dependencies

If reversed (switch primary runtime away from LocalAI):

- **All 14 model configs** must be rewritten for the new runtime's format
- **aicp/backends/localai.py** rewritten (or aliased + new backend added)
- **docker-compose.yaml** rewritten for the new runtime's env vars, ports, volumes
- **Makefile model-* targets** rewritten for the new runtime's model-install mechanism
- **KB Collections** replaced by a separate vector DB (Qdrant, Weaviate, pgvector)
- **Reliability stack** (circuit breaker, DLQ) continues to work at AICP's layer; watchdog semantics may differ
- **Profiles** (9 YAML files) retain their shape but `backends:` section may need runtime-specific tuning

If extended (add a SECOND runtime alongside LocalAI):

- New backend module (e.g., `aicp/backends/ollama.py`)
- Router needs new tier or per-capability dispatch logic (currently assumes one local runtime per tier)
- `config/models/` may need subdirectories per runtime OR a `runtime:` field per YAML
- MCP server `aicp_route` tool needs to return which runtime served the request

## Relationships

- BUILDS ON: ~/devops-solutions-research-wiki/wiki/spine/models/depth/model-local-ai.md (Local AI $0 Target model)
- RELATES TO: [4-tier router with profiles over hardcoded routing](./4-tier-router-with-profiles-over-hardcoded-routing.md) (sibling decision — router's per-tier backend selection assumes LocalAI for the first tier)
- RELATES TO: [Skills as primary extension pattern](./skills-as-primary-extension-pattern.md) (sibling decision — both concern AICP's foundational architectural shape)
- RELATES TO: [Profile as Coordination Bundle](../../patterns/01_drafts/profile-as-coordination-bundle.md) (dual-gpu profile couples LocalAI-specific envs CONTEXT_SIZE + LLAMACPP_PARALLEL with the 19GB hardware reality)
- ENABLES: AICP's unified 7-capability inference stack via one container
- CONSTRAINS: future capability additions — new modalities must be expressible through LocalAI or justify a second runtime
