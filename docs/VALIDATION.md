# Pilot validation record

17 November 2026. Implementation checks ran in the managed Cloud workspace and
dedicated Debian builder. Native lifecycle checks ran on the explicitly
authorized Proxmox VE 9.2.21 test host, using unprivileged OCI containers.

## Implementation and builds

- `uv sync --frozen` and Ruff lint/format checks: passed.
- `uv run pytest -q`: **45 passed**. Covers authentication/CSRF/session reset,
  official source/version validation, stale status and bounded queue handling,
  generation fences, active/unknown terminal blocking, rollback modes, failed
  backup/start, ownership markers, interrupted data swap recovery, mapped-root
  image staging, restrictive umasks and guarded initial-install resumption.
- Clean operational source:
  `d43ac1c7748c2e52014994c21a6548ce26927f01`. Its GitHub Actions checks passed.
  The dedicated builder's final private OCI export also exited zero and recorded
  that clean source commit plus upstream/archive SHA-256 digests. Later
  documentation-only commits do not change the deployed worker source.
- Runtime, provider extension and manager images built successfully. Native Orca
  reports **1.4.261**, bundled Node **24.22.1**. Codex **0.169.0**, OpenCode
  **1.19.5** and the reused OpenAI tunnel binary **0.0.16** execute in the native
  runtime. Installed binaries do not establish provider authentication.
- `python3 scripts/smoke.py`: passed with its own disposable Compose resources.
  Verified HTTPS/certificate and redirect, English bootstrap, sessions/CSRF,
  native RPC, bridge MCP initialize/tools/health and data after recreation.
  An unreadable optional bridge token leaves the runtime available. No paid
  agent task was dispatched.
- Chromium/Playwright: **18 offline-prototype checks** and **10 actual-manager
  browser checks**, including responsive layouts and English text. Those browser
  update/rollback requests used a separate controller fixture. They are distinct
  from the real native operations below.

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

The initial native CTs came from the immediately preceding clean image build;
the final runtime PATH correction was applied to native CT configuration. The
current worker uses the clean operational source above. The final private image
export includes that same correction for subsequent imports. Private build
manifests retain the exact provenance of each archive.

Not exercised: provider sign-in, a user-started agent task, Mac/mobile pairing,
repository writes, a dedicated external OpenAI tunnel profile or authenticated
end-to-end external MCP access. No production deployment or arm64 verification
is claimed.

These checks validate the manager implementation and recovery process. They are
not an Orca release approval, stability classification or gate imposed on
user-selected versions. Versions and labels still come directly from Orca.
