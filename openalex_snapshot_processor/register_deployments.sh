#!/usr/bin/env bash
set -euo pipefail

PREFECT_API=${PREFECT_API_URL:-http://prefect-server:4200/api}
echo "Registering deployments via Python API..."

uv run prefect_config/register_deployments.py

echo "Deployments registered (or updated)."
exec "$@"
