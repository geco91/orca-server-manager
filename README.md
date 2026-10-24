# Orca Server Manager

Portable Headless Orca Server with Guided Setup, MCP Integration and OCI Deployment.

Dieses Projekt stellt die Infrastruktur für einen headless Orca-Server bereit.
Orca selbst verwaltet Coding-Agenten, Projekte, Sessions und Worktrees.
Der Manager bietet einen geschützten Einstieg für Einrichtung und Diagnose.

**Stand: erstes technisches MVP.** Orca-Runtime, HTTPS-Manager, Einrichtung des
Administrators, Setup-Anleitungen und persistente Daten sind implementiert.
Provider-Logins und Geräte-Pairing erfolgen über die nativen Werkzeuge.
Die UI meldet diese Verbindungen ausdrücklich als nicht verifiziert.
Ein Secure MCP Tunnel und eine Proxmox-Installation sind noch keine abgenommenen Funktionen.

## Schnellstart auf einem Docker-Host

Voraussetzungen: Linux x86-64, Docker mit Compose v2, Bash und OpenSSL.
Die erste Referenzplattform ist eine Debian-13-VM, kein privilegierter LXC.

```bash
cp config/.env.example .env
# .env an Hostnamen, LAN/VPN-Adresse und gewünschte Ports anpassen.
# Zusätzliche DNS-Namen und IPv4-Adressen als Zertifikats-SAN:
bash scripts/create-tls.sh orca.example.internal 192.168.1.50
bash scripts/build.sh
docker compose --env-file .env -f compose/compose.yaml up -d --wait
docker compose --env-file .env -f compose/compose.yaml exec manager cat /data/bootstrap.token
```

Die HTTPS-Adresse aus `OSM_ORIGIN` im Browser öffnen. Das selbstsignierte
Zertifikat `state/tls/server.crt` nach Prüfung auf den Clients vertrauen oder durch
ein eigenes Zertifikat ersetzen. Token vertraulich in die Ersteinrichtung
eintragen und ein eigenes Administrator-Passwort vergeben. Der Token wird
anschließend gelöscht. Ein Passwort wird ausschließlich als scrypt-Hash gespeichert.

Standardmäßig lauschen veröffentlichte Ports nur auf Host-Loopback.
Für LAN/VPN die Bind-Adressen, `OSM_ORIGIN` und `OSM_TRUSTED_HOSTS` in `.env`
bewusst anpassen. Der Manager verwendet außen Port 80 für den Redirect und 443
für HTTPS, intern unprivilegierte Ports 8080/8443. Orca verwendet separat 6768.
Die Management-UI startet auch dann, wenn optionale Integrationen fehlen.

## Entwicklung in Codex Cloud

Python 3.12 und uv 0.12.23 werden verwendet; alle Python-Pakete sind in `uv.lock`
festgelegt. Ein vorhandenes isoliertes Cloud-Checkout weiterverwenden.

```bash
uv sync --frozen
uv run ruff check manager tests scripts
uv run ruff format --check manager tests scripts
uv run pytest -q
bash scripts/create-tls.sh
# Session-CA nur als BuildKit-Secret, niemals ins Image kopieren:
OSM_BUILD_CA_FILE=/etc/ssl/certs/ca-certificates.crt bash scripts/build.sh
OSM_HTTP_PORT=8080 OSM_HTTPS_PORT=8443 OSM_ORIGIN=https://localhost:8443 \
  docker compose -f compose/compose.yaml -f compose/cloud.yaml up -d --wait
python3 scripts/smoke.py
```

`compose/cloud.yaml` ergänzt ausschließlich das öffentliche CA-Bundle für die
ausgehenden HTTPS-Verbindungen der Runtime. Proxy- und Registry-Konfiguration der
Cloud-Umgebung erhalten. Tests kommunizieren intern; Onboarding bietet keine
Web-Vorschau. Der Cloud-Start wird zusätzlich in den Umgebungseinstellungen gespeichert.

Für lokale UI-Entwicklung ohne Container:

```bash
bash scripts/create-tls.sh
uv run flask --app manager.app run --host 127.0.0.1 --port 8443 \
  --cert state/tls/server.crt --key state/tls/server.key
```

Der Flask-Entwicklungsserver ist nur für lokale Entwicklung gedacht. Die Runtime
wird separat über Compose gestartet; `ORCA_INTERNAL_URL` muss im lokalen
Entwicklungsprozess auf deren tatsächlich erreichbaren Endpunkt zeigen.

## Dokumentation

Die [interaktive Mock-WebUI](mock/README.md) lässt sich ohne Server und Zugangsdaten
durchspielen: `python3 scripts/export-mock.py` erzeugt eine einzelne HTML-Datei zum
lokalen Öffnen im Browser. Alle Aktionen und Verbindungen darin sind simuliert.

- [Originalauftrag, unverändert](docs/PROJECT_BRIEF.md)
- [Architektur und recherchierte Entscheidungen](docs/ARCHITECTURE.md)
- [Betrieb, Provider, Pairing, MCP, Backup und Recovery](docs/OPERATIONS.md)
- [Phasen und offene Abnahmen](docs/ROADMAP.md)
- [Proxmox-VM als Zielplattform](deploy/proxmox/README.md)
- [Sicherheitsmodell](SECURITY.md)

Feature-Branches und Pull Requests verwenden, kein automatischer Merge nach
`main`. Die bereits vorhandene MIT-Lizenz bleibt erhalten. Eine öffentliche
Veröffentlichung des Repositories oder von Images braucht eine gesonderte Freigabe.

Orca und die Community-Bridge sind unabhängige Upstream-Projekte. Dieses Projekt
ist kein offizielles Produkt von Stably oder BuildContext.
