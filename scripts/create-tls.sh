#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
tls_dir=${OSM_TLS_OUTPUT_DIR:-state/tls}
if [[ -e "$tls_dir/server.crt" || -e "$tls_dir/server.key" ]]; then
  if [[ ! -e "$tls_dir/server.crt" || ! -e "$tls_dir/server.key" ]]; then
    echo "Incomplete TLS state: restore the missing certificate or key." >&2
    exit 1
  fi
  echo "Certificate or key already exists; refusing to overwrite."
  exit 0
fi
mkdir -p "$tls_dir"
chmod 700 "$tls_dir"
umask 077
san="DNS:localhost,IP:127.0.0.1"
for host in "$@"; do
  if [[ "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    san+=",IP:$host"
  elif [[ "$host" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]]; then
    san+=",DNS:$host"
  else
    echo "Unsupported SAN: use a DNS hostname or IPv4 address" >&2
    exit 1
  fi
done
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
  -keyout "$tls_dir/server.key" -out "$tls_dir/server.crt" \
  -subj '/CN=Orca Server Manager' -addext "subjectAltName=$san" \
  -addext 'basicConstraints=critical,CA:FALSE' 2>/dev/null
chmod 600 "$tls_dir/server.key"
chmod 644 "$tls_dir/server.crt"
echo "Self-signed certificate created. Trust server.crt explicitly on your clients."
