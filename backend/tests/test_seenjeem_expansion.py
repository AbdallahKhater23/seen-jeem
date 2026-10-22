from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from app.data import matchstick
from app.db import connect, init_db, transaction
from app.schema import SCHEMA_VERSION
from app.services.content import CATEGORY_SLUGS
from app.services.seed import seed_database


NEW_CATEGORIES = ("quran", "nicknames", "technology", "videogames", "matchstick")
API_CATEGORIES = ("quran", "nicknames", "technology", "videogames")


def test_matchstick_bank_is_complete_and_strictly_unique():
    rows = matchstick.build_rows()
    assert len(rows) == 360
    assert Counter(row["difficulty"] for row in rows) == {200: 120, 400: 120, 600: 120}
    equations = [row["payload"]["equation"] for row in rows]
    assert len(set(equations)) == 360

    for row in rows:
        payload = row["payload"]
        assert payload["kind"] == "matchstick"
        assert payload["moves_required"] in (1, 2)
        assert payload["solution"] != payload["equation"]
        assert sum(len(segment) for segment in payload["start"]) == sum(
            len(segment) for segment in payload["end"]
        )
        assert matchstick.validate_puzzle(payload, strict=True) == []


@pytest.mark.asyncio
async def test_new_buckets_have_120_questions_and_complete_provenance(seeded_settings):
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            """
            SELECT c.slug, q.difficulty, COUNT(*) AS n
            FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE c.slug IN (?, ?, ?, ?, ?)
            GROUP BY c.slug, q.difficulty
            """,
            NEW_CATEGORIES,
        )
        counts = {
            f"{row['slug']}:{row['difficulty']}": int(row["n"])
            for row in await cursor.fetchall()
        }
        await cursor.close()
        expected = {
            f"{slug}:{difficulty}": 120
            for slug in NEW_CATEGORIES
            for difficulty in (200, 400, 600)
        }
        assert counts == expected

        cursor = await db.execute(
            """
            SELECT c.slug, q.source_name, q.source_url, q.source_entity_id,
                   q.source_checked_at, q.source_license, q.source_claim,
                   q.payload_json
            FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE c.slug IN (?, ?, ?, ?, ?)
            """,
            NEW_CATEGORIES,
        )
        rows = await cursor.fetchall()
        await cursor.close()

    assert len(rows) == 1800
    for row in rows:
        assert row["source_name"], row["source_name"]
        assert row["source_license"], row["source_license"]
        assert row["source_claim"], row["source_claim"]
        if row["slug"] in API_CATEGORIES:
            assert row["source_url"].startswith("http"), row["source_url"]
            assert row["source_entity_id"], row["source_entity_id"]
            assert row["source_checked_at"], row["source_checked_at"]
        else:
            assert row["source_url"] == "internal://seenjeem/matchstick-generator/v1"
            assert row["source_checked_at"] == "2026-10-20"
            payload = json.loads(row["payload_json"])
            assert payload["kind"] == "matchstick"
            assert payload["moves_required"] in (1, 2)


@pytest.mark.asyncio
async def test_api_returns_matchstick_payload_and_provenance(client, seeded_settings):
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            """
            SELECT q.id FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE c.slug = 'matchstick' ORDER BY q.id LIMIT 1
            """
        )
        matchstick_id = int((await cursor.fetchone())["id"])
        await cursor.close()
        cursor = await db.execute(
            """
            SELECT q.id FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE c.slug = 'technology' ORDER BY q.id LIMIT 1
            """
        )
        technology_id = int((await cursor.fetchone())["id"])
        await cursor.close()

    response = await client.get(f"/api/v1/questions/{matchstick_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["question_type"] == "text"
    assert body["payload"]["kind"] == "matchstick"
    assert body['source_url'] is None and body['answer_text'] is None
    async with connect(seeded_settings) as db:
        stored = dict(await (await db.execute('SELECT * FROM questions WHERE id=?', (matchstick_id,))).fetchone())
    assert stored["source_url"] == "internal://seenjeem/matchstick-generator/v1"
    assert stored["source_checked_at"] == "2026-10-20"
    assert stored["source_license"] == "internal deterministic generator"
    assert stored["source_claim"]

    response = await client.get(f"/api/v1/questions/{technology_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['source_url'] is None and body['answer_text'] is None
    async with connect(seeded_settings) as db:
        stored = dict(await (await db.execute('SELECT * FROM questions WHERE id=?', (technology_id,))).fetchone())
    assert stored["source_url"].startswith("https://www.wikidata.org/")
    assert stored["source_license"] == "CC0 1.0 (Wikidata structured data)"
    assert stored["source_claim"] == "P17 country, P112 founder, P571 inception"


@pytest.mark.asyncio
async def test_v6_to_v7_migration_preserves_rows_and_adds_provenance_columns(tmp_path: Path):
    from app.config import load_settings

    path = tmp_path / "v6.db"
    settings = replace(load_settings(), database_path=path)
    await init_db(settings)
    async with transaction(settings) as db:
        await db.execute(
            "INSERT INTO categories(slug, name_ar, icon) VALUES ('legacy', 'قديم', 'Flag')"
        )
        await db.execute(
            """
            INSERT INTO questions(
                category_id, difficulty, question_type, question_text,
                answer_text, content_origin, fingerprint
            ) VALUES (1, 200, 'text', 'سؤال قديم؟', 'جواب', 'curated', 'v6-fingerprint')
            """
        )
        await db.execute(
            """
            INSERT INTO fact_records(fact_group_id, fact_type, source_name, payload_json)
            VALUES ('v6:fact', 'legacy', 'legacy-source', '{}')
            """
        )
        await db.execute(
            "INSERT INTO matches(match_code, team1_name, team2_name) VALUES ('V6CODE', 'أ', 'ب')"
        )
        await db.execute("ALTER TABLE questions DROP COLUMN source_license")
        await db.execute("ALTER TABLE questions DROP COLUMN source_claim")
        await db.execute("ALTER TABLE fact_records DROP COLUMN source_license")
        await db.execute("ALTER TABLE fact_records DROP COLUMN source_claim")
        await db.execute("PRAGMA user_version = 6")

    await init_db(settings)
    async with connect(settings) as db:
        version = (await (await db.execute("PRAGMA user_version")).fetchone())[0]
        assert version == SCHEMA_VERSION
        question_columns = {
            row["name"] for row in await (await db.execute("PRAGMA table_info(questions)")).fetchall()
        }
        fact_columns = {
            row["name"] for row in await (await db.execute("PRAGMA table_info(fact_records)")).fetchall()
        }
        assert {"source_license", "source_claim"} <= question_columns
        assert {"source_license", "source_claim"} <= fact_columns
        assert (
            await (await db.execute("SELECT COUNT(*) FROM questions")).fetchone()
        )[0] == 1
        assert (
            await (await db.execute("SELECT COUNT(*) FROM fact_records")).fetchone()
        )[0] == 1
        assert (
            await (await db.execute("SELECT COUNT(*) FROM matches WHERE match_code = 'V6CODE'")).fetchone()
        )[0] == 1
        row = await (await db.execute("SELECT question_text FROM questions")).fetchone()
        assert row["question_text"] == "سؤال قديم؟"


@pytest.mark.asyncio
async def test_seed_remains_idempotent_with_all_new_categories(seeded_settings):
    first = await seed_database(seeded_settings, deterministic_seed=12345)
    second = await seed_database(seeded_settings, deterministic_seed=12345)
    assert second["inserted"] == 0
    assert second["skipped"] == first["total_active"]
    async with connect(seeded_settings) as db:
        categories = (await (await db.execute("SELECT COUNT(*) FROM categories")).fetchone())[0]
        assert categories == len(CATEGORY_SLUGS) == 18
        new_rows = (
            await (
                await db.execute(
                    """
                    SELECT COUNT(*) FROM questions q
                    JOIN categories c ON c.id = q.category_id
                    WHERE c.slug IN (?, ?, ?, ?, ?)
                    """,
                    NEW_CATEGORIES,
                )
            ).fetchone()
        )[0]
        assert new_rows == 1800
