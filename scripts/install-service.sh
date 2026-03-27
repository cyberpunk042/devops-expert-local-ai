#!/usr/bin/env bash
# =============================================================================
# AICP — Install aicp-agent as a systemd user service
# Runs without root. Uses `systemctl --user` (loginctl linger for auto-start).
# Usage:
#   make install-service       install and enable
#   make uninstall-service     disable and remove
# =============================================================================
set -euo pipefail

ACTION="${1:-install}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="aicp-agent"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT_FILE="$UNIT_DIR/$SERVICE_NAME.service"

if [ -t 1 ]; then
    GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; RESET='\033[0m'
else
    GREEN=''; YELLOW=''; RED=''; RESET=''
fi

# ── Uninstall ─────────────────────────────────────────────────────────────────
if [[ "$ACTION" == "uninstall" ]]; then
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$UNIT_FILE"
    systemctl --user daemon-reload
    echo -e "${GREEN}[OK]${RESET}  aicp-agent service removed."
    exit 0
fi

# ── Install ───────────────────────────────────────────────────────────────────
[[ -d .venv ]] || { echo -e "${RED}[FAIL]${RESET} .venv not found. Run 'make setup' first."; exit 1; }
VENV_AICP_AGENT="$REPO_ROOT/.venv/bin/aicp-agent"
[[ -f "$VENV_AICP_AGENT" ]] || { echo -e "${RED}[FAIL]${RESET} aicp-agent not found in .venv. Run 'pip install -e .[dev]'."; exit 1; }

mkdir -p "$UNIT_DIR"

# Stamp the real repo path into the service template
sed "s|REPO_ROOT|$REPO_ROOT|g" "$REPO_ROOT/scripts/aicp-agent.service" > "$UNIT_FILE"

systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user start "$SERVICE_NAME"

echo -e "${GREEN}[OK]${RESET}  aicp-agent service installed and started."
echo ""
echo "  Check status:   systemctl --user status $SERVICE_NAME"
echo "  View logs:      journalctl --user -u $SERVICE_NAME -f"
echo "  Stop:           systemctl --user stop $SERVICE_NAME"
echo "  Uninstall:      make uninstall-service"
echo ""

# Enable linger so the service starts at boot without login
if command -v loginctl &>/dev/null; then
    if loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=no"; then
        echo -e "${YELLOW}[WARN]${RESET}  Linger is disabled. The service will stop when you log out."
        echo "  Enable auto-start at boot: sudo loginctl enable-linger $USER"
    else
        echo -e "${GREEN}[OK]${RESET}  Linger enabled — service will auto-start at boot."
    fi
fi
