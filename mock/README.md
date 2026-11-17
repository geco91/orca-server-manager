# English interactive UI prototype

```bash
python3 scripts/export-mock.py
```

Open `dist/orca-manager-mock.html` locally. It is a single offline file with
simulated state only: no accounts, images, agents or real data are changed.
Reload or Reset clears the tab's state. A restrictive CSP prevents network calls
and form submission; explicit documentation links open their upstream source.

The fresh scenario opens with GitHub, GitLab and Forgejo setup, then the launch step with OpenCode 2. Complete or skip Git setup to reach Overview. Try the native setup guides, then change a demo connection's external state and
refresh it. A changed state marks an earlier observation as stale. Pairing and
online/offline are separate demo states; the real pilot reports unknown when a
native census is unavailable. GitHub is optional. External control uses the
community bridge and the selected OpenAI Secure MCP Tunnel.

Under **Versions & updates**, select a release, run the simulated change and
browse other sections during it. Simulate newer data, then try software-only
rollback (newer data remains) or software plus saved data (newer data is
discarded). The scenario menu also covers a failed new start, active work and a
failed tunnel. Reset during an operation cancels that demo generation.

Release examples are an offline snapshot of official Orca versions 1.4.257,
1.4.258, 1.4.259 and 1.4.261, dated 16 November 2026. The historical starting
version 1.4.239 reflects the previous project image. No local stability rating,
release approval or pre-installation acceptance stage is added.

The actual English manager now implements login, official release metadata,
technical observations and queued deployment operations. This offline prototype
remains separate and is not evidence of a running Proxmox pilot. See
[the native deployment guide](../deploy/proxmox/README.md).
