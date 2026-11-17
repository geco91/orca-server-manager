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
- Initial OpenCode setup changes only the native host agent preference through
  the local authenticated settings RPC. Runtime metadata must be an owned,
  private regular file; the Unix socket and directory must belong to that same
  runtime user. Requests are bounded and fenced to the published runtime ID.
  Existing choices and later user changes are preserved. No API key or provider
  account is supplied by this preparation step.
- The existing HTTPS proxy serves the original Orca WebUI under `/orca/`.
  Native Orca pairing remains required; the manager password is not forwarded.
  Manager cookies and upstream Set-Cookie headers are stripped at this boundary.
  Automatic upstream discovery accepts only the host-published private IPv4
  address on port 6768. Browser requests cannot choose another destination.
  Only that assigned upstream bypasses any configured outgoing HTTP proxy.
- Browser-pairing preparation requires an authenticated, CSRF-protected POST.
  The fixed worker command uses the supervisor's protected HTTPS origin and
  validates Orca's returned endpoint/fragment. Private offers are stored outside
  status/results with mapped-group read access, expire locally after two minutes
  and are served only to the requesting browser session without caching.
  Credential JSON uses no-referrer; HTML keeps same-origin referrers for strict
  HTTPS CSRF checks. Native offer fragments are never sent as HTTP referrers.
  The underlying pairing and credential lifetime remain native Orca behavior.
- Native Git provider clients own OAuth tokens in runtime HOME. The manager
  sends only fixed provider actions. The initiating browser session can read
  its human-entered code for up to ten minutes. Ordinary results and logs omit
  CLI output and credentials. Forgejo setup shares only an Ed25519 public key.
  The browser opens the operator's Forgejo address directly.
- Administrator passwords accept 8–256 characters and remain scrypt-hashed.
  Release selection and both deployment layers reject downgrades/reinstalls;
  older software is accessible only through an existing saved rollback point.
  This applies independently to Orca and OpenCode. Provider update requests cannot
  choose an Orca version or arbitrary package URL. Official package hashes and
  both software versions must match the private image manifest before import.
- TLS and official package checksums remain enabled. Builds may mount the Cloud
  CA bundle as a secret; no private CA key belongs in an image.
- A rollback with data restore discards newer active HOME/workspace contents.
  Images, credentials, backups and retained data require protected storage.
  Bind-mounted data is not automatically covered by ordinary CT rootfs backups.

Login throttling is a local pilot measure. MFA, roles, automatic credential
rotation and public internet exposure are not validated starter features.
Report vulnerabilities privately to the repository owner. Do not change repository
visibility or publish images without a separate instruction.
