#!/usr/bin/env bash
# Run only inside the dedicated Debian test VM, never on the Proxmox host.
set -euo pipefail
if [[ ${1:-} != --apply ]]; then
  echo 'Inside the dedicated Debian 13 VM, run as root with --apply.'
  exit 0
fi
[[ $EUID -eq 0 ]] || { echo 'Root is required inside the guest.' >&2; exit 1; }
source /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'This helper targets Debian 13.' >&2; exit 1; }
if command -v pveversion >/dev/null; then
  echo 'Refusing to modify a Proxmox host.' >&2
  exit 1
fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose git openssl ca-certificates
systemctl enable --now docker
docker compose version
echo 'OCI runtime prepared. Continue with README.md; no repository or stack was deployed.'
