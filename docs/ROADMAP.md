# Pilot scope and remaining checks

Updated 16 November 2026. See [original brief](PROJECT_BRIEF.md).

| Area | Implemented/prepared | Still requires real pilot validation |
| --- | --- | --- |
| Runtime | Official 1.4.261 server bundle, checksum and bundled Node verification, UID 1000, RPC health | Native PVE OCI import/start and signal handling |
| Manager | English default, HTTPS, one-time administrator setup, secure sessions, CSRF, login throttling, responsive guides/status | LAN certificate trust and operator usability on the guest |
| Native integrations | Installed pinned Codex/OpenCode CLIs; account/GitHub probes; optional native setup guides | Actual sign-in, first user-started agent task, repository access and Mac/mobile pairing |
| Versions | Official release pages, upstream labels and version selection; no local release approval | Builder access and available packages for other user-selected versions |
| Update/rollback | Scoped queue/worker, generation fence, graceful stop, backup, replacement, two rollback policies, interruption journal | Actual PVE version change and rollback with disposable data |
| MCP | Existing community bridge included, private token, read-only default, real protocol/Orca health smoke | Explicit dispatch setup and external delegation |
| Tunnel | Existing OpenAI product fixed; private binary/profile mounts and local readiness probe | Dedicated native profile and authenticated end-to-end MCP call |
| Deployment | Private OCI export, checksum/source manifest, read-only plan, explicit native CT installer and timer | Authorization and creation of dedicated test resources |

Cloud/container tests are implementation checks, not a release-approval service
for Orca versions. The operator chooses and tries upstream versions themselves.

The test Proxmox host was inspected read-only, plus a small private Debian-image
verification record. No new VM/CT was provisioned. Automatic approval review
rejected creation/start of a persistent builder VM with the proposed password
access and passwordless sudo. Provisioning remains pending explicit approval;
local preparation does not bypass that decision.

Out of the starter scope: production deployment, multi-tenant roles, public
image publication, automatic merges, full native-chat activity enumeration,
arm64 build/guest verification, automatic backup pruning and fleet management.
