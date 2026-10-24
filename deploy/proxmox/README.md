# Referenz: Debian-VM unter Proxmox

In dieser Aufgabe wurde keine Proxmox-Infrastruktur verändert oder VM provisioniert.
Die folgenden Schritte sind eine vorbereitete Anleitung, keine ausgeführte Abnahme.

Eine dedizierte Debian-13-Minimal-VM verwenden. Startwerte: 4 vCPU, 8 GB RAM,
40 GB Systemdisk, 60 GB separater Workspace-Datenträger. Kleinere Piloten mit
2 vCPU und 4 GB RAM sind möglich, Agentjobs und `ORCA_MEMORY_LIMIT` passend begrenzen.
Keine grafische Desktopumgebung nötig. Backup und Firewall über vorhandene
Proxmox-/Debian-Verfahren betreiben.

1. VM über vorhandene Proxmox-Verwaltung anlegen. Keine produktiven Systeme ersetzen.
2. Im **Gast** das Vorbereitungsskript lesen und bewusst als root ausführen:
   `bash deploy/proxmox/prepare-debian.sh --apply`.
3. Repository mit dem eigenen GitHub-Zugang im Gast auschecken. README-Schnellstart
   befolgen. Zertifikats-SAN und `.env` auf die LAN/VPN-Adresse abstimmen.
4. Workspace-Volume auf den vorgesehenen Datenträger legen. Host-Bindmounts nur
   für explizite Datenverzeichnisse; UID/GID 1000 und minimale Rechte erhalten.
5. Healthchecks, HTTPS, Administrator, Provider-Login, Pairing und Neustart testen.
   Backup und Restore in einer Testinstanz prüfen, bevor produktive Nutzung beginnt.

OCI/LXC ab Proxmox 9.1 ist ein separater Prüfpfad. Compose-Diensttrennung,
Netzwerknamespace der Bridge, UID-Zuordnung, native Addons, Init-/Signalverhalten
und Volume-Pfade sind dort explizit zu validieren. Kein privilegierter LXC als
Workaround. Bis zur echten Abnahme bleibt die VM mit Docker die Referenzvariante.
Podman ist ebenfalls noch nicht getestet; besonders `network_mode: service:runtime`
und Compose-Secrets benötigen einen tatsächlichen Kompatibilitätstest.
