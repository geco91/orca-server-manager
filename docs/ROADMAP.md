# Pilot scope and remaining checks

Updated 17 November 2026. See [original brief](PROJECT_BRIEF.md) and the
[validation record](VALIDATION.md).

| Area | Implemented and observed | Remaining checks |
| --- | --- | --- |
| Runtime | Official 1.4.261 server bundle/checksums, UID 1000, native PVE OCI import/start, RPC and graceful replacement | User workload behavior and other architectures |
| Manager | English Git-first setup, resumable direct launch and Overview, HTTPS, setup code in Proxmox Notes, 8-character password minimum, prepared native browser pairing in new tabs, private URL/code fallback, sessions/CSRF and responsive guides/status | Operator usability feedback |
| Native integrations | OpenCode 2 host default, preserved v1 workspaces, native GitHub/GitLab browser sign-in and identity probes, Forgejo public-key setup | Actual provider access, first user-started agent task, repository access and Mac/mobile pairing |
| Versions | Separate official Orca/OpenCode catalogs and labels, preserved software pair, upgrades only, SemVer ordering, downgrade guards in UI/controller/worker, saved rollback when available | Availability of packages for other user-selected upgrades |
| Update/rollback | Real native version changes, software-only rollback retaining newer data, full rollback restoring saved data; generation fences and interruption handling | Recovery under further host/storage failure scenarios and operator experience |
| MCP | Existing pinned community bridge, private token, read-only default, real local initialize/tools/Orca health | Explicit dispatch setup and external delegation |
| Tunnel | Existing OpenAI binary reused and executable in the native runtime; separate private profile mounts/probe prepared | Dedicated native profile and authenticated end-to-end external MCP call |
| Deployment | Dedicated builder VM/data filesystem, native manager/runtime OCI CTs, private checksum/source manifests and scoped host timer | Independent data backup/restore procedure and deliberate retention cleanup |

The explicitly authorized test deployment is running; native image replacement
and both return paths passed with disposable data. The temporary test account
was removed so the operator can create their own administrator. Existing
unrelated guests and the working SSH connector/tunnel profile were preserved.
Private handoff records contain actual resource IDs, addresses and bootstrap
instructions; credentials do not belong in this repository.

Implementation and lifecycle checks are not a release-approval service for Orca
versions. The operator chooses and tries upstream versions themselves.

Out of the starter scope: production deployment, multi-tenant roles, public
image publication, automatic merges, full native-chat activity enumeration,
arm64 build/guest verification, automatic backup pruning and fleet management.
