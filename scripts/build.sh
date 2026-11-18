#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
build_args=()
if [[ -n ${OSM_BUILD_CA_FILE:-} ]]; then
  [[ -r "$OSM_BUILD_CA_FILE" ]] || { echo 'Build CA bundle is unreadable' >&2; exit 1; }
  build_args+=(--secret "id=proxy_ca,src=$OSM_BUILD_CA_FILE")
fi
# Default package checksum is pinned in the Dockerfile. Arbitrary version selection
# and checksummed private OCI export use scripts/build-oci.py instead.
docker build "${build_args[@]}" -f container/runtime.Dockerfile \
  -t orca-server-manager/runtime:1.4.261 .
docker build "${build_args[@]}" -f container/providers.Dockerfile \
  -t orca-server-manager/runtime-tools:1.4.261 .
