"""Integration attacks using explicitly synthetic facts in temporary databases."""

import asyncio

import pytest

from app.db import transaction
from app.services.selector import allocate_bucket
from app.utils.errors import AppError


async def inventory(db):
    cursor = await db.execute("INSERT INTO categories(slug,name_ar,icon) VALUES('tiny','اختبار','Hash')")
    category_id = cursor.lastrowid
    await db.execute("INSERT INTO football_entities(id,display_name_ar) VALUES('player:test','اختبار')")
    ids = []
    for index in range(9):
        cursor = await db.execute(
            """INSERT INTO questions(category_id,difficulty,question_type,question_text,answer_text,
            content_origin,fingerprint,fact_group_id) VALUES(?,200,'text',?,?,'generated_puzzle',?,?)""",
            (category_id, f"سؤال اختبار {index}", str(index), f"test:{index}", f"legacy:{index}"),
        )
        ids.append(cursor.lastrowid)
        if index == 8:  # Legacy rows remain readable, never implicitly verified.
            continue
        await db.execute(
            "INSERT OR IGNORE INTO football_facts(id,topic_id,primary_entity_id) VALUES(?, 'test', 'player:test')",
            (f"fact:{index // 2}" if index < 2 else f"fact:{index}",),
        )
        await db.execute(
            """INSERT INTO question_metadata(question_id,fact_id,archetype,template_family,
            quality_score,editorial_note,review_status,mechanic,visual_json)
            VALUES(?,?,'career_clues','test',0.8,'Synthetic fixture',?,?,?)""",
            (ids[-1], f"fact:{index // 2}" if index < 2 else f"fact:{index}",
             "quarantined" if index == 6 else "published",
             "vector_formation" if index == 7 else "direct_recall",
             '{"version":1,"type":"malicious_svg"}' if index == 7 else None),
        )
    return category_id, ids


@pytest.mark.asyncio
async def test_strict_policy_rejects_legacy_quarantined_and_invalid_visual(settings):
    async with transaction(settings) as db:
        category_id, ids = await inventory(db)
        await db.execute("INSERT INTO football_category_policy(category_id) VALUES(?)", (category_id,))
        allocation = await allocate_bucket(db, settings, category_id=category_id, slug="tiny", difficulty=200,
                                           used_groups=set(), cooldown_groups=set(), salt="strict")
        selected = allocation.primary_ids + [allocation.backup_id]
        assert len(selected) == 3
        assert not set(selected) & set(ids[6:])
        assert len(set(selected) & set(ids[:2])) <= 1


@pytest.mark.asyncio
async def test_participant_seen_fact_excludes_unseen_paraphrase(settings):
    async with transaction(settings) as db:
        category_id, ids = await inventory(db)
        cursor = await db.execute("INSERT INTO users(display_name) VALUES('اختبار')")
        user_id = cursor.lastrowid
        await db.execute("INSERT INTO user_question_history(user_id,question_id) VALUES(?,?)", (user_id, ids[0]))
        allocation = await allocate_bucket(db, settings, category_id=category_id, slug="tiny", difficulty=200,
                                           used_groups=set(), cooldown_groups=set(), salt="seen",
                                           excluded_user_ids=(user_id,))
        assert not set(allocation.primary_ids + [allocation.backup_id]) & set(ids[:2])


@pytest.mark.asyncio
async def test_strict_exhaustion_does_not_fall_back_to_unverified_legacy(settings):
    with pytest.raises(AppError) as error:
        async with transaction(settings) as db:
            category_id, ids = await inventory(db)
            await db.execute("INSERT INTO football_category_policy(category_id) VALUES(?)", (category_id,))
            await db.execute("UPDATE question_metadata SET review_status='quarantined' WHERE question_id NOT IN (?,?)", (ids[0], ids[1]))
            await allocate_bucket(db, settings, category_id=category_id, slug="tiny", difficulty=200,
                                  used_groups=set(), cooldown_groups=set(), salt="exhaust")
    assert error.value.code == "INSUFFICIENT_QUESTIONS"


@pytest.mark.asyncio
async def test_null_legacy_group_is_not_a_shared_fact(settings):
    async with transaction(settings) as db:
        category_id, ids = await inventory(db)
        await db.execute("UPDATE questions SET is_active=0 WHERE id NOT IN (?,?,?)", tuple(ids[2:5]))
        await db.execute("UPDATE questions SET fact_group_id=NULL WHERE id IN (?,?,?)", tuple(ids[2:5]))
        allocation = await allocate_bucket(db, settings, category_id=category_id, slug="tiny", difficulty=200,
                                           used_groups=set(), cooldown_groups=set(), salt="unknown")
        assert set(allocation.primary_ids + [allocation.backup_id]) == set(ids[2:5])


@pytest.mark.asyncio
async def test_active_reservation_excludes_canonical_paraphrase(settings):
    from app.services.selector import eligible_questions

    async with transaction(settings) as db:
        category_id, ids = await inventory(db)
        cursor = await db.execute("INSERT INTO matches(match_code,team1_name,team2_name) VALUES('RESERVE','أ','ب')")
        await db.execute(
            "INSERT INTO match_tiles(match_id,tile_key,category_id,difficulty,question_id) VALUES(?,'one',?,200,?)",
            (cursor.lastrowid, category_id, ids[0]),
        )
        eligible = await eligible_questions(db, category_id, 200, 1)
        assert not {row["id"] for row in eligible} & set(ids[:2])


@pytest.mark.asyncio
async def test_concurrent_transactions_reserve_disjoint_canonical_facts(settings):
    from app.db import connect

    async with transaction(settings) as db:
        category_id, _ = await inventory(db)

    async def reserve(code):
        async with transaction(settings) as db:
            allocation = await allocate_bucket(db, settings, category_id=category_id, slug="tiny", difficulty=200,
                                               used_groups=set(), cooldown_groups=set(), salt=code)
            cursor = await db.execute("INSERT INTO matches(match_code,team1_name,team2_name) VALUES(?,'أ','ب')", (code,))
            match_id = cursor.lastrowid
            selected = allocation.primary_ids + [allocation.backup_id]
            for index, question_id in enumerate(selected):
                await db.execute(
                    "INSERT INTO match_tiles(match_id,tile_key,category_id,difficulty,question_id) VALUES(?,?,?,200,?)",
                    (match_id, str(index), category_id, question_id),
                )
            return selected

    first, second = await asyncio.gather(reserve("FIRST"), reserve("SECOND"))
    assert set(first).isdisjoint(second)
    async with connect(settings) as db:
        cursor = await db.execute(
            "SELECT qm.fact_id FROM match_tiles mt JOIN question_metadata qm ON qm.question_id=mt.question_id"
        )
        facts = [row["fact_id"] for row in await cursor.fetchall()]
    assert len(facts) == len(set(facts))
