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

# Enable BuildKit and build with SSH forwarding and USE_SSH=true
echo "Building Docker image: $IMAGE_TAG"
DOCKER_BUILDKIT=1 docker build \
  --ssh default \
  --build-arg USE_SSH=true \
  -t "refresh-requester:${IMAGE_TAG}" \
  refresh_requester

echo "Build complete: $IMAGE_TAG"
