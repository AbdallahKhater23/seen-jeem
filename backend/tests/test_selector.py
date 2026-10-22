from __future__ import annotations

import asyncio
import random
from dataclasses import replace

import pytest

from app.config import load_settings
from app.db import connect, init_db, transaction
from app.models import MatchCreateIn
from app.services.matches import (
    abandon_match,
    get_match,
    reroll_tile,
    resolve_tile,
)
from app.services.selector import (
    COOLDOWN_MATCHES,
    allocate_bucket,
    recent_cooldown_groups,
)
from app.utils.errors import AppError
from tests.conftest import SIX_CATEGORIES, hosted_create


def match_payload(**overrides):
    values = {
        "team1_name": "فريق الصقور",
        "team2_name": "فريق الذيابة",
        "starting_turn": "team1",
        "category_slugs": list(SIX_CATEGORIES),
    }
    values.update(overrides)
    return MatchCreateIn(**values)


@pytest.mark.asyncio
async def test_create_match_allocates_36_primaries_and_18_backups(seeded_settings):
    board = await hosted_create(seeded_settings, match_payload(), "match-shape")
    assert board["match"]["selected_categories"] == SIX_CATEGORIES
    assert board["match"]["current_turn"] == "team1"
    assert len(board["tiles"]) == 36
    assert len(board["backups"]) == 18
    assert {tile["category_slug"] for tile in board["tiles"]} == set(SIX_CATEGORIES)
    counts: dict[tuple[str, int], int] = {}
    for tile in board["tiles"]:
        counts[(tile["category_slug"], tile["difficulty"])] = (
            counts.get((tile["category_slug"], tile["difficulty"]), 0) + 1
        )
    assert len(counts) == 18
    assert all(value == 2 for value in counts.values())
    assert all(tile["is_backup"] is False for tile in board["tiles"])
    assert all(tile["is_backup"] is True for tile in board["backups"])

    primaries = {tile["question"]["id"] for tile in board["tiles"]}
    backups = {tile["question"]["id"] for tile in board["backups"]}
    assert len(primaries) == 36
    assert len(backups) == 18
    assert primaries.isdisjoint(backups)
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT q.fact_group_id FROM match_tiles mt JOIN questions q ON q.id=mt.question_id "
            "JOIN matches m ON m.id=mt.match_id WHERE m.match_code=?",
            (board["match"]["match_code"],),
        )
        groups = [row["fact_group_id"] for row in await cursor.fetchall()]
        await cursor.close()
        assert len(groups) == len(set(groups)) == 54
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions WHERE times_played > 0"
        )
        assert (await cursor.fetchone())["n"] == 0
        await cursor.close()


@pytest.mark.asyncio
async def test_backups_are_bucket_scoped(seeded_settings):
    board = await hosted_create(seeded_settings, match_payload(), "match-backups")
    assert {tile["tile_key"] for tile in board["backups"]} == {
        f"backup-{slug}-{difficulty}"
        for slug in SIX_CATEGORIES
        for difficulty in (200, 400, 600)
    }
    for tile in board["backups"]:
        assert tile["compatible_categories"] == [tile["category_slug"]]
        assert tile["compatible_difficulties"] == [tile["difficulty"]]
        assert tile["question"]["category_slug"] == tile["category_slug"]
        assert tile["question"]["difficulty"] == tile["difficulty"]


@pytest.mark.asyncio
async def test_creation_is_deterministic_for_same_seed(tmp_path):
    base = load_settings()
    first_settings = replace(
        base, database_path=tmp_path / "one.db", seed_random_seed=777, seed_version="det"
    )
    second_settings = replace(
        base, database_path=tmp_path / "two.db", seed_random_seed=777, seed_version="det"
    )
    from app.services.seed import seed_database

    await seed_database(first_settings, deterministic_seed=777)
    await seed_database(second_settings, deterministic_seed=777)
    first = await hosted_create(first_settings, match_payload(), "det-1")
    second = await hosted_create(second_settings, match_payload(), "det-1")
    assert [tile["question"]["id"] for tile in first["tiles"]] == [
        tile["question"]["id"] for tile in second["tiles"]
    ]


@pytest.mark.asyncio
async def test_concurrent_creates_reserve_disjoint_questions(seeded_settings):
    first, second = await asyncio.gather(
        hosted_create(seeded_settings, match_payload(), "concurrent-a"),
        hosted_create(seeded_settings, match_payload(), "concurrent-b"),
    )
    q1 = {tile["question"]["id"] for tile in first["tiles"] + first["backups"]}
    q2 = {tile["question"]["id"] for tile in second["tiles"] + second["backups"]}
    assert len(q1) == len(q2) == 54
    assert q1.isdisjoint(q2)


@pytest.mark.asyncio
async def test_resolution_counts_usage_once_and_respects_idempotency(seeded_settings):
    board = await hosted_create(seeded_settings, match_payload(), "usage-shape")
    code = board["match"]["match_code"]
    host = board["host_token"]
    tile = board["tiles"][0]
    result = await resolve_tile(
        seeded_settings,
        code,
        tile["tile_key"],
        outcome="team1",
        powers_applied=[],
        expected_version=1,
        idempotency_key="usage-resolve",
        host_token=host,
    )
    assert result["match"]["score_team1"] == tile["difficulty"]
    assert result["match"]["current_turn"] == "team2"
    replay = await resolve_tile(
        seeded_settings,
        code,
        tile["tile_key"],
        outcome="team1",
        powers_applied=[],
        expected_version=1,
        idempotency_key="usage-resolve",
        host_token=host,
    )
    assert replay["idempotent_replay"] is True
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT times_played FROM questions WHERE id = ?", (tile["question"]["id"],)
        )
        assert (await cursor.fetchone())["times_played"] == 1
        await cursor.close()
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM question_usage WHERE question_id = ?",
            (tile["question"]["id"],),
        )
        assert (await cursor.fetchone())["n"] == 1
        await cursor.close()

    with pytest.raises(AppError) as exc:
        await resolve_tile(
            seeded_settings,
            code,
            tile["tile_key"],
            outcome="team1",
            powers_applied=[],
            expected_version=2,
            idempotency_key="usage-resolve-2",
            host_token=host,
        )
    assert exc.value.code == "TILE_ALREADY_PLAYED"
    with pytest.raises(AppError) as exc:
        await resolve_tile(
            seeded_settings,
            code,
            tile["tile_key"],
            outcome="team1",
            powers_applied=[],
            expected_version=2,
            idempotency_key="usage-resolve-intruder",
        )
    assert exc.value.code == "HOST_TOKEN_REQUIRED"
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT times_played FROM questions WHERE id = ?", (tile["question"]["id"],)
        )
        assert (await cursor.fetchone())["times_played"] == 1
        await cursor.close()


@pytest.mark.asyncio
async def test_reroll_swaps_bucket_backup_without_burning_question(seeded_settings):
    board = await hosted_create(seeded_settings, match_payload(), "reroll-shape")
    code = board["match"]["match_code"]
    host = board["host_token"]
    tile = board["tiles"][0]
    old_question = tile["question"]["id"]
    result = await reroll_tile(
        seeded_settings,
        code,
        tile["tile_key"],
        expected_version=1,
        idempotency_key="reroll-1",
        host_token=host,
    )
    assert result["backup_used"] == f"backup-{tile['category_slug']}-{tile['difficulty']}"
    assert result["tile"]["question"]["id"] != old_question
    assert result["tile"]["question"]["difficulty"] == tile["difficulty"]
    assert result["match"]["version"] == 2

    resolved = await resolve_tile(
        seeded_settings,
        code,
        tile["tile_key"],
        outcome="team1",
        powers_applied=[],
        expected_version=2,
        idempotency_key="reroll-resolve",
        host_token=host,
    )
    assert resolved["match"]["score_team1"] == tile["difficulty"]
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT times_played FROM questions WHERE id IN (?, ?)",
            (old_question, result["tile"]["question"]["id"]),
        )
        usage = {row[0] for row in await cursor.fetchall()}
        await cursor.close()
    assert usage == {0, 1}

    with pytest.raises(AppError) as exc:
        await reroll_tile(
            seeded_settings,
            code,
            tile["tile_key"],
            expected_version=3,
            idempotency_key="reroll-after-play",
            host_token=host,
        )
    assert exc.value.code == "TILE_ALREADY_PLAYED"


@pytest.mark.asyncio
async def test_concurrent_reroll_same_tile_succeeds_once(seeded_settings):
    board = await hosted_create(seeded_settings, match_payload(), "reroll-concurrent")
    code = board["match"]["match_code"]
    host = board["host_token"]
    tile = board["tiles"][0]
    results = await asyncio.gather(
        reroll_tile(
            seeded_settings,
            code,
            tile["tile_key"],
            expected_version=1,
            idempotency_key="reroll-a",
            host_token=host,
        ),
        reroll_tile(
            seeded_settings,
            code,
            tile["tile_key"],
            expected_version=1,
            idempotency_key="reroll-b",
            host_token=host,
        ),
        return_exceptions=True,
    )
    success = [item for item in results if isinstance(item, dict)]
    failure = [item for item in results if isinstance(item, Exception)]
    assert len(success) == 1
    assert len(failure) == 1
    assert isinstance(failure[0], AppError)
    fresh = await get_match(seeded_settings, code)
    assert fresh["match"]["version"] == 2
    assert len([tile for tile in fresh["backups"] if tile["status"] == "rerolled"]) == 1


@pytest.mark.asyncio
async def test_abandon_releases_reservations(seeded_settings):
    board = await hosted_create(seeded_settings, match_payload(), "abandon-release")
    code = board["match"]["match_code"]
    host = board["host_token"]
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) AS n FROM match_tiles mt
            JOIN matches m ON m.id = mt.match_id
            WHERE m.status = 'active' AND mt.status = 'unplayed'
            """
        )
        assert (await cursor.fetchone())["n"] == 54
        await cursor.close()
    await abandon_match(
        seeded_settings,
        code,
        expected_version=1,
        idempotency_key="abandon-release",
        host_token=host,
    )
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) AS n FROM match_tiles mt
            JOIN matches m ON m.id = mt.match_id
            WHERE m.status = 'active' AND mt.status = 'unplayed'
            """
        )
        assert (await cursor.fetchone())["n"] == 0
        await cursor.close()
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions WHERE times_played > 0"
        )
        assert (await cursor.fetchone())["n"] == 0
        await cursor.close()


@pytest.mark.asyncio
async def test_bucket_exhaustion_reshuffles_only_that_bucket(seeded_settings):
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            """
            SELECT q.id FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE c.slug = 'flags' AND q.difficulty = 200 AND q.is_reserved_backup = 0
            """
        )
        ids = [row["id"] for row in await cursor.fetchall()]
        await cursor.close()
        for question_id in ids:
            await db.execute(
                "INSERT OR IGNORE INTO question_usage(question_id, cycle) VALUES (?, 1)",
                (question_id,),
            )
        await db.commit()
        total = len(ids)
    assert total >= 100

    board = await hosted_create(seeded_settings, match_payload(), "exhaustion-create")
    assert len(board["tiles"]) == 36
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            """
            SELECT c.slug, b.difficulty, b.cycle
            FROM question_buckets b JOIN categories c ON c.id = b.category_id
            """
        )
        cycles = {
            (row["slug"], row["difficulty"]): row["cycle"] for row in await cursor.fetchall()
        }
        await cursor.close()
        cursor = await db.execute("SELECT COUNT(*) AS n FROM question_usage")
        usage = (await cursor.fetchone())["n"]
        await cursor.close()
    assert cycles[("flags", 200)] == 2
    assert all(cycle == 1 for key, cycle in cycles.items() if key != ("flags", 200))
    assert usage == total


@pytest.mark.asyncio
async def test_insufficient_inventory_rolls_back_entire_match(seeded_settings):
    async with connect(seeded_settings) as db:
        await db.execute(
            """
            DELETE FROM questions
            WHERE category_id = (SELECT id FROM categories WHERE slug = 'flags')
              AND difficulty = 200 AND is_reserved_backup = 0
            """
        )
        await db.commit()
    with pytest.raises(AppError) as exc:
        await hosted_create(seeded_settings, match_payload(), "rollback-create")
    assert exc.value.code == "INSUFFICIENT_QUESTIONS"
    assert exc.value.details["bucket"] == "flags:200"
    async with connect(seeded_settings) as db:
        cursor = await db.execute("SELECT COUNT(*) AS n FROM matches")
        assert (await cursor.fetchone())["n"] == 0
        await cursor.close()
        cursor = await db.execute("SELECT COUNT(*) AS n FROM match_tiles")
        assert (await cursor.fetchone())["n"] == 0
        await cursor.close()


@pytest.mark.asyncio
async def test_unknown_category_and_duplicate_slugs_rejected(seeded_settings):
    with pytest.raises(Exception):
        MatchCreateIn(
            team1_name="أ",
            team2_name="ب",
            category_slugs=["flags", "flags", "ucl", "riddles", "spotdiff", "clubs"],
        )
    with pytest.raises(AppError) as exc:
        await hosted_create(
            seeded_settings,
            MatchCreateIn(
                team1_name="أ",
                team2_name="ب",
                category_slugs=["flags", "capitals", "ucl", "riddles", "spotdiff", "nope"],
            ),
            "unknown-category",
        )
    assert exc.value.code == "UNKNOWN_CATEGORY"
    assert exc.value.details["categories"] == ["nope"]


@pytest.mark.asyncio
async def test_cooldown_query_uses_last_five_completed_matches(seeded_settings):
    board = await hosted_create(seeded_settings, match_payload(), "cooldown-create")
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT q.fact_group_id FROM match_tiles mt JOIN questions q ON q.id=mt.question_id "
            "JOIN categories c ON c.id=mt.category_id JOIN matches m ON m.id=mt.match_id "
            "WHERE m.match_code=? AND c.slug='riddles' AND mt.is_backup=0",
            (board["match"]["match_code"],),
        )
        groups = {row["fact_group_id"] for row in await cursor.fetchall()}
        await cursor.close()
    async with transaction(seeded_settings) as db:
        # نعلّم المباراة مكتملة وخاناتها ملعوبة لاختبار استعلام التهدئة فقط.
        await db.execute(
            "UPDATE matches SET status = 'completed' WHERE match_code = ?",
            (board["match"]["match_code"],),
        )
        await db.execute(
            "UPDATE match_tiles SET status = 'played' WHERE match_id ="
            " (SELECT id FROM matches WHERE match_code = ?) AND category_id ="
            " (SELECT id FROM categories WHERE slug = 'riddles')",
            (board["match"]["match_code"],),
        )
    async with connect(seeded_settings) as db:
        cooldown = await recent_cooldown_groups(db)
    assert groups <= cooldown
    assert len(cooldown) >= len(groups)
    assert COOLDOWN_MATCHES == 5


@pytest.mark.asyncio
async def test_relaxation_only_when_hard_candidates_below_three(seeded_settings):
    """دلو مصغّر: 3 مجموعات كلها في التهدئة → ينجح مع تسجيل الاسترخاء."""
    async with transaction(seeded_settings) as db:
        cursor = await db.execute(
            "INSERT INTO categories(slug, name_ar, icon, sort_order) VALUES ('tiny', 'صغير', 'Hash', 99)"
        )
        category_id = int(cursor.lastrowid)
        await cursor.close()
        await db.execute(
            "INSERT INTO question_buckets(category_id, difficulty, cycle) VALUES (?, 200, 1)",
            (category_id,),
        )
        for index in range(3):
            await db.execute(
                """
                INSERT INTO questions(
                    category_id, difficulty, question_type, question_text, answer_text,
                    content_origin, fingerprint, is_active, is_reserved_backup,
                    fact_group_id, verification_status, times_played, deck_position
                ) VALUES (?, 200, 'text', ?, ?, 'generated_puzzle', ?, 1, 0, ?, 'test_fixture', 0, ?)
                """,
                (category_id, f"سؤال دلو صغير {index}؟", str(index), f"tiny-fp-{index}", f"tiny:{index}", index),
            )
        await db.execute(
            """
            INSERT INTO matches(match_code, team1_name, team2_name, status, updated_at)
            VALUES ('COOLDOWN', 'أ', 'ب', 'completed', '2026-01-01T00:00:00Z')
            """
        )
        match_id = (await (await db.execute("SELECT id FROM matches WHERE match_code='COOLDOWN'")).fetchone())["id"]
        for index in range(3):
            question_id = (
                await (await db.execute("SELECT id FROM questions WHERE fingerprint = ?", (f"tiny-fp-{index}",))).fetchone()
            )["id"]
            await db.execute(
                """
                INSERT INTO match_tiles(match_id, tile_key, category_id, difficulty, question_id,
                    is_backup, status)
                VALUES (?, ?, ?, 200, ?, 0, 'played')
                """,
                (match_id, f"tiny-{index}", category_id, question_id),
            )

    async with transaction(seeded_settings) as db:
        allocation = await allocate_bucket(
            db,
            seeded_settings,
            category_id=category_id,
            slug="tiny",
            difficulty=200,
            used_groups=set(),
            cooldown_groups={"tiny:0", "tiny:1", "tiny:2"},
            salt="test",
        )
    assert len(allocation.primary_ids) == 2
    assert allocation.backup_id not in allocation.primary_ids
    assert allocation.relaxed is True


@pytest.mark.asyncio
async def test_duplicate_slugs_and_missing_key_are_rejected_by_api(client):
    response = await client.post(
        "/api/v1/matches",
        json={
            "team1_name": "أ",
            "team2_name": "ب",
            "category_slugs": ["flags", "flags", "ucl", "riddles", "spotdiff", "clubs"],
        },
        headers={"Idempotency-Key": "dup-slugs"},
    )
    assert response.status_code == 422
    no_key = await client.post(
        "/api/v1/matches",
        json={
            "team1_name": "أ",
            "team2_name": "ب",
            "category_slugs": list(SIX_CATEGORIES),
        },
    )
    assert no_key.status_code == 400
    assert no_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
