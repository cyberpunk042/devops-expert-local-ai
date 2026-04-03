#!/bin/bash
# optimize-models.sh — Apply performance optimizations to model YAML configs
# Run after model download/setup. Idempotent: safe to re-run.
# Adds: KV cache quantization, Flash Attention, function calling grammar, prompt caching
set -euo pipefail

MODELS_DIR="${1:-models}"
UPDATED=0

log() { echo "  [optimize] $1"; }

# ── Apply optimization to a YAML file ──────────────────────────────
optimize_model() {
  local yaml="$1"
  local name
  name=$(basename "$yaml" .yaml)

  if [ ! -f "$yaml" ]; then
    return
  fi

  local changed=0

  # KV cache quantization (4x VRAM savings)
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

  # Function calling grammar (reliable tool use on small models)
  # Only for chat models, not embedding/reranker/audio
  case "$name" in
    hermes*|codellama|phi-*|llava)
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
      ;;
  esac

  # Parallel calls for Hermes 2 Pro (purpose-built for multi-tool)
  if [[ "$name" == "hermes" ]] && grep -q "parallel_calls: false" "$yaml"; then
    sed -i 's/parallel_calls: false/parallel_calls: true/' "$yaml"
    log "$name: enabled parallel function calls (Hermes 2 Pro)"
    changed=1
  fi

  # Prompt caching (skip if already present)
  if ! grep -q "prompt_cache_path" "$yaml"; then
    case "$name" in
      hermes*|codellama|phi-*|llava)
        cat >> "$yaml" << PCEOF

# ── Prompt caching ──
prompt_cache_path: ${name}-cache
prompt_cache_all: true
PCEOF
        log "$name: added prompt caching"
        changed=1
        ;;
    esac
  fi

  # Repeat penalty (prevents loops on small models)
  if ! grep -q "repeat_penalty" "$yaml"; then
    case "$name" in
      hermes-3b)
        sed -i '/top_p:/a\  repeat_penalty: 1.1' "$yaml"
        log "$name: added repeat_penalty 1.1"
        changed=1
        ;;
    esac
  fi

  # Batch size for embedding models (must handle full chunk inputs)
  if ! grep -q "batch_size" "$yaml"; then
    case "$name" in
      nomic-embed|bge-*)
        echo "batch_size: 2048" >> "$yaml"
        log "$name: added batch_size: 2048 (embedding inputs can exceed default 512)"
        changed=1
        ;;
    esac
  fi

  # Ensure context_size at ROOT level (NOT under parameters: — LocalAI ignores it there)
  # Must account for LLAMACPP_PARALLEL: LocalAI divides total context by parallel slots
  # With PARALLEL=4, need context_size=32768 so each slot gets 8192
  local target_ctx=16384
  if grep -q "^  context_size:" "$yaml"; then
    # Wrong location: under parameters — move to root
    sed -i '/^  context_size:/d' "$yaml"
    if ! grep -q "^context_size:" "$yaml"; then
      echo "context_size: $target_ctx" >> "$yaml"
      log "$name: moved context_size to root level → $target_ctx (8192 per parallel slot)"
      changed=1
    fi
  elif grep -q "^context_size:" "$yaml"; then
    local cur
    cur=$(grep "^context_size:" "$yaml" | awk '{print $2}')
    if [ "$cur" -lt "$target_ctx" ] 2>/dev/null; then
      sed -i "s/^context_size: .*/context_size: $target_ctx/" "$yaml"
      log "$name: bumped context_size $cur → $target_ctx (8192 per parallel slot)"
      changed=1
    fi
  elif ! grep -q "context_size:" "$yaml"; then
    echo "context_size: $target_ctx" >> "$yaml"
    log "$name: added context_size: $target_ctx at root level"
    changed=1
  fi

  if [ $changed -eq 1 ]; then
    UPDATED=$((UPDATED + 1))
  fi
}

echo "=== Model Optimization ==="

# Apply to all models (chat/LLM + embedding)
for yaml in "$MODELS_DIR"/hermes.yaml "$MODELS_DIR"/hermes-3b.yaml "$MODELS_DIR"/codellama.yaml "$MODELS_DIR"/llava.yaml "$MODELS_DIR"/phi-2.yaml "$MODELS_DIR"/nomic-embed.yaml; do
  optimize_model "$yaml"
done

if [ $UPDATED -eq 0 ]; then
  echo "  All models already optimized."
else
  echo "  $UPDATED model(s) optimized."
  echo "  Restart LocalAI to apply: docker compose restart localai"
fi
