# Win Challenge

Passwortgeschützte Website mit einer gemeinsamen Spiele-Liste. Alle eingeloggten
Nutzer sehen und bearbeiten dieselbe Liste live (WebSocket-Sync). Jedes Spiel
kann entweder **Gesamt-Siege** (z.B. 10 Siege insgesamt) oder **Siege am
Stück** (z.B. 4 in Folge, "B4B") als Ziel haben. Ist das Ziel erreicht, wird
der Eintrag grün markiert. Details zu allen Funktionen: [CHANGELOG.md](CHANGELOG.md).

## Lokal starten

1. Virtuelle Umgebung anlegen und Abhängigkeiten installieren:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. `.env.example` zu `.env` kopieren und `APP_PASSWORD` sowie `SECRET_KEY` anpassen.
   `DATABASE_URL` kann lokal leer bleiben – dann wird automatisch eine lokale
   SQLite-Datei (`winchallenge.db`) verwendet. `COOKIE_SECURE` lokal auf
   `false` lassen (siehe Sicherheitshinweise).
3. Server starten:
   ```powershell
   uvicorn app.main:app --reload
   ```
4. Im Browser `http://localhost:8000` öffnen, Passwort eingeben.

Zum Testen des Live-Syncs zwei Browserfenster (oder eins im Inkognito-Modus)
öffnen und Änderungen in einem Fenster vornehmen.

## Neon einrichten (kostenlose, dauerhafte Postgres-Datenbank)

Neon speichert eure Spieleliste dauerhaft, unabhängig davon, wie oft der
Render-Dienst neu startet oder deployt wird.

1. Auf [neon.tech](https://neon.tech) gehen und **"Sign up"** klicken. Registrierung
   z.B. per GitHub- oder Google-Konto ist am schnellsten.
2. Nach dem Login öffnet sich der Dashboard-Assistent **"Create a project"**:
   - **Project name**: z.B. `win-challenge`
   - **Postgres version**: Standardwert lassen
   - **Region**: eine Region nahe bei euch wählen (z.B. Frankfurt/EU)
   - Auf **"Create project"** klicken.
3. Nach der Erstellung zeigt Neon direkt einen Bereich **"Connection string"**
   an (falls nicht sichtbar: im linken Menü **"Dashboard"** → oben auf
   **"Connect"** klicken).
4. Dort ist ein Dropdown **"Connection string"** – sicherstellen, dass es die
   Variante für z.B. `psql` / allgemein ist (keine spezielle Framework-Variante
   nötig). Die Zeile sieht ungefähr so aus:
   ```
   postgresql://<user>:<password>@<host>.neon.tech/<database>?sslmode=require
   ```
5. Diese komplette Zeile kopieren (Copy-Button daneben) – das ist der Wert für
   `DATABASE_URL`.
6. Diesen Wert in die eigene `.env` (lokal) und später als Umgebungsvariable
   bei Render (siehe unten) eintragen. Nichts an der Zeile verändern.

Das war's – Neon legt die Tabellen automatisch an, sobald die App das erste
Mal startet (`init_db()` in `app/main.py`).

> Hinweis Free-Plan: Neon pausiert eine inaktive Datenbank nach einer Weile
> automatisch ("Autosuspend") und weckt sie bei der nächsten Anfrage von
> selbst wieder auf (dauert wenige Sekunden). Die Daten bleiben dabei erhalten.

## Sicherheitshinweise

- `APP_PASSWORD` und `SECRET_KEY` unbedingt auf eigene, nicht erratbare Werte
  ändern, bevor die Seite öffentlich erreichbar ist (die App warnt beim Start
  in den Logs, falls noch Standardwerte aktiv sind).
- `COOKIE_SECURE=true` setzen, sobald die Seite über HTTPS läuft (z.B. auf
  Render) – sonst bleibt es auf `false`, sonst verwirft der Browser das
  Login-Cookie.
- `.env` niemals committen (ist bereits in `.gitignore`).
- Nach einem Passwort-/Secret-Wechsel müssen sich alle Nutzer neu einloggen.
- Der WebSocket prüft den `Origin`-Header gegen den aufgerufenen Host, um
  Cross-Site WebSocket Hijacking zu verhindern.
