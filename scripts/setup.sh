#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --frozen
bash scripts/create-tls.sh "$@"
echo "Dependencies and local TLS prepared. See README.md for startup."
