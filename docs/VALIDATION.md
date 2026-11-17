# Pilot validation record

17 November 2026. Implementation checks ran in the managed Cloud workspace and
dedicated Debian builder. Native lifecycle checks ran on the explicitly
authorized Proxmox VE 9.2.21 test host, using unprivileged OCI containers.

## Implementation and builds

- `uv sync --frozen` and Ruff lint/format checks: passed.
- `uv run pytest -q`: **153 passed**. Covers authentication/CSRF/session reset,
  official source/version validation, stale status and bounded queue handling,
  generation fences, active/unknown terminal blocking, rollback modes, failed
  backup/start, ownership markers, interrupted data swap recovery, mapped-root
  image staging, restrictive umasks and guarded initial-install resumption.
  Ten setup-Notes checks cover private mapped-owner reads, symlink/hardlink and
  unsafe-file rejection, marker/operator-note preservation, idempotence, consumed
  code removal and keeping secrets out of argv/output/error messages.
  Additional checks cover the 8/256-character password boundaries, numeric and
  pre-release ordering, cached catalog refiltering, forged downgrade requests,
  missing rollback points, safe WebUI links/upstreams and original browser asset
  extraction/checksums without links, traversal, desktop-only files or source maps.
  Native browser pairing checks cover protected origin reads, fixed destinations,
  CSRF/login, session ownership, offer expiration/generation changes, secret-free
  public results and pairing without stopping active terminals.
  Native OpenCode setup checks cover the one-time host default, preservation of
  existing and later choices, private metadata/link rejection, runtime identity
  fencing and keeping unrelated settings and credentials untouched. A real
  disposable Orca runtime accepted the native settings update from no default
  to OpenCode. Installation/default selection do not establish provider access.
- Previous setup-Notes baseline source:
  `d78750b82f21ecd3738e26c3c9fe4e6ca349ea33`. Its GitHub Actions checks passed.
  The dedicated builder's final private OCI export also exited zero and recorded
  that clean source commit plus upstream/archive SHA-256 digests. Later
  documentation-only commits recorded that baseline. Current source and deployed
  main commit are recorded independently by CI and the private OCI manifests.
- Runtime, provider extension and manager images built successfully. Native Orca
  reports **1.4.261**, bundled Node **24.22.1**. Codex **0.169.0**, OpenCode
  **1.19.5** and the reused OpenAI tunnel binary **0.0.16** execute in the native
  runtime. Installed binaries do not establish provider authentication.
- `python3 scripts/smoke.py`: passed with its own disposable Compose resources.
  Verified HTTPS/certificate and redirect, English bootstrap using an eight-character
  password, sessions/CSRF, native RPC, bridge MCP initialize/tools/health and data after recreation.
  The original browser HTML and JavaScript load through Caddy over verified HTTPS;
  non-browser package/manifest paths return 404. Scoped NO_PROXY preserves the
  environment's outgoing proxy while routing only the assigned runtime locally.
  An unreadable optional bridge token leaves the runtime available. No paid
  agent task was dispatched.
- Chromium/Playwright: **18 offline-prototype checks** and **10 actual-manager
  browser checks**, including responsive layouts and English text. Those browser
  update/rollback requests used a separate controller fixture. They are distinct
  from the real native operations below.
- `OSM_BROWSER_QA=1 OSM_CHROMIUM=/usr/bin/chromium python3 scripts/smoke.py`:
  the real Chromium browser signed in, opened the dashboard's new-tab form and
  automatically imported Orca's original pairing URL. An authenticated native
  `status.get` RPC succeeded through the original WebUI before and after reload;
  Orca removed the secret fragment from the address bar. The disposable test uses
  a queue transport fixture instead of Proxmox, but its pairing CLI, HTTPS proxy,
  original Orca client and encrypted authenticated runtime connection are real.

## Native Proxmox trial

- Created the assigned Debian builder VM, dedicated data filesystem and separate
  unprivileged runtime/manager OCI CTs. Existing unrelated guests were preserved.
  Docker is used only in the builder, not to host the manager/runtime.
- Imported OCI archives with the real PVE extractor; verified native runtime
  RPC, complete local terminal observations and local MCP protocol/Orca health.
  Native import permissions, bind-mount traversal and administrative PATH issues
  found during this trial were corrected in the implementation.
- Exercised real HTTPS administrator bootstrap, login, CSRF rejection, native
  guides and official release listing inside the original manager CT. An
  external guest independently verified the certificate/hostname and English
  setup page with HTTP 200. The manager remained available during runtime changes.
- Changed **1.4.261 → 1.4.259**, then performed **software-only rollback** to
  1.4.261. A disposable file modified after the version change retained its
  newer contents.
- Repeated **1.4.261 → 1.4.259**, then performed **software plus saved data
  rollback**. The active file returned to its saved contents; the later change
  was discarded from active data. Both rollback requests and both update jobs
  completed through the real UI queue and host worker.
- Finished on **1.4.261**, deployment generation **4**, with the two replacement
  CTs stopped and retained for inspection. They must not run alongside the active
  runtime because the data and MAC are shared. Saved backups/retired data remain
  private on the dedicated data filesystem; pruning is an administrator task.
- Removed the disposable file and temporary test administrator, invalidated its
  sessions and left fresh first-administrator setup for the operator. TLS
  persisted. Credentials were not exported to the builder; authenticated UI
  tests stayed inside the original manager CT.
- The setup-Notes refinement was deployed to the existing manager and host
  worker. Real Proxmox Notes contain the pending code matching the private source
  file and retain the ownership marker. Verified HTTPS serves the new English
  **Summary → Notes** hint and does not expose the code in its unauthenticated
  HTML. The code was left pending for the operator's own setup. Automatic cleanup
  after consumption is covered by the setup-Notes tests above.

The initial native CTs came from the clean `e14bab3` image build; the runtime PATH
correction was applied to native CT configuration. Native update/rollback trials
used worker source `d43ac1c`. The current worker uses the clean operational source
above. Its manager setup template was synchronized into the existing manager CT
and the application workers were gracefully reloaded, preserving its data, TLS
and address. The final private image export includes the same source for future
imports. Private build manifests retain the exact provenance of each archive.
The later upgrade/WebUI refinement uses the original manifest-listed browser
files from the matching checksummed desktop package; Electron is not run.
Native rollout records distinguish the application component refresh from the
original CT rootfs imports and retain the exact main source and archive hashes.

Not exercised: provider sign-in, a user-started agent task, Mac/mobile pairing,
repository writes, a dedicated external OpenAI tunnel profile or authenticated
end-to-end external MCP access. No production deployment or arm64 verification
is claimed.

These checks validate the manager implementation and recovery process. They are
not an Orca release approval, stability classification or gate imposed on
user-selected versions. Versions and labels still come directly from Orca.

## OpenCode image upgrades

- Source `2e0b4096781afb24e478ee115202b3f28217b337`: 153 pytest checks,
  Ruff lint/format and GitHub Actions passed. Added coverage includes official
  provider metadata/checksums, downgrade rejection, shared operation locking,
  cached catalog refiltering, the preserved Orca/OpenCode pair, both rollback
  data policies, unknown installed versions and mismatched build manifests.
- Private OCI exports with OpenCode **1.19.4** and **1.19.5** both recorded the
  clean source and official package/archive digests. The real disposable Compose
  smoke passed after the build guest received its missing official, checksummed
  Compose CLI plugin. Original failed attempt records remain separate.
- A separate native Proxmox runtime with disposable HOME/workspace data changed
  **OpenCode 1.19.4 → 1.19.5**, keeping **Orca 1.4.261**. Native startup
  observations confirmed both versions. Software-only rollback restored 1.19.4
  and retained a file changed after the upgrade. A repeated upgrade followed by
  software-and-data rollback restored the saved file contents instead.
- All four native operations completed. The main manager/runtime deployment was
  unchanged during this trial; all three additional scoped CTs were removed.
  The first isolated import used a non-traversable staging ancestor and failed
  before boot. The successful trial used a separate staging path with the
  intended mapped-root traversal rights, preserving private-directory modes.
- No provider login, API key or agent task was used. This checks the manager's
  update/return process; it is no classification or approval of OpenCode releases.
