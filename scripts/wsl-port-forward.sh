#!/usr/bin/env bash
# =============================================================================
# WSL Port Forward — expose WSL ports to the LAN via Windows netsh portproxy
#
# Docker ports (like 8090) are auto-exposed by Windows because Docker binds
# on dual-stack [::]. But plain WSL processes (like aicp-agent on 9100) bind
# only on WSL's internal 172.x.x.x network and are NOT reachable from LAN.
#
# This script sets up Windows port forwarding so LAN machines can reach
# WSL services on the specified ports.
#
# Usage:
#   scripts/wsl-port-forward.sh              # forward port 9100 (default)
#   scripts/wsl-port-forward.sh 9100 9200    # forward multiple ports
#   scripts/wsl-port-forward.sh --remove     # remove all AICP port forwards
#   scripts/wsl-port-forward.sh --check      # check current forwards
# =============================================================================
set -euo pipefail

if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi

log_ok()   { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_fail() { echo -e "${RED}[FAIL]${RESET}  $*" >&2; }
log_info() { echo -e "        $*"; }
log_step() { echo -e "${CYAN}[STEP]${RESET}  $*"; }

# Detect WSL IP
WSL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

is_wsl() {
    grep -qi microsoft /proc/version 2>/dev/null
}

check_forwards() {
    echo -e "${BOLD}Current Windows port forwards:${RESET}"
    powershell.exe -NoProfile -Command "netsh interface portproxy show v4tov4" 2>/dev/null | tr -d '\r'
}

add_forward() {
    local port="$1"
    log_step "Forwarding LAN:$port → WSL($WSL_IP):$port"
    powershell.exe -NoProfile -Command \
        "Start-Process netsh -ArgumentList 'interface portproxy add v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$WSL_IP' -Verb RunAs -Wait" \
        2>/dev/null
    # Verify
    if powershell.exe -NoProfile -Command "netsh interface portproxy show v4tov4" 2>/dev/null | tr -d '\r' | grep -q "$port"; then
        log_ok "Port $port forwarded"
    else
        log_fail "Port $port forward may have failed (check UAC prompt)"
        log_info "Manual fallback (run in admin PowerShell):"
        log_info "  netsh interface portproxy add v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$WSL_IP"
    fi
}

remove_forwards() {
    for port in 9100 9200; do
        powershell.exe -NoProfile -Command \
            "Start-Process netsh -ArgumentList 'interface portproxy delete v4tov4 listenport=$port listenaddress=0.0.0.0' -Verb RunAs -Wait" \
            2>/dev/null || true
    done
    log_ok "AICP port forwards removed"
}

# ── Main ──────────────────────────────────────────────────────────────────────

if ! is_wsl; then
    echo "Not running in WSL — port forwarding not needed."
    echo "Services bound to 0.0.0.0 are already reachable from LAN."
    exit 0
fi

if [[ -z "$WSL_IP" ]]; then
    log_fail "Cannot detect WSL IP"
    exit 1
fi

case "${1:-}" in
    --check)
        check_forwards
        exit 0
        ;;
    --remove)
        remove_forwards
        exit 0
        ;;
    "")
        # Default: forward agent port
        add_forward 9100
        ;;
    *)
        # Forward all specified ports
        for port in "$@"; do
            add_forward "$port"
        done
        ;;
esac

echo ""
check_forwards
