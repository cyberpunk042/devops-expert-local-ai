#!/usr/bin/env bash
# =============================================================================
# Sync KB content to LocalAI Collections (persistent, visible in UI)
#
# Uses /api/agents/collections API — persistent chromem-backed storage.
# Visible at http://localhost:8090/app/collections
#
# Usage: make kb-sync
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCALAI_URL="${LOCALAI_URL:-http://localhost:8090}"
COLLECTION="${KB_COLLECTION:-aicp-kb}"

if [ -t 1 ]; then
    GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; RESET='\033[0m'
else
    GREEN=''; RED=''; CYAN=''; RESET=''
fi

log_ok()   { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_fail() { echo -e "${RED}[FAIL]${RESET}  $*" >&2; }
log_info() { echo -e "${CYAN}[INFO]${RESET}  $*"; }

# Check LocalAI is reachable
if ! curl -sf "${LOCALAI_URL}/v1/models" >/dev/null 2>&1; then
    log_fail "LocalAI not reachable at ${LOCALAI_URL}. Start it: make local-up"
    exit 1
fi

# Create collection (idempotent — no error if exists)
log_info "Creating collection '${COLLECTION}'..."
curl -sf -X POST "${LOCALAI_URL}/api/agents/collections" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${COLLECTION}\"}" >/dev/null 2>&1 || true

# Verify collection exists
COLLECTIONS=$(curl -sf "${LOCALAI_URL}/api/agents/collections" 2>/dev/null)
if ! echo "$COLLECTIONS" | grep -q "$COLLECTION"; then
    log_fail "Could not create collection '${COLLECTION}'"
    echo "$COLLECTIONS"
    exit 1
fi
log_ok "Collection '${COLLECTION}' ready"

SYNCED=0
FAILED=0

upload_file() {
    local filepath="$1"

    local resp
    resp=$(curl -sf -X POST "${LOCALAI_URL}/api/agents/collections/${COLLECTION}/upload" \
        -F "file=@${filepath}" 2>&1) || {
        log_fail "Upload: $(basename "$filepath")"
        FAILED=$((FAILED+1))
        return
    }
    SYNCED=$((SYNCED+1))
}

# Sync docs/kb/
if [ -d "$REPO_ROOT/docs/kb" ]; then
    log_info "Uploading docs/kb/ ..."
    while IFS= read -r f; do
        upload_file "$f"
        echo -ne "\r  ${SYNCED} synced, ${FAILED} failed"
    done < <(find "$REPO_ROOT/docs/kb" -name '*.md' -type f | sort)
    echo ""
fi

# Sync docs/knowledge-map/systems/
if [ -d "$REPO_ROOT/docs/knowledge-map/systems" ]; then
    log_info "Uploading docs/knowledge-map/systems/ ..."
    while IFS= read -r f; do
        upload_file "$f"
        echo -ne "\r  ${SYNCED} synced, ${FAILED} failed"
    done < <(find "$REPO_ROOT/docs/knowledge-map/systems" -name '*.md' -type f | sort)
    echo ""
fi

log_ok "Done: ${SYNCED} files synced to collection '${COLLECTION}', ${FAILED} failures"

# Verify
log_info "Verification: listing entries..."
ENTRIES=$(curl -sf "${LOCALAI_URL}/api/agents/collections/${COLLECTION}/entries" 2>/dev/null)
ENTRY_COUNT=$(echo "$ENTRIES" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo "?")
log_ok "${ENTRY_COUNT} entries in collection"

log_info "Verification: search 'how does routing work'..."
SEARCH=$(curl -sf -X POST "${LOCALAI_URL}/api/agents/collections/${COLLECTION}/search" \
    -H "Content-Type: application/json" \
    -d '{"query":"how does routing work","max_results":3}' 2>/dev/null)
echo "$SEARCH" | python3 -c "
import sys,json
d=json.load(sys.stdin)
results = d if isinstance(d, list) else d.get('results', d.get('chunks', []))
print(f'  Found {len(results)} results')
for r in results[:3]:
    text = r.get('content', r.get('text', str(r)))[:120]
    print(f'  - {text}...')
" 2>/dev/null || echo "  (search parse failed — check manually at ${LOCALAI_URL}/app/collections)"
