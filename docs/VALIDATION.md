# Validierung am 24.10.2026

Ausgeführt in der Codex-Cloud auf Linux x86-64, Docker Engine 28.4.0,
Compose 2.40.3, Python 3.12.14 und uv 0.12.23.

| Prüfung | Ergebnis |
| --- | --- |
| Python-Installation aus `uv.lock` | erfolgreich |
| Ruff-Prüfung und Formatprüfung | erfolgreich |
| Manager-Tests | 6 Tests bestanden: HTTPS-/Login-Grenzen, Bootstrap, CSRF, übersprungene Schritte, Persistenz, Cookies, Fehlversuchssperre und Passwortreset |
| OCI-Build Runtime, Manager, HTTPS, MCP | erfolgreich, lokal; keine Images veröffentlicht |
| Runtime-Integrität | offizieller Paket-SHA-512, Manifest-SHA-256, Node-Archiv und ausführbare Node-Datei verifiziert; Inhaltshash gegen Upstream-Funktion abgeglichen |
| Echte Orca-RPC | `runtime.state=ready`, `runtime.reachable=true`, Version 1.4.239; Worktree-Leseaufruf erfolgreich |
| Runtime-Terminals | Upstream-PTY-Selbsttest erfolgreich; kein Coding-Agent aufgerufen |
| Compose-Smoke-Test | HTTPS mit vertrautem Zertifikat, HTTP-308-Redirect, echter Administrator-Bootstrap, sichere Session, verweigerte Änderung ohne CSRF, Web-Endpunkt der Runtime |
| Container-Neuerstellung | Runtime und Manager sauber ersetzt; Login-Session, übersprungener Schritt und Workspace-Testdatei erhalten |
| MCP im privaten Runtime-Netz | initialize, tools/list und orca/action=health erfolgreich, `statusProbe.ok=true`; keine Delegation gestartet |
| Cloud-Git-Zugang | Git-Lesezugriff erfolgreich; GitHub API durch Netzwerkpolicy mit Forbidden blockiert |

Der Smoke-Test verwendet eigene, danach entfernte Volumes. Der reguläre Stack
bleibt ohne eingerichteten Administrator verfügbar; sein Einmaltoken wird nicht
in Testausgaben geschrieben. Zertifikate, Token und `.env` sind von Git ausgeschlossen.

Nicht ausgeführt: GitHub-Actions-Läufe, GUI-/Browserautomation, echte Mac-/Mobile-
Pairings, Provider-Authentifizierung und Coding-Agentlauf, externer Secure MCP
Tunnel, MCP-Delegation, Proxmox-VM, Podman, natives OCI/LXC, arm64 und VM-Backup-Restore.
Die native Runtime meldet ohne installiertes Chromium `browser_unavailable`;
das betrifft Orcas Browserautomation, nicht den getesteten Runtime-Web-Endpunkt.
