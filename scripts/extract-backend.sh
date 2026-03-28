#!/usr/bin/env bash
# =============================================================================
# Extract the CUDA 12 llama-cpp backend from the upstream OCI image.
#
# This is the proven method to get a working GPU backend without the bloated
# AIO image. The backend is extracted once and baked into the Docker image
# via COPY in Dockerfile.localai.
#
# Usage:
#   bash scripts/extract-backend.sh            # idempotent — skips if exists
#   bash scripts/extract-backend.sh --force    # re-extract even if exists
# =============================================================================
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
BACKEND_IMAGE="quay.io/go-skynet/local-ai-backends:latest-gpu-nvidia-cuda-12-llama-cpp"
CONTAINER_NAME="aicp-backend-extract"
TMP_DIR="/tmp/aicp-backend-raw"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backends/cuda12-llama-cpp"

# ── Colors ────────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi

log_step()  { echo -e "${CYAN}[STEP]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_skip()  { echo -e "${YELLOW}[SKIP]${RESET}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${RESET}  $*" >&2; }
die()       { log_fail "$*"; exit 1; }

# ── Args ──────────────────────────────────────────────────────────────────────
FORCE=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) FORCE=1; shift ;;
        *)       die "Unknown argument: $1" ;;
    esac
done

# ── Idempotency check ────────────────────────────────────────────────────────
if [[ -f "$BACKEND_DIR/run.sh" && -f "$BACKEND_DIR/llama-cpp-grpc" && "$FORCE" -eq 0 ]]; then
    log_skip "Backend already exists at $BACKEND_DIR (use --force to re-extract)"
    exit 0
fi

# ── Prerequisites ─────────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || die "docker is required but not found"

# ── Cleanup from previous failed runs ────────────────────────────────────────
docker rm "$CONTAINER_NAME" 2>/dev/null || true
rm -rf "$TMP_DIR"

# ── Step 1: Pull the backend image ───────────────────────────────────────────
log_step "Pulling backend image: $BACKEND_IMAGE"
docker pull "$BACKEND_IMAGE"

# ── Step 2: Create temporary container and extract filesystem ─────────────────
log_step "Extracting backend from OCI image"
docker create --name "$CONTAINER_NAME" --entrypoint /bin/true "$BACKEND_IMAGE" >/dev/null
docker cp "$CONTAINER_NAME":/ "$TMP_DIR"

# ── Step 3: Copy backend files to target directory ────────────────────────────
log_step "Installing backend to $BACKEND_DIR"
rm -rf "$BACKEND_DIR"
mkdir -p "$BACKEND_DIR/lib"

# All binaries (avx, avx2, avx512, fallback, grpc, rpc-server) + run.sh
for f in "$TMP_DIR"/llama-cpp-* "$TMP_DIR"/run.sh; do
    [ -f "$f" ] && cp "$f" "$BACKEND_DIR/"
done

# CUDA runtime libraries
cp -r "$TMP_DIR/lib/"*         "$BACKEND_DIR/lib/"

# Make all binaries executable
chmod +x "$BACKEND_DIR"/llama-cpp-* "$BACKEND_DIR/run.sh"

# ── Step 4: Cleanup ──────────────────────────────────────────────────────────
log_step "Cleaning up"
docker rm "$CONTAINER_NAME" >/dev/null
rm -rf "$TMP_DIR"

# ── Done ──────────────────────────────────────────────────────────────────────
FILE_COUNT=$(find "$BACKEND_DIR" -type f | wc -l)
DIR_SIZE=$(du -sh "$BACKEND_DIR" | cut -f1)
log_ok "Backend extracted: $FILE_COUNT files, $DIR_SIZE total"
log_ok "Ready for: docker compose build"
