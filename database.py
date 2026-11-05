from __future__ import annotations

import aiosqlite

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS role_permissions (guild_id INTEGER NOT NULL, role_id INTEGER NOT NULL, permission TEXT NOT NULL, PRIMARY KEY(guild_id,role_id,permission));
CREATE TABLE IF NOT EXISTS profile_fields (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL, field_type TEXT NOT NULL CHECK(field_type IN ('text','number','role','image')), required INTEGER NOT NULL DEFAULT 0, public_filter INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS profiles (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, published INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(guild_id,user_id));
CREATE TABLE IF NOT EXISTS profile_values (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, field_id INTEGER NOT NULL, value TEXT NOT NULL, PRIMARY KEY(guild_id,user_id,field_id), FOREIGN KEY(field_id) REFERENCES profile_fields(id));
CREATE TABLE IF NOT EXISTS field_role_options (field_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, role_id INTEGER NOT NULL, PRIMARY KEY(field_id,role_id), FOREIGN KEY(field_id) REFERENCES profile_fields(id));
CREATE TABLE IF NOT EXISTS profile_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL, color INTEGER NOT NULL DEFAULT 5793266, UNIQUE(guild_id,name));
CREATE TABLE IF NOT EXISTS profile_group_members (guild_id INTEGER NOT NULL, group_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY(guild_id,user_id), FOREIGN KEY(group_id) REFERENCES profile_groups(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL, UNIQUE(guild_id,name));
CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, category_id INTEGER, content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL);
"""

class Database:
    def __init__(self, path: str):
        self.path = path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def execute(self, sql: str, params: tuple = ()) -> tuple[int, int]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(sql, params)
            await db.commit()
            return cursor.lastrowid, cursor.rowcount

    async def fetchone(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            return await cursor.fetchall()
