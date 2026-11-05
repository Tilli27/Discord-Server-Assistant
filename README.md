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

## Steckbrieffelder

- `/feld erstellen name typ pflicht filterbar` unterstützt `text`, `number`, `role`, `image` und `link`. Der Typ `role` bedeutet, dass Spieler für das Feld eine Discord-Rolle auswählen; `image` nimmt Bilddateien auf und `link` HTTPS-Adressen.
- `/feld rollen hinzufuegen feld_id rolle`, `/feld rollen entfernen feld_id rolle` und `/feld rollen liste feld_id` verwalten die erlaubten Discord-Rollen direkt unter dem Feld-Menü. Nur der Serverinhaber und Rollen mit `felder_verwalten` dürfen das.
- `/steckbrief-rolle feld_id rolle` setzt ein eigenes Rollenfeld. Sind Optionen für dieses Feld konfiguriert, kann nur eine davon verwendet werden.
- `/steckbrief-link feld_id url` speichert einen HTTPS-Link in einem Link-Feld.
- Die Datenbank aktualisiert das Feldtyp-Schema beim Start, erhält bestehende Feld-IDs und gespeicherte Werte.

## Steckbriefe und Gruppen

- `/steckbrief-alle` zeigt veröffentlichte Profile als Dropdown; die Auswahl öffnet den gewählten Steckbrief.
- `/steckbrief-suche feld_id wert` sucht nur in freigegebenen Feldern und zeigt private Ergebnisse.
- `/steckbrief-gruppe` öffnet ein privates Dropdown mit den bestehenden Gruppen.
- `/gruppe erstellen name farbe`, `/gruppe farbe gruppen_id farbe`, `/gruppe liste` und `/gruppe zuweisen spieler gruppen_id` verwalten Gruppen und ihre HEX-Farben.
- Profiländerungen setzen ein veröffentlichtes Profil zurück auf privat.

Weitere Befehle: `/profil bearbeiten`, `/profil setzen`, `/profil vorschau`, `/profil ansehen`, `/profil suche`, `/helfer berechtigung` und `/notiz ...`.
