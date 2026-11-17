# Orca Server Manager

Read README.md, docs/ARCHITECTURE.md and docs/ROADMAP.md before implementation.
The original user mandate is preserved in docs/PROJECT_BRIEF.md.

- This cloud task already has an isolated checkout. Do not create worktrees unless
  explicitly requested. Use a feature branch and a pull request; do not auto-merge.
- Keep Orca's agent, session, project and worktree operations in Orca. The manager
  provides setup and infrastructure diagnostics, not a second orchestrator.
- Do not publish the repository or images publicly. Keep the existing MIT license;
  a public release requires a separate user instruction.
- Never put credentials, pairing URLs, tokens or private keys in Git, images or logs.
- No Docker socket, privileged containers, host network or root shell endpoints.
- Preserve TLS, package checksums, native runtime markers and upstream manifests.
- Report only observed readiness. CLI installation is not provider authentication;
  a reachable web endpoint is not an authenticated runtime or connected client.
- Run `uv sync --frozen`, `uv run ruff check manager tests scripts`,
  `uv run ruff format --check manager tests scripts`, `uv run pytest -q`.
- For container changes build the affected images and run `python3 scripts/smoke.py`.
  It creates and removes only its own disposable Compose volumes.
- Changes to productive Proxmox infrastructure require separate approval.
