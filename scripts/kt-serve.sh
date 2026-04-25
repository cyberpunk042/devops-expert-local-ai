#!/usr/bin/env bash
# ============================================================================
# SUPERSEDED — DO NOT USE on this hardware.
# ----------------------------------------------------------------------------
# This script targets sglang+kt-kernel against Moonshot's 555GB safetensors,
# which require ~50GB peak RAM at startup and crashed WSL on 64GB hardware
# (2026-04-24). The Moonshot weights have been deleted. The model directory
# default below (/mnt/models/kimi-k2-6-moonshot) no longer exists, so this
# script will fail its own preflight check.
#
# Canonical replacement: scripts/llama-serve.sh
#   — llama.cpp + Unsloth Q2 GGUF (318GB), ~22GB RAM, fits this hardware.
#
# Kept here as historical reference for the failure-mode postmortem
# (docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md). Delete if you want
# the cleanup.
# ============================================================================
#
# kt-serve.sh — launch KTransformers sglang-kt server for Kimi K2.6 local inference.
#
# This is the operational wrapper that E008-m004 (OpenAI-compat endpoint at :8091)
# calls into. It encapsulates three non-obvious pieces of config that kt CLI's
# defaults get wrong for this hardware + WSL:
#
# 1. LD_PRELOAD=numa_shim.so — WSL's kernel doesn't expose /sys/devices/system/node,
#    so libnuma reports numa_available()=-1. kt-kernel unconditionally calls
#    numa_bitmask_alloc(numa_num_configured_nodes()) which becomes alloc(0) and
#    hangs with "request to allocate mask for invalid number". The shim fakes
#    single-node NUMA and makes all binds no-ops.
#
# 2. CUDA_VISIBLE_DEVICES=0 + --tp 1 — the RTX 2080 Ti (11GB) + RTX 2080 (8GB)
#    are imbalanced beyond sglang's 10% tolerance for tensor-parallel. Use the
#    single larger GPU.
#
# 3. --cpu-threads 4 — the WSL VM exposes 4 physical cores (i7-7800X host has 6
#    but Hyper-V restricts). Matching this avoids CPU affinity mask errors.
#
# 4. PATH="${VENV}/bin:${PATH}" — sglang JIT-compiles CUDA kernels at startup
#    via `ninja`. Without venv/bin prepended, execvp hits a `ninja/` *directory*
#    in one of the Windows-mapped /mnt/c/... PATH entries (platformio / esp32
#    tools) and fails with EACCES before reaching the real binary.
#
# Model + kt-method expectations:
# - Model dir should be the Moonshot K2.6 repo (safetensors + config). Unsloth's
#   GGUF-only dump doesn't work because HF transformers doesn't support GGUF for
#   deepseek2 architecture.
# - --kt-method RAWINT4 matches Moonshot's native weight format.
#
# Usage:
#   bash scripts/kt-serve.sh [MODEL_DIR] [PORT]
# Default MODEL_DIR: /home/jfortin/kimi-k2-6-moonshot (per E008-m002 layout)
# Default PORT:      8091 (AICP E011-m003 expects this)
#
# The script runs in foreground; Ctrl-C stops the server cleanly.
# For background / systemd use, wrap with nohup or a user systemd unit.

set -euo pipefail

MODEL_DIR="${1:-/mnt/models/kimi-k2-6-moonshot}"
PORT="${2:-8091}"

VENV="/mnt/dev-envs/ktransformers-env"
SHIM="${VENV}/numa_shim.so"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHIM_SRC="${REPO_DIR}/scripts/numa_shim.c"

# Build the NUMA shim on first run if missing (self-sufficient bootstrap)
if [ ! -f "${SHIM}" ]; then
    if [ ! -f "${SHIM_SRC}" ]; then
        echo "ERROR: numa_shim.c missing at ${SHIM_SRC}" >&2
        exit 1
    fi
    echo "→ Building numa_shim.so (first run)"
    gcc -shared -fPIC "${SHIM_SRC}" -o "${SHIM}" || {
        echo "ERROR: failed to compile numa shim" >&2; exit 1;
    }
fi
if [ ! -d "${MODEL_DIR}" ]; then
    echo "ERROR: model directory not found: ${MODEL_DIR}" >&2
    exit 1
fi
if [ ! -f "${MODEL_DIR}/config.json" ]; then
    echo "ERROR: ${MODEL_DIR}/config.json missing — not a valid HF model dir" >&2
    echo "If you only have Unsloth GGUFs, download config.json + tokenizer files from moonshotai/Kimi-K2.6" >&2
    exit 1
fi

echo "→ Model dir: ${MODEL_DIR}"
echo "→ Port:      ${PORT}"
echo "→ Shim:      ${SHIM} (WSL NUMA workaround)"
echo "→ GPU:       device 0 only (--tp 1, VRAM-balanced)"
echo

exec env \
    LD_PRELOAD="${SHIM}" \
    CUDA_VISIBLE_DEVICES=0 \
    PATH="${VENV}/bin:${PATH}" \
    "${VENV}/bin/kt" run \
    "${MODEL_DIR}" \
    --port "${PORT}" \
    --tp 1 \
    --cpu-threads 4 \
    --kt-method RAWINT4
