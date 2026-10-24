# Codex-Entwicklungsauftrag: Orca Server Manager

## 1. Projektziel und Mandat

Entwickle ein neues, portables und möglichst schlankes Open-Source-Projekt für den Betrieb und die Einrichtung eines headless Orca-Servers.

**Projektname:** Orca Server Manager  
**GitHub-Repository:** `geco91/orca-server-manager`  
**GitHub-Account:** `geco91`  
**Beschreibung:** Portable Headless Orca Server with Guided Setup, MCP Integration and OCI Deployment

Das Repository soll zunächst privat angelegt werden. Eine spätere Veröffentlichung als Open Source ist vorgesehen, benötigt aber eine gesonderte Freigabe.

### Grundidee

Orca übernimmt die eigentliche operative Entwicklungsarbeit:

- Coding-Agenten starten und verwalten.
- Projekte und Repositories bearbeiten.
- Sessions verwalten.
- Git-Worktrees verwenden.
- Entwicklungsarbeiten koordinieren.
- Remote-Clients bedienen.

Unser Projekt stellt die Infrastruktur dafür bereit.

Es unterstützt den Benutzer dabei, einen Orca-Server einzurichten, notwendige Integrationen zu verbinden und den technischen Betrieb sicherzustellen.

**Wir entwickeln ausdrücklich keinen Ersatz für die Orca-Oberfläche.**

Die eigene WebUI ist primär ein Setup-, Verbindungs- und Infrastrukturmanager.

## 2. Übergeordnete Architekturprinzipien

Für das Projekt gelten folgende Grundsätze:

**OCI-first, Proxmox-ready, Docker-compatible.**

Die Software soll als OCI-Containerlösung bereitgestellt werden können.

Primäre Zielumgebung für den ersten realen Einsatz ist eine eigene VM unter Proxmox VE.

Die Architektur muss jedoch auch einen Betrieb auf gewöhnlichen Docker- oder Podman-Hosts ermöglichen.

Wichtig:

- Keine feste Bindung an Proxmox.
- Keine feste Bindung an Cockpit.
- Keine unnötige Abhängigkeit von systemd innerhalb der Anwendungscontainer.
- Keine zwingende Desktop-Umgebung.
- Möglichst geringer Ressourcenverbrauch.
- Möglichst wenige Abhängigkeiten.
- Konfigurierbare persistente Datenbereiche.
- Keine eigenen Implementierungen für Funktionen, die Orca bereits anbietet.
- Kein unnötiges Orchestrierungsframework.

Bevorzuge eine kleine, verständliche Architektur mit klaren Komponenten.

## 3. Zielarchitektur

Die Lösung besteht logisch aus vier Bereichen.

### A. Orca Headless Runtime

Orca läuft als dauerhafter Serverprozess ohne Linux-Desktop.

Die Runtime stellt die bestehenden Orca-Funktionen für Agenten, Projekte, Worktrees und Remote-Clients bereit.

### B. Orca Server Manager

Eine eigenständige webbasierte Verwaltungsanwendung.

Sie übernimmt:

- Erstinstallation und Initialisierung.
- Konfiguration und Verifikation.
- Einrichtung externer Verbindungen.
- Agent-Provider-Authentifizierung.
- GitHub-Verbindung.
- MCP-Integration.
- Remote-Client-Pairing.
- Dienststatus und technische Diagnose.
- Verlinkung zur eigentlichen Orca-Weboberfläche.

Der Manager dient als zentraler Einstieg für die technische Einrichtung.

### C. MCP Bridge

Eine bestehende Community-MCP-Bridge soll die Orca-Runtime für externe KI-Koordinatoren steuerbar machen.

Zu prüfen:

https://github.com/BuildContext/orca-mcp

Die Bridge wird über einen Secure MCP Tunnel mit externen Clients verbunden.

### D. Deployment Layer

Ein portables OCI-Deployment mit plattformspezifischen Konfigurations- und Installationshilfen.

Vorgesehene Plattformen:

1. Docker beziehungsweise Docker Compose.
2. Podman, soweit kompatibel.
3. Debian-VM unter Proxmox mit OCI-Runtime.
4. Optional direkte Proxmox-OCI/LXC-Ausführung.

Die Proxmox-OCI/LXC-Kompatibilität ist zu prüfen, nicht vorauszusetzen.

## 4. Technische Recherche vor Implementierung

Prüfe anhand aktueller Dokumentation und gegebenenfalls Quellcode:

- Aktuelle Orca-Linux-Version.
- Orca Headless Server.
- `serve` und `serve --supervise`.
- Containerfähigkeit der Runtime.
- Anforderungen an persistente Sessions.
- Verhalten bei Neustarts.
- Client-Pairing.
- Orca-Web-Client.
- GitHub-Integration.
- Unterstützte Coding-Agenten.
- Verfügbare CLI-Schnittstellen.
- Community-MCP-Bridge und deren aktuelle API.
- Bestehende Orca-Server-Manager-Projekte.
- Proxmox-OCI-Unterstützung.
- Besonderheiten von OCI-Images in Proxmox-LXC.
- Geeignete schlanke Webframeworks.

Wichtige technische Entscheidungen dokumentieren.

Falls Annahmen aus dieser Aufgabenbeschreibung durch aktuelle Quellen widerlegt werden, korrigiere die Architektur anhand der überprüften Fakten.

## 5. Eigenständige Management-WebUI

### Grundkonzept

Die WebUI soll den Benutzer schrittweise durch die vollständige Einrichtung seines Orca-Servers führen.

Sie soll nicht primär ein komplexes Administrations-Dashboard sein, sondern ein **Setup-Assistent mit dauerhaft verfügbaren Verwaltungsfunktionen**.

Das Design soll:

- Modern und aufgeräumt sein.
- Klare Statusanzeigen besitzen.
- Möglichst selbsterklärend sein.
- Komplexe technische Details nur bei Bedarf zeigen.
- Sinnvolle nächste Einrichtungsschritte anbieten.
- Fehler verständlich diagnostizieren.
- Nach erfolgreicher Einrichtung eine kompakte Statusübersicht bieten.

Keine Überladung mit Funktionen, die bereits über den Orca-Desktop oder Orca-Web-Client erreichbar sind.

### Vorgeschlagener Setup-Ablauf

**Schritt 1: Server prüfen**

Nach dem ersten Start prüft der Manager:

- Läuft Orca?
- Ist Orca korrekt initialisiert?
- Welche Version ist installiert?
- Sind notwendige Verzeichnisse verfügbar?
- Funktionieren Persistenz und Schreibrechte?
- Sind benötigte Netzwerkports erreichbar?
- Gibt es erkennbare Konfigurationsprobleme?

Der Benutzer erhält eine verständliche Übersicht und gegebenenfalls konkrete Behebungsschritte.

**Schritt 2: Agent-Provider verbinden**

Geführtes Setup für:

- OpenAI Codex CLI.
- OpenCode.

Funktionen:

- Installation beziehungsweise Verfügbarkeit prüfen.
- Version anzeigen.
- Login- oder API-Konfiguration einrichten.
- Authentifizierungsstatus prüfen.
- Verbindung möglichst mit einer harmlosen Probe verifizieren.

Bestehende native Authentifizierungsmechanismen verwenden.

Keine eigene API-Key-Datenbank entwickeln.

**Schritt 3: GitHub verbinden**

Vorgesehener GitHub-Account: `geco91`.

Funktionen:

- GitHub-Anmeldung vorbereiten.
- `git` und `gh` konfigurieren.
- Authentifizierungsstatus prüfen.
- Repository-Berechtigungen testen.
- SSH-/HTTPS-Git-Zugriff prüfen.
- Git-Identität konfigurieren.
- Fehler verständlich anzeigen.

Zugangsdaten dürfen nicht im OCI-Image oder Git-Repository landen.

**Schritt 4: Mac-Desktop verbinden**

Die WebUI hilft beim Einrichten des Orca-macOS-Clients.

- Serveradresse anzeigen.
- Pairing-Prozess erklären beziehungsweise auslösen.
- Pairing-Link bereitstellen, soweit unterstützt.
- Verbindungsprüfung.
- Statusanzeige.
- Weitere Clients hinzufügen ermöglichen.

**Schritt 5: Mobile-App verbinden**

Geführte Einrichtung der Orca-Mobile-App.

- QR-Code anzeigen, soweit offiziell unterstützt.
- Pairing initialisieren.
- Verbindung verifizieren.
- Hinweise zum Zugriff über LAN oder VPN.
- Bestehende Geräte anzeigen, soweit Orca dies ermöglicht.

**Schritt 6: MCP Bridge einrichten**

Einrichtung und Prüfung der Community-MCP-Bridge.

- Installation beziehungsweise Version kontrollieren.
- Konfiguration vornehmen.
- Dienst starten.
- MCP-Endpunkt prüfen.
- Erreichbarkeit validieren.
- Berechtigungsmodell anzeigen.
- Fehler diagnostizieren.

Keine allgemeine unsichere Fernadministrationsschnittstelle schaffen.

**Schritt 7: Secure MCP Tunnel verbinden**

Geführtes Setup für die Anbindung an die OpenAI-Welt.

Ziel:

ChatGPT / Tino / Codex-Koordinatoren
→ Secure MCP Tunnel
→ Orca MCP Bridge
→ Orca Runtime

Der Manager soll:

- Tunnel-Konfiguration vorbereiten.
- Benötigte Konfigurationswerte anzeigen.
- Sichere Initialisierung unterstützen.
- Verbindungsstatus anzeigen.
- Einen funktionalen MCP-Test ermöglichen.
- Fehler bei Authentifizierung und Verbindung diagnostizieren.

Verwende vorhandene Tunnelmechanismen und bestehende Konfigurationen.

Die vollständige Neuentwicklung des Secure MCP Tunnels ist nicht Teil dieses Projekts.

**Schritt 8: Fertigstellung**

Nach Abschluss der Einrichtung erscheint ein kompaktes Dashboard.

Dort werden angezeigt:

- Orca Server: bereit / Fehler.
- Coding-Agenten: konfiguriert / nicht konfiguriert.
- GitHub: verbunden / nicht verbunden.
- Mac-Client: verbunden / nicht verifiziert.
- Mobile-App: verbunden / nicht verifiziert.
- MCP Bridge: bereit / Fehler.
- Secure MCP Tunnel: verbunden / nicht eingerichtet.

Zeige nur Zustände an, die technisch überprüfbar sind.

Dazu die wichtigsten Aktionen:

- Orca öffnen.
- Verbindung erneut prüfen.
- Integration konfigurieren.
- Logs anzeigen.
- Einstellungen bearbeiten.

### Kein starrer Einrichtungszwang

Der Benutzer darf Schritte überspringen und später nachholen.

Orca selbst soll bereits nach erfolgreicher Basisinstallation verwendbar sein.

Fehlende optionale Verbindungen dürfen die grundlegende Orca-Runtime nicht blockieren.

## 6. Dauerhafte Verwaltungsfunktionen

Nach der Ersteinrichtung bleibt der Server Manager verfügbar.

Vorgesehene Bereiche:

- Overview
- Setup & Connections
- Agent Providers
- GitHub
- Remote Clients
- MCP Integration
- Server Settings
- Diagnostics

Ein separater vollständiger Linux-Systemmanager ist nicht erforderlich.

Sinnvolle Diagnosefunktionen:

- Orca-Version.
- Dienststatus.
- MCP-Status.
- Letzte Fehlermeldungen.
- Speicherplatz.
- RAM-Auslastung.
- Erreichbarkeit der relevanten Endpunkte.

Vermeide die Neuerfindung einer allgemeinen Serveradministration.

Wenn eine Funktion in Docker nicht sinnvoll verfügbar ist, zeige stattdessen nur die relevanten Container- beziehungsweise Anwendungsinformationen.

## 7. Web-Architektur

Die Management-WebUI soll unabhängig von Cockpit und Proxmox funktionieren.

Prüfe ein schlankes Framework mit möglichst wenigen Dependencies.

Bevorzuge etablierte Technologien, die gut in OCI-Containern funktionieren.

Eine kompakte serverseitige Anwendung mit einfacher Weboberfläche ist einer komplexen SPA-Architektur vorzuziehen, sofern sie die Anforderungen erfüllt.

Das UI soll sowohl am Desktop als auch auf Smartphones bedienbar sein.

### Ports und TLS

Vorgesehen:

- Port 80: HTTP → HTTPS-Weiterleitung.
- Port 443: Management-WebUI.
- Orca Headless: eigener konfigurierbarer Port.
- MCP Bridge: nur intern, soweit technisch möglich.

Bei der Erstinstallation soll ein Self-Signed-Zertifikat erzeugt werden.

Unterstütze:

- Hostnamen und IP-Adressen in SAN-Einträgen.
- Austausch durch eigene Zertifikate.
- Persistente Zertifikatsspeicherung.
- HTTPS als Standard.

Die grundlegende Webarchitektur muss auch unter Docker Compose funktionieren.

### Authentifizierung

Die Management-WebUI enthält sensible Verwaltungsfunktionen und muss diese schützen.

Bevorzugt:

- Kleine, etablierte Authentifizierungslösung.
- Initiale Administrator-Einrichtung.
- Sichere Session-Cookies.
- Schutz vor CSRF bei zustandsändernden Aktionen.
- Keine Klartextpasswörter.
- Zugriff ausschließlich über HTTPS, abgesehen vom HTTP-Redirect.

Eine später aktivierbare öffentliche Read-only-Statusansicht kann architektonisch vorgesehen werden, ist aber nicht Teil des MVP.

Kein Eigenbau eines umfangreichen Identitätsmanagementsystems.

## 8. OCI-Containerisierung

OCI ist das primäre Software-Artefakt.

Das Deployment soll möglichst einfach sein.

Angestrebter Ablauf:

1. OCI-Image beziehen oder bauen.
2. Persistente Volumes konfigurieren.
3. Container beziehungsweise Compose-Stack starten.
4. Management-WebUI im Browser öffnen.
5. Geführtes Setup durchführen.
6. Orca über die verbundenen Clients verwenden.

Erstelle:

- Containerfile beziehungsweise Dockerfile.
- Docker-Compose-Referenzkonfiguration.
- Environment-Konfiguration ohne Secrets.
- Dokumentation benötigter Volumes.
- Healthchecks.
- Definierte Restart-Strategie.

### Prozessarchitektur

Prüfe, ob Orca, Manager und MCP Bridge sinnvoll getrennte Container sein sollten.

Bevorzugt wird ein kleiner, nachvollziehbarer Compose-Stack mit klaren Komponenten.

Ein einzelner Container ist kein Selbstzweck.

Vermeide:

- Privileged Container.
- Unnötige Host-Mounts.
- Docker-Socket-Mounts.
- Unkontrollierte Root-Prozesse.
- Unnötige systemd-in-Container-Lösungen.

Es ist zu berücksichtigen, dass Coding-Agenten selbst weitere Prozesse starten und Entwicklungswerkzeuge benötigen.

Die Containerarchitektur muss dies ermöglichen, ohne unkontrollierten Host-Zugriff zu gewähren.

## 9. Proxmox als erste praktische Zielplattform

Der erste reale Einsatz soll auf einer eigenen VM unter Proxmox VE stattfinden.

Empfohlene VM-Ressourcen:

- 4 vCPU.
- 8 GB RAM.
- 40 GB Systemdisk.
- 60 GB Workspace-Speicher.
- Debian 13 Minimal.
- Keine grafische Desktopumgebung.

Diese Werte müssen anpassbar sein.

Eine kleinere Konfiguration mit 2 vCPU und 4 GB RAM soll möglich sein.

### Deployment-Konzept

Erstelle eine einfache Möglichkeit, die VM vorzubereiten und darin den OCI-Stack bereitzustellen.

Nutze vorhandene Proxmox- und Debian-Mechanismen.

Nicht erforderlich ist ein umfangreicher eigener Proxmox-Orchestrator.

### Native Proxmox-OCI-Unterstützung

Untersuche außerdem die OCI/LXC-Unterstützung von Proxmox VE ab Version 9.1.

Prüfe, ob unser OCI-Image dort direkt sinnvoll betrieben werden kann.

Falls dies technische oder sicherheitsrelevante Einschränkungen erzeugt, dokumentiere diese.

Die Debian-VM mit OCI-Runtime bleibt dann die Referenzvariante.

Eine vollständige Unterstützung beider Proxmox-Betriebsarten ist nicht zwingend Voraussetzung für den ersten MVP.

## 10. GitHub als gemeinsame Koordinationsplattform

Das System soll gemeinsam mit Codex Cloud und anderen Entwicklungsumgebungen genutzt werden können.

GitHub übernimmt die Koordination der Repositories.

Regeln:

- Unabhängige Arbeitsaufträge auf getrennten Branches.
- Lokale Git-Worktrees zur Isolation.
- Pull Requests für Integration.
- Geschützter Main-Branch, soweit möglich.
- Keine unkoordinierten parallelen Pushes auf denselben Branch.
- Keine ungeprüften automatischen Merges.
- GitHub Issues und PRs als langfristig nachvollziehbare Arbeitsergebnisse.

Die operative Agentensteuerung erfolgt über Orca.

Der Server Manager verwaltet lediglich die GitHub-Verbindung und diagnostiziert Authentifizierungsprobleme.

Keine eigene Git-Orchestrierungsplattform entwickeln.

## 11. MCP und externe Delegation

Ziel ist, dass externe KI-Koordinatoren auf der Orca-Runtime Agentenaufträge auslösen und deren Ergebnisse abrufen können.

Initial vorgesehen:

- ChatGPT / Tino.
- Codex-basierte Koordinatoren.
- Weitere kompatible MCP-Clients.

Prüfe die tatsächlich verfügbaren MCP-Tools der Community-Bridge.

Die Nutzung vorhandener MCP-Funktionen hat Vorrang vor Eigenentwicklung.

Sicherheitsanforderungen:

- Eingeschränkte Standardberechtigungen.
- Keine allgemeine Root-Fernsteuerung.
- Keine öffentliche MCP-Bridge ohne Schutz.
- Klare Authentifizierung.
- Externe Delegationsfunktionen nachvollziehbar dokumentieren.
- Agentenausführung von Serveradministration trennen.

Die Integration muss über den vorhandenen Secure MCP Tunnel realisierbar sein.

## 12. Sicherheit und Credentials

Sicherheit ist integraler Bestandteil des Setups.

Anforderungen:

- Agenten laufen unprivilegiert.
- Secrets niemals in Images oder Git.
- Credentials werden persistent und mit eingeschränkten Dateirechten gespeichert.
- GitHub-Zugänge möglichst eng begrenzen.
- Keine unkontrollierten Host-Freigaben.
- Keine beliebigen Root-Befehle über das Management-UI.
- Sichere und nachvollziehbare Setup-Aktionen.
- Keine Protokollierung sensibler Tokenwerte.

Berücksichtige besonders, dass KI-Agenten auf dem Server Code ausführen können.

Die Containergrenze ersetzt keine vollständige VM-Isolation.

Die Proxmox-VM ist deshalb für den ersten Pilotbetrieb die bevorzugte zusätzliche Sicherheitsgrenze.

## 13. Persistenz und Recovery

Folgende Daten sollen Container-Updates überleben:

- Orca-Konfiguration.
- Orca-Sessionzustand, soweit technisch möglich.
- Agent-Provider-Konfiguration.
- GitHub-Credentials.
- Remote-Client-Pairings.
- MCP-Konfiguration.
- Zertifikate.
- Git-Repositories und Worktrees.

Trenne persistente Daten von ersetzbaren Programmbestandteilen.

Dokumentiere:

- Backup.
- Wiederherstellung.
- Updates.
- Rollback.
- Umgang mit inkompatiblen Orca-Versionen.
- Wiederherstellung von Verbindungen nach einem Neustart.

Verwende bestehende Backupmechanismen.

Keine eigene komplexe Backupsoftware entwickeln.

## 14. Projektstruktur

Wähle eine einfache Struktur, beispielsweise:

- `container/` – OCI-Images.
- `compose/` – Docker-Compose-Konfiguration.
- `manager/` – eigenständige WebUI.
- `deploy/proxmox/` – Proxmox-Deployment.
- `scripts/` – Setup- und Wartungswerkzeuge.
- `config/` – Konfigurationsvorlagen.
- `docs/` – Architektur und Betriebsdokumentation.
- `tests/` – relevante Funktions- und Integrationstests.

Passe die Struktur an, wenn eine einfachere Aufteilung sinnvoller ist.

## 15. Arbeitsphasen und Prioritäten

### Phase 1 – Technische Validierung

- Orca-Headless-Anforderungen prüfen.
- Containerfähigkeit prüfen.
- MCP-Bridge prüfen.
- Portabilität der WebUI sicherstellen.
- Plattformstrategie dokumentieren.
- Repository auf GitHub anlegen.

### Phase 2 – Lauffähige OCI-Runtime

- Orca-OCI-Image bauen.
- Container starten.
- Persistenz prüfen.
- LAN-Verbindung ermöglichen.
- Headless-Betrieb verifizieren.

### Phase 3 – Setup-WebUI

- Eigenständigen Webmanager erstellen.
- HTTPS einrichten.
- Initialisierung und Serverstatus anzeigen.
- Guided-Setup-Mechanik umsetzen.
- Provider- und GitHub-Konfiguration vorbereiten.

### Phase 4 – Verbindungen

- macOS-Client-Pairing.
- Mobile-App-Pairing.
- GitHub-Authentifizierung.
- Codex-/OpenCode-Konfiguration.
- MCP-Bridge.
- Secure MCP Tunnel.

### Phase 5 – Proxmox

- VM-basierte Bereitstellung automatisieren.
- OCI-Stack auf Debian installieren.
- Native Proxmox-OCI/LXC-Kompatibilität prüfen.
- Betriebsanleitung erstellen.

### Phase 6 – Abnahmetests

Prüfe möglichst real:

- OCI-Image lässt sich bauen.
- Container starten und sind erreichbar.
- WebUI funktioniert über HTTPS.
- Statusanzeigen melden reale Zustände.
- Persistenz über Neustarts funktioniert.
- Mac-Client kann verbunden werden.
- Mobile-App kann verbunden werden.
- Ein Coding-Agent kann gestartet werden.
- GitHub-Branch-/PR-Workflow funktioniert.
- MCP-Delegation funktioniert.
- Tunnelverbindung funktioniert.

Keine überdimensionierten Test-Harnesses oder künstlichen Mock-Infrastrukturen entwickeln.

Fehlende Zugänge und Testumgebungen offen dokumentieren. Keine nicht ausgeführten Tests als erfolgreich melden.

## 16. Repository-Erstellung und Arbeitsregeln

Verifiziere den GitHub-Account:

`geco91`

Erstelle das private Repository:

`geco91/orca-server-manager`

Initialisiere:

- README.
- Lizenzentscheidung dokumentieren, aber Veröffentlichung vorerst zurückstellen.
- `.gitignore`.
- Projektstruktur.
- Architektur-Dokumentation.
- Konfigurationsbeispiele ohne Secrets.

Verwende Feature-Branches und Pull Requests.

Keine Änderungen an bestehender produktiver Proxmox-Infrastruktur ohne separate Freigabe.

Keine eigenständige öffentliche Repository-Veröffentlichung.

### Optimistic-MVP-Mandat

Arbeite selbstständig und ergebnisorientiert.

- Triff normale technische Entscheidungen selbst.
- Hinterfrage unnötige Dependencies.
- Bevorzuge robuste, einfache Lösungen.
- Nutze etablierte Werkzeuge.
- Vermeide Eigenbau, wenn vorhandene Komponenten ausreichen.
- Setze keine neuen Sicherheits- oder Berechtigungsgrenzen ohne Freigabe außer Kraft.
- Halte den Implementierungsaufwand proportional zum Nutzen.
- Arbeite bis zum nächsten belastbaren Ergebnis weiter.
- Verliere dich nicht in unnötigen Tests, Abstraktionen oder Frameworks.

## 17. Erwartete Ergebnisse

Erstelle möglichst:

1. Privates GitHub-Repository `geco91/orca-server-manager`.
2. Überprüfte und dokumentierte Architektur.
3. Funktionierenden Orca-OCI-Kern.
4. Docker-Compose-Deployment.
5. Schlanke eigenständige Management-WebUI.
6. Geführten Setup-Prozess.
7. HTTPS auf Port 443 und HTTP-Redirect auf Port 80.
8. GitHub- und Agent-Provider-Integration.
9. Mac-/Mobile-Pairing-Unterstützung.
10. MCP-Bridge und Secure-MCP-Tunnel-Anbindung.
11. Proxmox-VM-Deployment.
12. Tests, Dokumentation und Recovery-Anleitung.

Falls Funktionen wegen fehlender Zugänge, inkompatibler APIs oder anderer Voraussetzungen nicht vollständig implementierbar sind, liefere die funktionierenden Teile aus und dokumentiere die Einschränkungen.

## 18. Abschluss und Berichterstattung

Berichte am Ende:

- GitHub-Repository-URL.
- Gewählte technische Architektur.
- Tatsächlich implementierte Funktionen.
- Getestete OCI-/Docker-/Proxmox-Betriebsarten.
- Ergebnisse der Orca-Client-Verbindungstests.
- MCP-Integrationsstatus.
- Offene Risiken und Einschränkungen.
- Nächste sinnvolle Schritte.

**Beginne mit der Repository-Erstellung und einer kurzen technischen Validierung. Anschließend implementiere den kleinstmöglichen funktionierenden OCI-Server mit Management-WebUI und arbeite schrittweise bis zum belastbaren MVP weiter.**

Ziel ist eine portable Orca-Serverplattform, deren technische Inbetriebnahme und Integration über eine moderne, leicht verständliche Weboberfläche möglich ist.

Orca selbst bleibt die operative Entwicklungsumgebung. Der Orca Server Manager macht Einrichtung, Verbindung und Betrieb einfach.
