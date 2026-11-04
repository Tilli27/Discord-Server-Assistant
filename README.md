# Individueller Discord-Rollenspielbot

Modularer Discord-Bot für Rollenspielserver mit `discord.py`, SQLite und Slash-Befehlen. Profile, Felddefinitionen, Helferrechte, Kategorien und Notizen werden dauerhaft gespeichert. Der Bot-Token darf ausschließlich in Umgebungsvariablen oder einer nicht committeten `.env`-Datei liegen.

## Voraussetzungen

- Python 3.10 oder neuer
- Discord-App/Bot im Discord Developer Portal
- OAuth-Scopes `bot` und `applications.commands`; Berechtigungen zum Senden von Nachrichten und Einbetten von Links
- Für die Member-Intent-Funktion die Server Members Intent im Developer Portal aktivieren

## Lokal installieren

```bash
git clone https://github.com/Tilli27/Discord-Server-Assistant.git
cd Discord-Server-Assistant
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
```

Trage den Token in `.env` ein und starte mit `python main.py`. `.env` und die SQLite-Datenbank sind in `.gitignore` ausgeschlossen. Wenn `GUILD_ID` gesetzt ist, synchronisiert der Bot Befehle sofort für den angegebenen Testserver. Ohne diese Variable erfolgt globale Synchronisierung.

## Wispbyte

Installiere `requirements.txt`, setze `DISCORD_TOKEN` und optional `GUILD_ID` in den Umgebungsvariablen des Hosters und nutze `python main.py` als Startbefehl. `DATABASE_PATH` muss auf einen persistenten Speicherort zeigen, der Bot-Neustarts übersteht.

## Slash-Befehle

- `/helfer berechtigung`: Serverinhaber vergibt oder entzieht einzeln Rechte für Rollen.
- `/feld erstellen`, `/feld umbenennen`, `/feld einstellungen`, `/feld liste`, `/feld entfernen`: dynamische Profilfelder (Text, Zahl, Rolle, Bild). Entfernen deaktiviert das Feld und behält gespeicherte Werte.
- `/profil bearbeiten`: privates Modal für bis zu fünf Text-/Zahlenfelder. `/profil setzen` setzt einzelne Felder und unterstützt Bildanhänge/Rollen. `/profil vorschau` zeigt die private Vorschau samt Veröffentlichungsbutton. Änderungen stellen das Profil auf privat zurück.
- `/profil ansehen` öffnet veröffentlichte Profile; `/profil suche` durchsucht nur ausdrücklich freigegebene Felder.
- `/notiz kategorie`, `/notiz kategorien`, `/notiz einreichen`, `/notiz meine`, `/notiz offen`, `/notiz entscheidung`, `/notiz bearbeiten`.

Nutze `/feld liste`, um Feld-IDs zu sehen. Für die Suche muss das Feld mit `/feld einstellungen` auf `filterbar: true` gesetzt sein. Für Rollenfelder gib eine Rollen-Erwähnung oder ID ein.

## Berechtigungen und Daten

Serverinhaber haben grundsätzlich alle Rechte. Nur der Serverinhaber kann Helferrollen-Rechte vergeben oder entziehen. Prüfrechte werden bei Aktionen serverseitig kontrolliert. Spieler können nur eigene Profile bearbeiten. SQLite wird beim Start initialisiert; erstelle regelmäßige Backups des persistenten Datenverzeichnisses.

## Dateien

`main.py` startet und konfiguriert den Bot; `config.py` lädt Umgebungsvariablen; `database.py` enthält SQLite-Schema und Zugriffe; `cogs/roleplay.py` enthält Profil-, Helfer-, Such- und Notizbefehle.
