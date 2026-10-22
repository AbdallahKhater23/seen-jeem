"""استعلامات لوحة الإدارة: توازن البنك، تاريخ الزرع، وآخر المباريات.

كل الدوال هنا للقراءة فقط وتعمل على اتصال قصير. الحماية بالتوكن تُفرض في
طبقة المسار (`require_admin`) قبل الوصول إلى هذه الاستعلامات.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..config import Settings
from ..db import connect
from ..utils.errors import not_found
from .content import (
    CAPACITY_PER_BUCKET,
    CONTENT_FLOOR_PER_BUCKET,
    OPERATIONAL_MIN_PER_BUCKET,
)

BANK_BUCKET_SQL = """
SELECT
    c.id AS category_id,
    c.slug,
    c.name_ar,
    c.icon,
    c.sort_order,
    q.difficulty,
    COALESCE(b.cycle, 1) AS cycle,
    COUNT(*) AS total,
    SUM(CASE WHEN q.is_reserved_backup = 0 THEN 1 ELSE 0 END) AS playable,
    SUM(CASE WHEN q.is_reserved_backup = 1 THEN 1 ELSE 0 END) AS reserved_backup,
    SUM(CASE WHEN q.times_played > 0 THEN 1 ELSE 0 END) AS played_questions,
    SUM(CASE WHEN q.times_played = 0 THEN 1 ELSE 0 END) AS never_played,
    COALESCE(SUM(q.times_played), 0) AS total_plays,
    SUM(
        CASE WHEN q.is_reserved_backup = 0 AND EXISTS (
            SELECT 1
            FROM question_usage u
            JOIN question_buckets b
              ON b.category_id = q.category_id AND b.difficulty = q.difficulty
            WHERE u.question_id = q.id AND u.cycle = b.cycle
        ) THEN 1 ELSE 0 END
    ) AS used_current_cycle,
    SUM(
        CASE WHEN q.is_reserved_backup = 0 AND EXISTS (
            SELECT 1
            FROM match_tiles mt
            JOIN matches m ON m.id = mt.match_id
            WHERE mt.question_id = q.id
              AND mt.status = 'unplayed'
              AND m.status = 'active'
        ) THEN 1 ELSE 0 END
    ) AS reserved_active,
    SUM(
        CASE WHEN q.is_reserved_backup = 0
            AND NOT EXISTS (
                SELECT 1
                FROM question_usage u
                JOIN question_buckets b
                  ON b.category_id = q.category_id AND b.difficulty = q.difficulty
                WHERE u.question_id = q.id AND u.cycle = b.cycle
            )
            AND NOT EXISTS (
                SELECT 1
                FROM match_tiles mt
                JOIN matches m ON m.id = mt.match_id
                WHERE mt.question_id = q.id
                  AND mt.status = 'unplayed'
                  AND m.status = 'active'
            )
        THEN 1 ELSE 0 END
    ) AS eligible
FROM questions q
JOIN categories c ON c.id = q.category_id
LEFT JOIN question_buckets b
  ON b.category_id = q.category_id AND b.difficulty = q.difficulty
WHERE q.is_active = 1
GROUP BY c.id, c.slug, c.name_ar, c.icon, c.sort_order, q.difficulty, b.cycle
ORDER BY c.sort_order, q.difficulty
"""

CATEGORY_SQL = """
SELECT c.id, c.slug, c.name_ar, c.icon, c.sort_order
FROM categories c
ORDER BY c.sort_order
"""

CYCLES_SQL = """
SELECT
    COUNT(*) AS buckets,
    COALESCE(MAX(cycle), 1) AS max_cycle,
    COALESCE(SUM(cycle), 0) AS total_cycles
FROM question_buckets
"""

ORIGINS_SQL = """
SELECT content_origin, COUNT(*) AS n
FROM questions
WHERE is_active = 1
GROUP BY content_origin
ORDER BY content_origin
"""

MATCH_SQL = """
SELECT
    m.match_code, m.team1_name, m.team2_name, m.score_team1, m.score_team2,
    m.current_turn, m.status, m.winner, m.coin_toss_winner, m.version,
    m.selected_categories_json, m.created_at, m.updated_at,
    COUNT(e.id) AS event_count,
    MAX(e.created_at) AS last_event_at
FROM matches m
LEFT JOIN match_events e ON e.match_id = m.id
{where}
GROUP BY m.id
ORDER BY m.updated_at DESC, m.id DESC
LIMIT ?
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _int(row, key: str) -> int:
    value = row[key]
    return int(value) if value is not None else 0


def _bucket_out(row) -> dict:
    total = _int(row, "total")
    eligible = _int(row, "eligible")
    return {
        "category_slug": row["slug"],
        "category_name": row["name_ar"],
        "icon": row["icon"],
        "difficulty": _int(row, "difficulty"),
        "cycle": _int(row, "cycle"),
        "total": total,
        "playable": _int(row, "playable"),
        "reserved_backup": _int(row, "reserved_backup"),
        "eligible": eligible,
        "used_current_cycle": _int(row, "used_current_cycle"),
        "reserved_active": _int(row, "reserved_active"),
        "played_questions": _int(row, "played_questions"),
        "never_played": _int(row, "never_played"),
        "total_plays": _int(row, "total_plays"),
        "meets_operational_min": eligible >= OPERATIONAL_MIN_PER_BUCKET,
        "meets_content_floor": total >= CONTENT_FLOOR_PER_BUCKET,
        "meets_capacity": total >= CAPACITY_PER_BUCKET,
    }


async def question_bank(settings: Settings) -> dict:
    """ملخص توازن البنك لكل فئة/صعوبة مع عدّادات الدورة والحجز."""
    async with connect(settings) as db:
        cursor = await db.execute(BANK_BUCKET_SQL)
        bucket_rows = await cursor.fetchall()
        await cursor.close()

        cursor = await db.execute(CATEGORY_SQL)
        category_rows = await cursor.fetchall()
        await cursor.close()

        cursor = await db.execute(CYCLES_SQL)
        cycles = await cursor.fetchone()
        await cursor.close()

        cursor = await db.execute(ORIGINS_SQL)
        origin_rows = await cursor.fetchall()
        await cursor.close()

        cursor = await db.execute(
            """
            SELECT
                COUNT(DISTINCT q.fact_group_id) AS fact_groups,
                COUNT(*) AS active_questions,
                SUM(CASE WHEN q.times_played > 0 THEN 1 ELSE 0 END) AS played_questions,
                COALESCE(SUM(q.times_played), 0) AS total_plays
            FROM questions q
            WHERE q.is_active = 1 AND q.is_reserved_backup = 0
              AND q.fact_group_id IS NOT NULL AND q.fact_group_id <> ''
            """
        )
        facts = await cursor.fetchone()
        await cursor.close()

    buckets = [_bucket_out(row) for row in bucket_rows]
    buckets_by_slug: dict[str, dict] = {}
    for bucket in buckets:
        buckets_by_slug.setdefault(bucket["category_slug"], {})[
            str(bucket["difficulty"])
        ] = bucket

    categories = []
    for row in category_rows:
        slug = row["slug"]
        per_difficulty = buckets_by_slug.get(slug, {})
        categories.append(
            {
                "slug": slug,
                "name_ar": row["name_ar"],
                "icon": row["icon"],
                "sort_order": _int(row, "sort_order"),
                "total": sum(item["total"] for item in per_difficulty.values()),
                "playable": sum(item["playable"] for item in per_difficulty.values()),
                "eligible": sum(item["eligible"] for item in per_difficulty.values()),
                "used_current_cycle": sum(
                    item["used_current_cycle"] for item in per_difficulty.values()
                ),
                "reserved_active": sum(
                    item["reserved_active"] for item in per_difficulty.values()
                ),
                "total_plays": sum(item["total_plays"] for item in per_difficulty.values()),
                "buckets": per_difficulty,
            }
        )

    totals = {
        "questions": sum(item["total"] for item in buckets),
        "playable": sum(item["playable"] for item in buckets),
        "eligible": sum(item["eligible"] for item in buckets),
        "used_current_cycle": sum(item["used_current_cycle"] for item in buckets),
        "reserved_active": sum(item["reserved_active"] for item in buckets),
        "played_questions": int(facts["played_questions"] or 0),
        "total_plays": int(facts["total_plays"] or 0),
        "fact_groups": int(facts["fact_groups"] or 0),
        "buckets": int(cycles["buckets"] or 0),
        "max_cycle": int(cycles["max_cycle"] or 1),
        "total_cycles": int(cycles["total_cycles"] or 0),
    }
    return {
        "generated_at": _utc_now(),
        "standards": {
            "operational_min_per_bucket": OPERATIONAL_MIN_PER_BUCKET,
            "content_floor_per_bucket": CONTENT_FLOOR_PER_BUCKET,
            "capacity_per_bucket": CAPACITY_PER_BUCKET,
        },
        "totals": totals,
        "origins": {row["content_origin"]: _int(row, "n") for row in origin_rows},
        "categories": categories,
        "buckets": buckets,
    }


async def seed_history(settings: Settings, *, limit: int = 20) -> dict:
    """آخر عمليات الزرع مع التقرير المحفوظ لكل عملية."""
    async with connect(settings) as db:
        cursor = await db.execute("SELECT COUNT(*) AS n FROM seed_runs")
        total = int((await cursor.fetchone())["n"])
        await cursor.close()
        cursor = await db.execute(
            """
            SELECT id, seed_version, deterministic_seed, inserted, updated, skipped,
                   invalid, total_active, network_status, report_json, created_at
            FROM seed_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        await cursor.close()

    runs = []
    for row in rows:
        report = _json_dict(row["report_json"])
        runs.append(
            {
                "id": _int(row, "id"),
                "seed_version": row["seed_version"],
                "deterministic_seed": _int(row, "deterministic_seed"),
                "inserted": _int(row, "inserted"),
                "updated": _int(row, "updated"),
                "skipped": _int(row, "skipped"),
                "invalid": _int(row, "invalid"),
                "total_active": _int(row, "total_active"),
                "network_status": row["network_status"],
                "created_at": row["created_at"],
                "report": report,
            }
        )
    return {"runs": runs, "total": total}


async def recent_matches(
    settings: Settings, *, limit: int = 50, status: str | None = None
) -> dict:
    """آخر المباريات مع عدد أحداثها، ويمكن تصفيتها بالحالة."""
    where = ""
    params: list = []
    count_params: list = []
    if status:
        where = "WHERE m.status = ?"
        params.append(status)
        count_params.append(status)
    params.append(limit)

    async with connect(settings) as db:
        cursor = await db.execute(MATCH_SQL.format(where=where), params)
        rows = await cursor.fetchall()
        await cursor.close()
        cursor = await db.execute(
            f"SELECT COUNT(*) AS n FROM matches m {where}", count_params
        )
        total = int((await cursor.fetchone())["n"])
        await cursor.close()
        cursor = await db.execute(
            "SELECT status, COUNT(*) AS n FROM matches GROUP BY status"
        )
        status_counts = {
            row["status"]: _int(row, "n") for row in await cursor.fetchall()
        }
        await cursor.close()

    matches = []
    for row in rows:
        matches.append(
            {
                "match_code": row["match_code"],
                "team1_name": row["team1_name"],
                "team2_name": row["team2_name"],
                "score_team1": _int(row, "score_team1"),
                "score_team2": _int(row, "score_team2"),
                "current_turn": row["current_turn"],
                "status": row["status"],
                "winner": row["winner"],
                "coin_toss_winner": row["coin_toss_winner"],
                "version": _int(row, "version"),
                "selected_categories": _json_list(row["selected_categories_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "event_count": _int(row, "event_count"),
                "last_event_at": row["last_event_at"],
            }
        )
    return {"matches": matches, "total": total, "status_counts": status_counts}


async def match_events(
    settings: Settings,
    match_code: str,
    *,
    limit: int = 100,
    before_id: int | None = None,
) -> dict:
    """أحداث مباراة محددة بترتيب تنازلي مع بيانات المباراة للسياق."""
    async with connect(settings) as db:
        cursor = await db.execute(
            """
            SELECT match_code, team1_name, team2_name, status, winner,
                   score_team1, score_team2
            FROM matches WHERE match_code = ?
            """,
            (match_code,),
        )
        match = await cursor.fetchone()
        await cursor.close()
        if not match:
            raise not_found("MATCH_NOT_FOUND", "المباراة غير موجودة.", match_code=match_code)

        params: list = [match_code]
        sql = """
            SELECT e.id, e.event_type, e.request_key, e.payload_json, e.created_at
            FROM match_events e
            JOIN matches m ON m.id = e.match_id
            WHERE m.match_code = ?
        """
        if before_id:
            sql += " AND e.id < ?"
            params.append(before_id)
        sql += " ORDER BY e.id DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        await cursor.close()

    events = [
        {
            "id": _int(row, "id"),
            "event_type": row["event_type"],
            "request_key": row["request_key"],
            "payload": _json_dict(row["payload_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {
        "match": {
            "match_code": match["match_code"],
            "team1_name": match["team1_name"],
            "team2_name": match["team2_name"],
            "status": match["status"],
            "winner": match["winner"],
            "score_team1": _int(match, "score_team1"),
            "score_team2": _int(match, "score_team2"),
        },
        "events": events,
        "next_before_id": events[-1]["id"] if len(events) == limit else None,
    }
