# Changelog

## [1.0.0] – Erste Version

### Zugriff & Sicherheit
- Zugriff über ein gemeinsames Passwort, geschützt durch ein signiertes Session-Cookie (itsdangerous).
- Zeitkonstanter Passwortvergleich gegen Timing-Angriffe.
- `Origin`-Prüfung beim WebSocket-Handshake gegen Cross-Site WebSocket Hijacking.
- Konfigurierbares `Secure`-Cookie-Flag (`COOKIE_SECURE`) für den Betrieb hinter HTTPS.
- Warnung in den Server-Logs, falls Passwort/Secret-Key noch auf dem Standardwert stehen.

### Spiele-Liste & Live-Sync
- Gemeinsame Spiele-Liste, live synchronisiert über WebSockets zwischen allen verbundenen Nutzern.
- Persistente Speicherung per Datenbank (lokal SQLite, produktiv per `DATABASE_URL` z.B. Neon Postgres) inklusive automatischer Schema-Migrationen für neue Felder.
- Zwei Eintrags-Typen pro Spiel:
  - **Gesamt-Siege**: freie Anzahl an Siegen bis zum Ziel, mit +1/-1-Korrektur.
  - **Siege am Stück** ("B4B"): Serienzähler, der bei einer Niederlage auf 0 zurückgesetzt wird, statt nur -1 zu rechnen.
- Automatische grüne Hervorhebung, sobald das Ziel erreicht ist.
- Frei sortierbare Liste per Drag-and-Drop (Reihenfolge wird gespeichert und an alle Nutzer verteilt).
- Spielname und Zielanzahl können direkt in der Karte bearbeitet werden.
- Löschen und Serien-Reset erfordern eine Bestätigung über einen eigens gestalteten Dialog (kein natives Browser-Popup).
- Kurze Shake-/Rot-Animation auf der Karte, wenn eine Serie zurückgesetzt wird.

### Bedienung & Design
- Modernes, minimalistisches Dark-Theme.
- Mausrad über Zahlenfeldern ändert deren Wert nicht mehr versehentlich.
- Verbindungsstatus und Fehlermeldungen werden unterhalb der Spiele-Liste angezeigt.
- Automatischer WebSocket-Reconnect bei Verbindungsabbruch.

### Betrieb
- Enthält Dockerfile sowie Anleitung für kostenloses Hosting auf Render + Neon Postgres.
- Angepinnte Abhängigkeiten in `requirements.txt` für reproduzierbare Deployments.
