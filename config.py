from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.sqlite3")
GUILD_ID = int(os.environ["GUILD_ID"]) if os.getenv("GUILD_ID") else None


def validate_config() -> None:
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN fehlt. Lege die Umgebungsvariable in .env oder beim Hoster fest.")
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
