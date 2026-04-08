#!/usr/bin/env bash
# ── Build stable-diffusion.cpp from source (CUDA) ────────────────────────────
# Builds the latest sd.cpp with CUDA support for SD 3.5 compatibility.
# LocalAI v4.1.3's bundled backend is too old for SD 3.5 — this builds
# a standalone sd-cli and sd-server that work.
#
# Usage: bash scripts/build-sd-cpp.sh
#        make build-sd-cpp
#
# Prerequisites: gcc, cmake, nvcc (CUDA toolkit), git
# Output: builds/sd-cpp/sd-cli, builds/sd-cpp/sd-server
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/builds/sd-cpp"
SRC_DIR="$BUILD_DIR/src"
BIN_DIR="$BUILD_DIR"

# ── GPU architecture (default: RTX 3060 Ti = sm_86) ──
CUDA_ARCH="${CUDA_ARCH:-86}"

echo "╔═══════════════════════════════════════════════╗"
echo "║   Build stable-diffusion.cpp (CUDA)           ║"
echo "╚═══════════════════════════════════════════════╝"

# ── Check prerequisites ──
for cmd in gcc cmake nvcc git; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: $cmd not found. Install it first."
        exit 1
    fi
done
echo "✓ Prerequisites: gcc, cmake, nvcc, git"

# ── Clone or update source ──
if [ -d "$SRC_DIR/.git" ]; then
    echo "Updating existing source..."
    cd "$SRC_DIR"
    git pull --ff-only 2>/dev/null || true
    git submodule update --init --recursive
else
    echo "Cloning stable-diffusion.cpp..."
    mkdir -p "$BUILD_DIR"
    git clone --depth 1 https://github.com/leejet/stable-diffusion.cpp.git "$SRC_DIR"
    cd "$SRC_DIR"
    git submodule update --init --recursive
fi

COMMIT="$(git -C "$SRC_DIR" rev-parse --short HEAD)"
echo "✓ Source: commit $COMMIT"

# ── Configure ──
echo "Configuring (CUDA arch: sm_$CUDA_ARCH)..."
mkdir -p "$SRC_DIR/build"
cd "$SRC_DIR/build"
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DSD_CUDA=ON \
    -DBUILD_SHARED_LIBS=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_INSTALL_PREFIX="$BIN_DIR" \
    > /dev/null 2>&1
echo "✓ Configured"

# ── Build ──
NPROC="$(nproc)"
echo "Building with $NPROC threads (this takes ~3 minutes)..."
make -j"$NPROC" 2>&1 | grep -E "^\[|Built target|Error" || true

# ── Install binaries ──
if [ -f "$SRC_DIR/build/bin/sd-cli" ] && [ -f "$SRC_DIR/build/bin/sd-server" ]; then
    cp "$SRC_DIR/build/bin/sd-cli" "$BIN_DIR/sd-cli"
    cp "$SRC_DIR/build/bin/sd-server" "$BIN_DIR/sd-server"
    chmod +x "$BIN_DIR/sd-cli" "$BIN_DIR/sd-server"
    echo ""
    echo "╔═══════════════════════════════════════════════╗"
    echo "║   Build complete!                             ║"
    echo "╚═══════════════════════════════════════════════╝"
    echo ""
    echo "  sd-cli:    $BIN_DIR/sd-cli ($(du -h "$BIN_DIR/sd-cli" | cut -f1))"
    echo "  sd-server: $BIN_DIR/sd-server ($(du -h "$BIN_DIR/sd-server" | cut -f1))"
    echo "  commit:    $COMMIT"
    echo ""
    echo "  Test:"
    echo "    $BIN_DIR/sd-cli \\"
    echo "      -m models/sd3.5_medium.safetensors \\"
    echo "      --clip_l models/clip_l-Q8_0.gguf \\"
    echo "      --clip_g models/clip_g-Q8_0.gguf \\"
    echo "      --t5xxl models/t5xxl-Q4_0.gguf \\"
    echo "      --clip-on-cpu --vae-on-cpu \\"
    echo "      --sampling-method euler --cfg-scale 4.5 --steps 25 \\"
    echo "      -H 512 -W 512 -p \"a sunset over mountains\" \\"
    echo "      -o /tmp/sd35_test.png"
    echo ""
    echo "  Run as API server:"
    echo "    $BIN_DIR/sd-server \\"
    echo "      -m models/sd3.5_medium.safetensors \\"
    echo "      --clip_l models/clip_l-Q8_0.gguf \\"
    echo "      --clip_g models/clip_g-Q8_0.gguf \\"
    echo "      --t5xxl models/t5xxl-Q4_0.gguf \\"
    echo "      --clip-on-cpu --vae-on-cpu \\"
    echo "      --port 8091"
else
    echo "ERROR: Build failed — binaries not found."
    echo "Check $SRC_DIR/build/ for error details."
    exit 1
fi
