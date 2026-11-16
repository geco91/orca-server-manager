# Pilot validation record

16 November 2026, Linux x86-64 in the managed Cloud workspace.

- `uv sync --frozen`: passed with the committed dependency lock.
- Ruff lint/format checks for manager, scripts, tests, Proxmox tools and manager
  entrypoint: passed.
- `uv run pytest -q`: **35 passed**. Includes authentication/CSRF/session reset,
  official source/version validation, stale status and bounded queue handling,
  generation fences, active/unknown terminal blocking, two rollback modes,
  failed backup/start, ownership markers and interrupted data swap recovery.
- Runtime, provider extension and manager OCI-source images: built successfully.
  Real Orca reports **1.4.261** with bundled Node **24.22.1**. Provider CLI
  binaries are installed; this does not claim a provider login or agent run.
- `python3 scripts/smoke.py`: passed using only its own disposable Compose
  resources. Verified HTTPS/certificate and HTTP redirect, English bootstrap,
  session persistence/CSRF, real native RPC, bridge MCP initialize/tools/health
  and data after container recreation. An unreadable optional bridge token was
  also verified to leave the runtime available. The temporary test nonce supports
  CI users whose UID differs from runtime UID 1000; its host parent stays private.
  No paid agent dispatched.
- Chromium/Playwright: **18 offline-prototype checks** and **10 actual-manager
  browser checks**, including desktop/mobile layout and English text. Actual
  browser update/rollback requests used the real Flask queue with a clearly
  separate controller fixture, not a Proxmox executor.
- Native installer default mode: generated a read-only plan locally. Worker PVE
  command tests use a simulator; their backup/restore file operations are real.

Not exercised: native PVE OCI import/start, real PVE update/rollback, provider
credentials, Mac/mobile pairing, repository writes or authenticated external
OpenAI tunnel access. The host was inspected (PVE 9.2.21), but resource creation
was rejected by automatic approval review and remains pending explicit approval.

These checks validate the manager implementation. They are not a local Orca
release approval, stability classification or gate imposed on user-selected
versions. Exported private OCI manifests record their exact source commit and
archive hashes independently of this report.
