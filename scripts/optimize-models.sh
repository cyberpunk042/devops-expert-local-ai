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

  # Bump context_size to 8192 if still at 4096
  if grep -q "context_size: 4096" "$yaml"; then
    sed -i 's/context_size: 4096/context_size: 8192/' "$yaml"
    log "$name: bumped context_size 4096 → 8192 (KV cache quant makes this safe)"
    changed=1
  fi

  if [ $changed -eq 1 ]; then
    UPDATED=$((UPDATED + 1))
  fi
}

echo "=== Model Optimization ==="

# Apply to all chat/LLM models
for yaml in "$MODELS_DIR"/hermes.yaml "$MODELS_DIR"/hermes-3b.yaml "$MODELS_DIR"/codellama.yaml "$MODELS_DIR"/llava.yaml "$MODELS_DIR"/phi-2.yaml; do
  optimize_model "$yaml"
done

if [ $UPDATED -eq 0 ]; then
  echo "  All models already optimized."
else
  echo "  $UPDATED model(s) optimized."
  echo "  Restart LocalAI to apply: docker compose restart localai"
fi
