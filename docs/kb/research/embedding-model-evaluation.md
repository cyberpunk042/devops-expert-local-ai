# Embedding Model Evaluation for AICP RAG

**Type:** Research Finding
**Date:** 2026-04-03
**Status:** RESEARCHED — current model works, alternatives identified

---

## Current: nomic-embed-text v1.5

| Property | Value |
|----------|-------|
| Model | `nomic-embed-text-v1.5.Q8_0.gguf` |
| Size | ~140 MB |
| Dimensions | 768 |
| Context | 8192 tokens |
| Runs on | CPU (gpu_layers: 0) |
| VRAM cost | 0 (fully CPU) |
| Quality | Good for general-purpose retrieval |

**Key advantage:** Runs on CPU alongside GPU LLM models. Zero GPU cost for RAG.

---

## Alternatives to Evaluate

### Upgrade candidates (all CPU-compatible)

| Model | Dims | Context | Size | Notes |
|-------|------|---------|------|-------|
| **nomic-embed-text v2** | 768 | 8192 | ~150 MB | Incremental improvement |
| **bge-m3** | 1024 | 8192 | ~560 MB | Multi-lingual, dense+sparse hybrid |
| **gte-Qwen2-1.5B** | 1536 | 32K | ~1.5 GB | Massive context, high quality |
| **snowflake-arctic-embed-m** | 768 | 512 | ~110 MB | Small, fast, competitive |
| **mxbai-embed-large** | 1024 | 512 | ~670 MB | High MTEB scores |

### When to upgrade

Current `nomic-embed-text v1.5` is **good enough** for:
- Project file indexing
- KB search with reranking (BGE reranker compensates for embedding quality)
- Fleet agent context retrieval

Consider upgrading when:
- RAG quality is demonstrably poor (missed relevant chunks)
- Multi-lingual content needs indexing (→ bge-m3)
- Very long documents need single-chunk embedding (→ gte-Qwen2)

### Important: CPU embedding + GPU reranking

Our architecture runs embeddings on CPU and reranking on GPU (via BGE reranker).
This means:
- Embedding quality matters less because reranker fixes ranking
- Embedding speed matters more (CPU-bound)
- Smaller embedding models are preferred for throughput

---

## Recommendation

**Keep nomic-embed-text v1.5 for now.** The BGE reranker compensates for any
quality gaps. If RAG quality is insufficient after real-world testing, evaluate
`bge-m3` as the next step (better quality, still CPU-friendly, ~4x larger).

---

## GGUF Sources

| Model | URL |
|-------|-----|
| nomic-embed v1.5 (current) | `huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF` |
| bge-m3 | `huggingface.co/BAAI/bge-m3` (needs GGUF conversion) |
| snowflake-arctic-embed | `huggingface.co/Snowflake/snowflake-arctic-embed-m-v2.0` |
