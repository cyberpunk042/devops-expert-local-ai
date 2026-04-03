#!/usr/bin/env bash
# =============================================================================
# AICP — GGUF Model Catalog
# Lists curated models with VRAM requirements and download URLs.
# Usage:
#   make model-list-remote           Print catalog
#   make model-list-remote VRAM=6    Filter to models fitting in 6GB VRAM
# =============================================================================

VRAM_FILTER="${VRAM:-0}"

if [ -t 1 ]; then
    BOLD='\033[1m'; CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'
else
    BOLD=''; CYAN=''; GREEN=''; YELLOW=''; RESET=''
fi

echo ""
echo -e "${BOLD}AICP — Curated GGUF Model Catalog${RESET}"
echo -e "Use: make model-download MODEL=<filename> URL=<url>"
echo ""
printf "${BOLD}%-12s %-8s %-10s %-45s %s${RESET}\n" "ALIAS" "VRAM" "SIZE" "FILENAME" "QUALITY"
printf "%-12s %-8s %-10s %-45s %s\n"   "─────────────" "───────" "──────────" "────────────────────────────────────────────" "────────────"

# Catalog entries: ALIAS  MIN_VRAM_GB  SIZE  FILENAME  QUALITY  URL
declare -A URLS
declare -A SIZES
declare -A VRAMS
declare -A QUALITY

# ── Qwen3 models (next-gen, 2025 — recommended) ──────────────────────────
VRAMS[qwen3-8b]="6"
SIZES[qwen3-8b]="4.9 GB"
QUALITY[qwen3-8b]="⭐⭐⭐⭐⭐ best 8B: thinking mode, 119 langs, native tool calling"
URLS[qwen3-8b]="https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf"

VRAMS[qwen3-4b]="4"
SIZES[qwen3-4b]="3.3 GB"
QUALITY[qwen3-4b]="⭐⭐⭐⭐  fast, smart fleet model (replaces hermes-3b)"
URLS[qwen3-4b]="https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q6_K.gguf"

VRAMS[qwen3-30b-a3b]="18"
SIZES[qwen3-30b-a3b]="17 GB"
QUALITY[qwen3-30b-a3b]="⭐⭐⭐⭐⭐ MoE: 30B knowledge, 3B speed — needs dual GPU (8+11GB)"
URLS[qwen3-30b-a3b]="https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF/resolve/main/Qwen3-30B-A3B-Q4_K_M.gguf"

# ── 7B models (legacy — kept for compatibility) ──────────────────────────
VRAMS[hermes]="6"
SIZES[hermes]="4.4 GB"
QUALITY[hermes]="⭐⭐⭐⭐  instruction-following, tool use"
URLS[hermes]="https://huggingface.co/NousResearch/Hermes-2-Pro-Mistral-7B-GGUF/resolve/main/Hermes-2-Pro-Mistral-7B.Q4_K_M.gguf"

VRAMS[mistral-7b]="6"
SIZES[mistral-7b]="4.4 GB"
QUALITY[mistral-7b]="⭐⭐⭐⭐  fast, solid general purpose"
URLS[mistral-7b]="https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"

VRAMS[codellama-7b]="6"
SIZES[codellama-7b]="4.4 GB"
QUALITY[codellama-7b]="⭐⭐⭐⭐  code-focused"
URLS[codellama-7b]="https://huggingface.co/TheBloke/CodeLlama-7B-Instruct-GGUF/resolve/main/codellama-7b-instruct.Q4_K_M.gguf"

# ── 13B models (better quality, needs 8+ GB VRAM for full GPU offload) ─────
VRAMS[hermes-13b]="10"
SIZES[hermes-13b]="8.5 GB"
QUALITY[hermes-13b]="⭐⭐⭐⭐⭐ best instruction quality in class"
URLS[hermes-13b]="https://huggingface.co/TheBloke/Nous-Hermes-2-SOLAR-10.7B-GGUF/resolve/main/nous-hermes-2-solar-10.7b.Q4_K_M.gguf"

VRAMS[codellama-13b]="10"
SIZES[codellama-13b]="8.5 GB"
QUALITY[codellama-13b]="⭐⭐⭐⭐⭐ best local code model"
URLS[codellama-13b]="https://huggingface.co/TheBloke/CodeLlama-13B-Instruct-GGUF/resolve/main/codellama-13b-instruct.Q4_K_M.gguf"

# ── Small models (low VRAM, fast, good for quick queries) ──────────────────
VRAMS[phi3-mini]="3"
SIZES[phi3-mini]="2.2 GB"
QUALITY[phi3-mini]="⭐⭐⭐    fast, surprisingly capable for 3B"
URLS[phi3-mini]="https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf"

VRAMS[gemma-2b]="3"
SIZES[gemma-2b]="1.5 GB"
QUALITY[gemma-2b]="⭐⭐     very fast, limited context"
URLS[gemma-2b]="https://huggingface.co/google/gemma-2b-it-GGUF/resolve/main/gemma-2b-it.gguf"

# ── Print catalog ──────────────────────────────────────────────────────────
ALIASES=("qwen3-8b" "qwen3-4b" "qwen3-30b-a3b" "hermes" "mistral-7b" "codellama-7b" "phi3-mini" "gemma-2b" "hermes-13b" "codellama-13b")

for alias in "${ALIASES[@]}"; do
    vram="${VRAMS[$alias]}"
    if [[ "$VRAM_FILTER" -gt 0 && "$vram" -gt "$VRAM_FILTER" ]]; then
        continue
    fi
    if [[ "$vram" -le 4 ]]; then col="$GREEN"
    elif [[ "$vram" -le 8 ]]; then col="$CYAN"
    else col="$YELLOW"
    fi
    printf "${col}%-12s${RESET} %-8s %-10s %-45s %s\n" \
        "$alias" "${vram}GB" "${SIZES[$alias]}" \
        "$(basename "${URLS[$alias]}")" "${QUALITY[$alias]}"
done

echo ""
echo -e "${BOLD}Download example:${RESET}"
echo "  make model-download MODEL=hermes-2-pro-mistral-7b.Q4_K_M.gguf \\"
echo "    URL=${URLS[hermes]}"
echo ""
echo -e "${BOLD}Download + full setup:${RESET}"
echo "  make setup                          (auto-selects model based on VRAM)"
echo "  make setup-low-vram                 (forces phi3-mini for <6GB VRAM)"
echo "  make setup --model codellama-7b     (explicit model choice)"
echo ""
if [[ "$VRAM_FILTER" -eq 0 ]]; then
    echo -e "Filter by VRAM:  ${CYAN}make model-list-remote VRAM=8${RESET}  (show only models fitting in 8GB)"
    echo ""
fi
