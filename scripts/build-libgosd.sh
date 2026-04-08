#!/usr/bin/env bash
# ── Rebuild libgosd*.so from vendored LocalAI source (CUDA) ────────────────
# LocalAI v4.1.3's gallery-installed stablediffusion-ggml backend ships with
# an older sd.cpp that can't load SD 3.5 models (wrong VAE tensor mapping).
# The v4.1.3 SOURCE already pins sd.cpp @ 8afbeb6 which supports SD 3.5,
# but the pre-built gallery OCI image wasn't rebuilt.
#
# This script builds libgosd-avx2.so from the vendored LocalAI source with
# CUDA support. The result is staged in backends/cuda12-stablediffusion-ggml/
# and copied into the Docker container at startup via entrypoint.sh.
#
# Usage: bash scripts/build-libgosd.sh
#        make build-libgosd
#
# Prerequisites: gcc, g++, cmake, nvcc (CUDA toolkit), git
# Output: backends/cuda12-stablediffusion-ggml-rebuild/libgosd-avx2.so
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_SD="$ROOT_DIR/vendor/LocalAI/backend/go/stablediffusion-ggml"
OUTPUT_DIR="$ROOT_DIR/backends/cuda12-stablediffusion-ggml-rebuild"
BUILD_DIR="$VENDOR_SD/build-libgosd"

# ── GPU architecture (default: RTX 3060 Ti = sm_86) ──
CUDA_ARCH="${CUDA_ARCH:-86}"

echo "╔═══════════════════════════════════════════════╗"
echo "║   Rebuild libgosd (sd.cpp CUDA)               ║"
echo "╚═══════════════════════════════════════════════╝"

# ── Check prerequisites ──
for cmd in gcc g++ cmake nvcc git; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: $cmd not found. Install it first."
        exit 1
    fi
done
echo "✓ Prerequisites: gcc, g++, cmake, nvcc, git"

# ── Check vendor source exists ──
if [ ! -f "$VENDOR_SD/gosd.cpp" ]; then
    echo "ERROR: Vendored LocalAI source not found at $VENDOR_SD"
    echo "       Run: git clone https://github.com/mudler/LocalAI vendor/LocalAI"
    exit 1
fi
echo "✓ Vendor source: $VENDOR_SD"

# ── Clone sd.cpp submodule if not present ──
SD_CPP_DIR="$VENDOR_SD/sources/stablediffusion-ggml.cpp"
SD_CPP_VERSION="8afbeb6ba9702c15d41a38296f2ab1fe5c829fa0"

if [ ! -f "$SD_CPP_DIR/CMakeLists.txt" ]; then
    echo "Cloning sd.cpp @ $SD_CPP_VERSION..."
    mkdir -p "$VENDOR_SD/sources"
    git clone --recursive https://github.com/leejet/stable-diffusion.cpp.git "$SD_CPP_DIR"
    cd "$SD_CPP_DIR"
    git checkout "$SD_CPP_VERSION"
    git submodule update --init --recursive --depth 1 --single-branch
else
    CURRENT="$(git -C "$SD_CPP_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "✓ sd.cpp source present (commit ${CURRENT:0:7})"
    if [ "$CURRENT" != "$SD_CPP_VERSION" ]; then
        echo "  Checking out pinned version $SD_CPP_VERSION..."
        cd "$SD_CPP_DIR"
        git fetch origin
        git checkout "$SD_CPP_VERSION"
        git submodule update --init --recursive --depth 1 --single-branch
    fi
fi

# ── Configure ──
echo "Configuring (CUDA arch: sm_$CUDA_ARCH)..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

cmake "$VENDOR_SD" \
    -DCMAKE_BUILD_TYPE=Release \
    -DSD_CUDA=ON \
    -DGGML_CUDA=ON \
    -DGGML_NATIVE=OFF \
    -DGGML_AVX=ON \
    -DGGML_AVX2=ON \
    -DGGML_AVX512=OFF \
    -DGGML_FMA=ON \
    -DGGML_F16C=ON \
    -DGGML_BMI2=ON \
    -DGGML_MAX_NAME=128 \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    > /dev/null 2>&1
echo "✓ Configured"

# ── Build ──
NPROC="$(nproc)"
echo "Building with $NPROC threads..."
cmake --build . --config Release -j"$NPROC" 2>&1 | grep -E "^\[|Built target|Error|error:" || true

# ── Check output ──
if [ ! -f "$BUILD_DIR/libgosd.so" ]; then
    echo "ERROR: Build failed — libgosd.so not found in $BUILD_DIR"
    echo "Check build output above for errors."
    exit 1
fi

# ── Stage for Docker ──
mkdir -p "$OUTPUT_DIR"
cp "$BUILD_DIR/libgosd.so" "$OUTPUT_DIR/libgosd-avx2.so"
chmod +x "$OUTPUT_DIR/libgosd-avx2.so"

SIZE=$(du -h "$OUTPUT_DIR/libgosd-avx2.so" | cut -f1)
echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║   Build complete!                             ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""
echo "  Output: $OUTPUT_DIR/libgosd-avx2.so ($SIZE)"
echo "  sd.cpp: $SD_CPP_VERSION"
echo ""
echo "  Next: docker compose down && make setup"
echo "        (entrypoint.sh will copy the rebuilt .so)"
echo ""
