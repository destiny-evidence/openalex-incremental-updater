#!/usr/bin/env bash

set -euo pipefail

IMAGE_TAG="latest"
IGNORE_CACHE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag=*|-t=*) IMAGE_TAG="${1#*=}" ;;
    --tag|-t) [[ -n "$2" && "$2" != -* ]] && IMAGE_TAG="$2" && shift ;;
    --no-cache) IGNORE_CACHE=true ;;
  esac
  shift
done


echo "Checking for SSH agent and key..."

# Ensure SSH agent is running and a key is loaded
if ! ssh-add -L &>/dev/null; then
    echo "SSH agent not running or no SSH key is loaded."
    echo "Run: eval \$(ssh-agent) && ssh-add ~/.ssh/id_ed25519 (or your SSH key path)"
    exit 1
fi

echo "SSH agent is running."

echo "Building Docker image openalex-incremental-updater:$IMAGE_TAG"

DOCKER_BUILD_STRING="buildx build --ssh default=$SSH_AUTH_SOCK --build-arg USE_SSH=true -t "openalex-incremental-updater:${IMAGE_TAG}" openalex_incremental_updater"
if $IGNORE_CACHE; then
  echo "Ignoring cache for this build."
  DOCKER_BUILD_STRING+=" --no-cache"
fi
docker ${DOCKER_BUILD_STRING}

echo "Build complete - openalex-incremental-updater:$IMAGE_TAG"
