"""الهوية الجهازية والملفات وضمان عدم التكرار.

تغطي هذه الوحدة ضمانات المهمة الأساسية ضد قاعدة حقيقية:
تسجيل التثبيت الخامل، الملفات المسماة، تسجيل التعرّض لحظة الفتح،
استبعاد سجل أي هوية فعلية عند الاختيار، وبقاء السجل بعد حذف المباراة.
"""

from __future__ import annotations

import asyncio
import sqlite3

import pytest

from app.db import connect, init_db, transaction
from app.models import MatchCreateIn
from app.services.history import history_count, record_exposures
from app.services.identity import create_profile, list_profiles, register_installation
from app.services.matches import create_match, open_tile, reroll_tile, resolve_tile
from app.services.selector import bucket_cycle, eligible_questions
from app.utils.errors import AppError
from tests.conftest import (
    SIX_CATEGORIES,
    auth_headers,
    hosted_create,
    make_installation,
    make_installation_row,
)
from tests.test_api_and_matches import make_match


def profile_payload(team1_ids=(), team2_ids=()):
    return MatchCreateIn(
        team1_name="فريق الصقور",
        team2_name="فريق الذيابة",
        starting_turn="team1",
        category_slugs=list(SIX_CATEGORIES),
        team1_user_ids=list(team1_ids),
        team2_user_ids=list(team2_ids),
    )


async def hosted_profile_match(settings, payload, key):
    installation_id, _ = await make_installation_row(settings, f"{key}-host")
    board = await create_match(
        settings, payload, key, host_installation_id=installation_id
    )
    return installation_id, board


async def history_rows(settings, user_id):
    async with connect(settings) as db:
        cursor = await db.execute(
            "SELECT question_id, match_id, outcome FROM user_question_history"
            " WHERE user_id = ? ORDER BY question_id",
            (user_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            (int(row["question_id"]), row["match_id"], row["outcome"]) for row in rows
        ]


@pytest.mark.asyncio
async def test_installation_registration_idempotent_and_shadow_bound(seeded_settings):
    first = await register_installation(seeded_settings, "install-idem")
    second = await register_installation(seeded_settings, "install-idem")
    assert first["installation_id"] == second["installation_id"]
    assert first["shadow_user_id"] == second["shadow_user_id"]
    assert second["idempotent_replay"] is True
    assert first["credential"] == second["credential"]
    assert "credential_hash" not in first

    other = await register_installation(seeded_settings, "install-other")
    assert other["installation_id"] != first["installation_id"]
    assert other["shadow_user_id"] != first["shadow_user_id"]

    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM users WHERE kind = 'shadow'"
        )
        assert (await cursor.fetchone())["n"] == 2
        await cursor.close()


@pytest.mark.asyncio
async def test_concurrent_same_key_registration_single_installation(seeded_settings):
    results = await asyncio.gather(
        *(register_installation(seeded_settings, "install-race") for _ in range(5))
    )
    ids = {result["installation_id"] for result in results}
    shadows = {result["shadow_user_id"] for result in results}
    assert len(ids) == 1
    assert len(shadows) == 1
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM device_installations WHERE id = ?",
            (next(iter(ids)),),
        )
        assert (await cursor.fetchone())["n"] == 1
        await cursor.close()


@pytest.mark.asyncio
async def test_profile_creation_duplicate_and_listing(seeded_settings):
    profile = await create_profile(
        seeded_settings, username="sara", display_name="سارة"
    )
    assert profile["kind"] == "named"
    with pytest.raises(AppError) as exc:
        await create_profile(seeded_settings, username="sara", display_name="سارة 2")
    assert exc.value.code == "PROFILE_USERNAME_TAKEN"

    await register_installation(seeded_settings, "install-shadow-list")
    names = [row["username"] for row in await list_profiles(seeded_settings)]
    assert names == ["sara"]


@pytest.mark.asyncio
async def test_open_tile_records_exposure_for_all_effective_identities(seeded_settings):
    profile = await create_profile(seeded_settings, username="omar", display_name="عمر")
    installation_id, board = await hosted_profile_match(
        seeded_settings, profile_payload(team1_ids=[profile["id"]]), "expose-all"
    )
    code = board["match"]["match_code"]
    tile = board["tiles"][0]
    opened = await open_tile(
        seeded_settings,
        code,
        tile["tile_key"],
        expected_version=1,
        idempotency_key="expose-open-1",
        host_token=board["host_token"],
    )
    question_id = opened["tile"]["question"]["id"]

    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT shadow_user_id FROM device_installations WHERE id = ?",
            (installation_id,),
        )
        shadow_id = int((await cursor.fetchone())["shadow_user_id"])
        await cursor.close()

    profile_rows = await history_rows(seeded_settings, profile["id"])
    shadow_rows = await history_rows(seeded_settings, shadow_id)
    assert len(profile_rows) == 1
    assert len(shadow_rows) == 1
    assert profile_rows[0][0] == question_id == shadow_rows[0][0]
    assert profile_rows[0][2] == "none"

    # إعادة نفس الفتح بنفس مفتاح التكرار: ردّ مخزّن دون صفوف مكررة.
    replay = await open_tile(
        seeded_settings,
        code,
        tile["tile_key"],
        expected_version=1,
        idempotency_key="expose-open-1",
        host_token=board["host_token"],
    )
    assert replay["idempotent_replay"] is True
    assert await history_rows(seeded_settings, profile["id"]) == profile_rows


@pytest.mark.asyncio
async def test_seen_question_excluded_for_any_member_even_cross_team(seeded_settings):
    seen_profile = await create_profile(
        seeded_settings, username="seen-a", display_name="أ"
    )
    _, first = await hosted_profile_match(
        seeded_settings, profile_payload(team1_ids=[seen_profile["id"]]), "cross-first"
    )
    opened = await open_tile(
        seeded_settings,
        first["match"]["match_code"],
        first["tiles"][0]["tile_key"],
        expected_version=1,
        idempotency_key="cross-open-1",
        host_token=first["host_token"],
    )
    seen_qid = opened["tile"]["question"]["id"]

    fresh = await create_profile(seeded_settings, username="fresh-b", display_name="ب")
    _, second = await hosted_profile_match(
        seeded_settings,
        profile_payload(team1_ids=[seen_profile["id"]], team2_ids=[fresh["id"]]),
        "cross-second",
    )
    allocated = {
        tile["question"]["id"] for tile in second["tiles"] + second["backups"]
    }
    assert seen_qid not in allocated


@pytest.mark.asyncio
async def test_installation_history_applies_across_profiles(seeded_settings):
    installation_id, credential = await make_installation_row(
        seeded_settings, "install-shared"
    )
    first = await create_match(
        seeded_settings,
        profile_payload(),
        "install-shared-first",
        host_installation_id=installation_id,
    )
    opened = await open_tile(
        seeded_settings,
        first["match"]["match_code"],
        first["tiles"][0]["tile_key"],
        expected_version=1,
        idempotency_key="install-shared-open",
        host_token=first["host_token"],
    )
    seen_qid = opened["tile"]["question"]["id"]

    newcomer = await create_profile(
        seeded_settings, username="newcomer", display_name="جديد"
    )
    second = await create_match(
        seeded_settings,
        profile_payload(team1_ids=[newcomer["id"]]),
        "install-shared-second",
        host_installation_id=installation_id,
    )
    allocated = {
        tile["question"]["id"] for tile in second["tiles"] + second["backups"]
    }
    assert seen_qid not in allocated
    assert credential  # الاعتماد صدر وسجّل؛ لا حاجة لإعادة استخدامه هنا.


@pytest.mark.asyncio
async def test_profile_history_follows_across_installations(seeded_settings):
    traveler = await create_profile(
        seeded_settings, username="traveler", display_name="متنقل"
    )
    _, first = await hosted_profile_match(
        seeded_settings, profile_payload(team1_ids=[traveler["id"]]), "travel-first"
    )
    opened = await open_tile(
        seeded_settings,
        first["match"]["match_code"],
        first["tiles"][0]["tile_key"],
        expected_version=1,
        idempotency_key="travel-open-1",
        host_token=first["host_token"],
    )
    seen_qid = opened["tile"]["question"]["id"]

    _, second = await hosted_profile_match(
        seeded_settings, profile_payload(team1_ids=[traveler["id"]]), "travel-second"
    )
    allocated = {
        tile["question"]["id"] for tile in second["tiles"] + second["backups"]
    }
    assert seen_qid not in allocated


@pytest.mark.asyncio
async def test_unused_backup_not_recorded_but_rerolled_backup_is(seeded_settings):
    profile = await create_profile(
        seeded_settings, username="backup-p", display_name="احتياط"
    )
    installation_id, board = await hosted_profile_match(
        seeded_settings, profile_payload(team1_ids=[profile["id"]]), "backup-flow"
    )
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT shadow_user_id FROM device_installations WHERE id = ?",
            (installation_id,),
        )
        shadow_id = int((await cursor.fetchone())["shadow_user_id"])
        await cursor.close()
    async with connect(seeded_settings) as db:
        cursor = await db.execute("SELECT COUNT(*) AS n FROM user_question_history")
        assert (await cursor.fetchone())["n"] == 0
        await cursor.close()

    old_qid = board["tiles"][0]["question"]["id"]
    rerolled = await reroll_tile(
        seeded_settings,
        board["match"]["match_code"],
        board["tiles"][0]["tile_key"],
        expected_version=1,
        idempotency_key="backup-reroll-1",
        host_token=board["host_token"],
    )
    new_qid = rerolled["tile"]["question"]["id"]
    assert new_qid != old_qid
    assert [row[0] for row in await history_rows(seeded_settings, profile["id"])] == [
        new_qid
    ]
    assert [row[0] for row in await history_rows(seeded_settings, shadow_id)] == [
        new_qid
    ]

    resolved = await resolve_tile(
        seeded_settings,
        board["match"]["match_code"],
        board["tiles"][0]["tile_key"],
        outcome="team1",
        powers_applied=[],
        expected_version=2,
        idempotency_key="backup-resolve-1",
        host_token=board["host_token"],
    )
    assert resolved["match"]["score_team1"] >= 0
    profile_rows = await history_rows(seeded_settings, profile["id"])
    assert len(profile_rows) == 1
    assert profile_rows[0][2] == "team1"


@pytest.mark.asyncio
async def test_exposure_conflict_from_other_match_fails_closed(seeded_settings):
    profile = await create_profile(
        seeded_settings, username="conflict-p", display_name="ت"
    )
    _, first = await hosted_profile_match(
        seeded_settings, profile_payload(team1_ids=[profile["id"]]), "conflict-first"
    )
    _, second = await hosted_profile_match(
        seeded_settings, profile_payload(team1_ids=[profile["id"]]), "conflict-second"
    )
    question_id = first["tiles"][0]["question"]["id"]
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT id, match_code FROM matches ORDER BY id"
        )
        matches = {row["match_code"]: int(row["id"]) for row in await cursor.fetchall()}
        await cursor.close()
    first_id = matches[first["match"]["match_code"]]
    second_id = matches[second["match"]["match_code"]]
    async with transaction(seeded_settings) as db:
        assert await record_exposures(db, [profile["id"]], question_id, first_id) == 1
        assert await record_exposures(db, [profile["id"]], question_id, first_id) == 0
        with pytest.raises(AppError) as exc:
            await record_exposures(db, [profile["id"]], question_id, second_id)
        assert exc.value.code == "HISTORY_CONFLICT"


@pytest.mark.asyncio
async def test_invalid_and_cross_team_participants_rejected(seeded_settings):
    profile = await create_profile(seeded_settings, username="dup-p", display_name="م")
    with pytest.raises(AppError) as exc:
        await hosted_create(
            seeded_settings, profile_payload(team1_ids=[profile["id"]],
                                             team2_ids=[profile["id"]]), "dup-teams",
        )
    assert exc.value.code == "PARTICIPANT_TEAM_CONFLICT"
    with pytest.raises(AppError) as exc:
        await hosted_create(
            seeded_settings, profile_payload(team1_ids=[999999]), "ghost-member"
        )
    assert exc.value.code == "PARTICIPANT_NOT_FOUND"


@pytest.mark.asyncio
async def test_history_survives_match_delete_and_blocks_question_delete(seeded_settings):
    profile = await create_profile(seeded_settings, username="kept", display_name="باقي")
    _, board = await hosted_profile_match(
        seeded_settings, profile_payload(team1_ids=[profile["id"]]), "kept-first"
    )
    opened = await open_tile(
        seeded_settings,
        board["match"]["match_code"],
        board["tiles"][0]["tile_key"],
        expected_version=1,
        idempotency_key="kept-open-1",
        host_token=board["host_token"],
    )
    seen_qid = opened["tile"]["question"]["id"]
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT id FROM matches WHERE match_code = ?", (board["match"]["match_code"],)
        )
        match_id = int((await cursor.fetchone())["id"])
        await cursor.close()
    async with transaction(seeded_settings) as db:
        await db.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    rows = await history_rows(seeded_settings, profile["id"])
    assert [row[0] for row in rows] == [seen_qid]
    assert rows[0][1] is None
    with pytest.raises(sqlite3.IntegrityError):
        async with transaction(seeded_settings) as db:
            await db.execute("DELETE FROM questions WHERE id = ?", (seen_qid,))


@pytest.mark.asyncio
async def test_eligible_query_excludes_seen_and_keeps_unseen(seeded_settings):
    profile = await create_profile(seeded_settings, username="query-p", display_name="س")
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT id, category_id, difficulty FROM questions"
            " WHERE is_active = 1 AND is_reserved_backup = 0 LIMIT 1"
        )
        row = await cursor.fetchone()
        await cursor.close()
        question_id = int(row["id"])
        cycle = await bucket_cycle(db, int(row["category_id"]), int(row["difficulty"]))
        before = await eligible_questions(
            db, int(row["category_id"]), int(row["difficulty"]), cycle,
            excluded_user_ids=(profile["id"],),
        )
        assert {int(item["id"]) for item in before} == {
            int(item["id"])
            for item in await eligible_questions(
                db, int(row["category_id"]), int(row["difficulty"]), cycle
            )
        }
        assert question_id in {int(item["id"]) for item in before}
    _, holder = await hosted_profile_match(
        seeded_settings, profile_payload(), "query-holder"
    )
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT id FROM matches WHERE match_code = ?",
            (holder["match"]["match_code"],),
        )
        holder_id = int((await cursor.fetchone())["id"])
        await cursor.close()
    async with transaction(seeded_settings) as db:
        await record_exposures(db, [profile["id"]], question_id, holder_id)
    async with connect(seeded_settings) as db:
        after = await eligible_questions(
            db, int(row["category_id"]), int(row["difficulty"]), cycle,
            excluded_user_ids=(profile["id"],),
        )
        assert question_id not in {int(item["id"]) for item in after}


@pytest.mark.asyncio
async def test_migration_rerun_is_idempotent(seeded_settings):
    async with connect(seeded_settings) as db:
        cursor = await db.execute("SELECT COUNT(*) AS n FROM questions")
        before = int((await cursor.fetchone())["n"])
        await cursor.close()
    await init_db(seeded_settings)
    async with connect(seeded_settings) as db:
        cursor = await db.execute("SELECT COUNT(*) AS n FROM questions")
        assert int((await cursor.fetchone())["n"]) == before
        await cursor.close()
        cursor = await db.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'user_question_history'"
        )
        assert "UNIQUE(user_id, question_id)" in (await cursor.fetchone())["sql"]
        await cursor.close()


@pytest.mark.asyncio
async def test_identity_api_contracts(client):
    created = await client.post(
        "/api/v1/users",
        json={"username": "api-sara", "display_name": "سارة"},
        headers=auth_headers("api-user-1"),
    )
    assert created.status_code == 201, created.text
    profile_id = created.json()["id"]
    duplicate = await client.post(
        "/api/v1/users",
        json={"username": "api-sara", "display_name": "أخرى"},
        headers=auth_headers("api-user-2"),
    )
    assert duplicate.status_code == 409

    registration = await make_installation(client, "api-install-1")
    assert registration["credential"]
    listing = await client.get("/api/v1/users")
    assert listing.status_code == 200
    assert {row["kind"] for row in listing.json()} == {"named"}

    me = await client.get(
        "/api/v1/installations/me",
        headers={"X-Install-Token": registration["credential"]},
    )
    assert me.status_code == 200
    assert me.json()["installation_id"] == registration["installation_id"]
    anonymous = await client.get("/api/v1/installations/me")
    assert anonymous.status_code == 403

    missing = await client.post(
        "/api/v1/matches",
        json={
            "team1_name": "فريق الصقور",
            "team2_name": "فريق الذيابة",
            "starting_turn": "team1",
            "category_slugs": list(SIX_CATEGORIES),
            "team1_user_ids": [profile_id],
        },
        headers=auth_headers("api-no-install"),
    )
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "INSTALL_TOKEN_REQUIRED"

    bogus = await client.post(
        "/api/v1/matches",
        json={
            "team1_name": "فريق الصقور",
            "team2_name": "فريق الذيابة",
            "starting_turn": "team1",
            "category_slugs": list(SIX_CATEGORIES),
        },
        headers=auth_headers("api-bad-install", install="bogus-token"),
    )
    assert bogus.status_code == 403

    board = await make_match(
        client, key="api-profile-match", install=registration["credential"],
        team1_user_ids=[profile_id],
    )
    participants = board.get("participants", [])
    assert {member["user_id"] for member in participants} >= {profile_id}
