#!/usr/bin/env bash
# =============================================================================
# AICP — One-command setup script
# Usage:
#   make setup                  Full setup: venv + deps + model + LocalAI + verify
#   make setup-force            Same but re-runs every step even if already done
#   make setup-claude-only      venv + deps + verify Claude CLI (no LocalAI)
#   make setup-local-only       Model + LocalAI only (assumes venv exists)
#   make setup-low-vram         Force phi3-mini model for <6GB VRAM machines
#   make check-prereqs          Environment checks only, no changes
# =============================================================================
set -euo pipefail

# ── Colors (only if stdout is a terminal) ─────────────────────────────────────
if [ -t 1 ]; then
    RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED=''; YELLOW=''; GREEN=''; CYAN=''; BOLD=''; RESET=''
fi

log_step()  { echo -e "${CYAN}[STEP]${RESET}  $*"; }
log_skip()  { echo -e "${YELLOW}[SKIP]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${RESET}  $*" >&2; }
log_info()  { echo -e "        $*"; }
log_head()  { echo -e "\n${BOLD}── $* ──${RESET}"; }

die() { log_fail "$*"; exit 1; }

# ── Arg parsing ───────────────────────────────────────────────────────────────
MODE="full"           # full | claude | local | check-only
FORCE=0
MODEL_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)       MODE="$2"; shift 2 ;;
        --force)      FORCE=1; shift ;;
        --model)      MODEL_OVERRIDE="$2"; shift 2 ;;
        *)            die "Unknown argument: $1" ;;
    esac
done

# ── Repo root ─────────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── Model catalog (keep in sync with scripts/models-catalog.sh) ───────────────
# Each entry: ALIAS → GGUF_FILENAME / MIN_VRAM_MB (MiB) / DOWNLOAD_URL
CATALOG_ALIASES=("phi3-mini" "gemma-2b" "hermes" "mistral-7b" "codellama-7b" "hermes-13b" "codellama-13b")
declare -A MODEL_GGUF=(
    [phi3-mini]="Phi-3-mini-4k-instruct-q4.gguf"
    [gemma-2b]="gemma-2b-it.gguf"
    [hermes]="hermes-2-pro-mistral-7b.Q4_K_M.gguf"
    [mistral-7b]="mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    [codellama-7b]="codellama-7b-instruct.Q4_K_M.gguf"
    [hermes-13b]="nous-hermes-2-solar-10.7b.Q4_K_M.gguf"
    [codellama-13b]="codellama-13b-instruct.Q4_K_M.gguf"
)
declare -A MODEL_URL=(
    [phi3-mini]="https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf"
    [gemma-2b]="https://huggingface.co/google/gemma-2b-it-GGUF/resolve/main/gemma-2b-it.gguf"
    [hermes]="https://huggingface.co/NousResearch/Hermes-2-Pro-Mistral-7B-GGUF/resolve/main/Hermes-2-Pro-Mistral-7B.Q4_K_M.gguf"
    [mistral-7b]="https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    [codellama-7b]="https://huggingface.co/TheBloke/CodeLlama-7B-Instruct-GGUF/resolve/main/codellama-7b-instruct.Q4_K_M.gguf"
    [hermes-13b]="https://huggingface.co/TheBloke/Nous-Hermes-2-SOLAR-10.7B-GGUF/resolve/main/nous-hermes-2-solar-10.7b.Q4_K_M.gguf"
    [codellama-13b]="https://huggingface.co/TheBloke/CodeLlama-13B-Instruct-GGUF/resolve/main/codellama-13b-instruct.Q4_K_M.gguf"
)
# Minimum free VRAM (MiB) needed for comfortable use
declare -A MODEL_MIN_VRAM=(
    [phi3-mini]=3000
    [gemma-2b]=2000
    [hermes]=6000
    [mistral-7b]=6000
    [codellama-7b]=6000
    [hermes-13b]=10000
    [codellama-13b]=10000
)

LOCALAI_PORT="${PORT:-8090}"
STEPS_DONE=()
STEPS_SKIPPED=()
GPU_DOCKER_OK=0  # set to 1 by check_nvidia_toolkit if passthrough works

# =============================================================================
# SECTION 1 — Environment checks
# =============================================================================
log_head "Checking prerequisites"

check_python() {
    log_step "Python 3.8+"
    PYTHON=$(which python3 2>/dev/null) || die "python3 not found. Install Python 3.8+."
    PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
    if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 8 ]]; then
        die "Python 3.8+ required, found $PY_VERSION"
    fi
    log_ok "Python $PY_VERSION at $PYTHON"
}

check_docker() {
    if [[ "$MODE" == "claude" || "$MODE" == "check-only" ]]; then return; fi
    log_step "Docker + Compose plugin"
    docker version >/dev/null 2>&1 || die "Docker not found. Install Docker: https://docs.docker.com/get-docker/"
    docker compose version >/dev/null 2>&1 || die "Docker Compose plugin not found. Install it alongside Docker."
    log_ok "$(docker version --format 'Docker {{.Server.Version}}')"
}

check_gpu() {
    if [[ "$MODE" == "claude" || "$MODE" == "check-only" ]]; then return; fi
    log_step "NVIDIA GPU"
    VRAM_MB=0
    if VRAM_RAW=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' '); then
        VRAM_MB="${VRAM_RAW:-0}"
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | xargs)
        log_ok "GPU: $GPU_NAME (${VRAM_MB} MiB VRAM)"
    else
        log_warn "nvidia-smi not found — will use CPU mode (slow inference)"
        VRAM_MB=0
    fi
}

check_nvidia_toolkit() {
    if [[ "$MODE" == "claude" || "$MODE" == "check-only" || "$VRAM_MB" -eq 0 ]]; then return; fi
    log_step "NVIDIA Container Toolkit (GPU passthrough to Docker)"
    if docker run --rm --gpus all --pid=host ubuntu:22.04 \
        nvidia-smi -L >/dev/null 2>&1; then
        log_ok "GPU passthrough to Docker works"
        GPU_DOCKER_OK=1
    else
        log_warn "GPU passthrough to Docker NOT working."
        log_info "Install NVIDIA Container Toolkit:"
        log_info "  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"
        log_info "  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \\"
        log_info "    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \\"
        log_info "    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list"
        log_info "  sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit"
        log_info "  sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
        log_info "LocalAI will start but may run on CPU only."
    fi
}

check_python
check_docker
check_gpu
check_nvidia_toolkit

if [[ "$MODE" == "check-only" ]]; then
    log_ok "Prerequisite check complete."
    exit 0
fi

# =============================================================================
# SECTION 2 — Python venv + dependencies
# =============================================================================
if [[ "$MODE" == "full" || "$MODE" == "claude" ]]; then
    log_head "Python environment"

    if [[ -d .venv && "$FORCE" -eq 0 ]]; then
        log_skip "Virtual environment (.venv exists)"
        STEPS_SKIPPED+=("venv")
    else
        log_step "Creating virtual environment"
        $PYTHON -m venv .venv
        log_ok ".venv created"
        STEPS_DONE+=("venv")
    fi

    VENV_PIP=".venv/bin/pip"
    VENV_PYTHON=".venv/bin/python"

    # Always ensure deps are current (fast if nothing changed)
    log_step "Installing Python dependencies"
    "$VENV_PIP" install --upgrade pip -q
    "$VENV_PIP" install -e ".[dev]" -q
    log_ok "Dependencies installed (aicp, httpx, rich, pyyaml, pytest, ruff)"
    STEPS_DONE+=("deps")
else
    # local mode — assume .venv exists
    [[ -d .venv ]] || die "No .venv found. Run 'make setup' first (not 'make setup-local-only')."
    VENV_PIP=".venv/bin/pip"
    VENV_PYTHON=".venv/bin/python"
fi

if [[ "$MODE" == "claude" ]]; then
    log_head "Claude CLI check"
    if CLAUDE_PATH=$(which claude 2>/dev/null); then
        log_ok "claude CLI found at $CLAUDE_PATH"
    else
        log_warn "claude CLI not found in PATH."
        log_info "Install via: pip install anthropic  or  follow https://docs.anthropic.com/en/docs/claude-code"
    fi
    log_head "Verification"
    .venv/bin/aicp --check || true
    exit 0
fi

# =============================================================================
# SECTION 3 — Model selection
# =============================================================================
log_head "Model selection"

# Auto-select based on VRAM, unless overridden
if [[ -n "$MODEL_OVERRIDE" ]]; then
    MODEL_ALIAS="$MODEL_OVERRIDE"
    [[ -v MODEL_GGUF[$MODEL_ALIAS] ]] || die "Unknown model: $MODEL_ALIAS. Choose from: ${CATALOG_ALIASES[*]}"
    log_info "Using model override: $MODEL_ALIAS"
    [[ -v MODEL_GGUF[$MODEL_ALIAS] ]] || {
        log_fail "Unknown model: $MODEL_ALIAS"
        log_info "Available: ${CATALOG_ALIASES[*]}"
        log_info "See full catalog: make model-list-remote"
        exit 1
    }
elif [[ "$VRAM_MB" -ge "${MODEL_MIN_VRAM[hermes-13b]}" ]]; then
    MODEL_ALIAS="hermes-13b"
    log_info "Auto-selected: hermes-13b (${VRAM_MB} MiB VRAM, best quality available)"
elif [[ "$VRAM_MB" -ge "${MODEL_MIN_VRAM[hermes]}" ]]; then
    MODEL_ALIAS="hermes"
    log_info "Auto-selected: hermes (${VRAM_MB} MiB VRAM, good balance of speed and quality)"
elif [[ "$VRAM_MB" -ge "${MODEL_MIN_VRAM[phi3-mini]}" ]]; then
    MODEL_ALIAS="phi3-mini"
    log_info "Auto-selected: phi3-mini (${VRAM_MB} MiB VRAM, fast 3B model)"
else
    MODEL_ALIAS="gemma-2b"
    log_info "Auto-selected: gemma-2b (${VRAM_MB} MiB VRAM or CPU, smallest available)"
fi

GGUF_FILENAME="${MODEL_GGUF[$MODEL_ALIAS]}"
DOWNLOAD_URL="${MODEL_URL[$MODEL_ALIAS]}"
log_ok "Model: $MODEL_ALIAS  →  models/$GGUF_FILENAME"

# =============================================================================
# SECTION 4 — Model download
# =============================================================================
log_head "Model download"

mkdir -p models

if [[ -f "models/$GGUF_FILENAME" && "$FORCE" -eq 0 ]]; then
    FILESIZE=$(du -sh "models/$GGUF_FILENAME" | cut -f1)
    log_skip "models/$GGUF_FILENAME already present ($FILESIZE)"
    STEPS_SKIPPED+=("model-download")
else
    log_step "Downloading models/$GGUF_FILENAME"
    log_info "Source: $DOWNLOAD_URL"
    log_info "This may take several minutes depending on your connection (~4-5 GB)."
    log_info "Download is resumable — safe to cancel and re-run."
    # -C - resumes partial downloads; --progress-bar shows a clean progress bar
    curl -L --progress-bar -C - -o "models/$GGUF_FILENAME" "$DOWNLOAD_URL"
    [[ -s "models/$GGUF_FILENAME" ]] || die "Download failed or produced empty file."
    FILESIZE=$(du -sh "models/$GGUF_FILENAME" | cut -f1)
    log_ok "Downloaded models/$GGUF_FILENAME ($FILESIZE)"
    STEPS_DONE+=("model-download")
fi

# ── Supplementary models (embedding + code) ─────────────────────────────────
EMBED_GGUF="nomic-embed-text-v1.5.Q8_0.gguf"
EMBED_URL="https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q8_0.gguf"
CODE_GGUF="codellama-7b-instruct.Q4_K_M.gguf"
CODE_URL="https://huggingface.co/TheBloke/CodeLlama-7B-Instruct-GGUF/resolve/main/codellama-7b-instruct.Q4_K_M.gguf"

if [[ -f "models/$EMBED_GGUF" && "$FORCE" -eq 0 ]]; then
    log_skip "Embedding model already present: $EMBED_GGUF"
else
    log_step "Downloading embedding model: $EMBED_GGUF (~140 MB)"
    curl -L --progress-bar -C - -o "models/$EMBED_GGUF" "$EMBED_URL"
    [[ -s "models/$EMBED_GGUF" ]] || die "Embedding model download failed."
    log_ok "Downloaded embedding model: $EMBED_GGUF"
fi

if [[ -f "models/$CODE_GGUF" && "$FORCE" -eq 0 ]]; then
    log_skip "Code model already present: $CODE_GGUF"
else
    log_step "Downloading code model: $CODE_GGUF (~3.8 GB)"
    curl -L --progress-bar -C - -o "models/$CODE_GGUF" "$CODE_URL"
    [[ -s "models/$CODE_GGUF" ]] || die "Code model download failed."
    log_ok "Downloaded code model: $CODE_GGUF"
fi

# =============================================================================
# SECTION 5 — Generate LocalAI model YAML
# =============================================================================
log_head "LocalAI model configuration"

if [[ -f "models/$MODEL_ALIAS.yaml" && "$FORCE" -eq 0 ]]; then
    log_skip "models/$MODEL_ALIAS.yaml already exists"
    STEPS_SKIPPED+=("model-yaml")
else
    log_step "Generating models/$MODEL_ALIAS.yaml (auto-detecting optimal GPU config)"
    "$VENV_PYTHON" - <<PYEOF
from aicp.core.gpu import detect_gpus, calculate_optimal_config, generate_model_yaml
from pathlib import Path

gpus = detect_gpus()
gguf_path = Path("models/${GGUF_FILENAME}")
cfg = calculate_optimal_config(gguf_path, gpus)
docker_gpu_ok = "${GPU_DOCKER_OK}" == "1"
backend = "cuda12-llama-cpp" if (gpus and docker_gpu_ok) else "llama-cpp"
yaml_str = generate_model_yaml("${MODEL_ALIAS}", "${GGUF_FILENAME}", cfg, backend)
Path("models/${MODEL_ALIAS}.yaml").write_text(yaml_str)
print(f"  gpu_layers:   {cfg['gpu_layers']} ({'full GPU offload' if cfg['gpu_layers'] >= 99 else 'partial' if cfg['gpu_layers'] > 0 else 'CPU only'})")
print(f"  context_size: {cfg['context_size']}")
print(f"  threads:      {cfg['threads']}")
print(f"  backend:      {backend}")
PYEOF
    log_ok "models/$MODEL_ALIAS.yaml written"
    STEPS_DONE+=("model-yaml")
fi

# ── Activate supplementary model YAMLs if their GGUF files exist ─────────────
if [[ -f "models/$EMBED_GGUF" && ! -f "models/nomic-embed.yaml" ]]; then
    log_step "Activating nomic-embed model config"
    # nomic-embed.yaml is committed to the repo — should already be in models/
fi

if [[ -f "models/$CODE_GGUF" ]]; then
    if [[ ! -f "models/codellama.yaml" ]]; then
        log_step "Activating codellama model config"
        cp "config/codellama.yaml.template" "models/codellama.yaml"
        log_ok "models/codellama.yaml activated"
    else
        log_skip "models/codellama.yaml already exists"
    fi
fi

# =============================================================================
# SECTION 6 — Sync config/default.yaml model name
# =============================================================================
CURRENT_MODEL=$(grep -E '^\s+model:' config/default.yaml | head -1 | awk '{print $2}' | tr -d '"')
if [[ "$CURRENT_MODEL" != "$MODEL_ALIAS" ]]; then
    log_step "Updating config/default.yaml: model '$CURRENT_MODEL' → '$MODEL_ALIAS'"
    "$VENV_PYTHON" - <<PYEOF
import yaml
path = "config/default.yaml"
with open(path) as f:
    cfg = yaml.safe_load(f)
cfg["backends"]["local"]["model"] = "${MODEL_ALIAS}"
with open(path, "w") as f:
    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
PYEOF
    log_ok "config/default.yaml updated"
    STEPS_DONE+=("config-update")
else
    log_skip "config/default.yaml already uses model '$MODEL_ALIAS'"
fi

# =============================================================================
# SECTION 7 — Write Docker .env (THREADS, log level)
# =============================================================================
if [[ -f .env && "$FORCE" -eq 0 ]]; then
    # .env exists — only add THREADS if missing (don't overwrite user customizations)
    if ! grep -q '^THREADS=' .env 2>/dev/null; then
        THREAD_COUNT=$(( $(nproc) > 1 ? $(nproc) - 1 : 1 ))
        echo "THREADS=$THREAD_COUNT" >> .env
        log_ok "Added THREADS=$THREAD_COUNT to existing .env"
    else
        log_skip ".env already exists with THREADS set"
    fi
else
    log_step "Writing .env (Docker Compose + AICP environment)"
    THREAD_COUNT=$(( $(nproc) > 1 ? $(nproc) - 1 : 1 ))
    cat > .env <<ENVEOF
# Auto-generated by scripts/setup.sh — edit as needed.
# See .env.example for full reference.

# ── Docker Compose / LocalAI ──────────────────────────────────────────────────
THREADS=${THREAD_COUNT}
LOCALAI_LOG_LEVEL=info

# ── AICP defaults ─────────────────────────────────────────────────────────────
AICP_DEFAULT_MODE=think
AICP_DEFAULT_BACKEND=local
ENVEOF
    log_ok ".env written (THREADS=$THREAD_COUNT)"
    STEPS_DONE+=("dotenv")
fi

# =============================================================================
# SECTION 8 — Build and start LocalAI
# =============================================================================
log_head "LocalAI container"

# Ensure backend is extracted before building the image
if [[ ! -f "$REPO_ROOT/backends/cuda12-llama-cpp/run.sh" ]]; then
    log_step "Extracting CUDA backend from quay.io (first time only)..."
    bash "$REPO_ROOT/scripts/extract-backend.sh"
    STEPS_DONE+=("backend-extract")
else
    log_skip "Backend already extracted at backends/cuda12-llama-cpp/"
fi

# Check if image already exists
IMAGE_EXISTS=0
docker image inspect aicp-localai:latest >/dev/null 2>&1 && IMAGE_EXISTS=1

if [[ "$IMAGE_EXISTS" -eq 1 && "$FORCE" -eq 0 ]]; then
    log_skip "Docker image aicp-localai:latest already built"
    STEPS_SKIPPED+=("docker-build")
else
    log_step "Building Docker image (aicp-localai:latest)"
    log_info "This pulls the LocalAI base image on first run (~2-5 GB)."
    docker compose build
    log_ok "Docker image built"
    STEPS_DONE+=("docker-build")
fi

# Check if already running
CONTAINER_RUNNING=0
docker compose ps --filter "status=running" 2>/dev/null | grep -q "localai" && CONTAINER_RUNNING=1

if [[ "$CONTAINER_RUNNING" -eq 1 && "$FORCE" -eq 0 ]]; then
    log_skip "LocalAI container already running"
    STEPS_SKIPPED+=("docker-up")
else
    log_step "Starting LocalAI container"
    docker compose up -d
    log_ok "Container started"
    STEPS_DONE+=("docker-up")
fi

# =============================================================================
# SECTION 9 — Wait for model readiness (not just API readiness)
# =============================================================================
log_head "Waiting for LocalAI to load model '$MODEL_ALIAS'"
log_info "Model GGUF loading into VRAM can take 15–60 seconds. Polling up to 2 minutes..."

MAX_WAIT=120
INTERVAL=5
ELAPSED=0
READY=0

while [[ "$ELAPSED" -lt "$MAX_WAIT" ]]; do
    if "$VENV_PYTHON" - <<PYEOF 2>/dev/null
import sys, json
try:
    import httpx
    resp = httpx.get("http://localhost:${LOCALAI_PORT}/v1/models", timeout=3.0)
    data = resp.json()
    ids = [m["id"] for m in data.get("data", [])]
    sys.exit(0 if "${MODEL_ALIAS}" in ids else 1)
except Exception:
    sys.exit(1)
PYEOF
    then
        READY=1
        break
    fi
    printf "        waiting... (%ds elapsed)\r" "$ELAPSED"
    sleep "$INTERVAL"
    ELAPSED=$(( ELAPSED + INTERVAL ))
done

echo ""  # clear the \r line

if [[ "$READY" -eq 1 ]]; then
    log_ok "LocalAI is serving model '$MODEL_ALIAS' at http://localhost:${LOCALAI_PORT}"
    STEPS_DONE+=("localai-ready")
else
    log_warn "LocalAI did not report model '$MODEL_ALIAS' within ${MAX_WAIT}s."
    log_info "This can happen on first boot while the model initializes."
    log_info "Check logs with: make local-logs"
    log_info "Re-run readiness check with: make check"
fi

# =============================================================================
# SECTION 10 — Verify
# =============================================================================
log_head "Verification"
.venv/bin/aicp --check || true   # non-fatal: check prints its own output

# =============================================================================
# SECTION 11 — Summary
# =============================================================================
echo ""
echo -e "${BOLD}══════════════════════════════════════════${RESET}"
echo -e "${BOLD}  AICP Setup Summary${RESET}"
echo -e "${BOLD}══════════════════════════════════════════${RESET}"

if [[ ${#STEPS_DONE[@]} -gt 0 ]]; then
    echo -e "${GREEN}  Completed:${RESET}"
    for s in "${STEPS_DONE[@]}"; do echo "    ✓ $s"; done
fi
if [[ ${#STEPS_SKIPPED[@]} -gt 0 ]]; then
    echo -e "${YELLOW}  Skipped (already done):${RESET}"
    for s in "${STEPS_SKIPPED[@]}"; do echo "    - $s"; done
fi

if [[ "$GPU_DOCKER_OK" -eq 0 && "$VRAM_MB" -gt 0 ]]; then
    echo -e "${YELLOW}  ⚠ GPU passthrough to Docker is NOT working.${RESET}"
    echo -e "${YELLOW}    LocalAI is running on CPU — inference will be slow.${RESET}"
    echo ""
    echo -e "${BOLD}  → To enable GPU acceleration (one command):${RESET}"
    echo "    make install-nvidia-toolkit"
    echo "    make setup-force          # rebuild with cuda backend after toolkit install"
    echo ""
fi

echo ""
echo -e "${BOLD}  Quick start:${RESET}"
echo "    source .venv/bin/activate"
echo "    aicp 'What does this project do?'        # think mode, local"
echo "    aicp -i                                   # interactive chat"
echo "    aicp 'refactor X' -m edit -b claude      # Claude Code for complex tasks"
echo ""
echo -e "${BOLD}  Useful commands:${RESET}"
echo "    make check          verify everything is working"
echo "    make local-logs     stream LocalAI logs"
echo "    make local-down     stop LocalAI"
echo "    make update         git pull + reinstall deps"
echo ""
