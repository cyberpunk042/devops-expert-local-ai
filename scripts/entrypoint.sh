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

# Install gallery backends (downloaded at runtime, not OCI-extracted)
GALLERY_BACKENDS="localai@cuda12-stablediffusion-ggml"
for gb in $GALLERY_BACKENDS; do
    short_name="${gb##*@}"
    if [ ! -d "/backends/$short_name" ]; then
        echo "Installing gallery backend: $gb"
        /local-ai backends install "$gb" 2>&1 || echo "WARNING: failed to install $gb"
    fi
done

# Hand off to the original entrypoint
exec /local-ai "$@"
