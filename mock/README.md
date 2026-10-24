# Interaktive WebUI-Demo

```bash
python3 scripts/export-mock.py
```

Die erzeugte Datei `dist/orca-manager-mock.html` lokal im Browser öffnen. Sie
funktioniert vollständig offline und benötigt weder einen Webserver noch ein
Konto. Der Zustand bleibt nur im geöffneten Tab und wird beim Neuladen verworfen.

Durchspielbar sind alle sieben Einrichtungsschritte, einzelne optionale
Provider, Geräte-Pairing als Vorschau, Überspringen, Wiederaufnahme und eine
Zusammenfassung. Über „Szenario“ lassen sich eine Neuinstallation, eine komplett
eingerichtete Instanz sowie Runtime- und Tunnel-Fehler auswählen und beheben.

Die Demo verwendet das vorhandene Manager-Stylesheet, erweitert aber bewusst die
Bedienung zu einem interaktiven Prototyp. Die laufende Anwendung erhält dadurch
keinen Mock-Schalter, keine Testzugänge und keine Änderungen an ihrer Anmeldung.
Die simulierten Verbindungsaktionen sind noch keine implementierten nativen
Einrichtungsfunktionen. Auch die QR-Darstellung ist kein scannbarer Pairing-Code.

Der HTML-Export enthält keine externen Ressourcen. Seine Content Security Policy
verhindert Netzwerkaufrufe und Formularversand. Keine Secrets eingeben.
