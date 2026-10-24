#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
build_args=()
if [[ -n ${OSM_BUILD_CA_FILE:-} ]]; then
  [[ -r "$OSM_BUILD_CA_FILE" ]] || { echo "Build CA bundle is unreadable" >&2; exit 1; }
  build_args+=(--secret "id=proxy_ca,src=$OSM_BUILD_CA_FILE")
fi
# Runtime first: the optional bridge uses that exact local base image.
for component in runtime manager https mcp; do
  docker build "${build_args[@]}" -f "container/$component.Dockerfile" \
    -t "orca-server-manager/$component:0.1.0" .
done
