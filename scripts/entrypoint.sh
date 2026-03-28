#!/bin/bash
# AICP entrypoint: copy extra backends into the volume, then start LocalAI.
# The base image declares /backends as a VOLUME, so COPY in Dockerfile
# is overridden at runtime. This script copies them at startup instead.
set -e

# Copy AICP-managed backends into the runtime volume
for backend in /aicp-backends/*/; do
    name=$(basename "$backend")
    if [ ! -d "/backends/$name" ]; then
        cp -r "$backend" "/backends/$name"
        echo "Installed backend: $name"
    fi
done

# Hand off to the original entrypoint
exec /local-ai "$@"
