#!/bin/bash
# install-statusline.sh — IaC for Claude Code statusline
# Installs the AICP fleet statusline: context %, model, cost, rate limits.
# Dependencies: jq, git, Claude Code
# Idempotent: safe to re-run.
set -euo pipefail

STATUSLINE_PATH="$HOME/.claude/statusline.sh"
SETTINGS_PATH="$HOME/.claude/settings.json"

echo "=== AICP Statusline Installer ==="

# --- Pre-flight checks ---

if [ ! -d "$HOME/.claude" ]; then
  echo "ERROR: ~/.claude directory not found. Is Claude Code installed?"
  exit 1
fi

# Ensure jq is available (install if missing, prefer non-sudo methods)
if ! command -v jq &>/dev/null; then
  echo "[dep] jq not found. Installing..."
  if command -v brew &>/dev/null; then
    brew install jq
  elif command -v nix-env &>/dev/null; then
    nix-env -iA nixpkgs.jq
  elif command -v apt-get &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y -qq jq
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y jq
  elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm jq
  else
    echo "ERROR: Cannot install jq automatically."
    echo "  Install manually: brew install jq OR sudo apt install jq"
    echo "  See: https://jqlang.github.io/jq/download/"
    exit 1
  fi
  if ! command -v jq &>/dev/null; then
    echo "ERROR: jq installation failed. Install manually and re-run."
    exit 1
  fi
  echo "  -> jq installed: $(jq --version)"
fi

echo "  jq: $(jq --version)"
echo "  Claude Code: $HOME/.claude"

# --- Step 1: Install statusline script ---
echo "[1/3] Installing statusline script..."
cat > "$STATUSLINE_PATH" << 'SCRIPT'
#!/bin/bash
# AICP Fleet Statusline — context awareness for Claude Code
# IaC-managed: installed via scripts/install-statusline.sh
# Dependency: jq
set -euo pipefail

input=$(cat)

# --- Extract fields (jq with safe defaults) ---
MODEL=$(echo "$input" | jq -r '.model.display_name // "unknown"')
CTX_SIZE=$(echo "$input" | jq -r '.context_window.context_window_size // 0')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
COST=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')
LINES_ADD=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
LINES_DEL=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
DIR=$(echo "$input" | jq -r '.workspace.current_dir // "."')
DIR_NAME="${DIR##*/}"

# Rate limits (absent for non-subscribers)
FIVE_H=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
WEEK=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

# Context window size label
if [ "$CTX_SIZE" -ge 900000 ] 2>/dev/null; then
  CTX_LABEL="1M"
elif [ "$CTX_SIZE" -ge 180000 ] 2>/dev/null; then
  CTX_LABEL="200K"
elif [ "$CTX_SIZE" -gt 0 ] 2>/dev/null; then
  CTX_LABEL="$((CTX_SIZE / 1000))K"
else
  CTX_LABEL="?"
fi

# --- Colors ---
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
DIM='\033[2m'
RESET='\033[0m'

# Context bar color by usage
if [ "$PCT" -ge 90 ]; then
  BAR_COLOR="$RED"
elif [ "$PCT" -ge 70 ]; then
  BAR_COLOR="$YELLOW"
else
  BAR_COLOR="$GREEN"
fi

# Build 20-char progress bar
FILLED=$((PCT * 20 / 100))
EMPTY=$((20 - FILLED))
BAR=""
for ((i=0; i<FILLED; i++)); do BAR="${BAR}█"; done
for ((i=0; i<EMPTY; i++)); do BAR="${BAR}░"; done

# Duration
MINS=$((DURATION_MS / 60000))
SECS=$(((DURATION_MS % 60000) / 1000))

# Cost formatted
COST_FMT=$(printf '$%.2f' "$COST")

# Git branch
BRANCH=""
if git rev-parse --git-dir > /dev/null 2>&1; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "")
  [ -n "$BRANCH" ] && BRANCH=" ${DIM}${BRANCH}${RESET}"
fi

# Rate limit string with color thresholds
LIMITS=""
if [ -n "$FIVE_H" ]; then
  FIVE_H_INT=$(printf '%.0f' "$FIVE_H")
  if [ "$FIVE_H_INT" -ge 80 ]; then
    LIMITS="${RED}5h:${FIVE_H_INT}%${RESET}"
  elif [ "$FIVE_H_INT" -ge 50 ]; then
    LIMITS="${YELLOW}5h:${FIVE_H_INT}%${RESET}"
  else
    LIMITS="${DIM}5h:${FIVE_H_INT}%${RESET}"
  fi
fi
if [ -n "$WEEK" ]; then
  WEEK_INT=$(printf '%.0f' "$WEEK")
  if [ "$WEEK_INT" -ge 80 ]; then
    LIMITS="${LIMITS:+$LIMITS }${RED}7d:${WEEK_INT}%${RESET}"
  elif [ "$WEEK_INT" -ge 50 ]; then
    LIMITS="${LIMITS:+$LIMITS }${YELLOW}7d:${WEEK_INT}%${RESET}"
  else
    LIMITS="${LIMITS:+$LIMITS }${DIM}7d:${WEEK_INT}%${RESET}"
  fi
fi

# --- Output ---
# Line 1: Model [context size] | project | branch
echo -e "${CYAN}${MODEL}${RESET} ${DIM}[${CTX_LABEL}]${RESET} ${DIR_NAME}${BRANCH}"

# Line 2: Context bar | cost | duration | lines | rate limits
echo -e "${BAR_COLOR}${BAR}${RESET} ${PCT}% | ${YELLOW}${COST_FMT}${RESET} ${DIM}${MINS}m${SECS}s${RESET} ${GREEN}+${LINES_ADD}${RESET}/${RED}-${LINES_DEL}${RESET} ${LIMITS}"
SCRIPT

chmod +x "$STATUSLINE_PATH"
echo "  -> Installed: $STATUSLINE_PATH"

# --- Step 2: Wire into settings.json ---
echo "[2/3] Configuring settings.json..."
if [ -f "$SETTINGS_PATH" ]; then
  if echo "$(cat "$SETTINGS_PATH")" | jq -e '.statusLine' &>/dev/null; then
    echo "  -> statusLine already configured"
  else
    # Add statusLine key to existing settings
    TMP=$(mktemp)
    jq '. + {"statusLine": {"type": "command", "command": "~/.claude/statusline.sh"}}' "$SETTINGS_PATH" > "$TMP"
    mv "$TMP" "$SETTINGS_PATH"
    echo "  -> Added statusLine to settings.json"
  fi
else
  cat > "$SETTINGS_PATH" << 'SETTINGS'
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
SETTINGS
  echo "  -> Created settings.json with statusLine"
fi

# --- Step 3: Smoke test ---
echo "[3/3] Testing statusline..."
TEST_JSON='{"model":{"display_name":"Opus"},"context_window":{"context_window_size":1000000,"used_percentage":42},"cost":{"total_cost_usd":0.15,"total_duration_ms":180000,"total_lines_added":256,"total_lines_removed":31},"rate_limits":{"five_hour":{"used_percentage":23.5},"seven_day":{"used_percentage":41.2}},"workspace":{"current_dir":"/home/test/project"}}'

echo "  Test output:"
echo "$TEST_JSON" | "$STATUSLINE_PATH"
echo ""
echo "=== Statusline installed successfully ==="
echo "Restart Claude Code session to activate."
