# Individueller Discord-Rollenspielbot

Modularer Discord-Bot für Rollenspielserver mit `discord.py`, SQLite und Slash-Befehlen. Profile, Felddefinitionen, Helferrechte, Gruppen, Kategorien und Notizen werden dauerhaft gespeichert. Bot-Tokens gehören ausschließlich in Umgebungsvariablen oder eine nicht committete `.env`.

## Installation

Benötigt Python 3.10+, einen Discord-Bot mit Scopes `bot` und `applications.commands`, sowie Nachrichten-/Embed-Berechtigungen. Für Member-Anzeigen den Server Members Intent aktivieren.

```bash
git clone https://github.com/Tilli27/Discord-Server-Assistant.git
cd Discord-Server-Assistant
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```
Setze `DISCORD_TOKEN` in `.env`; niemals Tokens committen. `GUILD_ID` kann für sofortige Slash-Befehl-Synchronisierung im Testserver verwendet werden.

## Wispbyte

Installiere `requirements.txt`, setze `DISCORD_TOKEN` und optional `GUILD_ID` in den Hoster-Umgebungsvariablen, nutze `python main.py` als Startbefehl und stelle sicher, dass `DATABASE_PATH` auf persistenten Speicher zeigt.

## Steckbriefe und Gruppen

- `/steckbrief-alle` zeigt veröffentlichte Profile öffentlich als Dropdown-Liste. Die Auswahl öffnet den gewählten Steckbrief privat; bei über 25 Treffern kann durch die Seiten geblättert werden.
- `/steckbrief-suche feld_id wert` sucht nur in freigegebenen Feldern. Ergebnisse und Dropdown sind ausschließlich für den Befehl-Aufrufer sichtbar; die Auswahl öffnet das Profil.
- `/steckbrief-gruppe` öffnet ein privates Dropdown mit den bestehenden Gruppen und den zugehörigen veröffentlichten Steckbriefen.
- `/gruppe erstellen name farbe` erstellt eine Gruppe mit HEX-Farbe; `/gruppe farbe gruppen_id farbe` ändert die Farbe; `/gruppe liste` zeigt IDs; `/gruppe zuweisen spieler gruppen_id` weist ein veröffentlichtes Profil zu.
- Gruppen- und Feldverwaltung ist dem Serverinhaber und Rollen mit `felder_verwalten` vorbehalten. Die Gruppenfarbe erscheint am Steckbrief.
- `/feldrolle hinzufuegen feld_id rolle` und `/feldrolle entfernen feld_id rolle` verwalten die erlaubten Discord-Rollen eines Rollenfeldes. `/steckbrief-rolle feld_id rolle` speichert eine ausgewählte Serverrolle im eigenen Profil. Wenn für das Feld erlaubte Rollen hinterlegt sind, können nur diese gewählt werden.

Bestehende Befehle bleiben verfügbar: `/profil bearbeiten`, `/profil setzen`, `/profil vorschau`, `/profil ansehen`, `/profil suche`, `/feld ...`, `/helfer berechtigung` und `/notiz ...`. Profiländerungen setzen ein veröffentlichtes Profil wieder auf privat. SQLite-Schemaerweiterungen werden beim Start mit `CREATE TABLE IF NOT EXISTS` ergänzt und löschen keine bestehenden Profilwerte.

## Projektdateien

- `main.py` – Start und Slash-Synchronisierung
- `config.py` – Umgebungsvariablen
- `database.py` – SQLite-Schema
- `cogs/roleplay.py` – Profile, Helfer, Notizen und Felder
- `cogs/profile_browse.py` – Steckbriefübersichten, Suche, Gruppen und Rollenoptionen
