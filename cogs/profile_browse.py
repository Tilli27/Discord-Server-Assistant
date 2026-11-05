from __future__ import annotations

import re

import discord
from discord import app_commands
from discord.ext import commands

from database import Database
from cogs.roleplay import allowed

PAGE_SIZE = 25


async def public_profile_embed(bot: commands.Bot, db: Database, guild_id: int, user_id: int) -> discord.Embed:
    profile = await db.fetchone(
        "SELECT published FROM profiles WHERE guild_id=? AND user_id=?", (guild_id, user_id)
    )
    if not profile or not profile["published"]:
        return discord.Embed(title="Profil nicht verfügbar", description="Dieses Profil ist nicht veröffentlicht.")

    rows = await db.fetchall(
        "SELECT f.name,f.field_type,v.value FROM profile_fields f "
        "JOIN profile_values v ON v.field_id=f.id AND v.guild_id=f.guild_id "
        "WHERE f.guild_id=? AND f.active=1 AND v.user_id=? ORDER BY f.position,f.id",
        (guild_id, user_id),
    )
    group = await db.fetchone(
        "SELECT g.name,g.color FROM profile_group_members m JOIN profile_groups g ON g.id=m.group_id "
        "WHERE m.guild_id=? AND m.user_id=?", (guild_id, user_id)
    )
    user = bot.get_user(user_id)
    if user is None:
        try:
            user = await bot.fetch_user(user_id)
        except discord.HTTPException:
            user = None
    embed = discord.Embed(
        title=f"Steckbrief · {user.display_name if user else user_id}",
        color=discord.Color(group["color"] if group else discord.Color.blurple().value),
    )
    if group:
        embed.description = f"Gruppe: **{group['name']}**"
    for row in rows:
        value = row["value"]
        if row["field_type"] == "image" and value.startswith(("https://", "http://")):
            embed.set_image(url=value)
        else:
            embed.add_field(name=row["name"][:256], value=value[:1024], inline=row["field_type"] != "text")
    if not rows:
        embed.add_field(name="Steckbrief", value="Noch keine Angaben eingetragen.", inline=False)
    return embed


class ProfileResultsSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, db: Database, rows: list[dict]):
        self.bot, self.db = bot, db
        start = rows[:PAGE_SIZE]
        options = [discord.SelectOption(label=r["name"][:100], value=str(r["user_id"])) for r in start]
        super().__init__(placeholder="Steckbrief öffnen …", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        embed = await public_profile_embed(self.bot, self.db, interaction.guild_id, int(self.values[0]))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ProfileResultsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, db: Database, rows: list[dict], *, title: str, ephemeral_owner: int | None = None):
        super().__init__(timeout=300)
        self.bot, self.db, self.rows = bot, db, rows
        self.title, self.page, self.ephemeral_owner = title, 0, ephemeral_owner
        self.add_item(ProfileResultsSelect(bot, db, rows))
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        page_rows = self.rows[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]
        if page_rows:
            self.add_item(ProfileResultsSelect(self.bot, self.db, page_rows))
        if self.page > 0:
            self.add_item(discord.ui.Button(label="Zurück", style=discord.ButtonStyle.secondary, custom_id="profiles:prev"))
        if (self.page + 1) * PAGE_SIZE < len(self.rows):
            self.add_item(discord.ui.Button(label="Weiter", style=discord.ButtonStyle.secondary, custom_id="profiles:next"))
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.callback = self._page_callback

    async def _page_callback(self, interaction: discord.Interaction):
        if self.ephemeral_owner is not None and interaction.user.id != self.ephemeral_owner:
            return await interaction.response.send_message("Dieses Suchfenster gehört einer anderen Person.", ephemeral=True)
        if interaction.data.get("custom_id") == "profiles:next":
            self.page += 1
        else:
            self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(content=self._content(), view=self)

    def _content(self) -> str:
        count = len(self.rows)
        return f"{self.title} · {count} Treffer (Seite {self.page + 1}/{max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)}). Wähle einen Steckbrief aus."


class GroupPicker(discord.ui.Select):
    def __init__(self, cog: "ProfileBrowse", groups: list):
        self.cog = cog
        super().__init__(placeholder="Gruppe auswählen …", options=[
            discord.SelectOption(label=row["name"][:100], value=str(row["id"]),
                                 description=f"Farbe #{row['color']:06X}") for row in groups[:25]
        ])

    async def callback(self, interaction: discord.Interaction):
        group_id = int(self.values[0])
        rows = await self.cog.group_profiles(interaction.guild_id, group_id)
        if not rows:
            return await interaction.response.send_message("In dieser Gruppe gibt es noch keine veröffentlichten Steckbriefe.", ephemeral=True)
        view = ProfileResultsView(self.cog.bot, self.cog.db, rows, title="Gruppen-Steckbriefe", ephemeral_owner=interaction.user.id)
        await interaction.response.edit_message(content=view._content(), view=view)


class GroupPickerView(discord.ui.View):
    def __init__(self, cog: "ProfileBrowse", groups: list):
        super().__init__(timeout=180)
        self.add_item(GroupPicker(cog, groups))


class ProfileBrowse(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot, self.db = bot, db

    async def all_profiles(self, guild_id: int) -> list[dict]:
        rows = await self.db.fetchall(
            "SELECT user_id FROM profiles WHERE guild_id=? AND published=1 ORDER BY updated_at DESC",
            (guild_id,),
        )
        result = []
        for row in rows:
            member = self.bot.get_guild(guild_id).get_member(row["user_id"]) if self.bot.get_guild(guild_id) else None
            result.append({"user_id": row["user_id"], "name": member.display_name if member else str(row["user_id"])})
        return result

    async def group_profiles(self, guild_id: int, group_id: int) -> list[dict]:
        rows = await self.db.fetchall(
            "SELECT p.user_id FROM profiles p JOIN profile_group_members m ON m.guild_id=p.guild_id AND m.user_id=p.user_id "
            "JOIN profile_groups g ON g.id=m.group_id AND g.guild_id=m.guild_id "
            "WHERE p.guild_id=? AND p.published=1 AND g.id=? ORDER BY p.updated_at DESC",
            (guild_id, group_id),
        )
        guild = self.bot.get_guild(guild_id)
        return [{"user_id": r["user_id"], "name": (guild.get_member(r["user_id"]).display_name if guild and guild.get_member(r["user_id"]) else str(r["user_id"]))} for r in rows]

    @app_commands.command(name="steckbrief-alle", description="Alle veröffentlichten Steckbriefe mit Auswahlmenü anzeigen")
    async def all_profiles_command(self, interaction: discord.Interaction):
        rows = await self.all_profiles(interaction.guild_id)
        if not rows:
            return await interaction.response.send_message("Es gibt noch keine veröffentlichten Steckbriefe.", ephemeral=True)
        view = ProfileResultsView(self.bot, self.db, rows, title="Alle veröffentlichten Steckbriefe")
        await interaction.response.send_message(view._content(), view=view)

    @app_commands.command(name="steckbrief-suche", description="Veröffentlichte Steckbriefe nach Filterfeld durchsuchen")
    async def search_profiles_command(self, interaction: discord.Interaction, feld_id: int, wert: str):
        field = await self.db.fetchone(
            "SELECT name FROM profile_fields WHERE guild_id=? AND id=? AND active=1 AND public_filter=1",
            (interaction.guild_id, feld_id),
        )
        if not field:
            return await interaction.response.send_message("Dieses Feld ist nicht für die öffentliche Suche freigegeben.", ephemeral=True)
        rows = await self.db.fetchall(
            "SELECT p.user_id FROM profiles p JOIN profile_values v ON v.guild_id=p.guild_id AND v.user_id=p.user_id "
            "WHERE p.guild_id=? AND p.published=1 AND v.field_id=? AND lower(v.value)=lower(?) ORDER BY p.updated_at DESC",
            (interaction.guild_id, feld_id, wert),
        )
        guild = interaction.guild
        results = [{"user_id": r["user_id"], "name": (guild.get_member(r["user_id"]).display_name if guild and guild.get_member(r["user_id"]) else str(r["user_id"]))} for r in rows]
        if not results:
            return await interaction.response.send_message("Keine veröffentlichten Steckbriefe mit dieser Eigenschaft gefunden.", ephemeral=True)
        view = ProfileResultsView(self.bot, self.db, results, title=f"{field['name']} = {wert}", ephemeral_owner=interaction.user.id)
        await interaction.response.send_message(view._content(), view=view, ephemeral=True)

    @app_commands.command(name="steckbrief-gruppe", description="Veröffentlichte Steckbriefe nach Gruppe durchsuchen")
    async def profiles_by_group(self, interaction: discord.Interaction):
        groups = await self.db.fetchall("SELECT id,name,color FROM profile_groups WHERE guild_id=? ORDER BY name", (interaction.guild_id,))
        if not groups:
            return await interaction.response.send_message("Es wurden noch keine Gruppen erstellt.", ephemeral=True)
        await interaction.response.send_message("Wähle eine Gruppe aus:", view=GroupPickerView(self, groups), ephemeral=True)

    group = app_commands.Group(name="gruppe", description="Steckbriefgruppen und ihre Farben verwalten")

    @group.command(name="erstellen", description="Eine Steckbriefgruppe mit Farbe erstellen")
    async def group_create(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 80], farbe: str = "#5865F2"):
        if not await allowed(self.db, interaction, "felder_verwalten"):
            return await interaction.response.send_message("Dafür hast du keine Berechtigung.", ephemeral=True)
        color = self.parse_color(farbe)
        if color is None:
            return await interaction.response.send_message("Farbe bitte als HEX-Wert angeben, zum Beispiel `#5865F2`.", ephemeral=True)
        try:
            group_id, _ = await self.db.execute("INSERT INTO profile_groups(guild_id,name,color) VALUES(?,?,?)", (interaction.guild_id, name, color))
        except Exception:
            return await interaction.response.send_message("Eine Gruppe mit diesem Namen existiert bereits.", ephemeral=True)
        await interaction.response.send_message(f"Gruppe **{name}** (`{group_id}`) mit Farbe `#{color:06X}` erstellt.", ephemeral=True)

    @group.command(name="farbe", description="Die Farbe einer Gruppe ändern")
    async def group_color(self, interaction: discord.Interaction, gruppen_id: int, farbe: str):
        if not await allowed(self.db, interaction, "felder_verwalten"):
            return await interaction.response.send_message("Dafür hast du keine Berechtigung.", ephemeral=True)
        color = self.parse_color(farbe)
        if color is None:
            return await interaction.response.send_message("Farbe bitte als HEX-Wert angeben, zum Beispiel `#FF8800`.", ephemeral=True)
        _, count = await self.db.execute("UPDATE profile_groups SET color=? WHERE guild_id=? AND id=?", (color, interaction.guild_id, gruppen_id))
        await interaction.response.send_message(f"Gruppenfarbe auf `#{color:06X}` gesetzt." if count else "Gruppe nicht gefunden.", ephemeral=True)

    @group.command(name="zuweisen", description="Einen veröffentlichten Steckbrief einer Gruppe zuweisen")
    async def group_assign(self, interaction: discord.Interaction, spieler: discord.Member, gruppen_id: int):
        if not await allowed(self.db, interaction, "felder_verwalten"):
            return await interaction.response.send_message("Dafür hast du keine Berechtigung.", ephemeral=True)
        group = await self.db.fetchone("SELECT id,name FROM profile_groups WHERE guild_id=? AND id=?", (interaction.guild_id, gruppen_id))
        profile = await self.db.fetchone("SELECT published FROM profiles WHERE guild_id=? AND user_id=?", (interaction.guild_id, spieler.id))
        if not group or not profile or not profile["published"]:
            return await interaction.response.send_message("Gruppe nicht gefunden oder Steckbrief nicht veröffentlicht.", ephemeral=True)
        await self.db.execute("INSERT INTO profile_group_members(guild_id,group_id,user_id) VALUES(?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET group_id=excluded.group_id", (interaction.guild_id, gruppen_id, spieler.id))
        await interaction.response.send_message(f"{spieler.mention} wurde der Gruppe **{group['name']}** zugewiesen.", ephemeral=True)

    @group.command(name="liste", description="Erstellte Gruppen samt IDs und Farben anzeigen")
    async def group_list(self, interaction: discord.Interaction):
        groups = await self.db.fetchall("SELECT id,name,color FROM profile_groups WHERE guild_id=? ORDER BY name", (interaction.guild_id,))
        text = "\n".join(f"`{r['id']}` · **{r['name']}** · `#{r['color']:06X}`" for r in groups) or "Noch keine Gruppen erstellt."
        await interaction.response.send_message(text[:1900], ephemeral=True)

    field_role = app_commands.Group(name="feldrolle", description="Erlaubte Discord-Rollen für Steckbrief-Rollenfelder verwalten")

    @field_role.command(name="hinzufuegen", description="Eine zulässige Discord-Rolle für ein Rollenfeld hinterlegen")
    async def field_role_add(self, interaction: discord.Interaction, feld_id: int, rolle: discord.Role):
        if not await allowed(self.db, interaction, "felder_verwalten"):
            return await interaction.response.send_message("Dafür hast du keine Berechtigung.", ephemeral=True)
        field = await self.db.fetchone("SELECT id,name,field_type FROM profile_fields WHERE guild_id=? AND id=? AND active=1", (interaction.guild_id, feld_id))
        if not field or field["field_type"] != "role":
            return await interaction.response.send_message("Das Feld existiert nicht oder ist kein Rollenfeld.", ephemeral=True)
        await self.db.execute("INSERT OR IGNORE INTO field_role_options(field_id,guild_id,role_id) VALUES(?,?,?)", (feld_id, interaction.guild_id, rolle.id))
        await interaction.response.send_message(f"{rolle.mention} ist jetzt für **{field['name']}** auswählbar.", ephemeral=True)

    @field_role.command(name="entfernen", description="Eine zulässige Rolle aus einem Rollenfeld entfernen")
    async def field_role_remove(self, interaction: discord.Interaction, feld_id: int, rolle: discord.Role):
        if not await allowed(self.db, interaction, "felder_verwalten"):
            return await interaction.response.send_message("Dafür hast du keine Berechtigung.", ephemeral=True)
        _, count = await self.db.execute("DELETE FROM field_role_options WHERE guild_id=? AND field_id=? AND role_id=?", (interaction.guild_id, feld_id, rolle.id))
        await interaction.response.send_message("Rolle aus den Feldoptionen entfernt." if count else "Diese Rolle war für das Feld nicht hinterlegt.", ephemeral=True)

    @app_commands.command(name="steckbrief-rolle", description="Eine Discord-Rolle in einem eigenen Rollenfeld speichern")
    async def set_profile_role(self, interaction: discord.Interaction, feld_id: int, rolle: discord.Role):
        field = await self.db.fetchone("SELECT id,name FROM profile_fields WHERE guild_id=? AND id=? AND field_type='role' AND active=1", (interaction.guild_id, feld_id))
        if not field:
            return await interaction.response.send_message("Aktives Rollenfeld nicht gefunden.", ephemeral=True)
        configured = await self.db.fetchone("SELECT 1 FROM field_role_options WHERE guild_id=? AND field_id=? LIMIT 1", (interaction.guild_id, feld_id))
        if configured:
            allowed_role = await self.db.fetchone("SELECT 1 FROM field_role_options WHERE guild_id=? AND field_id=? AND role_id=?", (interaction.guild_id, feld_id, rolle.id))
            if not allowed_role:
                return await interaction.response.send_message("Diese Rolle ist für das Feld nicht freigegeben.", ephemeral=True)
        await self.db.execute("INSERT INTO profile_values(guild_id,user_id,field_id,value) VALUES(?,?,?,?) ON CONFLICT(guild_id,user_id,field_id) DO UPDATE SET value=excluded.value", (interaction.guild_id, interaction.user.id, feld_id, rolle.mention))
        await self.db.execute("INSERT INTO profiles(guild_id,user_id,published) VALUES(?,?,0) ON CONFLICT(guild_id,user_id) DO UPDATE SET published=0,updated_at=CURRENT_TIMESTAMP", (interaction.guild_id, interaction.user.id))
        await interaction.response.send_message(f"Rolle {rolle.mention} in **{field['name']}** gespeichert. Dein Profil ist nun privat.", ephemeral=True)

    @staticmethod
    def parse_color(value: str) -> int | None:
        match = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
        return int(match.group(1), 16) if match else None


async def setup(bot: commands.Bot, db: Database):
    await bot.add_cog(ProfileBrowse(bot, db))
