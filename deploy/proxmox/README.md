# Native Proxmox OCI pilot

Verified on an explicitly assigned x86-64 Proxmox VE 9.2.21 test host.
OCI support is a Proxmox technology preview. The installed host code was checked:
it imports OCI archives and carries image entrypoint, user, environment and stop
signal into the CT. No direct image-layer update was verified, so updates use a
controlled replacement CT. This is not a Docker-in-VM runtime workaround.

## Resources and prerequisites

| Resource | Starting size | Purpose |
| --- | --- | --- |
| Dedicated Debian 13 builder VM | 2 vCPU, 2 GiB RAM, 24 GiB disk | Docker/skopeo builds only; explicit SSH alias and pinned host key |
| Unprivileged runtime OCI CT | 2 cores, 3 GiB RAM, 8 GiB rootfs | Native Orca, provider CLIs, optional existing bridge/tunnel |
| Unprivileged manager OCI CT | 1 core, 768 MiB RAM, 8 GiB rootfs | Caddy + English management UI, independent of runtime |
| Dedicated mounted data filesystem | Suggested 80 GiB initially | Workspaces, profile, queue, private images and return points |

Use existing storage and bridge. Allocate unused IDs immediately before applying;
the example IDs are placeholders, not reserved resources. Keep enough RAM and
storage for existing guests and at least one stopped replacement. The installer
never creates the builder, allocates/formats a data disk or overwrites a guest.
Those resources must be explicitly assigned first. Build and application-test
dependencies stay in the dedicated builder; the host needs only the scoped
worker's administrative tools, Python and clean Git checkout.

The assigned builder must have the description marker `OSM:pilot:builder` (use
your configured installation name), QEMU guest agent, a private SSH alias with
strict host-key verification, and an account allowed to build with Docker inside
that guest. Keep its access separate from the host's root credentials. Do not
reuse an unrelated test VM. If provisioning through the established SSH skill,
follow that workflow's guest credential/documentation requirements.

## Prepare private archives in the builder

Read `prepare-debian.sh`; it only changes a Debian 13 **guest** with `--apply` and
refuses a PVE host. Check out the selected manager source commit in the assigned
builder, then build from a clean tree:

```bash
bash deploy/proxmox/prepare-debian.sh --apply
python3 scripts/build-oci.py --version 1.4.261 --manager --output /srv/orca-oci
```

Output: `orca-runtime-1.4.261.oci.tar`, `orca-manager-0.2.0.oci.tar` and
`manifest-1.4.261.json`. Transfer these privately through the existing SSH/SCP
connection. The worker rejects a different/dirty manager source or mismatched
upstream/OCI checksum. No registry push, GitHub account pairing or public image
is required. An output lock prevents overlapping builds.

## Print the exact installation plan

On the host, keep a clean root-owned source checkout (for example
`/opt/orca-server-manager`) and a private root-owned configuration. Start from
`deployment.example.json` and replace IDs, paths, storage, bridge, builder SSH
alias/config and `source_commit` with the intended clean commit. The assigned
filesystem at `data` must already be mounted, empty and root-owned. The script
checks it before writing and never formats disks.

```bash
python3 deploy/proxmox/install.py --config /root/orca-pilot.json \
  --archives /mnt/private-transfer
```

This default mode prints the concrete `pct` commands without running them. Review
the plan. Applying is a separate explicit action after resources are assigned:

```bash
python3 deploy/proxmox/install.py --config /root/orca-pilot.json \
  --archives /mnt/private-transfer --apply
```

The installer verifies IDs, clean source, ownership, OCI format and checksums;
creates two unprivileged CTs with explicit mounts; starts them; and installs
`orca-manager-INSTALLATION.service/.timer`. No force flags, host socket mounts,
privileged mode or automatic cleanup are used. Failed imports leave inspectable
partial resources and the saved installation plan; the installer refuses to
reuse a previous base directory. Do not rerun by deleting it blindly.
If the initial import failed before either CT exists, inspect the native PVE task
log and the saved plan, correct the cause, then explicitly use `--apply --resume`.
This path requires the same initial installation, generation zero and both IDs
still unused. It never replaces an existing CT or reinitializes an updated deployment.

The importer temporarily stages each image for mapped root UID 100000, because
PVE extracts unprivileged OCI archives in a user namespace. Only that UID can
read the copy; private backup/profile directories keep their original protection.
The staging directory permits traversal without listing; each private archive
copy is removed after the import. Native `pct create` uses a normal filesystem
creation umask so mapped root can traverse PVE's extraction directories; other
worker actions retain the private default umask.

The queue directory is shared, but only its `requests` subdirectory is writable
by the web process. Status/results are host-owned. Runtime HOME/workspaces and
private integration files are not mounted into the manager. Host IDs 100000 and
101000 assume the default PVE unprivileged UID mapping; custom idmaps need an
explicit implementation review before use.

## First trial

Read the guest IPs from PVE, open the manager via HTTPS and follow the native
setup guides. The exact bootstrap command and native shell commands are in
[OPERATIONS.md](../../docs/OPERATIONS.md). Reserve the DHCP leases; the runtime
MAC is reused across replacements. Install/trust a certificate matching your
actual manager address. Restrict access to the intended LAN/VPN.

The authorized pilot exercised native OCI import/start, RPC and local MCP,
HTTPS bootstrap/login/CSRF, two version changes and both rollback policies with
disposable files. It ended on Orca 1.4.261 with a fresh administrator setup and
retained stopped replacement CTs. See [VALIDATION.md](../../docs/VALIDATION.md).

Complete a provider login and first user-started Orca task, Mac/mobile pairing,
optional GitHub access and the separate external tunnel in their native tools.
These are not established by the local MCP health check or by the lifecycle
trial. Never start a retained CT alongside the active runtime: they share data
and the runtime MAC. Keep actual host addresses and credentials in the private
operator handoff, outside this repository.
