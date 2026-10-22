"""محاكاة 100 مباراة متتالية وسعة المخزون.

ملاحظة صريحة: بنك المحتوى الحقيقي (5,152 سؤالًا) لا يبلغ 201 سؤالًا في كل
دلو، لذلك **لا** يمكن ضمان 100 مباراة كاملة بست فئات حقيقية. الاختبار الأول
يوثّق هذا النقص بصدق، والثاني يثبت صحة محرك الاختيار على قاعدة اختبار معزولة
تحتوي مخزونًا اصطناعيًا موسومًا `test_fixture` (ليس محتوى إنتاجيًا).
"""

from __future__ import annotations

import pytest

from app.db import connect
from app.models import MatchCreateIn
from app.services.content import (
    CAPACITY_PER_BUCKET,
    CATEGORIES,
    CATEGORY_SLUGS,
    DIFFICULTIES,
    build_question_bank,
    inventory_report,
)
from app.services.matches import get_match, reroll_tile, resolve_tile
from tests.conftest import SIX_CATEGORIES, hosted_create

TOTAL_MATCHES = 100
PRIMARY_TILES = 36


def match_input(slugs: list[str], **overrides) -> MatchCreateIn:
    values = {
        "team1_name": "فريق الاختبار",
        "team2_name": "فريق التحقق",
        "starting_turn": "team1",
        "category_slugs": slugs,
    }
    values.update(overrides)
    return MatchCreateIn(**values)


def test_production_capacity_shortfall_is_documented():
    rows = build_question_bank()
    report = inventory_report(rows)
    assert report["meets_100_match_capacity"] is False
    missing_buckets = report["buckets_below_capacity_gate"]
    assert len(missing_buckets) > 0
    # الفئات الست المختارة للاختبار ليست كلها قادرة، لذا لا ندّعي ضمانًا.
    blocked = [
        f"{slug}:{difficulty}"
        for slug in SIX_CATEGORIES
        for difficulty in DIFFICULTIES
        if report["buckets"].get(f"{slug}:{difficulty}", 0) < CAPACITY_PER_BUCKET
    ]
    assert blocked, "لو تغيّر هذا، حدّث تقرير السعة بدل إخفاء النجاح"
    # التوزيع الكروي يُقاس من الوسوم الفعلية، والهدف غير محقق.
    distribution = report["football_distribution"]
    assert distribution["target_arab_percent"] == 15.0
    assert distribution["arab_percent"] < 15.0
    assert report["total"] < 4320 or report["meets_content_floor"] is False


@pytest.mark.asyncio
async def test_capacity_fixture_meets_gate_for_selected_categories(capacity_settings):
    async with connect(capacity_settings) as db:
        cursor = await db.execute(
            """
            SELECT c.slug, q.difficulty, COUNT(*) AS n
            FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE q.is_active = 1 AND q.is_reserved_backup = 0
            GROUP BY c.slug, q.difficulty
            """
        )
        counts = {(row["slug"], row["difficulty"]): row["n"] for row in await cursor.fetchall()}
        await cursor.close()
    for slug in CATEGORY_SLUGS:
        for difficulty in DIFFICULTIES:
            assert counts[(slug, difficulty)] >= CAPACITY_PER_BUCKET, (slug, difficulty)


@pytest.mark.asyncio
async def test_every_category_can_be_allocated(capacity_settings):
    """كل فئة من الاثنتي عشرة صالحة للاختيار مع خمس فئات أخرى."""
    for index, slug in enumerate(CATEGORY_SLUGS):
        others = [value for value in CATEGORY_SLUGS if value != slug][:5]
        board = await hosted_create(
            capacity_settings,
            match_input([slug, *others]),
            f"category-coverage-{index}",
        )
        assert len(board["tiles"]) == 36
        async with connect(capacity_settings) as db:
            cursor = await db.execute(
                'SELECT q.fact_group_id FROM match_tiles mt JOIN questions q ON q.id=mt.question_id '
                'JOIN matches m ON m.id=mt.match_id WHERE m.match_code=? AND mt.is_backup=0',
                (board['match']['match_code'],),
            )
            groups = [row[0] for row in await cursor.fetchall()]
            await cursor.close()
        assert len(set(groups)) == 36


@pytest.mark.asyncio
@pytest.mark.slow
async def test_100_consecutive_matches_zero_repeat_and_no_fact_collisions(capacity_settings):
    resolved_ids: set[int] = set()
    per_bucket_resolved: dict[tuple[str, int], int] = {}
    versions_checked = 0

    for match_index in range(TOTAL_MATCHES):
        board = await hosted_create(
            capacity_settings,
            match_input(SIX_CATEGORIES),
            f"hundred-create-{match_index}",
        )
        code = board["match"]["match_code"]
        host = board["host_token"]
        version = 1
        allocation = board["tiles"] + board["backups"]
        allocation_ids = [tile["question"]["id"] for tile in allocation]
        async with connect(capacity_settings) as db:
            cursor = await db.execute(
                'SELECT q.fact_group_id FROM match_tiles mt JOIN questions q ON q.id=mt.question_id '
                'JOIN matches m ON m.id=mt.match_id WHERE m.match_code=?', (code,),
            )
            allocation_groups = [row[0] for row in await cursor.fetchall()]
            await cursor.close()
        assert len(allocation) == 54
        assert len(set(allocation_ids)) == 54
        assert len(set(allocation_groups)) == 54
        assert len({(tile["category_slug"], tile["difficulty"]) for tile in allocation}) == 18

        question_by_tile = {
            tile["tile_key"]: tile["question"]["id"] for tile in board["tiles"]
        }
        # إعادة تخصيص احتياطي كل عشر مباريات لإثبات عدم التكرار بعد التبديل.
        if match_index % 10 == 0:
            target = board["tiles"][0]
            rerolled = await reroll_tile(
                capacity_settings,
                code,
                target["tile_key"],
                expected_version=version,
                idempotency_key=f"hundred-reroll-{match_index}",
                host_token=host,
            )
            version = rerolled["match"]["version"]
            new_id = rerolled["tile"]["question"]["id"]
            assert new_id != target["question"]["id"]
            assert new_id not in resolved_ids
            question_by_tile[target["tile_key"]] = new_id

        for tile_index, tile in enumerate(board["tiles"]):
            question_id = question_by_tile[tile["tile_key"]]
            result = await resolve_tile(
                capacity_settings,
                code,
                tile["tile_key"],
                outcome="team1" if tile_index % 2 == 0 else "team2",
                powers_applied=[],
                expected_version=version,
                idempotency_key=f"hundred-resolve-{match_index}-{tile_index}",
                host_token=host,
            )
            version = result["match"]["version"]
            played_id = result["tile"]["question"]["id"]
            assert played_id == question_id
            assert played_id not in resolved_ids, (
                f"repeat at match {match_index} tile {tile['tile_key']}: {played_id}"
            )
            resolved_ids.add(played_id)
            key = (result["tile"]["category_slug"], result["tile"]["difficulty"])
            per_bucket_resolved[key] = per_bucket_resolved.get(key, 0) + 1
            versions_checked += 1

        fresh = await get_match(capacity_settings, code)
        assert fresh["match"]["status"] == "completed"
        assert len(fresh["tiles"]) == PRIMARY_TILES
        assert all(tile["status"] == "played" for tile in fresh["tiles"])
        # الخانات الاحتياطية غير المستخدمة لا تُحتسب ملعوبة.
        assert all(tile["status"] in {"unplayed", "rerolled"} for tile in fresh["backups"])

    assert len(resolved_ids) == TOTAL_MATCHES * PRIMARY_TILES
    assert versions_checked == TOTAL_MATCHES * PRIMARY_TILES
    assert len(per_bucket_resolved) == 18
    assert all(count == TOTAL_MATCHES * 2 for count in per_bucket_resolved.values())

    async with connect(capacity_settings) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions WHERE times_played > 0"
        )
        played_questions = (await cursor.fetchone())["n"]
        await cursor.close()
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM question_usage"
        )
        usage_rows = (await cursor.fetchone())["n"]
        await cursor.close()
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions WHERE times_played > 1"
        )
        overused = (await cursor.fetchone())["n"]
        await cursor.close()
    # 3,600 خانة لُعبت فقط؛ الأسئلة الأساسية المستبدلة قبل اللعب لم تُحتسب.
    assert played_questions == TOTAL_MATCHES * PRIMARY_TILES
    assert usage_rows == played_questions
    assert overused == 0
