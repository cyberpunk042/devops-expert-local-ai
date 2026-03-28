#!/usr/bin/env bash
# =============================================================================
# Extract LocalAI backends from upstream OCI images.
#
# Backends are extracted once and staged in backends/ for the Docker build.
# The entrypoint.sh copies them into the /backends volume at container start
# (the base image declares /backends as a Docker volume).
#
# Usage:
#   bash scripts/extract-backend.sh            # extract all (idempotent)
#   bash scripts/extract-backend.sh --force    # re-extract even if exists
#   bash scripts/extract-backend.sh --only whisper  # extract one backend
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Backend catalog ──────────────────────────────────────────────────────────
# Each backend: IMAGE_TAG → local directory name
declare -A BACKEND_IMAGES=(
    [cuda12-llama-cpp]="quay.io/go-skynet/local-ai-backends:latest-gpu-nvidia-cuda-12-llama-cpp"
    [whisper]="quay.io/go-skynet/local-ai-backends:latest-gpu-nvidia-cuda-12-whisper"
    [piper]="quay.io/go-skynet/local-ai-backends:latest-piper"
)

# Files that indicate a backend is already extracted (idempotency check)
declare -A BACKEND_MARKER=(
    [cuda12-llama-cpp]="llama-cpp-grpc"
    [whisper]="whisper"
    [piper]="piper"
)

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
ONLY=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) FORCE=1; shift ;;
        --only)  ONLY="$2"; shift 2 ;;
        *)       die "Unknown argument: $1" ;;
    esac
done

command -v docker >/dev/null 2>&1 || die "docker is required but not found"

# ── Extract a single backend ─────────────────────────────────────────────────
extract_backend() {
    local name="$1"
    local image="${BACKEND_IMAGES[$name]}"
    local marker="${BACKEND_MARKER[$name]}"
    local backend_dir="$REPO_ROOT/backends/$name"
    local container_name="aicp-extract-$name"
    local tmp_dir="/tmp/aicp-backend-$name"

    # Idempotency check
    if [[ -f "$backend_dir/$marker" && "$FORCE" -eq 0 ]]; then
        log_skip "backends/$name/ already extracted (use --force to re-extract)"
        return 0
    fi

    log_step "Pulling $name backend: $image"
    docker pull "$image"

    log_step "Extracting $name backend"
    docker rm "$container_name" 2>/dev/null || true
    rm -rf "$tmp_dir"
    docker create --name "$container_name" --entrypoint /bin/true "$image" >/dev/null
    docker cp "$container_name":/ "$tmp_dir"

    # Install to backends directory
    rm -rf "$backend_dir"
    mkdir -p "$backend_dir"

    # Copy everything except Docker metadata dirs
    for item in "$tmp_dir"/*; do
        base=$(basename "$item")
        case "$base" in
            dev|etc|proc|sys|.dockerenv) continue ;;
            *) cp -r "$item" "$backend_dir/" ;;
        esac
    done

    # Make binaries executable
    find "$backend_dir" -maxdepth 1 -type f -name "*.sh" -exec chmod +x {} +
    find "$backend_dir" -maxdepth 1 -type f ! -name "*.so" ! -name "*.so.*" ! -name "*.json" \
        ! -name "*.yaml" ! -name "*.txt" -exec chmod +x {} + 2>/dev/null || true

    # Cleanup
    docker rm "$container_name" >/dev/null
    rm -rf "$tmp_dir"

    local file_count dir_size
    file_count=$(find "$backend_dir" -type f | wc -l)
    dir_size=$(du -sh "$backend_dir" | cut -f1)
    log_ok "backends/$name/ extracted: $file_count files, $dir_size"
}

# ── Main ──────────────────────────────────────────────────────────────────────
if [[ -n "$ONLY" ]]; then
    [[ -v BACKEND_IMAGES[$ONLY] ]] || die "Unknown backend: $ONLY. Available: ${!BACKEND_IMAGES[*]}"
    extract_backend "$ONLY"
else
    for name in cuda12-llama-cpp whisper piper; do
        extract_backend "$name"
    done
fi

log_ok "All backends ready for: docker compose build"
