#!/usr/bin/env bash
# llama-serve.sh — launch llama.cpp's llama-server for Kimi K2.6 Q2 local inference.
#
# This is the operational wrapper that E008-m004 / E011-m003 (OpenAI-compat
# endpoint at :8091) calls into. Replaces the earlier kt-serve.sh sglang+kt-kernel
# path, which was wrong for this operator's 64GB consumer hardware — see
# docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md for why.
#
# Configuration rationale:
#
# 1. llama.cpp (not sglang+kt-kernel) because:
#    - Consumes Unsloth's Q2_K_XL GGUF natively (the brain's M002 spec).
#    - Memory profile ~20-30GB at startup (fits 64GB comfortably).
#    - No GPTQ Marlin repack / JIT compile / static KV pre-allocation at startup.
#
# 2. --n-gpu-layers 0 — pure CPU/mmap. Rationale: K2.6 layers at Q2 are ~5.3 GB
#    each; even 2 layers exceeds the 11 GB RTX 2080 Ti's available VRAM after
#    overhead. -ngl 0 keeps everything mmap'd and paged from NVMe on demand.
#    Cost: ~0.3 tok/s single-user throughput. To try partial GPU offload, set
#    NGL=1 or NGL=2 (experimental, may OOM VRAM on peak).
#
# 3. --ctx-size 4096 — conservative initial context. KV cache at 4K takes ~2 GB
#    RAM. Raise to 8192 or 16384 for longer conversations if RAM allows.
#
# 4. --threads 4 — WSL VM exposes 4 physical cores (i7-7800X is 6 physical,
#    Hyper-V caps at 4).
#
# 5. --alias kimi-k2.6-q2 — matches `backends.k2_6_local.model` in
#    config/default.yaml and what AICP's adapter expects in /v1/models response.
#
# 6. NO --chat-template override — K2.6's GGUF metadata embeds its own
#    chat_template.jinja. Earlier attempts with --chat-template deepseek
#    produced garbled output (subtitle-style tokens instead of chat responses).
#    Let llama-server use the embedded template.
#
# Usage:
#   bash scripts/llama-serve.sh [PORT] [NGL]
# Defaults: PORT=8091, NGL=0
#
# Foreground by default; Ctrl-C stops cleanly. For background, wrap with nohup
# or a user systemd unit.

set -euo pipefail

PORT="${1:-8091}"
NGL="${2:-0}"

LLAMA_BIN="/mnt/dev-envs/llama.cpp/build/bin/llama-server"
MODEL="/mnt/models/kimi-k2-6-q2/UD-Q2_K_XL/Kimi-K2.6-UD-Q2_K_XL-00001-of-00008.gguf"
CTX_SIZE="${CTX_SIZE:-4096}"
THREADS="${THREADS:-4}"

if [ ! -x "${LLAMA_BIN}" ]; then
    echo "ERROR: llama-server not found at ${LLAMA_BIN}" >&2
    echo "Build it with: cd /mnt/dev-envs/llama.cpp && cmake --build build --config Release -j 8" >&2
    exit 1
fi
if [ ! -f "${MODEL}" ]; then
    echo "ERROR: K2.6 Q2 weights not found at ${MODEL}" >&2
    echo "Download with: hf download unsloth/Kimi-K2.6-GGUF --include 'UD-Q2_K_XL/*' --local-dir /mnt/models/kimi-k2-6-q2" >&2
    exit 1
fi

# Sanity warn on RAM budget
AVAIL_GB=$(free -g | awk '/^Mem:/ {print $7}')
if [ "${AVAIL_GB}" -lt 30 ]; then
    echo "WARNING: only ${AVAIL_GB} GB RAM available. llama-server may be tight." >&2
    echo "         Close heavy apps or raise WSL memory cap in .wslconfig." >&2
fi

echo "→ Model:    ${MODEL}"
echo "→ Port:     ${PORT}"
echo "→ Context:  ${CTX_SIZE}"
echo "→ GPU lyrs: ${NGL} (0 = CPU-only / mmap, safest on this hardware)"
echo "→ Threads:  ${THREADS}"
echo "→ RAM avl:  ${AVAIL_GB} GB"
echo
echo "First-call cold mmap load: ~10-17 min."
echo "After warm: ~0.3 tok/s single-user at -ngl 0 on this hardware."
echo "Press Ctrl-C to stop."
echo

exec "${LLAMA_BIN}" \
    --model "${MODEL}" \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --n-gpu-layers "${NGL}" \
    --ctx-size "${CTX_SIZE}" \
    --threads "${THREADS}" \
    --batch-size 512 \
    --alias kimi-k2.6-q2
