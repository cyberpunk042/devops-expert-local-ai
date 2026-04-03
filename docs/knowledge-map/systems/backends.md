# Backend System

## Minimal
Three AI backends: LocalAI (free, local, GPU), OpenRouter (free cloud, 200+ models), Claude Code (powerful, expensive). Unified interface via Backend ABC.

## Condensed

### Purpose
Abstract multiple AI providers behind a single interface. Each backend can execute prompts, stream responses, and report usage/cost.

### Components
- **base.py** — Backend ABC: execute(), execute_stream(), is_available(), status_detail()
- **localai.py** — LocalAI client (3400 LOC): chat, embed, vision, audio, tools, streaming, Qwen3 reasoning support
- **openrouter.py** — OpenRouter client: OpenAI-compatible API, free model support, cost estimation
- **claude_code.py** — Claude CLI wrapper: subprocess, session management, mode mapping

### Backend Hierarchy
```
Cost:     $0          $0          $$-$$$       $$$$
Speed:    ~1-10s      ~2-5s       ~2-5s        ~5-30s
Quality:  Good        Good        Good-Great   Excellent
          LocalAI     OpenRouter  OpenRouter   Claude
          (local)     (free)      (paid)       (opus)
```

### LocalAI Models (Qwen3 generation)
- **qwen3-8b** — main reasoning, thinking mode, 8K context
- **qwen3-8b-fast** — no-think mode, structured tasks
- **qwen3-4b** — fleet lightweight, 16K context
- **qwen3-30b-a3b** — MoE flagship (dual GPU: 8+11GB)
- **nomic-embed** — embeddings (CPU, 0 GPU cost)
- **bge-reranker** — reranking (CPU)

### Qwen3 Thinking Mode
Models return `reasoning` field (chain-of-thought) + `content` (final answer). Backend's `_extract_content()` handles both. `/no_think` disables reasoning.

### Key Config
```yaml
backends:
  local:
    model: qwen3-8b
    fast_model: qwen3-8b-fast
    fleet_model: qwen3-4b
    auto_route: true
  openrouter:
    # Set OPENROUTER_API_KEY in .env
    max_tokens: 4096
  claude:
    model: opus
    timeout: 300
```
