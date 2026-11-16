# Interaktiver UI-Prototyp

```bash
python3 scripts/export-mock.py
```

Die erzeugte Datei `dist/orca-manager-mock.html` lokal im Browser öffnen. Sie
funktioniert vollständig offline und benötigt weder Webserver noch Konto. Alle
Zustände bleiben im geöffneten Tab; Neuladen oder Zurücksetzen verwirft sie.

## Konzept vom 16. November 2026

- Übersicht, optionale Verbindungen und Versionen sind getrennte Bereiche. Es
  gibt keinen verpflichtenden Fortschritt über alle Integrationen.
- Provider-Konten und Geräte werden in Orca beziehungsweise mit den nativen
  Werkzeugen eingerichtet. Der Manager zeigt Anleitungen und liest Status.
  Der aktuelle native Pairing-Befehl braucht keinen Runtime-Neustart.
- GitHub ist optional für Repositories, Pushes und Pull Requests. Die
  GitHub-Anmeldung gehört auf den Server; sie ist keine Voraussetzung für
  Orca, Tunnel oder öffentliche Releases.
- Die externe Steuerung verwendet die separate Community-MCP-Bridge und den
  bereits festgelegten OpenAI Secure MCP Tunnel. Eine native MCP-Integration
  für Orcas Agenten ist eine andere Verbindungsrichtung.
- Die Versionsliste übernimmt Orcas Release-Angaben ohne eigene
  Stabilitätsbewertung, Freigabeliste oder vorgelagerte Versionsabnahme.
  Der Nutzer wählt seine Zielversion und erprobt sie nach dem Wechsel selbst.
- Für Proxmox-OCI zeigt der Ablauf Image-Vorbereitung, konsistente Sicherung,
  Containerwechsel und Start. Die technische Bereitstellung eines Images ist
  keine Versionsfreigabe. Das ist eine UI-Vorschau, kein implementierter
  Proxmox-Updater.
- Der Rücksprung bietet getrennt Softwarewechsel und Wiederherstellung des
  gesicherten Datenstands an. Das Zurücksetzen von Daten verwirft spätere
  Änderungen; ein reiner Softwarewechsel macht keine Migration rückgängig.

## Durchspielen

1. Mit dem ersten Szenario den Server prüfen. Optionale Verbindungen bleiben
   unabhängig davon offen.
2. Eine Verbindung öffnen und ihre native Anleitung lesen. Unter „Demo steuern“
   einen Zustand außerhalb des Managers wählen. Das Dashboard übernimmt ihn
   erst nach „Status erneut prüfen“; frühere Ergebnisse werden als veraltet
   markiert. Auch „gekoppelt, aber offline“ ist ein eigener Zustand.
3. Unter „Versionen & Updates“ eine beliebige angebotene Zielversion wählen
   und den Wechsel starten. Während des Ablaufs können andere Ansichten
   geöffnet werden. Keine weitere Versionsfreigabe oder Teststufe folgt.
4. Nach dem Wechsel eine Datenänderung simulieren und den Rücksprung öffnen.
   Software allein und Software mit Datenrestore lassen sich getrennt
   durchspielen. Nur beim Datenrestore wird die Änderung verworfen.
5. Die Szenarien für einen fehlgeschlagenen Start, laufende Agentaufträge und
   einen nicht erreichbaren Tunnel verwenden. Ein Rücksprung bleibt auch bei
   nicht erreichbarer Runtime zugänglich.

Die Versionsdaten sind ein fester Snapshot der offiziellen Orca-Releases vom
16. November 2026 (1.4.257, 1.4.258, 1.4.259 und 1.4.261), keine Live-Abfrage.
Die Demo beginnt mit der bisher im Projekt verwendeten Version 1.4.239.
Veröffentlichungsdaten und Release-Hinweise verlinken auf Orcas Quellen.

Die vorhandene Manager-Anwendung und ihre Anmeldung bleiben unverändert. Der
Prototyp hat keine echten Login-, Pairing-, Update- oder Backup-Funktionen und
belegt keine Produktionsbereitschaft der dargestellten Proxmox-Integration.
Die Content Security Policy verhindert Netzwerkaufrufe und Formularversand;
explizit geöffnete Dokumentationslinks führen zum jeweiligen Projekt.

## Quellen

- [Offizielle Orca-Releases](https://github.com/stablyai/orca/releases)
- [Native Account-Befehle](https://github.com/stablyai/orca/blob/v1.4.261/src/cli/specs/account.ts)
- [Pairing ohne Neustart](https://github.com/stablyai/orca/blob/v1.4.261/src/cli/specs/pair.ts)
- [Orca-Server und Serverpakete](https://github.com/stablyai/orca/blob/v1.4.261/docs/site/content/docs/remote-servers.mdx)
- [Community-MCP-Bridge](https://github.com/BuildContext/orca-mcp)
- [Proxmox-OCI-Dokumentation](https://github.com/proxmox/pve-docs/blob/master/pct.adoc)
