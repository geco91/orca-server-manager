# Security model

For a trusted single operator. Orca and its agents run arbitrary code as the
runtime user; enabling MCP dispatch exposes that capability to an authenticated
coordinator. Containers are not a multi-tenant isolation boundary.

- Native Proxmox containers are unprivileged. Runtime/agents and Flask use UID
  1000. The manager's HTTPS launcher uses mapped guest root for its private TLS
  files and dropping Flask privileges. No privileged CT, Docker socket, host
  networking, host devices or web-facing shell is provided.
- Manager and runtime secrets are separate mounts. A root-owned host worker
  handles a bounded file protocol and fixed actions; the web process has no
  Proxmox credentials or generic execution endpoint. Keep its source, config,
  queue parent, status/results and backup parent administrator-owned.
- HTTPS, CSRF, trusted Host headers, strict secure cookies and a private one-time
  bootstrap token protect the manager. Only loopback Caddy reaches Gunicorn;
  port 8080 is never published. Reset the administrator through the local CLI.
- Orca port 6768 and the loopback bridge are a separate trust boundary. Use
  LAN/VPN and Orca pairing. Bridge toolset defaults to read-only `status`.
  Tokens, pairing offers, provider credentials and private keys never belong in
  Git, image layers or logs. Optional service output is suppressed because an
  upstream process may print a token-bearing URL.
- TLS and official package checksums remain enabled. Builds may mount the Cloud
  CA bundle as a secret; no private CA key belongs in an image.
- A rollback with data restore discards newer active HOME/workspace contents.
  Images, credentials, backups and retained data require protected storage.
  Bind-mounted data is not automatically covered by ordinary CT rootfs backups.

Login throttling is a local pilot measure. MFA, roles, automatic credential
rotation and public internet exposure are not validated starter features.
Report vulnerabilities privately to the repository owner. Do not change repository
visibility or publish images without a separate instruction.
