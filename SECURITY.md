# Sicherheitsmodell

Der Manager ist eine Verwaltungsoberfläche für vertrauenswürdige Betreiber.
Orca und Coding-Agenten können beliebigen Code mit den Rechten des Runtime-
Benutzers ausführen. Authentifizierte MCP-Delegation kann das mittelbar ebenfalls.
Container ersetzen keine zusätzliche VM-Isolation. Kein Mehrmandantenbetrieb.

- UID 1000, keine Host-Gerätemounts, kein Docker-Socket, kein Host-Netzwerk,
  keine privilegierten Container, keine Container-Capabilities.
- Separate Manager- und Runtime-Daten. Die WebUI besitzt keinen CLI-/Shell-
  Ausführungsendpunkt und keinen Zugriff auf die Credentials der Runtime.
- Ausschließlich HTTPS für Management, CSRF für Änderungen, sichere Cookies,
  vertrauenswürdige Hostnamen und initialer Einmaltoken aus einem lokalen Terminal.
- Der HTTP-Manager-Port bleibt im privaten Compose-Netz. Nur Caddy darf den
  vertrauten Forwarded-Proto-Header liefern. Kein direktes Publishing von 8080.
- Interner Orca-Port und Bridge sind ein anderer Vertrauensbereich als das
  Administrator-Login. Die Bridge ist standardmäßig nur lesend; ihr Token ist
  nicht das Manager-Passwort. Keine öffentliche Bridge ohne geprüften Tunnel.
- TLS- und Artefaktprüfung bleiben aktiv. CA-Bundles der Cloud werden nur
  während des Builds gemountet beziehungsweise bei Bedarf zur Laufzeit lesend
  eingebunden. Keine Secrets in Images, Git oder Testausgaben.

Die globale Login-Sperre ist ein einfacher Schutz für die Pilotinstallation,
kein verteilter Schutz gegen Angriffe. Wiederherstellung erfolgt lokal mit
`flask --app manager.app reset-admin`. MFA, Mandantenrollen, automatisierte
Credential-Rotation und öffentlicher Betrieb sind kein abgenommener MVP-Umfang.

Sicherheitsprobleme vertraulich an den Repository-Eigentümer melden, keine
Zugangsdaten in öffentliche Issues einfügen. Das Repository soll bis zur
gesonderten Veröffentlichungsfreigabe privat bleiben.
