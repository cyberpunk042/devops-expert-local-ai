#!/usr/bin/env bash
# =============================================================================
# Build the local-store backend from LocalAI source.
#
# The gallery version has a bug ("not implemented" on Load).
# This builds from source, installing all deps automatically.
#
# Usage: make build-local-store
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCALAI_VERSION="v4.0.0"
BUILD_DIR="/tmp/localai-local-store-build"
TARGET_DIR="$REPO_ROOT/backends/local-store"
LOCAL_BIN="$HOME/.local/bin"

if [ -t 1 ]; then
    GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; RESET='\033[0m'
else
    GREEN=''; RED=''; CYAN=''; RESET=''
fi

log_ok()   { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_fail() { echo -e "${RED}[FAIL]${RESET}  $*" >&2; }
log_info() { echo -e "${CYAN}[INFO]${RESET}  $*"; }

mkdir -p "$LOCAL_BIN"
export PATH="$HOME/.local/go/bin:$LOCAL_BIN:$HOME/.local/gopath/bin:$PATH"
export GOPATH="$HOME/.local/gopath"

# ── 1. Install Go if missing ────────────────────────────────────────────
if ! command -v go >/dev/null 2>&1; then
    log_info "Installing Go 1.24..."
    GO_TAR="go1.24.2.linux-amd64.tar.gz"
    [ -f "/tmp/$GO_TAR" ] || curl -sL "https://go.dev/dl/$GO_TAR" -o "/tmp/$GO_TAR"
    rm -rf "$HOME/.local/go"
    tar -C "$HOME/.local" -xzf "/tmp/$GO_TAR"
    log_ok "$(go version)"
fi

# ── 2. Install protoc if missing ────────────────────────────────────────
if ! command -v protoc >/dev/null 2>&1; then
    log_info "Installing protoc..."
    PROTOC_VER="28.3"
    PROTOC_ZIP="protoc-${PROTOC_VER}-linux-x86_64.zip"
    [ -f "/tmp/$PROTOC_ZIP" ] || curl -sL \
        "https://github.com/protocolbuffers/protobuf/releases/download/v${PROTOC_VER}/$PROTOC_ZIP" \
        -o "/tmp/$PROTOC_ZIP"
    unzip -qo "/tmp/$PROTOC_ZIP" -d "$HOME/.local" bin/protoc 'include/*'
    chmod +x "$HOME/.local/bin/protoc"
    log_ok "protoc $(protoc --version)"
fi

# ── 3. Install Go protoc plugins ────────────────────────────────────────
if ! command -v protoc-gen-go >/dev/null 2>&1; then
    log_info "Installing protoc-gen-go + protoc-gen-go-grpc..."
    go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@1958fcbe2ca8bd93af633f11e97d44e567e945af
    log_ok "protoc Go plugins installed"
fi

# ── 4. Download LocalAI source ──────────────────────────────────────────
if [ ! -d "$BUILD_DIR" ]; then
    log_info "Downloading LocalAI ${LOCALAI_VERSION} source..."
    mkdir -p "$BUILD_DIR"
    curl -sL "https://github.com/mudler/LocalAI/archive/refs/tags/${LOCALAI_VERSION}.tar.gz" \
        | tar xz -C "$BUILD_DIR" --strip-components=1
fi

# ── 5. Generate proto ───────────────────────────────────────────────────
log_info "Generating protobuf Go code..."
cd "$BUILD_DIR"
mkdir -p pkg/grpc/proto
protoc --go_out=. --go_opt="Mbackend/backend.proto=github.com/mudler/LocalAI/pkg/grpc/proto" \
       --go-grpc_out=. --go-grpc_opt="Mbackend/backend.proto=github.com/mudler/LocalAI/pkg/grpc/proto" \
       --go_opt=module=github.com/mudler/LocalAI \
       --go-grpc_opt=module=github.com/mudler/LocalAI \
       backend/backend.proto
log_ok "Proto generated at pkg/grpc/proto/"

# ── 6. Build local-store ────────────────────────────────────────────────
STORES_DIR="$BUILD_DIR/backend/go/local-store"
if [ ! -d "$STORES_DIR" ]; then
    log_fail "Stores backend source not found at $STORES_DIR"
    exit 1
fi

# Patch: Load() rejects non-empty model names with "not implemented".
# LocalAI passes the store name as the model, so we need to accept it.
log_info "Patching Load() to accept store names..."
sed -i 's/if opts.Model != "" {/if false {/' "$STORES_DIR/store.go"

log_info "Building local-store..."
cd "$BUILD_DIR"
CGO_ENABLED=0 go build -o "$BUILD_DIR/local-store-bin" "./backend/go/local-store"

# ── 7. Stage in backends/ ──────────────────────────────────────────────
mkdir -p "$TARGET_DIR"
cp "$BUILD_DIR/local-store-bin" "$TARGET_DIR/local-store"
chmod +x "$TARGET_DIR/local-store"
cat > "$TARGET_DIR/run.sh" << 'RUNEOF'
#!/bin/bash
set -ex
CURDIR=$(dirname "$(realpath $0)")
exec $CURDIR/local-store "$@"
RUNEOF
chmod +x "$TARGET_DIR/run.sh"

log_ok "Built and staged at $TARGET_DIR"
log_info "Next: docker compose restart localai"
