"""دورة حياة اتصالات SQLite والمعاملات والترحيل.

كل عملية تستخدم اتصالًا قصير العمر مع PRAGMA مناسبة. المعاملات الكتابية تبدأ
بـ BEGIN IMMEDIATE حتى تتسلسل كتابات SQLite بدل التعارض الصامت.

الترحيل تراكمي: الإصدار 1 → 7 بإضافة أعمدة وجداول فقط، دون حذف صفوف أو
لمس تاريخ المباريات. قواعد البيانات الجديدة تُنشأ مباشرة بالإصدار 7.
"""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from .config import Settings
from .schema import FOOTBALL_SCHEMA_SQL, SCHEMA_SQL, SCHEMA_VERSION


async def _configure(connection: aiosqlite.Connection, settings: Settings) -> None:
    await connection.execute("PRAGMA foreign_keys = ON")
    await connection.execute(f"PRAGMA busy_timeout = {int(settings.busy_timeout_ms)}")
    await connection.execute("PRAGMA synchronous = NORMAL")


async def _table_names(connection: aiosqlite.Connection) -> set[str]:
    cursor = await connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    rows = await cursor.fetchall()
    await cursor.close()
    return {row[0] for row in rows}


async def _columns(connection: aiosqlite.Connection, table: str) -> set[str]:
    cursor = await connection.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    await cursor.close()
    return {row[1] for row in rows}


async def _add_columns(
    connection: aiosqlite.Connection, add_column: dict[str, dict[str, str]]
) -> None:
    """يضيف أعمدة بأمان حتى لو توقف ترحيل سابق في المنتصف."""
    tables = await _table_names(connection)
    for table, columns in add_column.items():
        if table not in tables:
            continue
        existing = await _columns(connection, table)
        for name, definition in columns.items():
            if name not in existing:
                await connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                )


async def _migrate_v1_to_v2(connection: aiosqlite.Connection) -> None:
    """يضيف أعمدة الإصدار 2 ثم يرقّي بيانات الصفوف القديمة."""
    await _add_columns(
        connection,
        {
            "questions": {
                "fact_group_id": "TEXT NULL",
                "source_entity_id": "TEXT NULL",
                "verification_status": "TEXT NOT NULL DEFAULT 'curated'",
                "content_version": "INTEGER NOT NULL DEFAULT 1",
                "times_played": "INTEGER NOT NULL DEFAULT 0",
                "last_played_match_id": "INTEGER NULL",
                "deck_position": "INTEGER NOT NULL DEFAULT 0",
            },
            "matches": {"selected_categories_json": "TEXT NOT NULL DEFAULT '[]'"},
            "match_tiles": {"allocation_cycle": "INTEGER NOT NULL DEFAULT 1"},
        },
    )
    # دورات تُداريدية للصفوف القديمة؛ الهوية القديمة معلّمة بوضوح ولا تُدّعى أنها
    # مجموعة واقعية محققة.
    await connection.execute(
        "UPDATE questions SET fact_group_id = 'legacy:' || fingerprint"
        " WHERE fact_group_id IS NULL OR fact_group_id = ''"
    )
    await connection.execute(
        "UPDATE questions SET deck_position = id WHERE deck_position = 0"
    )
    await connection.execute(
        "UPDATE matches SET selected_categories_json ="
        " '[\"flags\",\"football\",\"worldcup\",\"career\",\"riddles\",\"spotdiff\"]'"
        " WHERE selected_categories_json = '[]' OR selected_categories_json IS NULL"
    )


async def _migrate_v3_to_v4(connection: aiosqlite.Connection) -> None:
    """يضيف بصمة توكن المضيف على المباريات."""
    await _add_columns(
        connection,
        {
            "matches": {"host_token_hash": "TEXT NULL"},
        },
    )


async def _migrate_v4_to_v5(connection: aiosqlite.Connection) -> None:
    """يربط المباريات بالتثبيت المضيف؛ جداول الهوية تُنشأ بـ SCHEMA_SQL."""
    await _add_columns(
        connection,
        {
            "matches": {
                "host_installation_id": (
                    "INTEGER NULL REFERENCES device_installations(id) ON DELETE SET NULL"
                ),
            },
        },
    )


async def _migrate_v6_to_v7(connection: aiosqlite.Connection) -> None:
    """يضيف حقلي الترخيص والادعاء إلى الأسئلة والوقائع (ترقية إضافية آمنة)."""
    await _add_columns(
        connection,
        {
            "questions": {
                "source_license": "TEXT NULL",
                "source_claim": "TEXT NULL",
            },
            "fact_records": {
                "source_license": "TEXT NULL",
                "source_claim": "TEXT NULL",
            },
        },
    )


async def _migrate_v2_to_v3(connection: aiosqlite.Connection) -> None:
    """يضيف أعمدة جلسة السؤال؛ جدول القوى يُنشأ بـ SCHEMA_SQL."""
    await _add_columns(
        connection,
        {
            "match_tiles": {
                "opened_at": "TEXT NULL",
                "revealed_at": "TEXT NULL",
                "active_team": "TEXT NULL",
                "noise_until": "TEXT NULL",
            }
        },
    )


async def init_db(settings: Settings) -> None:
    """ينشئ المجلد والمخطط، ويثبّت WAL، ويرحّل، ويرفض إصدارًا مستقبليًا."""
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = await aiosqlite.connect(str(path))
    try:
        connection.row_factory = sqlite3.Row
        await _configure(connection, settings)
        cursor = await connection.execute("PRAGMA journal_mode = WAL")
        row = await cursor.fetchone()
        await cursor.close()
        mode = (row[0] if row else "").lower()
        if mode != "wal":
            raise RuntimeError(f"تعذّر تفعيل WAL على قاعدة البيانات (الوضع: {mode or 'unknown'}).")

        current = await connection.execute("PRAGMA user_version")
        version_row = await current.fetchone()
        await current.close()
        current_version = int(version_row[0]) if version_row else 0
        if current_version > SCHEMA_VERSION:
            raise RuntimeError(
                f"إصدار قاعدة البيانات {current_version} أحدث من المدعوم {SCHEMA_VERSION}."
            )

        tables = await _table_names(connection)
        if current_version < 2:
            if "questions" in tables:
                await _migrate_v1_to_v2(connection)
            await connection.executescript(SCHEMA_SQL)
            await _migrate_v2_to_v3(connection)
            await _migrate_v3_to_v4(connection)
        elif current_version < 3:
            await _migrate_v2_to_v3(connection)
            await _migrate_v3_to_v4(connection)
            await connection.executescript(SCHEMA_SQL)
        elif current_version < 4:
            await _migrate_v3_to_v4(connection)
            await _migrate_v4_to_v5(connection)
            await connection.executescript(SCHEMA_SQL)
        elif current_version < 5:
            await _migrate_v4_to_v5(connection)
            await connection.executescript(SCHEMA_SQL)
        else:
            await connection.executescript(SCHEMA_SQL)
        await _migrate_v4_to_v5(connection)
        await _add_columns(connection, {
            "users": {"password_hash": "TEXT NULL"},
            "matches": {"host_user_id": "INTEGER NULL REFERENCES users(id) ON DELETE RESTRICT"},
        })
        await _migrate_v6_to_v7(connection)
        # v8 is strictly additive. Legacy identities/metadata remain unknown;
        # publication is a separate explicit operation, never a startup backfill.
        # executescript commits implicitly, so wrap the entire new migration
        # in its own explicit SQL transaction including the version marker.
        await connection.commit()
        try:
            await connection.executescript(
                'BEGIN IMMEDIATE;\n' + FOOTBALL_SCHEMA_SQL
                + f'\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;'
            )
        except BaseException:
            await connection.rollback()
            raise

        # تأكد من أن المخطط محفوظ قبل تسليم الاتصال.
        await connection.commit()
    finally:
        await connection.close()


@asynccontextmanager
async def connect(settings: Settings) -> AsyncIterator[aiosqlite.Connection]:
    connection = await aiosqlite.connect(str(settings.database_path))
    connection.row_factory = sqlite3.Row
    try:
        await _configure(connection, settings)
        yield connection
    finally:
        await connection.close()


@asynccontextmanager
async def transaction(settings: Settings) -> AsyncIterator[aiosqlite.Connection]:
    connection = await aiosqlite.connect(str(settings.database_path))
    connection.row_factory = sqlite3.Row
    try:
        await _configure(connection, settings)
        await connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        except BaseException:
            await connection.rollback()
            raise
        else:
            await connection.commit()
    finally:
        await connection.close()


async def database_ready(settings: Settings) -> bool:
    try:
        async with connect(settings) as db:
            cursor = await db.execute("SELECT 1")
            row = await cursor.fetchone()
            await cursor.close()
            return bool(row and row[0] == 1)
    except Exception:
        return False


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None
