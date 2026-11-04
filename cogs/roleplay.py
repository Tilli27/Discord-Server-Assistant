from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from database import Database

PERMISSIONS = {
    "notizen_bearbeiten": "Notizen anderer Spieler bearbeiten",
    "notizen_moderieren": "Notizen annehmen oder ablehnen",
    "kategorien_verwalten": "Kategorien erstellen und bearbeiten",
    "notizen_einreichen": "Eigene Notizen einreichen und bearbeiten",
    "felder_verwalten": "Steckbrief-Felder verwalten",
}


def owner(interaction: discord.Interaction) -> bool:
    return bool(interaction.guild and interaction.guild.owner_id == interaction.user.id)


async def allowed(db: Database, interaction: discord.Interaction, permission: str) -> bool:
    if owner(interaction):
        return True
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    roles = [role.id for role in interaction.user.roles]
    if not roles:
        return False
    marks = ",".join("?" for _ in roles)
    row = await db.fetchone(f"SELECT 1 FROM role_permissions WHERE guild_id=? AND permission=? AND role_id IN ({marks}) LIMIT 1", (interaction.guild_id, permission, *roles))
    return row is not None


async def denied(interaction: discord.Interaction):
    await interaction.response.send_message("Dafür hast du keine Berechtigung.", ephemeral=True)


class PublishView(discord.ui.View):
    def __init__(self, cog, user_id: int):
        super().__init__(timeout=300)
        self.cog, self.user_id = cog, user_id

    @discord.ui.button(label="Profil veröffentlichen", style=discord.ButtonStyle.success)
    async def publish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Dieses Fenster gehört einer anderen Person.", ephemeral=True)
        fields = await self.cog.db.fetchall("SELECT f.name,f.required,v.value FROM profile_fields f LEFT JOIN profile_values v ON v.field_id=f.id AND v.guild_id=f.guild_id AND v.user_id=? WHERE f.guild_id=? AND f.active=1", (self.user_id, interaction.guild_id))
        missing = [row['name'] for row in fields if row['required'] and not row['value']]
        if missing:
            return await interaction.response.send_message("Pflichtfelder fehlen: " + ", ".join(missing), ephemeral=True)
        await self.cog.db.execute("INSERT INTO profiles(guild_id,user_id,published) VALUES(?,?,1) ON CONFLICT(guild_id,user_id) DO UPDATE SET published=1,updated_at=CURRENT_TIMESTAMP", (interaction.guild_id, self.user_id))
        embed = await self.cog.profile_embed(interaction.guild_id, self.user_id)
        await interaction.response.send_message("Profil veröffentlicht.", ephemeral=True)
        if interaction.channel:
            await interaction.channel.send(embed=embed)
        self.stop()


class ProfileModal(discord.ui.Modal, title="Steckbrief bearbeiten"):
    def __init__(self, cog, fields):
        super().__init__(timeout=300)
        self.cog, self.fields_data = cog, fields
        for field in fields[:5]:
            self.add_item(discord.ui.TextInput(label=field['name'][:45], custom_id=f"field_{field['id']}", required=bool(field['required']), max_length=1000, style=discord.TextStyle.paragraph if field['field_type'] == 'text' else discord.TextStyle.short))

    async def on_submit(self, interaction: discord.Interaction):
        for item in self.children:
            value = str(item.value).strip()
            field_id = int(item.custom_id.removeprefix("field_"))
            if value:
                field = next(x for x in self.fields_data if x['id'] == field_id)
                if field['field_type'] == 'number':
                    try:
                        float(value)
                    except ValueError:
                        return await interaction.response.send_message(f"{field['name']} muss eine Zahl sein.", ephemeral=True)
                await self.cog.db.execute("INSERT INTO profile_values(guild_id,user_id,field_id,value) VALUES(?,?,?,?) ON CONFLICT(guild_id,user_id,field_id) DO UPDATE SET value=excluded.value", (interaction.guild_id, interaction.user.id, field_id, value))
        await self.cog.db.execute("INSERT INTO profiles(guild_id,user_id,published) VALUES(?,?,0) ON CONFLICT(guild_id,user_id) DO UPDATE SET published=0,updated_at=CURRENT_TIMESTAMP", (interaction.guild_id, interaction.user.id))
        embed = await self.cog.profile_embed(interaction.guild_id, interaction.user.id, preview=True)
        await interaction.response.send_message("Gespeichert; dein Profil ist privat. Prüfe die Vorschau und veröffentliche es bei Bedarf.", embed=embed, view=PublishView(self.cog, interaction.user.id), ephemeral=True)


class ProfileSelect(discord.ui.Select):
    def __init__(self, cog, rows):
        self.cog = cog
        super().__init__(placeholder="Profil öffnen …", options=[discord.SelectOption(label=r['name'][:100], value=str(r['user_id'])) for r in rows[:25]])

    async def callback(self, interaction: discord.Interaction):
        embed = await self.cog.profile_embed(interaction.guild_id, int(self.values[0]))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Roleplay(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot, self.db = bot, db

    async def profile_embed(self, guild_id: int, user_id: int, preview: bool = False) -> discord.Embed:
        profile = await self.db.fetchone("SELECT published FROM profiles WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        if not preview and (not profile or not profile['published']):
            return discord.Embed(title="Profil nicht verfügbar", description="Dieses Profil ist nicht veröffentlicht.")
        rows = await self.db.fetchall("SELECT f.name,f.field_type,v.value FROM profile_fields f JOIN profile_values v ON v.field_id=f.id AND v.guild_id=f.guild_id WHERE f.guild_id=? AND f.active=1 AND v.user_id=? ORDER BY f.position,f.id", (guild_id, user_id))
        user = self.bot.get_user(user_id)
        embed = discord.Embed(title=f"Steckbrief · {user.display_name if user else user_id}", color=discord.Color.blurple())
        for row in rows:
            if row['field_type'] == 'image' and row['value'].startswith(('https://','http://')):
                embed.set_image(url=row['value'])
            else:
                embed.add_field(name=row['name'][:256], value=row['value'][:1024], inline=row['field_type'] != 'text')
        if not rows:
            embed.description = "Noch keine Angaben eingetragen."
        return embed

    helper = app_commands.Group(name="helfer", description="Helferrollen verwalten")

    @helper.command(name="berechtigung", description="Einzelnes Recht für eine Rolle aktivieren oder deaktivieren")
    @app_commands.choices(berechtigung=[app_commands.Choice(name=v, value=k) for k,v in PERMISSIONS.items()])
    async def helper_permission(self, interaction: discord.Interaction, rolle: discord.Role, berechtigung: app_commands.Choice[str], aktiv: bool):
        if not owner(interaction):
            return await denied(interaction)
        if aktiv:
            await self.db.execute("INSERT OR IGNORE INTO role_permissions(guild_id,role_id,permission) VALUES(?,?,?)", (interaction.guild_id, rolle.id, berechtigung.value))
        else:
            await self.db.execute("DELETE FROM role_permissions WHERE guild_id=? AND role_id=? AND permission=?", (interaction.guild_id, rolle.id, berechtigung.value))
        await interaction.response.send_message(f"{berechtigung.name} für {rolle.mention} {'aktiviert' if aktiv else 'deaktiviert'}.", ephemeral=True)

    fields = app_commands.Group(name="feld", description="Steckbrief-Vorlage verwalten")

    @fields.command(name="erstellen", description="Dynamisches Steckbrief-Feld anlegen")
    @app_commands.choices(typ=[app_commands.Choice(name=x, value=x) for x in ('text','number','role','image')])
    async def field_create(self, interaction: discord.Interaction, name: app_commands.Range[str,1,80], typ: app_commands.Choice[str], pflicht: bool = False, filterbar: bool = False):
        if not await allowed(self.db, interaction, 'felder_verwalten'):
            return await denied(interaction)
        row = await self.db.fetchone("SELECT COALESCE(MAX(position),0)+1 AS n FROM profile_fields WHERE guild_id=?", (interaction.guild_id,))
        fid, _ = await self.db.execute("INSERT INTO profile_fields(guild_id,name,field_type,required,public_filter,position) VALUES(?,?,?,?,?,?)", (interaction.guild_id,name,typ.value,int(pflicht),int(filterbar),row['n']))
        await interaction.response.send_message(f"Feld **{name}** angelegt (ID `{fid}`).", ephemeral=True)

    @fields.command(name="umbenennen", description="Feld umbenennen, ohne gespeicherte Inhalte zu verlieren")
    async def field_rename(self, interaction: discord.Interaction, feld_id: int, neuer_name: app_commands.Range[str,1,80]):
        if not await allowed(self.db, interaction, 'felder_verwalten'):
            return await denied(interaction)
        _, count = await self.db.execute("UPDATE profile_fields SET name=? WHERE guild_id=? AND id=? AND active=1", (neuer_name, interaction.guild_id, feld_id))
        await interaction.response.send_message("Feld umbenannt." if count else "Aktives Feld nicht gefunden.", ephemeral=True)

    @fields.command(name="einstellungen", description="Pflichtstatus und Filterbarkeit einstellen")
    async def field_settings(self, interaction: discord.Interaction, feld_id: int, pflicht: bool, filterbar: bool):
        if not await allowed(self.db, interaction, 'felder_verwalten'):
            return await denied(interaction)
        _, count = await self.db.execute("UPDATE profile_fields SET required=?,public_filter=? WHERE guild_id=? AND id=? AND active=1", (int(pflicht),int(filterbar),interaction.guild_id,feld_id))
        await interaction.response.send_message("Einstellungen gespeichert." if count else "Aktives Feld nicht gefunden.", ephemeral=True)

    @fields.command(name="liste", description="Feld-IDs und Einstellungen anzeigen")
    async def field_list(self, interaction: discord.Interaction):
        rows = await self.db.fetchall("SELECT id,name,field_type,required,public_filter FROM profile_fields WHERE guild_id=? AND active=1 ORDER BY position,id", (interaction.guild_id,))
        text = "\n".join(f"`{r['id']}` {r['name']} ({r['field_type']}) · Pflicht {bool(r['required'])} · Filter {bool(r['public_filter'])}" for r in rows) or "Noch keine Felder angelegt."
        await interaction.response.send_message(text[:1900], ephemeral=True)

    @fields.command(name="entfernen", description="Feld deaktivieren; gespeicherte Inhalte bleiben erhalten")
    async def field_remove(self, interaction: discord.Interaction, feld_id: int):
        if not await allowed(self.db, interaction, 'felder_verwalten'):
            return await denied(interaction)
        _, count = await self.db.execute("UPDATE profile_fields SET active=0 WHERE guild_id=? AND id=? AND active=1", (interaction.guild_id,feld_id))
        await interaction.response.send_message("Feld deaktiviert; Inhalte bleiben erhalten." if count else "Aktives Feld nicht gefunden.", ephemeral=True)

    profile = app_commands.Group(name="profil", description="Spieler-Steckbriefe")

    @profile.command(name="bearbeiten", description="Eigene Text- und Zahlenfelder privat bearbeiten")
    async def profile_edit(self, interaction: discord.Interaction):
        rows = await self.db.fetchall("SELECT id,name,field_type,required FROM profile_fields WHERE guild_id=? AND active=1 AND field_type IN ('text','number') ORDER BY position,id", (interaction.guild_id,))
        if not rows:
            return await interaction.response.send_message("Es gibt noch keine Text- oder Zahlenfelder.", ephemeral=True)
        await interaction.response.send_modal(ProfileModal(self, rows))

    @profile.command(name="setzen", description="Eigenes Rollen-, Bild- oder Textfeld setzen")
    async def profile_set(self, interaction: discord.Interaction, feld_id: int, wert: str | None = None, bild: discord.Attachment | None = None):
        field = await self.db.fetchone("SELECT * FROM profile_fields WHERE guild_id=? AND id=? AND active=1", (interaction.guild_id, feld_id))
        if not field:
            return await interaction.response.send_message("Aktives Feld nicht gefunden.", ephemeral=True)
        value = wert or ''
        if field['field_type'] == 'image':
            if not bild or not bild.content_type or not bild.content_type.startswith('image/'):
                return await interaction.response.send_message("Für dieses Bildfeld bitte eine Bilddatei anhängen.", ephemeral=True)
            value = bild.url
        elif field['field_type'] == 'role':
            raw = value.replace('<@&','').replace('>','')
            role = interaction.guild.get_role(int(raw)) if interaction.guild and raw.isdigit() else None
            if not role:
                return await interaction.response.send_message("Bitte Rollen-ID oder Rollen-Erwähnung angeben.", ephemeral=True)
            value = role.mention
        elif field['field_type'] == 'number':
            try:
                float(value)
            except ValueError:
                return await interaction.response.send_message("Dieses Feld erwartet eine Zahl.", ephemeral=True)
        if not value or len(value) > 1000:
            return await interaction.response.send_message("Wert fehlt oder ist länger als 1000 Zeichen.", ephemeral=True)
        await self.db.execute("INSERT INTO profile_values(guild_id,user_id,field_id,value) VALUES(?,?,?,?) ON CONFLICT(guild_id,user_id,field_id) DO UPDATE SET value=excluded.value", (interaction.guild_id,interaction.user.id,feld_id,value))
        await self.db.execute("INSERT INTO profiles(guild_id,user_id,published) VALUES(?,?,0) ON CONFLICT(guild_id,user_id) DO UPDATE SET published=0,updated_at=CURRENT_TIMESTAMP", (interaction.guild_id,interaction.user.id))
        await interaction.response.send_message("Gespeichert. Profil ist nach Änderung privat; nutze `/profil vorschau`.", ephemeral=True)

    @profile.command(name="vorschau", description="Private Vorschau und Veröffentlichungsbutton")
    async def profile_preview(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=await self.profile_embed(interaction.guild_id,interaction.user.id,True), view=PublishView(self,interaction.user.id), ephemeral=True)

    @profile.command(name="ansehen", description="Veröffentlichtes Spielerprofil ansehen")
    async def profile_view(self, interaction: discord.Interaction, spieler: discord.Member):
        row = await self.db.fetchone("SELECT published FROM profiles WHERE guild_id=? AND user_id=?", (interaction.guild_id,spieler.id))
        if not row or not row['published']:
            return await interaction.response.send_message("Dieses Profil ist nicht veröffentlicht.", ephemeral=True)
        await interaction.response.send_message(embed=await self.profile_embed(interaction.guild_id,spieler.id), ephemeral=True)

    @profile.command(name="suche", description="Veröffentlichte Profile nach freigegebenem Feld durchsuchen")
    async def profile_search(self, interaction: discord.Interaction, feld_id: int, wert: str):
        field = await self.db.fetchone("SELECT name FROM profile_fields WHERE guild_id=? AND id=? AND active=1 AND public_filter=1", (interaction.guild_id,feld_id))
        if not field:
            return await interaction.response.send_message("Dieses Feld ist nicht für die öffentliche Suche freigegeben.", ephemeral=True)
        rows = await self.db.fetchall("SELECT p.user_id FROM profiles p JOIN profile_values v ON v.guild_id=p.guild_id AND v.user_id=p.user_id WHERE p.guild_id=? AND p.published=1 AND v.field_id=? AND lower(v.value)=lower(?) LIMIT 25", (interaction.guild_id,feld_id,wert))
        options = []
        for row in rows:
            member = interaction.guild.get_member(row['user_id']) if interaction.guild else None
            options.append({'user_id':row['user_id'],'name':member.display_name if member else str(row['user_id'])})
        if not options:
            return await interaction.response.send_message("Keine Treffer gefunden.", ephemeral=True)
        view = discord.ui.View(timeout=180)
        view.add_item(ProfileSelect(self,options))
        await interaction.response.send_message(f"Treffer für **{field['name']} = {wert}**:",view=view,ephemeral=True)

    note = app_commands.Group(name="notiz", description="Spielernotizen")

    @note.command(name="kategorie", description="Notizkategorie erstellen")
    async def note_category(self, interaction: discord.Interaction, name: app_commands.Range[str,1,80]):
        if not await allowed(self.db, interaction, 'kategorien_verwalten'):
            return await denied(interaction)
        try:
            await self.db.execute("INSERT INTO categories(guild_id,name) VALUES(?,?)",(interaction.guild_id,name))
        except Exception:
            return await interaction.response.send_message("Diese Kategorie existiert bereits.",ephemeral=True)
        await interaction.response.send_message(f"Kategorie **{name}** erstellt.",ephemeral=True)

    @note.command(name="kategorien", description="Kategorien mit IDs anzeigen")
    async def note_categories(self, interaction: discord.Interaction):
        rows = await self.db.fetchall("SELECT id,name FROM categories WHERE guild_id=? ORDER BY name",(interaction.guild_id,))
        await interaction.response.send_message("\n".join(f"`{r['id']}` · {r['name']}" for r in rows) or "Noch keine Kategorien.",ephemeral=True)

    @note.command(name="einreichen", description="Eigene Notiz zur Prüfung einreichen")
    async def note_submit(self, interaction: discord.Interaction, kategorie_id: int, inhalt: app_commands.Range[str,1,1500]):
        if not await allowed(self.db, interaction, 'notizen_einreichen'):
            return await denied(interaction)
        cat = await self.db.fetchone("SELECT id FROM categories WHERE guild_id=? AND id=?",(interaction.guild_id,kategorie_id))
        if not cat:
            return await interaction.response.send_message("Kategorie nicht gefunden; nutze `/notiz kategorien`.",ephemeral=True)
        nid, _ = await self.db.execute("INSERT INTO notes(guild_id,user_id,category_id,content) VALUES(?,?,?,?)",(interaction.guild_id,interaction.user.id,kategorie_id,inhalt))
        await interaction.response.send_message(f"Notiz `#{nid}` wurde eingereicht.",ephemeral=True)

    @note.command(name="meine", description="Eigene Notizen anzeigen")
    async def note_mine(self, interaction: discord.Interaction):
        rows = await self.db.fetchall("SELECT n.id,n.content,n.status,c.name FROM notes n LEFT JOIN categories c ON c.id=n.category_id WHERE n.guild_id=? AND n.user_id=? ORDER BY n.id DESC LIMIT 20",(interaction.guild_id,interaction.user.id))
        text = "\n".join(f"`#{r['id']}` [{r['status']}] {r['name'] or 'Ohne Kategorie'}: {r['content'][:150]}" for r in rows) or "Du hast noch keine Notizen."
        await interaction.response.send_message(text[:1900],ephemeral=True)

    @note.command(name="offen", description="Offene Notizen zur Moderation anzeigen")
    async def note_pending(self, interaction: discord.Interaction):
        if not await allowed(self.db, interaction, 'notizen_moderieren'):
            return await denied(interaction)
        rows = await self.db.fetchall("SELECT id,user_id,content FROM notes WHERE guild_id=? AND status='pending' ORDER BY id LIMIT 15",(interaction.guild_id,))
        await interaction.response.send_message("\n".join(f"`#{r['id']}` <@{r['user_id']}>: {r['content'][:160]}" for r in rows) or "Keine offenen Notizen.",ephemeral=True)

    @note.command(name="entscheidung", description="Notiz annehmen oder ablehnen")
    @app_commands.choices(status=[app_commands.Choice(name='Annehmen',value='approved'),app_commands.Choice(name='Ablehnen',value='rejected')])
    async def note_decide(self, interaction: discord.Interaction, notiz_id: int, status: app_commands.Choice[str]):
        if not await allowed(self.db, interaction, 'notizen_moderieren'):
            return await denied(interaction)
        _, count = await self.db.execute("UPDATE notes SET status=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND id=? AND status='pending'",(status.value,interaction.guild_id,notiz_id))
        await interaction.response.send_message("Entscheidung gespeichert." if count else "Offene Notiz nicht gefunden.",ephemeral=True)

    @note.command(name="bearbeiten", description="Eigene Notiz bearbeiten; Helfer dürfen fremde Notizen bearbeiten")
    async def note_edit(self, interaction: discord.Interaction, notiz_id: int, inhalt: app_commands.Range[str,1,1500]):
        row = await self.db.fetchone("SELECT user_id FROM notes WHERE guild_id=? AND id=?",(interaction.guild_id,notiz_id))
        if not row:
            return await interaction.response.send_message("Notiz nicht gefunden.",ephemeral=True)
        if row['user_id'] != interaction.user.id and not await allowed(self.db,interaction,'notizen_bearbeiten'):
            return await denied(interaction)
        await self.db.execute("UPDATE notes SET content=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND id=?",(inhalt,interaction.guild_id,notiz_id))
        await interaction.response.send_message("Notiz aktualisiert.",ephemeral=True)

async def setup(bot: commands.Bot, db: Database):
    await bot.add_cog(Roleplay(bot, db))
