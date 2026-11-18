# Orca Server Manager

An English-first operations dashboard for a headless Orca server. Work with agents,
projects, sessions and worktrees in **Orca**. The manager provides native setup
guides, technical observations and an explicit version-change/rollback process.

**Native pilot verified, 17 November 2026:** the English HTTPS manager and Orca
runtime run in unprivileged Proxmox OCI containers. Real version changes and both
rollback modes passed with disposable data. Private builds run in a dedicated
Debian VM. The runtime includes the virtual browser used by Orca Mobile. The phone pairs by scanning one native QR code. Provider logins, Mac pairing and external tunnel access use their native setup. See the [validation record](docs/VALIDATION.md).

## Native Proxmox OCI pilot

The target is two **unprivileged native Proxmox OCI containers**: manager and Orca
runtime. A separate Debian builder produces private OCI archives; Docker runs
only in that build guest. The Proxmox host runs a small, scoped queue worker.
This does not substitute a Docker VM for the intended native OCI deployment.

Start with the [installation plan and commands](deploy/proxmox/README.md). The
installer prints a plan by default and requires `--apply` to change a host.
It requires explicit unused IDs, an assigned builder, existing storage/network
and an empty dedicated data filesystem. It never formats a disk or replaces an
existing guest. No public image registry or user GitHub pairing is needed.

The Orca runtime container starts Orca Desktop on a private virtual display. Its
browser process pairs with the Orca server over loopback. The manager shows the
service status and issues a native Orca Mobile QR code. Open **Overview → Browser
service → Set up Orca Mobile** on the LAN or VPN. The browser profile and paired
devices persist with the runtime HOME.

For first-time administrator setup, copy the code from the **manager container →
Summary → Notes** in Proxmox and enter it on the English HTTPS setup page. The
host worker publishes the one-time code there and removes its copy after setup.

After signing in, **Connect your Git accounts** offers GitHub.com and GitLab.com
device sign-in and SSH key setup for your Forgejo instance. You can connect
several providers or continue immediately. The manager remembers your progress.
Use **Revisit setup** on the overview to return later.

Choose **Open Orca WebUI** in step two or at the top of the overview. The manager requests
Orca's native browser-pairing link and opens the original WebUI in a new tab
through its HTTPS endpoint. **Pairing details & manual fallback** provides the
actual URL/code and instructions if needed; no terminal lookup is required.
Its browser files come from the matching checksummed upstream
desktop package; the runtime still runs the headless server, without Electron.
Orca performs the pairing and confirms the connection. The manager login alone
does not mean a browser is paired.

The standard runtime includes **OpenCode 2 v2.3.0** and selects Orca's native
`opencode2` host preference on a fresh server. Existing workspaces can still
launch OpenCode 1. A previously manager-selected OpenCode 1 default migrates to
OpenCode 2 when the operator has kept it. In the WebUI's agent picker, right-click
**OpenCode 2 → Set as default** once for that browser. Configure model access
later in your workspace or with `opencode2 auth login` on the runtime.
[Official OpenCode release](https://github.com/anomalyco/opencode/releases/tag/v2.3.0)

The pilot starts with upstream [Orca 1.4.261](https://github.com/stablyai/orca/releases/tag/v1.4.261),
the current official release when checked for this pilot. It is not classified as stable or
approved by this project. Later versions are selected directly from Orca's
release metadata; a published server package and checksum are technical build
requirements. The manager maintains no release approval list.
Only newer versions are offered as upgrades; older software is accessible through
an existing saved rollback point.

OpenCode has its own official upgrade list on **Versions & updates**, with labels
and checksums from [anomalyco/opencode](https://github.com/anomalyco/opencode/releases).
An OpenCode upgrade keeps the installed Orca version; an Orca upgrade keeps the
selected OpenCode version. Both use the same image replacement, consistent data
backup and saved rollback point showing both software versions. Neither catalog
is a manager-maintained approval list.

```bash
# On the dedicated builder, from a clean checkout of the intended commit:
python3 scripts/build-oci.py --version 1.4.261 --opencode-version 2.3.0 --manager --output /srv/orca-oci
# Creates private OCI archives and a source/checksum manifest. Does not publish.
```

## Local container trial

Linux x86-64, Docker, Compose v2, Bash and Python 3.12+ are required. This is a
local runtime/UI trial. Without a Proxmox worker the dashboard reports its
runtime observations as unknown and disables version changes.

```bash
cp config/.env.example .env
bash scripts/build.sh
docker compose --env-file .env -f compose/compose.yaml up -d --wait
docker compose --env-file .env -f compose/compose.yaml exec --user 1000:1000 \
  manager cat /data/manager/bootstrap.token
```

Open `https://localhost`. Verify/trust the manager's self-signed certificate or
install your own certificate in its persistent `/data/tls` directory. Set your
own administrator password with 8–256 characters. The one-time setup token is
removed; passwords are stored as scrypt hashes. Ports bind to host loopback by
default. For LAN/VPN access, configure the bind address, origin, trusted hostnames
and certificate SAN deliberately. Manager and runtime data persist separately.

The [offline prototype](mock/README.md) can be tried without a server or account:

```bash
python3 scripts/export-mock.py
# Open dist/orca-manager-mock.html. All its actions are simulated.
```

## Development and verification

The native-settings unit checks require Node.js 20+ on the development machine.

```bash
uv sync --frozen
uv run ruff check manager tests scripts deploy/proxmox container/manager-service.py
uv run ruff format --check manager tests scripts deploy/proxmox container/manager-service.py
uv run pytest -q
bash scripts/build.sh
python3 scripts/smoke.py
# Optional real browser check (Playwright and Chromium installed separately):
OSM_BROWSER_QA=1 OSM_CHROMIUM=/usr/bin/chromium python3 scripts/smoke.py
```

In managed Cloud, preserve the provided proxy and trust configuration. Pass the
session CA only as a BuildKit secret:
`OSM_BUILD_CA_FILE=/etc/ssl/certs/ca-certificates.crt bash scripts/build.sh`.
`compose/cloud.yaml` optionally mounts the outgoing CA bundle read-only for both
services. No CA private key or credential belongs in an image.

The disposable smoke test checks verified HTTPS, English setup, secure sessions,
CSRF, real native Orca RPC, installed provider CLIs, MCP health and persistence
after container recreation. Its pairing fixture runs the real native Orca CLI;
the optional Chromium check also connects and reloads the original WebUI.
It dispatches no agent and claims no Proxmox or
external-tunnel validation. Worker tests simulate PVE commands and exercise real
filesystem backup and restore separately. The separately authorized native PVE
trial also exercised OCI import/start and both rollback policies; its evidence
and remaining limits are recorded in [VALIDATION.md](docs/VALIDATION.md).

## Documentation

- [Architecture, decisions and upstream evidence](docs/ARCHITECTURE.md)
- [Operation, native setup, updates and recovery](docs/OPERATIONS.md)
- [Pilot scope and remaining validation](docs/ROADMAP.md)
- [Native Proxmox installation](deploy/proxmox/README.md)
- [Security boundary](SECURITY.md)
- [Original user brief, unchanged](docs/PROJECT_BRIEF.md)

Use feature branches and pull requests; no automatic merge. Keep the existing MIT
license. Public releases, image publication and repository visibility changes
require a separate instruction. Orca and BuildContext's bridge are independent
upstream projects; this manager is not their official product.
