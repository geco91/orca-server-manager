# Betrieb und Wiederherstellung

Alle Compose-Kommandos aus dem Repository-Hauptverzeichnis ausführen. Bei eigener
Konfiguration `--env-file .env` ergänzen. Das Cloud-Override nur in der Cloud nutzen.

## Start, Diagnose und Administrator

```bash
docker compose --env-file .env -f compose/compose.yaml up -d --wait
docker compose --env-file .env -f compose/compose.yaml ps
docker compose --env-file .env -f compose/compose.yaml exec runtime orca status --json
docker compose --env-file .env -f compose/compose.yaml logs --tail=100 runtime manager https
docker compose --env-file .env -f compose/compose.yaml exec manager \
  flask --app manager.app reset-admin
```

`reset-admin` fragt das Passwort verdeckt ab und invalidiert vorhandene Sessions.
Ein HTTP-Healthcheck des Managers ist intern ohne Anmeldung erreichbar und
enthält nur den Dienststatus. Diagnose-API und Verbindungsseiten sind geschützt.
Die Oberfläche führt keine beliebigen Kommandos aus und installiert nichts als root.
Passwortänderungen bleiben ein lokaler Administratorvorgang.

## Native Provider und GitHub

Codex und OpenCode zunächst im abgeleiteten Runtime-Image installieren, Versionen
und Paketintegritäten festlegen. Sie sind im schlanken Basisimage noch nicht
enthalten. Installation per `docker compose exec` ist nur temporär und geht bei
Image-Neuerstellung verloren. Anmeldedaten dagegen gehören in das persistente
HOME, nicht in ein Dockerfile. Anschließend in einem vertrauenswürdigen Terminal:

```bash
docker compose --env-file .env -f compose/compose.yaml exec runtime bash
# Innerhalb der Runtime, nachdem die jeweilige CLI installiert ist:
codex --version
codex login --device-auth
codex login status
opencode --version
opencode auth login
opencode auth list
# GitHub CLI und git sind bereits enthalten:
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
gh auth status
git ls-remote https://github.com/geco91/orca-server-manager.git HEAD
```

Git-Identität selbst festlegen. Leserechte, Schreibrechte und GitHub-API-Zugriff
separat prüfen. In Codex Cloud zuerst den injizierten Git-Zugang weiterverwenden;
fehlende Tokenvariablen bedeuten nicht, dass GitHub-Zugang fehlt. Ein nativer
Provider-Login auf der Ziel-VM ist ein eigener Vorgang und wird nicht aus der
Cloud übernommen. Einen Agenten erst nach vorhandenem Provider-Login mit einem
harmlosen Auftrag in einem Testrepository abnehmen.

## Mac und Mobile pairen

Die Runtime startet standardmäßig ohne Pairing-Ausgabe. Für die Pilotverbindung
die Runtime kurz stoppen, dann einmalig interaktiv im gleichen Profil starten:

```bash
docker compose --env-file .env -f compose/compose.yaml stop runtime
docker compose --env-file .env -f compose/compose.yaml run --rm --service-ports runtime \
  orcad --bind 0.0.0.0 --port 6768 --pairing-address DEINE_LAN_ODER_VPN_ADRESSE \
  --web-client-root /opt/orca/web
# Mobile: --mobile-pairing ergänzen. Nicht parallel mit derselben Profil-Volume starten.
# Link auf dem Client übernehmen; danach Ctrl-C und regulär starten:
docker compose --env-file .env -f compose/compose.yaml up -d runtime
```

Für Remote-Clients `ORCA_BIND_IP` auf die passende LAN/VPN-Schnittstelle setzen.
Manager-HTTPS sichert nicht automatisch den separaten Orca-Port. Keine Ports
ungeprüft ins öffentliche Internet freigeben. Pairing-Links sind Zugangsdaten;
nicht in Logs oder `.env` ablegen. Echte Wiederverbindung nach dem Neustart auf
Mac und Mobile noch separat abnehmen.

## Optionale MCP Bridge

```bash
mkdir -p state/secrets
chmod 700 state/secrets
# Nur wenn noch kein Token existiert; vorhandene Tokens niemals überschreiben:
(umask 077; test -e state/secrets/bridge_token || openssl rand -hex 32 > state/secrets/bridge_token)
docker compose --env-file .env -f compose/compose.yaml -f compose/mcp.yaml up -d bridge
```

Token muss für Container-UID 1000 lesbar sein, Datei 0600, Verzeichnis 0700.
Die Bridge bleibt auf Loopback im Netzwerknamespace der Runtime. Es wird kein
MCP-Port veröffentlicht. Ein vorhandener Tunnel muss diesen Endpunkt aus
demselben Netzwerknamespace erreichen können; dessen Integration ist noch offen.
Runtime-Neuerstellung erfordert auch eine Neuerstellung des Bridge-Containers,
weil dessen Netzwerknamespace an den Runtime-Container gebunden ist.

Vor Delegation `initialize`, `tools/list` und `orca` mit `action=health` prüfen.
MCP-Transport allein ist kein erfolgreicher Orca-Test: `statusProbe.ok` muss true
sein. Erst danach `ORCA_BRIDGE_TOOLSETS=status,dispatch` ausdrücklich aktivieren.
`admin` bleibt ausgeschlossen. Bearer-/OAuth-Konfiguration und Tunnel nach deren
Dokumentation einrichten. Debug-Token-URLs niemals teilen oder in Logs ausgeben.

## Persistente Daten

| Speicher | Inhalt | Zugriff |
| --- | --- | --- |
| `manager-data` → `/data` | SQLite, Administrator-Hash, Session-Schlüssel, übersprungene Schritte | nur Manager, UID 1000 |
| `runtime-home` → `/home/orca` | Orca-Profil, Pairings, Provider-Konfiguration, GitHub CLI, Bridge-OAuth-Zustand | Runtime und optionale Bridge, UID 1000 |
| `workspaces` → `/workspaces` | Repositories, Git-Worktrees, Ergebnisse | Runtime und optionale Bridge |
| `state/tls` | HTTPS-Schlüssel und Zertifikat | Caddy lesend, Schlüssel 0600 |
| `state/secrets/bridge_token` | optionaler Bridge-Token | Bridge lesend, 0600 |

Docker-Volumes lassen sich über eine lokale Compose-Override-Datei durch eigene
Host-Datenträger ersetzen. Gleiche absoluten Workspace-Pfade beim Restore
verwenden, damit Git-Worktree-Verweise gültig bleiben. Dateieigentümer erhalten.
Bei anderem Host-Benutzer müssen TLS-/Secret-Dateien bewusst der Container-UID
1000 zugeordnet werden; nicht weltweit lesbar machen.

## Backup, Update, Rollback

Vor einem konsistenten Backup alle beteiligten Dienste sauber stoppen. Bestehende
VM-/Datenträger-Backups verwenden und alle drei Volumes sowie TLS/Secrets und
die private `.env` gemeinsam sichern. Backups enthalten entschlüsselbare
Credentials: verschlüsseln und Zugriff begrenzen. Keine eigene Backupsoftware.

Für Updates zuerst Commit, Image-IDs und Datenbackup festhalten. Release-Pins,
Prüfsummen und Manifestvertrag in einem separaten PR aktualisieren; danach
Images neu bauen und `scripts/smoke.py` ausführen. Für Pilotbetrieb Tags zusätzlich
an die lokal geprüften Image-Digests binden. Die Basisimages haben hier feste
Versions-Tags, noch keine unveränderlichen Registry-Digests.

Beim Restore gleichen Projekt-/Volumenamen oder explizite Volume-Zuordnungen
nutzen, UID/GID 1000 erhalten, Zertifikate zurückspielen und Healthchecks sowie
Client-/Provider-Verbindungen erneut prüfen. Ein Code-Rollback macht eine
Orca-Datenmigration nicht rückgängig. Bei inkompatiblen Versionen alte Images
**und** zugehöriges konsistentes Datenbackup wiederherstellen. Keine blinden
Lockdatei-Löschungen und niemals `down --volumes` für persistente Nutzdaten.

Ein Container-Restart erhält Dateien, aber keine laufenden Agentenprozesse.
Orcas eigene Session-Restoration ist nach realen Updates noch zu testen.
