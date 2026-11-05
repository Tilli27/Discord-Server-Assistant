from __future__ import annotations

import re
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

from database import Database
from cogs.roleplay import allowed


class ProfileFieldExtensions(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot, self.db = bot, db

    @staticmethod
    def parse_https_url(value: str) -> bool:
        parsed = urlparse(value.strip())
        return parsed.scheme == "https" and bool(parsed.netloc) and " " not in value

    async def add_field_role(self, interaction: discord.Interaction, feld_id: int, rolle: discord.Role):
        if not await allowed(self.db, interaction, "felder_verwalten"):
            return await interaction.response.send_message("Dafür hast du keine Berechtigung.", ephemeral=True)
        field = await self.db.fetchone(
            "SELECT name FROM profile_fields WHERE guild_id=? AND id=? AND field_type='role' AND active=1",
            (interaction.guild_id, feld_id),
        )
        if not field:
            return await interaction.response.send_message("Aktives Rollenfeld nicht gefunden.", ephemeral=True)
        await self.db.execute(
            "INSERT OR IGNORE INTO field_role_options(field_id,guild_id,role_id) VALUES(?,?,?)",
            (feld_id, interaction.guild_id, rolle.id),
        )
        await interaction.response.send_message(
            f"{rolle.mention} wurde als Auswahl für das Steckbrief-Feld **{field['name']}** hinzugefügt.", ephemeral=True
        )

    async def remove_field_role(self, interaction: discord.Interaction, feld_id: int, rolle: discord.Role):
        if not await allowed(self.db, interaction, "felder_verwalten"):
            return await interaction.response.send_message("Dafür hast du keine Berechtigung.", ephemeral=True)
        _, count = await self.db.execute(
            "DELETE FROM field_role_options WHERE guild_id=? AND field_id=? AND role_id=?",
            (interaction.guild_id, feld_id, rolle.id),
        )
        await interaction.response.send_message(
            "Rolle aus den Feldoptionen entfernt." if count else "Diese Rolle war für das Feld nicht hinterlegt.",
            ephemeral=True,
        )

    async def list_field_roles(self, interaction: discord.Interaction, feld_id: int):
        if not await allowed(self.db, interaction, "felder_verwalten"):
            return await interaction.response.send_message("Dafür hast du keine Berechtigung.", ephemeral=True)
        field = await self.db.fetchone(
            "SELECT name FROM profile_fields WHERE guild_id=? AND id=? AND field_type='role' AND active=1",
            (interaction.guild_id, feld_id),
        )
        if not field:
            return await interaction.response.send_message("Aktives Rollenfeld nicht gefunden.", ephemeral=True)
        rows = await self.db.fetchall(
            "SELECT role_id FROM field_role_options WHERE guild_id=? AND field_id=? ORDER BY role_id",
            (interaction.guild_id, feld_id),
        )
        roles = [interaction.guild.get_role(row["role_id"]) for row in rows] if interaction.guild else []
        mentions = [role.mention for role in roles if role]
        text = ", ".join(mentions) if mentions else "Noch keine Rollenoptionen hinterlegt. Ohne Optionen sind alle Serverrollen auswählbar."
        await interaction.response.send_message(f"**{field['name']}**: {text}", ephemeral=True)

    async def set_profile_link(self, interaction: discord.Interaction, feld_id: int, url: str):
        field = await self.db.fetchone(
            "SELECT name FROM profile_fields WHERE guild_id=? AND id=? AND field_type='link' AND active=1",
            (interaction.guild_id, feld_id),
        )
        if not field:
            return await interaction.response.send_message("Aktives Link-Feld nicht gefunden.", ephemeral=True)
        if len(url) > 1000 or not self.parse_https_url(url):
            return await interaction.response.send_message("Bitte eine gültige HTTPS-Adresse angeben.", ephemeral=True)
        await self.db.execute(
            "INSERT INTO profile_values(guild_id,user_id,field_id,value) VALUES(?,?,?,?) "
            "ON CONFLICT(guild_id,user_id,field_id) DO UPDATE SET value=excluded.value",
            (interaction.guild_id, interaction.user.id, feld_id, url.strip()),
        )
        await self.db.execute(
            "INSERT INTO profiles(guild_id,user_id,published) VALUES(?,?,0) "
            "ON CONFLICT(guild_id,user_id) DO UPDATE SET published=0,updated_at=CURRENT_TIMESTAMP",
            (interaction.guild_id, interaction.user.id),
        )
        await interaction.response.send_message(
            f"Link für **{field['name']}** gespeichert. Dein Profil ist nun privat; prüfe `/profil vorschau`.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot, db: Database):
    cog = ProfileFieldExtensions(bot, db)
    await bot.add_cog(cog)

    # Extend the existing /feld group so field types and role options live together.
    field_group = bot.tree.get_command("feld")
    if isinstance(field_group, app_commands.Group):
        create_command = field_group.get_command("erstellen")
        if isinstance(create_command, app_commands.Command) and "typ" in create_command._params:
            parameter = create_command._params["typ"]
            if not any(choice.value == "link" for choice in parameter.choices):
                parameter.choices = [*parameter.choices, app_commands.Choice(name="link", value="link")]

        role_group = app_commands.Group(name="rollen", description="Discord-Rollenauswahl für Rollenfelder verwalten")
        role_group.add_command(app_commands.Command(
            name="hinzufuegen", description="Eine Discord-Rolle als Feldoption hinzufügen",
            callback=cog.add_field_role,
        ))
        role_group.add_command(app_commands.Command(
            name="entfernen", description="Eine Discord-Rollenoption entfernen",
            callback=cog.remove_field_role,
        ))
        role_group.add_command(app_commands.Command(
            name="liste", description="Rollenoptionen eines Rollenfeldes anzeigen",
            callback=cog.list_field_roles,
        ))
        field_group.add_command(role_group)

    link_command = app_commands.Command(
        name="steckbrief-link", description="Einen HTTPS-Link in einem eigenen Link-Feld speichern",
        callback=cog.set_profile_link,
    )
    bot.tree.add_command(link_command)
