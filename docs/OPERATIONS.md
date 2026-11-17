# Operating the pilot

## Administrator and HTTPS

The manager starts independently of the Orca runtime. In Proxmox, select the
**manager container → Summary → Notes** and copy its **First-time setup code**.
Open the manager guest's HTTPS address and enter that code with your own
8–256 character password. No container console or filesystem lookup is needed.

The host worker publishes the code to that container's Notes, preserving its
ownership marker and operator notes. It never puts the code in command arguments,
logs, status JSON or images. The code becomes invalid immediately after successful
setup; its Notes copy is removed on the next worker pass. A new administrator
reset code is published in the same way. Anyone allowed to read the container's
Proxmox configuration can see a pending setup code; keep that access appropriate.

If the manager is still starting, refresh Notes shortly. For another deployment
or administrator recovery, the console command remains available:

```bash
pct exec MANAGER_CT_ID -- cat /data/manager/bootstrap.token
```

Verify the manager's HTTPS certificate before setup. The token file is removed
after setup. Existing
certificates and the manager's SQLite/session files survive recreation. For an
administrator password reset, use the local terminal, never an unauthenticated
web action:

```bash
pct exec MANAGER_CT_ID -- /usr/sbin/runuser -u manager -- /app/.venv/bin/flask \
  --app manager.app reset-admin
```

A reset invalidates old sessions. In the Docker trial use the corresponding
`docker compose exec` command. Certificate files are `/data/tls/server.crt` and
`server.key`; keep the private key mode 0600. The default self-signed certificate
includes localhost and the guest's detected IPv4 address. If DHCP changes that
address or a DNS name is used, install a matching certificate and restart the
manager. Do not disable TLS verification.

## Native setup, not a second Orca

The overview offers **Open Orca WebUI** links in a new tab. The original Orca
browser client is served through the manager's existing HTTPS endpoint at
`/orca/web-index.html`. It uses Orca's own pairing, separate from the manager
administrator login. Request the native pairing link inside the runtime with
`orca pair --address wss://YOUR-MANAGER-HOST/orca`; replace the host with the
manager's HTTPS address (including its port, if needed). Do not store pairing fragments in the
manager's public link configuration.

The proxy learns only the assigned private runtime address/port from the host
worker's sanitized status. It preserves that target during stale observations
and refreshes Caddy when the assigned address changes. Manager cookies are not
forwarded to Orca. The image includes only the original release's manifest-listed
browser files, not the desktop application. For Docker, the assigned upstream
is the Compose runtime service; `ORCA_WEB_URL` can point to the manager's HTTPS
`/orca/web-index.html` address.

The connection page shows the current runtime CT ID. Enter it as the Orca user
from the Proxmox administrator console:

```bash
pct exec RUNTIME_CT_ID -- /usr/sbin/runuser -u orca -- /bin/bash
```

Run native commands there. Codex/OpenCode are installed as pinned provider-image
extensions; installation does not mean authentication. Add accounts with
`orca account add --agent codex` or `orca account add --agent opencode` and inspect
`orca account list --json`. Follow Orca/provider login prompts and start your
first real task in Orca. The manager starts no paid agent task to check a login.

GitHub is optional. When a project needs repos, pushes or PRs, use native
`gh auth login --hostname github.com --web`, `gh auth setup-git` and
`gh auth status --hostname github.com`. The server's login is separate from your
Mac's. Reading an authenticated identity does not establish repository push
permission. Public Orca metadata/downloads do not require this runtime login.

Request a Mac pairing offer with `orca pair`, or mobile with `orca pair --mobile`.
The running runtime need not restart. Use Orca's link/QR code in its native
client over LAN/VPN. Keep offers private. This adapter does not expose a supported
native device census, so real dashboard device status remains **unknown** rather
than claiming that a paired/offline device is connected. The offline prototype
can simulate those states for interaction review.

## Status observations

The host timer reads fixed native commands and publishes a sanitized snapshot.
The dashboard considers it fresh for 90 seconds. A missing/stale worker never
claims a working connection. During long image builds the last snapshot may
expire; the operation page still displays the queued/running operation. The next
observation refreshes status. The worker reads native RPC, a complete local
terminal census, account counts, native Codex login status, GitHub identity and
MCP health. Raw account JSON, tokens and pairing offers are not returned to the UI.

## Update and rollback

1. Open **Versions & updates**. The paginated list comes from official Orca
   releases with upstream pre-release labels and links. Only versions newer than
   the installed version appear; no local stable/approved list exists. Releases lacking a
   checksummed server package for this platform cannot be built by this pilot.
2. Stop work in Orca, including native chat tasks. The live terminal census is
   not a complete chat-task census. Select a version and acknowledge stopped
   work. This is operational coordination, not a release acceptance test.
3. The worker prepares the private OCI image and stopped replacement CT, checks
   terminals again, gracefully stops the current CT and copies HOME/workspaces.
   It records the previous CT and backup before starting the replacement. The
   manager remains available. No force shutdown or automatic data restore occurs.
4. Read the resulting status and try Orca yourself. If needed, choose **Switch
   software only** (keep newer data, migrations remain) or **Restore software and
   saved data** (discard newer active changes, including profile/account/pairing
   state). Neither mode promises older software can read newer data.

One operation is active across browser sessions; the worker also checks the
installation generation. Interrupted operations are recorded and not blindly
replayed. A new-start failure retains the old CT and backup. If the new runtime
is unreachable, explicit rollback can still gracefully stop it and restore the
previous one. If a backup fails before switching, the old runtime is restarted.

Only the immediately previous version is offered as the saved rollback point.
Older retained containers/backups remain on disk for deliberate administrator
inspection/cleanup; they are not an automatic retention policy. Only newer
upstream versions remain selectable for a new upgrade. The saved previous
version is the only offered downgrade, through an explicit rollback.

## Community bridge and OpenAI tunnel

The runtime includes the pinned BuildContext bridge. Enable it by generating a
private random `bridge_token` (at least 32 characters) in the deployment's
`private/runtime-secrets` directory. Do not print it, paste it into Git or pass
it as a command-line argument. The secret directory and files map to runtime
UID/GID 1000 (host 101000 in the default unprivileged mapping); files use 0600.
Restart the runtime after changing integration files and stopping current work.

Default bridge toolsets are `status`. To allow the existing bridge's dispatch
features, the administrator explicitly creates `bridge-toolsets` containing
`status,dispatch` in that same private directory. CLI hardening remains enabled.
The bridge binds only `127.0.0.1:8787`. Do not publish that port.

Use the already selected **OpenAI Secure MCP Tunnel**:

- Reuse the existing tunnel binary and its native profile creation/connect
  workflow. Use a **separate profile/runtime**; never replace the profile that
  carries the working SSH connector. Inspect the installed client's own help
  rather than inventing profile fields. Version 0.0.16 was found on the test host.
- Copy the existing verified binary into `private/runtime-tunnel/tunnel-client`
  with read/execute permission; that directory is mounted read-only as
  `/opt/tunnel`. Keep the native private profile in `runtime-secrets`, with its
  MCP target pointing to the local bridge's token-protected endpoint. Keep
  tokens in the profile/private files, not argv or logs.
- `runtime-secrets/tunnel-command.json` contains only an argv array such as
  `["/opt/tunnel/tunnel-client", "run", "--profile-file",
  "/run/secrets/openai-tunnel-profile.json"]`. It is an administrator-managed
  file; the browser cannot submit a command. Use the client's native file/env
  references for control-plane secrets. Do not enable unsafe HTTP logging.
- Keep its local health listener at `127.0.0.1:8080` for the prepared `/readyz`
  probe. A successful local response is **partial** evidence. Only an
  authenticated external MCP call confirms the complete path. That check is
  still pending; the manager does not label it connected from a PID alone.

The Docker trial can enable just the bridge with `compose/mcp.yaml` and a private
`OSM_BRIDGE_TOKEN_FILE`. File-backed Docker secrets retain host ownership; make
sure the file is readable by container UID 1000 while keeping its host parent
private. The native deployment uses explicit host UID 101000 and mode 0600.
No external coordinator is connected by the smoke test.

## Recovery and data responsibility

The worker configuration, job results and installation plan live in its explicit
administrator-owned directories. If a host worker stops mid-change, inspect the
job, `pending` checkpoint, both scoped CTs and the saved data before proceeding.
Never start old and new CTs simultaneously: they share HOME/workspaces and a MAC.

A `prepared` checkpoint means the previous runtime/data are still selected; the
replacement must remain stopped. A `starting` checkpoint already names the new
runtime and holds a previous CT/backup, so use explicit rollback. For a data-swap
interruption the next worker tick restores a complete staged/retired directory
group and marks `rollback-interrupted`; inspect it, then explicitly choose the
rollback again. Do not delete or edit checkpoints blindly.

Images, backups and retired copies stay on the dedicated data filesystem.
Ordinary PVE rootfs backup does **not** automatically include these bind mounts.
Use an independent backup of the data filesystem and private deployment config;
verify restore with disposable data before relying on it. External project paths
outside `/workspaces` or runtime HOME are outside this backup contract. Active
terminals do not survive runtime container replacement. No retained resource is
automatically deleted by the pilot.
