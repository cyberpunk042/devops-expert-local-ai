#!/usr/bin/env bash
# =============================================================================
# Sync KB content to LocalAI /stores/ API
# Usage: make kb-sync
#
# Reads all markdown files from docs/kb/ and docs/knowledge-map/systems/,
# embeds them via LocalAI /v1/embeddings, and stores them in LocalAI's
# native /stores/ API under the "aicp-kb" collection.
#
# This is the ONLY way KB content gets into LocalAI. No SQLite, no
# intermediate databases. LocalAI IS the store.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCALAI_URL="${LOCALAI_URL:-http://localhost:8090}"
STORE_NAME="${KB_STORE:-aicp-kb}"
EMBED_MODEL="${EMBED_MODEL:-nomic-embed}"
MAX_CHARS=4000

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

log_info "Syncing KB to LocalAI store '${STORE_NAME}' at ${LOCALAI_URL}"

SYNCED=0
FAILED=0

sync_file() {
    local filepath="$1"
    local label="$2"
    local content
    content=$(head -c ${MAX_CHARS} "$filepath")

    if [ -z "$content" ]; then
        return
    fi

    # Embed via LocalAI
    local embed_resp
    embed_resp=$(curl -sf "${LOCALAI_URL}/v1/embeddings" \
        -H "Content-Type: application/json" \
        -d "$(jq -n --arg model "$EMBED_MODEL" --arg input "$content" \
            '{model: $model, input: $input}')" \
        2>/dev/null) || { log_fail "Embed failed: ${label}"; FAILED=$((FAILED+1)); return; }

    local embedding
    embedding=$(echo "$embed_resp" | jq -c '.data[0].embedding') || { log_fail "Parse embed: ${label}"; FAILED=$((FAILED+1)); return; }

    # Store in LocalAI
    local value
    value=$(jq -n --arg v "[${label}] ${content}" '$v')

    local store_resp
    store_resp=$(curl -sf "${LOCALAI_URL}/stores/set" \
        -H "Content-Type: application/json" \
        -d "$(jq -n \
            --arg store "$STORE_NAME" \
            --argjson keys "[$embedding]" \
            --argjson values "[$value]" \
            '{store: $store, keys: $keys, values: $values}')" \
        2>/dev/null) || { log_fail "Store failed: ${label}"; FAILED=$((FAILED+1)); return; }

    SYNCED=$((SYNCED+1))
}

# Sync docs/kb/ research files
if [ -d "$REPO_ROOT/docs/kb" ]; then
    log_info "Syncing docs/kb/ ..."
    while IFS= read -r f; do
        label=$(realpath --relative-to="$REPO_ROOT/docs/kb" "$f")
        sync_file "$f" "kb:${label}"
        echo -ne "\r  ${SYNCED} synced, ${FAILED} failed"
    done < <(find "$REPO_ROOT/docs/kb" -name '*.md' -type f | sort)
    echo ""
fi

# Sync docs/knowledge-map/systems/
if [ -d "$REPO_ROOT/docs/knowledge-map/systems" ]; then
    log_info "Syncing docs/knowledge-map/systems/ ..."
    while IFS= read -r f; do
        label="km:$(basename "$f")"
        sync_file "$f" "$label"
        echo -ne "\r  ${SYNCED} synced, ${FAILED} failed"
    done < <(find "$REPO_ROOT/docs/knowledge-map/systems" -name '*.md' -type f | sort)
    echo ""
fi

log_ok "Done: ${SYNCED} files synced to LocalAI store '${STORE_NAME}', ${FAILED} failures"

# Verify with a test query
log_info "Verification query: 'how does routing work'"
TEST_EMBED=$(curl -sf "${LOCALAI_URL}/v1/embeddings" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${EMBED_MODEL}\",\"input\":\"how does routing work\"}" \
    | jq -c '.data[0].embedding')

RESULTS=$(curl -sf "${LOCALAI_URL}/stores/find" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
        --arg store "$STORE_NAME" \
        --argjson key "$TEST_EMBED" \
        '{store: $store, key: $key, topk: 3}')")

RESULT_COUNT=$(echo "$RESULTS" | jq '.values | length')
log_ok "Found ${RESULT_COUNT} results in LocalAI store"
echo "$RESULTS" | jq -r '.values[]' | head -c 200
echo ""
