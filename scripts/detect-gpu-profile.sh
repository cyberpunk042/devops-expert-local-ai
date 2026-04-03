#!/usr/bin/env bash
# Detect GPU configuration and output the right docker-compose override.
# Used by setup.sh and Makefile to auto-select single vs dual GPU config.
#
# Output: prints the compose file argument to stdout
#   Single GPU:  (empty — use default docker-compose.yaml only)
#   Dual GPU:    -f config/docker-compose.dual-gpu.yaml
#   No GPU:      (empty — CPU mode)
set -euo pipefail

GPU_COUNT=0
TOTAL_VRAM=0

if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_COUNT=$(nvidia-smi --query-gpu=index --format=csv,noheader 2>/dev/null | wc -l)
    TOTAL_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | awk '{sum+=$1} END {print sum}')
fi

if [[ "$GPU_COUNT" -ge 2 ]]; then
    echo "-f docker-compose.yaml -f config/docker-compose.dual-gpu.yaml"
elif [[ "$GPU_COUNT" -eq 1 ]]; then
    echo "-f docker-compose.yaml"
else
    echo "-f docker-compose.yaml"
fi

# Also export for scripts that source this
export AICP_GPU_COUNT="$GPU_COUNT"
export AICP_TOTAL_VRAM_MB="$TOTAL_VRAM"
