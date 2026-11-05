from __future__ import annotations

import discord
from discord.ext import commands
import config
from database import Database
from cogs.roleplay import setup as setup_roleplay
from cogs.profile_browse import setup as setup_profile_browse

class RoleplayBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database(config.DATABASE_PATH)

    async def setup_hook(self) -> None:
        await self.db.initialize()
        await setup_roleplay(self, self.db)
        await setup_profile_browse(self, self.db)
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        print(f"Angemeldet als {self.user} (ID: {self.user.id})")

def main():
    config.validate_config()
    RoleplayBot().run(config.TOKEN, log_handler=None)

if __name__ == "__main__":
    main()
