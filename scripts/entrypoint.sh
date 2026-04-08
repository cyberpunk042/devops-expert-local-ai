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
# Note: local-store is built from source via make build-local-store
# (gallery version has "not implemented" bug). It persists in the
# localai-backends Docker volume after first build.
GALLERY_BACKENDS="localai@cuda12-stablediffusion-ggml"
for gb in $GALLERY_BACKENDS; do
    short_name="${gb##*@}"
    if [ ! -d "/backends/$short_name" ]; then
        echo "Installing gallery backend: $gb"
        /local-ai backends install "$gb" 2>&1 || echo "WARNING: failed to install $gb"
    fi
done

# Patch rebuilt backends over gallery-installed versions.
# The gallery OCI image for stablediffusion-ggml ships a stale libgosd*.so
# (old sd.cpp without SD 3.5 VAE support). Our rebuild (scripts/build-libgosd.sh)
# compiles from the pinned sd.cpp @ 8afbeb6 with CUDA and stages libgosd-avx2.so.
for patch_backend in /aicp-backends/*-rebuild/; do
    [ -d "$patch_backend" ] || continue
    # cuda12-stablediffusion-ggml-rebuild → cuda12-stablediffusion-ggml
    target_name=$(basename "$patch_backend" | sed 's/-rebuild$//')
    target_dir="/backends/$target_name"
    if [ -d "$target_dir" ]; then
        echo "Patching backend: $target_name (rebuilt .so)"
        cp -f "$patch_backend"/* "$target_dir/"
    else
        echo "WARNING: target backend $target_name not found, skipping patch"
    fi
done

# Hand off to the original entrypoint
exec /local-ai "$@"
