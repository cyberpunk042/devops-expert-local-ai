#!/usr/bin/env bash
# Install NVIDIA Container Toolkit so Docker can pass through the GPU to LocalAI.
# Supports Debian/Ubuntu on native Linux and WSL2.
# Run via: make install-nvidia-toolkit
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log_step() { echo -e "${CYAN}[STEP]${RESET}  $*"; }
log_ok()   { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_fail() { echo -e "${RED}[FAIL]${RESET}  $*" >&2; }
log_info() { echo -e "        $*"; }

die() { log_fail "$*"; exit 1; }

# ── Already installed? ────────────────────────────────────────────────────────
if docker run --rm --gpus all --pid=host ubuntu:22.04 \
    nvidia-smi -L >/dev/null 2>&1; then
    log_ok "GPU passthrough to Docker already works — nothing to do."
    echo ""
    echo "Run 'make setup-force' to regenerate model YAML with GPU backend."
    exit 0
fi

# ── GPU on host? ──────────────────────────────────────────────────────────────
if ! nvidia-smi >/dev/null 2>&1; then
    die "nvidia-smi not found. No NVIDIA GPU detected — toolkit not needed."
fi

# ── Detect environment ────────────────────────────────────────────────────────
IS_WSL=0
grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=1

# ── Apt available? ────────────────────────────────────────────────────────────
command -v apt-get >/dev/null 2>&1 || die "apt-get not found. Install manually: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html"

echo ""
echo -e "${BOLD}══════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Installing NVIDIA Container Toolkit${RESET}"
echo -e "${BOLD}══════════════════════════════════════════${RESET}"
echo ""
echo "  This will run sudo commands to install nvidia-container-toolkit"
echo "  and configure the Docker runtime. You will be prompted for your"
echo "  sudo password."
echo ""
read -r -p "  Continue? [y/N] " confirm
[[ "${confirm,,}" == "y" ]] || { echo "Aborted."; exit 0; }
echo ""

# ── Step 1: Add NVIDIA GPG key ────────────────────────────────────────────────
log_step "Adding NVIDIA Container Toolkit GPG key"
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
log_ok "GPG key added"

# ── Step 2: Add apt repo ──────────────────────────────────────────────────────
log_step "Adding NVIDIA Container Toolkit apt repository"
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
log_ok "Repository added"

# ── Step 3: Install ───────────────────────────────────────────────────────────
log_step "Installing nvidia-container-toolkit"
sudo apt-get update -q
sudo apt-get install -y nvidia-container-toolkit
log_ok "nvidia-container-toolkit installed"

# ── Step 4: Configure Docker runtime ─────────────────────────────────────────
log_step "Configuring Docker runtime (nvidia-ctk)"
sudo nvidia-ctk runtime configure --runtime=docker
log_ok "Docker runtime configured"

# ── Step 5: Restart Docker ────────────────────────────────────────────────────
log_step "Restarting Docker daemon"
if [[ "$IS_WSL" -eq 1 ]]; then
    # systemctl may not be available in WSL2 — fall back to service
    if sudo service docker restart 2>/dev/null; then
        log_ok "Docker restarted (WSL2: service docker restart)"
    else
        log_warn "Could not restart Docker automatically on WSL2."
        log_info "Run manually: sudo service docker restart"
        log_info "Or restart your WSL2 instance: wsl --shutdown  (from Windows)"
    fi
else
    sudo systemctl restart docker
    log_ok "Docker restarted"
fi

# ── Step 6: Verify ────────────────────────────────────────────────────────────
log_step "Verifying GPU passthrough"
sleep 2
if docker run --rm --gpus all --pid=host nvidia/cuda:12.0-base-ubuntu22.04 \
    nvidia-smi -L 2>/dev/null; then
    log_ok "GPU passthrough to Docker works!"
else
    log_warn "Verification failed. Docker may need a full restart."
    log_info "On WSL2: close all WSL terminals and run 'wsl --shutdown' from Windows PowerShell."
    log_info "Then re-run: make check-prereqs"
    exit 1
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  Next steps:${RESET}"
echo "    make local-down          # stop current CPU-mode container"
echo "    make setup-force         # rebuild image + regenerate model YAML with cuda12-llama-cpp"
echo "    make check               # verify everything including GPU"
echo "    make test-all            # integration tests should now pass"
echo ""
