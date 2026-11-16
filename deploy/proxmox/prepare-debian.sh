#!/usr/bin/env bash
# Only inside the dedicated Debian builder guest, never on the Proxmox host.
set -euo pipefail
if [[ ${1:-} != --apply ]]; then
  echo 'Plan: install Docker, skopeo, Python, git and QEMU guest agent in a Debian 13 builder.'
  echo 'Inside the assigned guest, run as root with --apply.'
  exit 0
fi
[[ $EUID -eq 0 ]] || { echo 'Root is required inside the assigned guest.' >&2; exit 1; }
source /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'This helper targets Debian 13.' >&2; exit 1; }
if command -v pveversion >/dev/null; then
  echo 'Refusing to modify a Proxmox host.' >&2
  exit 1
fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io skopeo git openssl ca-certificates python3 qemu-guest-agent
systemctl enable --now docker qemu-guest-agent
docker version
skopeo --version
echo 'Builder prepared. No repository, runtime container or tunnel was deployed.'
