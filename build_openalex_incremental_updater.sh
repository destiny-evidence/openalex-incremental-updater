#!/usr/bin/env bash

set -euo pipefail

# Image name/tag (optional first argument)
IMAGE_TAG=${1:-latest}

echo "Checking for SSH agent and key..."

# Ensure SSH agent is running and a key is loaded
if ! ssh-add -L &>/dev/null; then
    echo "SSH agent not running or no SSH key is loaded."
    echo "Run: eval \$(ssh-agent) && ssh-add ~/.ssh/id_ed25519 (or your SSH key path)"
    exit 1
fi

echo "SSH agent is running."

echo "Building Docker image openalex-incremental-updater:$IMAGE_TAG"
docker buildx build --ssh default=$SSH_AUTH_SOCK --build-arg USE_SSH=true -t "openalex-incremental-updater:${IMAGE_TAG}" openalex_incremental_updater

echo "Build complete - openalex-incremental-updater:$IMAGE_TAG"
