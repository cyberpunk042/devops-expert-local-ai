# AICP Tool Manual — 64 MCP Tools

Complete reference for all MCP tools exposed by `aicp/mcp/server.py`.
Accessible via Claude Code MCP, fleet agents, or direct HTTP.

---

## Chat & Inference (9)

| Tool | Args | Purpose |
|------|------|---------|
| `aicp_chat` | prompt, mode, seed | Send prompt to local LLM with auto-routing (qwen3-8b/4b/fast) |
| `aicp_complete` | prompt, max_tokens, stop | Raw text completion (no chat template) |
| `aicp_complete_n` | prompt, n, max_tokens, seed | Generate N completions for same prompt |
| `aicp_complete_logprobs` | prompt, max_tokens, top_logprobs, seed | Completion with per-token log probabilities |
| `aicp_agent` | prompt, mode, max_rounds | Autonomous tool-calling loop — LLM calls tools iteratively |
| `aicp_grammar` | prompt, grammar, mode | GBNF grammar-constrained generation |
| `aicp_json` | prompt, schema, mode, seed | Force valid JSON output (structured output mode) |
| `aicp_edit` | input_text, instruction | Edit text based on instruction |
| `aicp_infill` | prefix, suffix, max_tokens | Fill-in-the-Middle code completion |

## Embedding & Search (10)

| Tool | Args | Purpose |
|------|------|---------|
| `aicp_embed` | text | Generate 768-dim embedding (nomic-embed, CPU) |
| `aicp_embed_dims` | text, dimensions, model | Truncated embedding with specific dimensions |
| `aicp_embed_typed` | text, embed_type | Asymmetric embedding (query vs document) |
| `aicp_embed_typed_batch` | texts_json, embed_type | Batch embeddings for indexing |
| `aicp_embed_image` | image_path | CLIP-style image embedding |
| `aicp_similarity` | text_a, text_b | Cosine similarity between two texts |
| `aicp_nearest_neighbors` | query, documents_json, top_k | Find most similar documents |
| `aicp_rerank` | query, documents, top_n | Cross-encoder reranking (BGE reranker) |
| `aicp_store_set` | text, store | Store text in ephemeral working memory |
| `aicp_store_find` | query, top_k, store | Search ephemeral working memory |

## Knowledge Base (4)

| Tool | Args | Purpose |
|------|------|---------|
| `aicp_kb_search` | query, top_k | Semantic search across KB (RAG) |
| `aicp_kb_ingest` | path | Ingest file or directory into KB |
| `aicp_kb_stats` | | KB statistics (chunks, sources) |
| `aicp_kb_augment` | query, max_context_chars | Build RAG-augmented prompt with KB context |

## Tokenization (4)

| Tool | Args | Purpose |
|------|------|---------|
| `aicp_tokenize` | text | Count tokens using local tokenizer |
| `aicp_tokenize_batch` | texts | Batch tokenization (newline-separated) |
| `aicp_detokenize` | tokens_json, model | Token IDs → text |
| `aicp_token_count` | text, model | Quick token count |

## Model Management (10)

| Tool | Args | Purpose |
|------|------|---------|
| `aicp_models` | | List all available models |
| `aicp_models_loaded` | | List models currently in GPU memory |
| `aicp_model_gallery` | search | Browse model gallery |
| `aicp_model_install` | model_id, name | Install model from gallery |
| `aicp_model_status` | model_or_job | Check model state or download progress |
| `aicp_model_unload` | model_name | Unload from GPU (keep files) |
| `aicp_model_delete` | model_name | Delete model entirely |
| `aicp_model_config` | model_name | Read runtime config (gpu_layers, context, etc) |
| `aicp_model_config_update` | context_size, gpu_layers, threads, ... | Update runtime params without restart |
| `aicp_warmup` | model_name | Pre-load model into VRAM |

## Multimodal (4)

| Tool | Args | Purpose |
|------|------|---------|
| `aicp_vision` | image_path, prompt | Analyze image with LLaVA |
| `aicp_multimodal` | messages_json, images_json, mode | Multi-turn visual chat |
| `aicp_imagine` | prompt, output_path, size | Generate image (Stable Diffusion) |
| `aicp_detect` | image_path | Object detection in image |

## Audio & Voice (8)

| Tool | Args | Purpose |
|------|------|---------|
| `aicp_transcribe` | audio_path, language | Speech-to-text (Whisper) |
| `aicp_transcribe_detailed` | audio_path, language, timestamp_granularities, response_format | Verbose transcription with timestamps |
| `aicp_speak` | text, output_path | Text-to-speech (Piper TTS) |
| `aicp_tts` | text, output_path, voice, speed, response_format | OpenAI-compatible TTS |
| `aicp_tts_voices` | model | List available TTS voices |
| `aicp_voice_pipeline` | audio_input, audio_output | Full pipeline: transcribe → LLM → speak |
| `aicp_sound` | prompt, output_path | Generate sound/music from text |
| `aicp_vad` | audio_path | Voice activity detection |

## System & Observability (8)

| Tool | Args | Purpose |
|------|------|---------|
| `aicp_health` | | LocalAI health + readiness |
| `aicp_system` | | Active GPU model, backends, all models |
| `aicp_metrics` | | Live Prometheus metrics + GPU stats |
| `aicp_backends_list` | | Installed execution engines |
| `aicp_server_config` | | Server capabilities and features |
| `aicp_fleet_status` | | All fleet nodes status |
| `aicp_fleet_run` | prompt, mode | Route task to best fleet node |
| `aicp_p2p_status` | | P2P cluster stats |

## Advanced (7)

| Tool | Args | Purpose |
|------|------|---------|
| `aicp_batch` | prompts, mode, max_workers | Concurrent multi-prompt execution |
| `aicp_bestof` | prompt, n, mode, seed | Best-of-N sampling |
| `aicp_logprobs` | prompt, top_logprobs, mode, seed | Per-token confidence scores |
| `aicp_lora_load` | model_name, adapter_path | Load LoRA adapter at runtime |
| `aicp_lora_list` | | List LoRA-configured models |
| `aicp_seed` | seed | Set session-wide seed for reproducibility |
| `aicp_tools_stream` | prompt, mode | Streaming tool-calling loop |
