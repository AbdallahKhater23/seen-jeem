"""A populated v7 fixture, interruption rollback, and database allocation gates."""
import sqlite3

import pytest

from app import db as db_module
from app.db import connect, init_db, transaction


async def make_populated_v7(settings):
    async with transaction(settings) as db:
        await db.execute("INSERT INTO categories(id,slug,name_ar,icon) VALUES (1,'ucl','الأبطال','Star')")
        await db.execute("INSERT INTO questions(id,category_id,difficulty,question_type,question_text,answer_text,content_origin,fingerprint) VALUES (1,1,200,'text','منو اللاعب؟','قديم','curated','old')")
        await db.execute("INSERT INTO users(id,display_name) VALUES (1,'قديم')")
        await db.execute("INSERT INTO matches(id,match_code,team1_name,team2_name) VALUES (1,'LEGACY','الأول','الثاني')")
        await db.execute("INSERT INTO match_tiles(match_id,tile_key,category_id,difficulty,question_id) VALUES (1,'ucl-200-1',1,200,1)")
        await db.execute("INSERT INTO user_question_history(user_id,question_id,match_id) VALUES (1,1,1)")
        await db.execute('DROP TRIGGER trg_match_initial_allocation')
        for table in ('match_question_allocations', 'content_reviews', 'question_metadata',
                      'football_category_policy', 'football_facts', 'football_events', 'football_entities'):
            await db.execute(f'DROP TABLE {table}')
        await db.execute('PRAGMA user_version=7')


async def legacy_rows(settings):
    async with connect(settings) as db:
        return {table: [tuple(r) for r in await (await db.execute(f'SELECT * FROM {table} ORDER BY id')).fetchall()]
                for table in ('questions','matches','match_tiles','users','user_question_history')}


@pytest.mark.asyncio
async def test_populated_v7_upgrade_preserves_all_legacy_values(settings):
    await make_populated_v7(settings)
    before = await legacy_rows(settings)
    await init_db(settings)
    await init_db(settings)
    assert await legacy_rows(settings) == before
    async with connect(settings) as db:
        assert (await (await db.execute('PRAGMA user_version')).fetchone())[0] == 8
        assert await (await db.execute('PRAGMA foreign_key_check')).fetchall() == []
        assert (await (await db.execute('SELECT COUNT(*) FROM question_metadata')).fetchone())[0] == 0


@pytest.mark.asyncio
async def test_interrupted_v8_migration_rolls_back_schema_and_version(settings, monkeypatch):
    await make_populated_v7(settings)
    before = await legacy_rows(settings)
    sql = db_module.FOOTBALL_SCHEMA_SQL
    monkeypatch.setattr(db_module, 'FOOTBALL_SCHEMA_SQL', sql + '\nINVALID SQL TO INJECT INTERRUPTION;')
    with pytest.raises(sqlite3.OperationalError):
        await init_db(settings)
    async with connect(settings) as db:
        assert (await (await db.execute('PRAGMA user_version')).fetchone())[0] == 7
        assert await (await db.execute("SELECT name FROM sqlite_master WHERE name='question_metadata'")).fetchall() == []
    assert await legacy_rows(settings) == before
    monkeypatch.setattr(db_module, 'FOOTBALL_SCHEMA_SQL', sql)
    await init_db(settings)
    assert await legacy_rows(settings) == before


@pytest.mark.asyncio
async def test_invalid_json_and_duplicate_initial_fact_allocation_are_rejected(settings):
    from app.services.football_content import publish_candidates
    from tests.test_football_publication import candidate
    async with transaction(settings) as db:
        await db.execute("INSERT INTO categories(id,slug,name_ar,icon) VALUES (1,'ucl','الأبطال','Star')")
    await publish_candidates(settings, [candidate(), candidate(question='منو سجل مقصية نهائي 2018 مع ريال؟')])
    with pytest.raises(sqlite3.IntegrityError):
        async with transaction(settings) as db:
            await db.execute("UPDATE question_metadata SET aliases_json='invalid'")
    with pytest.raises(sqlite3.IntegrityError):
        async with transaction(settings) as db:
            ids = [r[0] for r in await (await db.execute('SELECT id FROM questions')).fetchall()]
            await db.execute("INSERT INTO matches(id,match_code,team1_name,team2_name) VALUES (1,'FAIL','الأول','الثاني')")
            for i, qid in enumerate(ids):
                await db.execute('INSERT INTO match_tiles(match_id,tile_key,category_id,difficulty,question_id) VALUES (1,?,1,200,?)', (str(i), qid))
    async with connect(settings) as db:
        assert (await (await db.execute('SELECT COUNT(*) FROM matches')).fetchone())[0] == 0
        assert (await (await db.execute('SELECT COUNT(*) FROM match_tiles')).fetchone())[0] == 0
        assert (await (await db.execute('SELECT COUNT(*) FROM match_question_allocations')).fetchone())[0] == 0
