from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.db import connect, init_db
from app.schema import SCHEMA_VERSION
from app.services.content import (
    CAPACITY_PER_BUCKET,
    CATEGORY_SLUGS,
    DIFFICULTIES,
    OPERATIONAL_MIN_PER_BUCKET,
    build_question_bank,
    inventory_report,
    validate_question_bank,
)
from app.services.harvester import (
    _country_payload,
    _validate_wikidata,
    validate_country_record,
)
from app.services.matches import resolve_tile
from app.services.seed import seed_database, seed_status
from app.models import MatchCreateIn
from app.utils.text import fingerprint, normalize_answer, normalize_text
from tests.conftest import SIX_CATEGORIES, hosted_create


@pytest.mark.asyncio
async def test_schema_v3_wal_foreign_keys_and_columns(settings):
    await init_db(settings)
    async with connect(settings) as db:
        cursor = await db.execute("PRAGMA user_version")
        assert (await cursor.fetchone())[0] == SCHEMA_VERSION
        await cursor.close()
        cursor = await db.execute("PRAGMA journal_mode")
        assert str((await cursor.fetchone())[0]).lower() == "wal"
        await cursor.close()
        cursor = await db.execute("PRAGMA foreign_keys")
        assert (await cursor.fetchone())[0] == 1
        await cursor.close()
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = {row["name"] for row in await cursor.fetchall()}
        await cursor.close()
        cursor = await db.execute("PRAGMA table_info(questions)")
        question_columns = {row["name"] for row in await cursor.fetchall()}
        await cursor.close()
        cursor = await db.execute("PRAGMA table_info(match_tiles)")
        tile_columns = {row["name"] for row in await cursor.fetchall()}
        await cursor.close()
        cursor = await db.execute("PRAGMA table_info(matches)")
        match_columns = {row["name"] for row in await cursor.fetchall()}
        await cursor.close()
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_questions_shoe'"
        )
        shoe_index = await cursor.fetchone()
        await cursor.close()
    assert {
        "categories",
        "questions",
        "matches",
        "match_tiles",
        "score_adjustments",
        "match_events",
        "question_usage",
        "question_buckets",
        "idempotency_keys",
        "seed_runs",
        "fact_records",
        "harvester_cursors",
        "sync_jobs",
        "match_powers",
    } <= tables
    assert {
        "fact_group_id",
        "times_played",
        "last_played_match_id",
        "deck_position",
        "verification_status",
        "content_version",
        "source_entity_id",
    } <= question_columns
    assert {
        "opened_at",
        "revealed_at",
        "active_team",
        "noise_until",
    } <= tile_columns
    assert "host_token_hash" in match_columns
    assert shoe_index is not None


@pytest.mark.asyncio
async def test_v1_database_migrates_without_row_loss(tmp_path: Path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE NOT NULL,
            name_ar TEXT NOT NULL, icon TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT 'x'
        );
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL, difficulty INTEGER NOT NULL,
            question_type TEXT NOT NULL, question_text TEXT NOT NULL,
            answer_text TEXT NOT NULL, content_origin TEXT NOT NULL,
            fingerprint TEXT UNIQUE NOT NULL, is_active INTEGER NOT NULL DEFAULT 1,
            is_reserved_backup INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, match_code TEXT UNIQUE NOT NULL,
            team1_name TEXT NOT NULL, team2_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', updated_at TEXT NOT NULL DEFAULT 'x',
            version INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO categories(slug, name_ar, icon) VALUES ('flags', 'أعلام', 'Flag');
        INSERT INTO questions(category_id, difficulty, question_type, question_text,
            answer_text, content_origin, fingerprint)
        VALUES (1, 200, 'text', 'سؤال قديم؟', 'إجابة', 'curated', 'legacy-fingerprint');
        INSERT INTO matches(match_code, team1_name, team2_name) VALUES ('OLDCODE', 'أ', 'ب');
        PRAGMA user_version = 1;
        """
    )
    connection.commit()
    connection.close()

    from dataclasses import replace

    from app.config import load_settings

    settings = replace(load_settings(), database_path=path)
    await init_db(settings)
    async with connect(settings) as db:
        cursor = await db.execute("SELECT * FROM questions")
        row = await cursor.fetchone()
        await cursor.close()
        cursor = await db.execute("SELECT * FROM matches WHERE match_code = 'OLDCODE'")
        match = await cursor.fetchone()
        await cursor.close()
        cursor = await db.execute("PRAGMA user_version")
        version = (await cursor.fetchone())[0]
        await cursor.close()
    assert version == SCHEMA_VERSION
    assert row["question_text"] == "سؤال قديم؟"
    assert row["fact_group_id"] == "legacy:legacy-fingerprint"
    assert row["times_played"] == 0
    assert row["deck_position"] == row["id"]
    assert match is not None
    assert json.loads(match["selected_categories_json"]) == [
        "flags",
        "football",
        "worldcup",
        "career",
        "riddles",
        "spotdiff",
    ]


@pytest.mark.asyncio
async def test_v2_database_gains_server_power_session_columns(tmp_path: Path):
    """ترقية v2 لا تحذف صفوف الخانات وتضيف أعمدة جلسة السؤال الأربعة."""
    path = tmp_path / "v2.db"
    from dataclasses import replace

    from app.config import load_settings

    settings = replace(load_settings(), database_path=path)
    await init_db(settings)
    async with connect(settings) as db:
        await db.execute(
            "ALTER TABLE match_tiles DROP COLUMN opened_at"
        )
        await db.execute(
            "ALTER TABLE match_tiles DROP COLUMN revealed_at"
        )
        await db.execute(
            "ALTER TABLE match_tiles DROP COLUMN active_team"
        )
        await db.execute(
            "ALTER TABLE match_tiles DROP COLUMN noise_until"
        )
        await db.execute("PRAGMA user_version = 2")
        await db.commit()

    await init_db(settings)
    async with connect(settings) as db:
        cursor = await db.execute("PRAGMA user_version")
        version = (await cursor.fetchone())[0]
        await cursor.close()
        cursor = await db.execute("PRAGMA table_info(match_tiles)")
        tile_columns = {row["name"] for row in await cursor.fetchall()}
        await cursor.close()
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'match_powers'"
        )
        powers_table = await cursor.fetchone()
        await cursor.close()
    assert version == SCHEMA_VERSION
    assert {"opened_at", "revealed_at", "active_team", "noise_until"} <= tile_columns
    assert powers_table is not None


@pytest.mark.asyncio
async def test_v3_database_gains_host_token_column(tmp_path: Path):
    """ترقية v3 تضيف بصمة توكن المضيف دون مساس بصفوف المباريات."""
    path = tmp_path / "v3.db"
    from dataclasses import replace

    from app.config import load_settings

    settings = replace(load_settings(), database_path=path)
    await init_db(settings)
    async with connect(settings) as db:
        await db.execute("ALTER TABLE matches DROP COLUMN host_token_hash")
        await db.execute("PRAGMA user_version = 3")
        await db.commit()

    await init_db(settings)
    async with connect(settings) as db:
        cursor = await db.execute("PRAGMA user_version")
        version = (await cursor.fetchone())[0]
        await cursor.close()
        cursor = await db.execute("PRAGMA table_info(matches)")
        match_columns = {row["name"] for row in await cursor.fetchall()}
        await cursor.close()
    assert version == SCHEMA_VERSION
    assert "host_token_hash" in match_columns


@pytest.mark.asyncio
async def test_seed_creates_all_categories_and_operational_inventory(settings):
    report = await seed_database(settings, deterministic_seed=12345)
    assert report["total_active"] >= 5000
    assert len(report["buckets"]) == len(CATEGORY_SLUGS) * len(DIFFICULTIES)
    assert all(count >= OPERATIONAL_MIN_PER_BUCKET for count in report["buckets"].values())
    status = await seed_status(settings)
    assert status["complete"] is True
    assert status["total_active"] == report["total_active"]

    async with connect(settings) as db:
        cursor = await db.execute("SELECT COUNT(*) AS n FROM categories")
        assert (await cursor.fetchone())["n"] == len(CATEGORY_SLUGS)
        await cursor.close()
        cursor = await db.execute("SELECT slug FROM categories ORDER BY sort_order")
        assert [row["slug"] for row in await cursor.fetchall()] == list(CATEGORY_SLUGS)
        await cursor.close()
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions"
            " WHERE is_active = 1 AND is_reserved_backup = 0"
            " AND (fact_group_id IS NULL OR fact_group_id = '')"
        )
        assert (await cursor.fetchone())["n"] == 0
        await cursor.close()
        cursor = await db.execute("SELECT COUNT(*) AS n FROM fact_records")
        assert (await cursor.fetchone())["n"] > 100
        await cursor.close()


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_preserves_usage(settings):
    first = await seed_database(settings, deterministic_seed=12345)
    board = await hosted_create(
        settings,
        MatchCreateIn(
            team1_name="أ",
            team2_name="ب",
            starting_turn="team1",
            category_slugs=SIX_CATEGORIES,
        ),
        "usage-create",
    )
    tile = board["tiles"][0]
    await resolve_tile(
        settings,
        board["match"]["match_code"],
        tile["tile_key"],
        outcome="team1",
        powers_applied=[],
        expected_version=1,
        idempotency_key="usage-resolve",
        host_token=board["host_token"],
    )
    question_id = tile["question"]["id"]

    second = await seed_database(settings, deterministic_seed=12345)
    assert second["inserted"] == 0
    assert second["skipped"] == first["total_active"]
    async with connect(settings) as db:
        cursor = await db.execute(
            "SELECT times_played, last_played_match_id, deck_position FROM questions WHERE id = ?",
            (question_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        cursor = await db.execute("SELECT COUNT(*) AS n FROM questions")
        assert (await cursor.fetchone())["n"] == first["total_active"]
        await cursor.close()
    assert row["times_played"] == 1
    assert row["last_played_match_id"] is not None
    assert row["deck_position"] >= 0


def test_question_bank_is_deterministic_and_fact_grouped():
    first = build_question_bank()
    second = build_question_bank()
    assert len(first) == len(second)
    assert [row["question"] for row in first] == [row["question"] for row in second]
    fingerprints = [
        fingerprint(row["category"], row["question"], row["answer"], row.get("flag_code"))
        for row in first
    ]
    assert len(set(fingerprints)) == len(fingerprints)
    assert all(row["fact_group_id"] for row in first)
    summary = validate_question_bank(first)
    assert summary["total"] == len(first)
    assert len(summary["fact_groups"]) == len(CATEGORY_SLUGS)

    spot = [row for row in first if row["type"] == "spot_diff"]
    assert len(spot) == 2640  # 12 مشهد × C(12,3)
    scenes = {row["payload"]["sceneId"] for row in spot}
    assert len(scenes) == 12
    for row in spot[:50]:
        payload = row["payload"]
        assert len(payload["differences"]) == 3
        assert len(payload["mutations"]) == 3
        assert len(payload["anchors"]) == 12
        assert {mutation["id"] for mutation in payload["mutations"]} == {
            difference["id"] for difference in payload["differences"]
        }
    assert len({row["payload"]["sceneId"] + ":" + "-".join(row["payload"]["combo"]) for row in spot}) == len(spot)


def test_inventory_report_is_honest_about_capacity():
    rows = build_question_bank()
    report = inventory_report(rows)
    assert report["content_floor_per_bucket"] == 120
    assert report["capacity_per_bucket"] == CAPACITY_PER_BUCKET == 201
    assert report["meets_content_floor"] is False
    assert report["meets_100_match_capacity"] is False
    assert len(report["buckets_below_capacity_gate"]) > 0
    # الفئتان الإجرائيتان فقط تبلغان سعة 201 لكل دلو.
    capable = {
        slug
        for slug, info in report["categories"].items()
        if info["bucket_min"] >= CAPACITY_PER_BUCKET
    }
    assert capable == {"riddles", "spotdiff"}
    distribution = report["football_distribution"]
    assert distribution["global"] + distribution["arab"] > 0
    assert distribution["arab_percent"] < distribution["target_arab_percent"]
    assert report["origins"]["curated"] > 0
    assert report["origins"]["generated_puzzle"] > 0


def test_spotdiff_difficulty_bands_are_deterministic():
    rows = [row for row in build_question_bank() if row["type"] == "spot_diff"]
    by_difficulty = {difficulty: 0 for difficulty in DIFFICULTIES}
    for row in rows:
        by_difficulty[row["difficulty"]] += 1
    assert sum(by_difficulty.values()) == 2640
    assert all(count > 201 for count in by_difficulty.values())
    # نفس المشهد والتركيبة يجب أن ينتج نفس الحمولة عند إعادة التوليد.
    first = rows[0]
    again = next(
        row
        for row in rows
        if row["payload"]["sceneId"] == first["payload"]["sceneId"]
        and row["payload"]["combo"] == first["payload"]["combo"]
    )
    assert again["payload"]["mutations"] == first["payload"]["mutations"]
    assert again["difficulty"] == first["difficulty"]


def test_country_record_validation_never_invents_arabic_names():
    valid = validate_country_record(
        {
            "cca2": "kw",
            "name": {"common": "Kuwait"},
            "translations": {"ara": {"common": "الكويت"}},
            "capital": ["Kuwait City"],
            "region": "Asia",
            "unMember": True,
            "borders": ["IRQ", "SAU"],
            "currencies": {"KWD": {"name": "Kuwaiti dinar"}},
        }
    )
    assert valid["code"] == "kw"
    assert valid["name_ar"] == "الكويت"
    assert valid["capital"] == "Kuwait City"
    assert validate_country_record(
        {
            "cca2": "xx",
            "name": {"common": "Nowhere"},
            "translations": {},
            "capital": ["X"],
        }
    ) is None
    assert validate_country_record({"cca2": "kw"}) is None


def test_country_payload_forms_and_deprecation():
    rows = [{"cca2": "kw"}]
    assert _country_payload(rows)[0] == rows
    assert _country_payload({"success": True, "data": rows})[0] == rows
    deprecated = _country_payload(
        {"success": False, "errors": [{"message": "This API version has been deprecated."}]}
    )
    assert deprecated == (None, "deprecated")


def test_wikidata_validation_rejects_incomplete_bindings():
    payload = {
        "results": {
            "bindings": [
                {
                    "player": {"value": "http://www.wikidata.org/entity/Q1"},
                    "playerLabel": {"value": "لاعب"},
                    "countryLabel": {"value": "الكويت"},
                },
                {"player": {"value": "not-a-url"}, "playerLabel": {"value": "x"}},
                {"player": {"value": "http://www.wikidata.org/entity/Q2"}},
            ]
        }
    }
    players = _validate_wikidata(payload)
    assert len(players) == 1
    assert players[0]["label"] == "لاعب"
    assert _validate_wikidata({"error": "bad"}) == []


def test_normalization_and_fingerprint_semantics():
    assert normalize_text("  أهلاً   بالعالم  ") == "أهلاً بالعالم"
    assert normalize_text("مـحـمـد") == "محمد"
    assert normalize_answer("أحمد") == normalize_answer("احمد")
    one = fingerprint("flags", "ما عاصمة الكويت؟", "مدينة الكويت")
    two = fingerprint("flags", "ما عاصمة الكويت؟", "مدينة الكويت")
    three = fingerprint("flags", "ما عاصمة قطر؟", "الدوحة")
    assert one == two
    assert one != three
    assert len(one) == 64
