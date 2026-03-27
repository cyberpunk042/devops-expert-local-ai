#!/bin/bash
# Wrapper around LocalAI's entrypoint that ensures backend metadata.json files
# are present before the server starts. LocalAI v4 stores backend binaries in
# /backends/<name>/ but only registers them when metadata.json exists. The
# metadata is written by the gallery installer at runtime and lost on container
# recreate. This script re-creates it from the known backend directories.

set -e

BACKENDS_DIR="/backends"

register_backend() {
    local name="$1"
    local alias="$2"
    local dir="$BACKENDS_DIR/$name"
    local meta="$dir/metadata.json"

    if [ -d "$dir" ] && [ ! -f "$meta" ]; then
        echo "[localai-entrypoint] Registering backend: $name (alias: $alias)"
        cat > "$meta" <<EOF
{"alias":"$alias","name":"$name","gallery_url":"github:mudler/LocalAI/backend/index.yaml@master","installed_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF
    fi
}

# Run the original entrypoint first (it sets up binaries, prints CPU info, etc.)
# We source it instead of exec so we can run code after it finishes setup.
# The original entrypoint ends with: exec ./local-ai "$@"
# We intercept by replacing the final exec via PATH trick.

# Step 1: let the original entrypoint do its setup work (CPU check, EXTRA_BACKENDS)
# but without the final exec. We do this by running a modified version.
if [ -n "$EXTRA_BACKENDS" ]; then
    for backend in $EXTRA_BACKENDS; do
        echo "Preparing backend: $backend"
        make -C "$backend" || true
    done
fi

echo "CPU info:"
grep -e "model\sname" /proc/cpuinfo | head -1
grep -e "flags" /proc/cpuinfo | head -1

for flag in avx avx2 avx512f; do
    if grep -q -e "\s${flag}\s" /proc/cpuinfo; then
        echo "CPU: $flag found OK"
    fi
done

# Step 2: after the original setup, register any backends whose metadata is missing
register_backend "cuda12-llama-cpp"  "llama-cpp"
register_backend "cpu-llama-cpp"     "llama-cpp"
register_backend "llama-cpp"         "llama-cpp"

# Step 3: hand off to local-ai with all original args
cd /
exec ./local-ai "$@"
