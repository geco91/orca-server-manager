# Umsetzungsplan und Abnahme

Der vollständige Zielumfang bleibt im [Originalauftrag](PROJECT_BRIEF.md).
Diese Liste trennt implementierte Grundlagen von ausstehenden Verbindungen.

| Phase | Aktueller Umfang | Noch erforderlich |
| --- | --- | --- |
| 1 · Validierung | Release, nativer Headless-Server, CLI, Web-Client, Bridge-Vertrag und Persistenzpfade recherchiert | Andere Manager-Projekte vergleichen; aktuelle Proxmox-OCI-Quelle zugänglich prüfen |
| 2 · OCI | Prüfsummenverifiziertes x86-64-Orca-Image, Non-root, echte RPC-Healthchecks, persistente Volumes | arm64-Paket und Node-Pins separat prüfen; Produktions-Digests festlegen |
| 3 · Manager | HTTPS, HTTP-Redirect, Administrator-Bootstrap, Sessions, CSRF, Login-Sperre, responsiver Assistent, Schritte überspringen, geschützte Diagnose-API | Verifizierte versionsgebundene Setup-Aktionen und mehr technische Diagnosewerte |
| 4 · Verbindungen | Native Anleitungen, optionale Bridge neben der echten CLI, restriktive Toolsets | Codex/OpenCode als gepinnte Image-Erweiterung installieren, echte Provider-Logins und Agentlauf; Mac-/Mobile-Abnahme; vorhandenen Secure MCP Tunnel verbinden |
| 5 · Proxmox | Debian-VM-Betriebsanleitung und explizites Gast-Vorbereitungsskript | Beauftragte Test-VM bereitstellen; Podman und natives Proxmox-OCI/LXC prüfen |
| 6 · Abnahme | Automatische Manager-Funktionstests und realer Compose-Smoke-Test vorhanden | Pilot mit echten Clients, Agenten, GitHub-PR und externer MCP-Delegation |

Nächster sinnvoller Meilenstein: den getesteten Grundaufbau per PR integrieren,
die Container in einer dedizierten Debian-13-Test-VM starten, dort Provider
authentifizieren und ein Mac-Pairing mit echtem Agentauftrag abnehmen.

Keine öffentlichen Releases oder Images, keine automatischen Merges und keine
Änderungen an produktiver Proxmox-Infrastruktur ohne die dafür verlangte Freigabe.
