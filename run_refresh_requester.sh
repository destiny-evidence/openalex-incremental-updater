#!/usr/bin/env bash

set -euo pipefail

TAG="latest"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      TAG="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [--tag TAG]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--tag TAG]"
      exit 1
      ;;
  esac
done

docker run --env-file refresh_requester/.env refresh-requester:"$TAG"
