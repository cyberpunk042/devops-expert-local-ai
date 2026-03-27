#!/usr/bin/env bash
# =============================================================================
# AICP — Install shell aliases
# Adds AICP convenience aliases to your shell profile.
# Safe to re-run — checks for existing aliases before adding.
# =============================================================================
set -euo pipefail

MARKER="# AICP aliases"
ALIASES=$(cat <<'ALIASEOF'

# AICP aliases — added by scripts/install-aliases.sh
alias think='aicp -m think -b local'   # fast local read-only
alias ask='aicp -m think -b claude'    # cloud reasoning, read-only
alias edit='aicp -m edit -b claude'    # cloud, file edits
alias act='aicp -m act -b claude'      # cloud, full execution
alias chat='aicp -i'                   # interactive LocalAI chat
ALIASEOF
)

# Detect shell profile
if [[ -n "${ZSH_VERSION:-}" ]]; then
    PROFILE="$HOME/.zshrc"
elif [[ -f "$HOME/.bashrc" ]]; then
    PROFILE="$HOME/.bashrc"
elif [[ -f "$HOME/.bash_profile" ]]; then
    PROFILE="$HOME/.bash_profile"
else
    PROFILE="$HOME/.bashrc"
fi

if grep -q "$MARKER" "$PROFILE" 2>/dev/null; then
    echo "[SKIP]  Aliases already present in $PROFILE"
else
    printf '%s\n' "$ALIASES" >> "$PROFILE"
    echo "[OK]    Aliases added to $PROFILE"
    echo ""
    echo "Reload your shell to activate:"
    echo "  source $PROFILE"
    echo ""
    echo "Available aliases:"
    echo "  think   → aicp -m think -b local   (fast, private)"
    echo "  ask     → aicp -m think -b claude   (cloud reasoning)"
    echo "  edit    → aicp -m edit  -b claude   (file edits)"
    echo "  act     → aicp -m act   -b claude   (full execution)"
    echo "  chat    → aicp -i                   (interactive chat)"
fi
