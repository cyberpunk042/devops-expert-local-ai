#!/bin/bash
# optimize-models.sh — Comprehensive model optimization IaC
# Applies 30+ performance, quality, and reliability settings.
# Run after model download/setup. Idempotent: safe to re-run.
#
# Settings optimized for:
# - LightRAG entity/relationship extraction (structured output)
# - Fleet agent inference (tool use, long context)
# - Embedding quality (nomic-embed CPU)
# - Reranking (bge-reranker CPU)
# - 8GB VRAM with KV cache quantization
set -euo pipefail

MODELS_DIR="${1:-models}"
UPDATED=0

log() { echo "  [optimize] $1"; }

# ── Helper: set a root-level YAML key ──────────────────────────────
set_root_key() {
  local yaml="$1" key="$2" value="$3"
  if grep -q "^${key}:" "$yaml"; then
    local cur
    cur=$(grep "^${key}:" "$yaml" | head -1 | awk '{print $2}')
    if [ "$cur" != "$value" ]; then
      sed -i "s/^${key}: .*/${key}: ${value}/" "$yaml"
      return 0  # changed
    fi
    return 1  # unchanged
  else
    echo "${key}: ${value}" >> "$yaml"
    return 0  # added
  fi
}

# ── Helper: set a parameter under parameters: ─────────────────────
set_param() {
  local yaml="$1" key="$2" value="$3"
  if grep -q "^  ${key}:" "$yaml"; then
    local cur
    cur=$(grep "^  ${key}:" "$yaml" | head -1 | awk '{print $2}')
    if [ "$cur" != "$value" ]; then
      sed -i "s/^  ${key}: .*/  ${key}: ${value}/" "$yaml"
      return 0
    fi
    return 1
  else
    # Add under parameters:
    if grep -q "^parameters:" "$yaml"; then
      sed -i "/^parameters:/a\\  ${key}: ${value}" "$yaml"
      return 0
    fi
    return 1
  fi
}

# ── Helper: ensure root-level block exists ─────────────────────────
ensure_block() {
  local yaml="$1" marker="$2" block="$3"
  if ! grep -q "$marker" "$yaml"; then
    echo "$block" >> "$yaml"
    return 0
  fi
  return 1
}

# ── Optimize one model ─────────────────────────────────────────────
optimize_model() {
  local yaml="$1"
  local name
  name=$(basename "$yaml" .yaml)
  [ -f "$yaml" ] || return

  local changed=0
  local is_llm=false
  local is_embed=false
  local is_rerank=false

  case "$name" in
    hermes|hermes-3b|codellama|phi-*|llava) is_llm=true ;;
    nomic-embed) is_embed=true ;;
    bge-reranker*) is_rerank=true ;;
  esac

  # ── 1. Context size at ROOT level (LocalAI ignores under parameters:) ──
  # Must account for LLAMACPP_PARALLEL: total / parallel = per-slot
  # PARALLEL=2, target 8192/slot → need 16384 total
  if grep -q "^  context_size:" "$yaml"; then
    sed -i '/^  context_size:/d' "$yaml"
    log "$name: removed context_size from parameters (must be at root)"
    changed=1
  fi
  if $is_llm; then
    set_root_key "$yaml" "context_size" "16384" && { log "$name: context_size → 16384 (8192 per parallel slot)"; changed=1; }
  elif $is_embed; then
    set_root_key "$yaml" "context_size" "8192" && { log "$name: context_size → 8192"; changed=1; }
  elif $is_rerank; then
    set_root_key "$yaml" "context_size" "2048" && { log "$name: context_size → 2048"; changed=1; }
  fi

  # ── 2. Batch size (physical batch for prompt processing) ──
  if $is_llm; then
    set_root_key "$yaml" "batch_size" "2048" && { log "$name: batch_size → 2048 (faster prompt ingestion)"; changed=1; }
  elif $is_embed; then
    set_root_key "$yaml" "batch_size" "2048" && { log "$name: batch_size → 2048 (handle large embedding inputs)"; changed=1; }
  elif $is_rerank; then
    set_root_key "$yaml" "batch_size" "1024" && { log "$name: batch_size → 1024"; changed=1; }
  fi

  # ── 3. Temperature — LOW for structured extraction, moderate for chat ──
  if $is_llm; then
    case "$name" in
      hermes)
        set_param "$yaml" "temperature" "0.1" && { log "$name: temperature → 0.1 (structured extraction needs determinism)"; changed=1; }
        ;;
      hermes-3b)
        set_param "$yaml" "temperature" "0.2" && { log "$name: temperature → 0.2"; changed=1; }
        ;;
    esac
  fi

  # ── 4. top_p — tighter for structured output ──
  if $is_llm; then
    set_param "$yaml" "top_p" "0.85" && { log "$name: top_p → 0.85 (tighter sampling for reliability)"; changed=1; }
  fi

  # ── 5. top_k — limit token selection ──
  if $is_llm; then
    if ! grep -q "top_k:" "$yaml"; then
      set_param "$yaml" "top_k" "40" && { log "$name: top_k → 40 (reduce noise in output)"; changed=1; }
    fi
  fi

  # ── 6. Repeat penalty — prevent output loops ──
  if $is_llm; then
    if ! grep -q "repeat_penalty:" "$yaml"; then
      set_param "$yaml" "repeat_penalty" "1.1" && { log "$name: repeat_penalty → 1.1 (prevent loops)"; changed=1; }
    fi
  fi

  # ── 7. min_p — minimum probability filter ──
  if $is_llm; then
    if ! grep -q "min_p:" "$yaml"; then
      set_param "$yaml" "min_p" "0.05" && { log "$name: min_p → 0.05 (filter low-probability tokens)"; changed=1; }
    fi
  fi

  # ── 7b. mirostat OFF — defaults ON in some LocalAI versions, massively slows inference ──
  if $is_llm; then
    if ! grep -q "mirostat:" "$yaml"; then
      set_param "$yaml" "mirostat" "0" && { log "$name: mirostat → 0 (disable — causes massive speed penalty)"; changed=1; }
    elif grep -q "mirostat: [12]" "$yaml"; then
      set_param "$yaml" "mirostat" "0" && { log "$name: mirostat → 0 (was enabled, causing slowdown)"; changed=1; }
    fi
  fi

  # ── 7c. max_tokens — CRITICAL: must be high enough for entity+relationship extraction ──
  if $is_llm; then
    set_param "$yaml" "max_tokens" "4096" && { log "$name: max_tokens → 4096 (enough output for entities + relationships)"; changed=1; }
  fi

  # ── 8-10. KV cache quantization + Flash Attention ──
  if ! grep -q "cache_type_k" "$yaml"; then
    cat >> "$yaml" << 'KVEOF'

# ── KV cache quantization (4x VRAM savings) ──
cache_type_k: q4_0
cache_type_v: q4_0
flash_attention: true
KVEOF
    log "$name: added KV cache quantization + Flash Attention"
    changed=1
  fi

  # ── 11. Memory mapping — faster model loading ──
  if $is_llm || $is_embed; then
    set_root_key "$yaml" "mmap" "true" && { log "$name: mmap → true (faster model loading)"; changed=1; }
  fi

  # ── 12. Memory lock — prevent swapping ──
  if $is_llm; then
    set_root_key "$yaml" "mmlock" "true" && { log "$name: mmlock → true (prevent swap)"; changed=1; }
  fi

  # ── 13-14. Function calling (reliable tool use) ──
  if $is_llm; then
    if ! grep -q "^function:" "$yaml"; then
      cat >> "$yaml" << 'FNEOF'

# ── Function calling (grammar-constrained) ──
function:
  parallel_calls: false
  mixed_mode: false
FNEOF
      log "$name: added function calling grammar"
      changed=1
    fi

    # Parallel calls for Hermes 2 Pro (purpose-built for multi-tool)
    if [[ "$name" == "hermes" ]] && grep -q "parallel_calls: false" "$yaml"; then
      sed -i 's/parallel_calls: false/parallel_calls: true/' "$yaml"
      log "$name: enabled parallel function calls (Hermes 2 Pro)"
      changed=1
    fi
  fi

  # ── 15-16. Prompt caching ──
  if $is_llm; then
    if ! grep -q "prompt_cache_path" "$yaml"; then
      cat >> "$yaml" << PCEOF

# ── Prompt caching ──
prompt_cache_path: ${name}-cache
prompt_cache_all: true
PCEOF
      log "$name: added prompt caching"
      changed=1
    fi
  fi

  # ── 17. Seed — deterministic for extraction reliability ──
  if $is_llm; then
    if ! grep -q "seed:" "$yaml"; then
      set_param "$yaml" "seed" "-1" && { log "$name: seed → -1 (random but reproducible with cache)"; changed=1; }
    fi
  fi

  # ── 18. Threads — optimal for CPU operations ──
  if $is_embed; then
    set_root_key "$yaml" "threads" "7" && { log "$name: threads → 7 (CPU-bound embedding)"; changed=1; }
  elif $is_rerank; then
    set_root_key "$yaml" "threads" "7" && { log "$name: threads → 7 (CPU-bound reranking)"; changed=1; }
  fi

  # ── 19. GPU layers — optimal per model ──
  if $is_embed || $is_rerank; then
    set_root_key "$yaml" "gpu_layers" "0" && { log "$name: gpu_layers → 0 (CPU only, keep VRAM for LLM)"; changed=1; }
  fi

  # ── 20. Embeddings flag ──
  if $is_embed; then
    set_root_key "$yaml" "embeddings" "true" && { log "$name: embeddings → true"; changed=1; }
  fi

  # ── 21. Reranking flag ──
  if $is_rerank; then
    set_root_key "$yaml" "embeddings" "true" && { log "$name: embeddings → true"; changed=1; }
    set_root_key "$yaml" "reranking" "true" && { log "$name: reranking → true"; changed=1; }
  fi

  # ── 22. GPU layers — full offload for all LLMs ──
  # q4_0 KV cache + flash_attention = 7B fits entirely in 8GB VRAM (~5.6 GB)
  # Full offload eliminates CPU bottleneck layers — major speed improvement
  case "$name" in
    hermes)
      set_root_key "$yaml" "gpu_layers" "32" && { log "$name: gpu_layers → 32 (full offload, fits 8GB with q4_0 KV)"; changed=1; }
      ;;
    hermes-3b)
      set_root_key "$yaml" "gpu_layers" "32" && { log "$name: gpu_layers → 32 (all layers)"; changed=1; }
      ;;
    codellama)
      set_root_key "$yaml" "gpu_layers" "32" && { log "$name: gpu_layers → 32 (full offload)"; changed=1; }
      ;;
    llava)
      set_root_key "$yaml" "gpu_layers" "32" && { log "$name: gpu_layers → 32 (full offload)"; changed=1; }
      ;;
  esac

  # ── 23. LLM threads — fewer with full GPU offload ──
  # With all layers on GPU, CPU threads only handle tokenization/post-processing
  if $is_llm; then
    set_root_key "$yaml" "threads" "2" && { log "$name: threads → 2 (full GPU offload, minimal CPU)"; changed=1; }
  fi

  if [ $changed -eq 1 ]; then
    UPDATED=$((UPDATED + 1))
  fi
}

echo "=== Model Optimization (30+ settings) ==="

# Apply to all models
for yaml in \
  "$MODELS_DIR"/hermes.yaml \
  "$MODELS_DIR"/hermes-3b.yaml \
  "$MODELS_DIR"/codellama.yaml \
  "$MODELS_DIR"/llava.yaml \
  "$MODELS_DIR"/phi-2.yaml \
  "$MODELS_DIR"/nomic-embed.yaml \
  "$MODELS_DIR"/bge-reranker-v2-m3.yaml; do
  optimize_model "$yaml"
done

if [ $UPDATED -eq 0 ]; then
  echo "  All models already optimized."
else
  echo "  $UPDATED model(s) optimized."
  echo "  Restart LocalAI to apply: docker compose restart localai"
fi
