"""زرع بنك الأسئلة حتميًا وآمن لإعادة التشغيل.

- الهوية المستقرة للسؤال هي `fingerprint`؛ إعادة الزرع لا تُنشئ نسخًا جديدة.
- الوقائع تُحفظ في `fact_records` بمصدرها ووسم التحقق.
- ترتيب `deck_position` يُخلط مرة واحدة لكل دلو عند إدخال أسئلة جديدة فقط.
- لا يُمسّ `times_played` أو تاريخ المباريات عند إعادة الزرع.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from ..config import Settings
from ..db import connect, init_db, transaction
from ..utils.text import fingerprint
from .content import (
    CAPACITY_PER_BUCKET,
    CATEGORIES,
    CATEGORY_SLUGS,
    CONTENT_FLOOR_PER_BUCKET,
    DIFFICULTIES,
    OPERATIONAL_MIN_PER_BUCKET,
    build_question_bank,
    inventory_report,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _deck_salt(settings: Settings, deterministic_seed: int | None) -> int:
    if deterministic_seed is not None and deterministic_seed != 0:
        return deterministic_seed
    if settings.seed_random_seed:
        return settings.seed_random_seed
    return random.SystemRandom().randrange(1, 2**31 - 1)


async def _assign_deck_positions(
    db, buckets: dict[tuple[int, int], str], salt: int
) -> None:
    """Fisher–Yates حتمي لكل دلو أُدخلت فيه أسئلة جديدة."""
    for (category_id, difficulty), slug in buckets.items():
        cursor = await db.execute(
            "SELECT id FROM questions WHERE category_id = ? AND difficulty = ?"
            " AND is_active = 1 AND is_reserved_backup = 0 ORDER BY id",
            (category_id, difficulty),
        )
        ids = [int(row["id"]) for row in await cursor.fetchall()]
        await cursor.close()
        rng = random.Random(f"{salt}:{slug}:{difficulty}:1")
        rng.shuffle(ids)
        for position, question_id in enumerate(ids):
            await db.execute(
                "UPDATE questions SET deck_position = ? WHERE id = ?",
                (position, question_id),
            )


async def seed_database(
    settings: Settings,
    *,
    seed_version: str | None = None,
    deterministic_seed: int | None = None,
) -> dict:
    await init_db(settings)
    version = seed_version or settings.seed_version
    salt = _deck_salt(settings, deterministic_seed)
    rows = build_question_bank()
    inventory = inventory_report(rows)

    inserted = 0
    skipped = 0
    invalid = 0
    updated = 0
    touched_buckets: dict[tuple[int, int], str] = {}
    categories_by_slug: dict[str, int] = {}
    to_update: list[tuple[int, str]] = []

    async with transaction(settings) as db:
        for category in CATEGORIES:
            await db.execute(
                """
                INSERT INTO categories(slug, name_ar, icon, sort_order)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name_ar = excluded.name_ar,
                    icon = excluded.icon,
                    sort_order = excluded.sort_order
                """,
                (category["slug"], category["name_ar"], category["icon"], category["sort_order"]),
            )
        cursor = await db.execute("SELECT id, slug FROM categories")
        for row in await cursor.fetchall():
            categories_by_slug[row["slug"]] = int(row["id"])
        await cursor.close()
        slugs_by_id = {item_id: slug for slug, item_id in categories_by_slug.items()}

        # خريطة البصمات الحالية لتقارب الدرجات: إعادة الزرع تُحدّث درجة أي سؤال
        # تغيّرت درجته في المحتوى، بدل تجميد الدرجة القديمة إلى الأبد.
        existing: dict[str, tuple[int, int]] = {}
        cursor = await db.execute("SELECT fingerprint, category_id, difficulty FROM questions")
        for row in await cursor.fetchall():
            existing[row["fingerprint"]] = (int(row["category_id"]), int(row["difficulty"]))
        await cursor.close()

        for category in CATEGORIES:
            for difficulty in DIFFICULTIES:
                await db.execute(
                    """
                    INSERT INTO question_buckets(category_id, difficulty, cycle)
                    VALUES (?, ?, 1)
                    ON CONFLICT(category_id, difficulty) DO NOTHING
                    """,
                    (categories_by_slug[category["slug"]], difficulty),
                )

        # سجل الوقائع والقطع المولّدة؛ كل صف يحمل مصدره وترخيصه وادعاءه.
        for row in rows:
            if not row.get("fact_payload"):
                continue
            await db.execute(
                """
                INSERT INTO fact_records(
                    fact_group_id, fact_type, source_name, source_entity_id,
                    source_url, source_license, source_claim,
                    verification_status, payload_json, content_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(fact_group_id, fact_type, source_name) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    verification_status = excluded.verification_status,
                    source_url = COALESCE(excluded.source_url, fact_records.source_url),
                    source_license = COALESCE(excluded.source_license, fact_records.source_license),
                    source_claim = COALESCE(excluded.source_claim, fact_records.source_claim),
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                """,
                (
                    row["fact_group_id"],
                    row["fact_type"],
                    row["source_name"] or "حزمة بيانات محلية منسّقة",
                    row["source_entity_id"],
                    row.get("source_url"),
                    row.get("source_license"),
                    row.get("source_claim"),
                    row["verification_status"],
                    json.dumps(row["fact_payload"], ensure_ascii=False, separators=(",", ":")),
                ),
            )

        for row in rows:
            category_id = categories_by_slug.get(row["category"])
            if not category_id:
                invalid += 1
                continue
            payload = row.get("payload")
            fp = fingerprint(
                row["category"], row["question"], row["answer"], row.get("flag_code")
            )
            previous = existing.get(fp)
            if previous is not None:
                old_category_id, old_difficulty = previous
                if old_difficulty != row["difficulty"]:
                    to_update.append((row["difficulty"], fp))
                    touched_buckets[(category_id, row["difficulty"])] = row["category"]
                    touched_buckets[(old_category_id, old_difficulty)] = slugs_by_id.get(
                        old_category_id, row["category"]
                    )
                else:
                    skipped += 1
                continue
            cursor = await db.execute(
                """
                INSERT INTO questions(
                    category_id, difficulty, question_type, question_text, flag_code,
                    payload_json, answer_text, tolerance, explanation, source_name,
                    source_url, source_checked_at, source_license, source_claim,
                    content_origin, fingerprint,
                    is_active, is_reserved_backup, fact_group_id, source_entity_id,
                    verification_status, content_version, times_played,
                    last_played_match_id, deck_position
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, 1, 0, NULL, 0)
                ON CONFLICT(fingerprint) DO NOTHING
                """,
                (
                    category_id,
                    row["difficulty"],
                    row["type"],
                    row["question"],
                    row.get("flag_code"),
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    if payload
                    else None,
                    row["answer"],
                    row["tolerance"],
                    row.get("explanation"),
                    row.get("source_name"),
                    row.get("source_url"),
                    row.get("source_checked_at"),
                    row.get("source_license"),
                    row.get("source_claim"),
                    row["content_origin"],
                    fp,
                    row["fact_group_id"],
                    row.get("source_entity_id"),
                    row["verification_status"],
                ),
            )
            if cursor.rowcount:
                inserted += 1
                touched_buckets[(category_id, row["difficulty"])] = row["category"]
            else:
                skipped += 1
            await cursor.close()

        if to_update:
            changes_cursor = await db.execute("SELECT total_changes() AS n")
            before = int((await changes_cursor.fetchone())["n"])
            await changes_cursor.close()
            await db.executemany(
                "UPDATE questions SET difficulty = ? WHERE fingerprint = ? AND difficulty != ?"
                " AND NOT EXISTS (SELECT 1 FROM match_tiles mt JOIN matches m ON m.id=mt.match_id"
                " WHERE mt.question_id=questions.id AND m.status='active')",
                [(difficulty, fp, difficulty) for difficulty, fp in to_update],
            )
            changes_cursor = await db.execute("SELECT total_changes() AS n")
            updated = int((await changes_cursor.fetchone())["n"]) - before
            await changes_cursor.close()

        await _assign_deck_positions(db, touched_buckets, salt)

        total_active_cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions"
            " WHERE is_active = 1 AND is_reserved_backup = 0"
        )
        total_active = int((await total_active_cursor.fetchone())["n"])
        await total_active_cursor.close()

        bucket_cursor = await db.execute(
            """
            SELECT c.slug, q.difficulty, COUNT(*) AS n
            FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE q.is_active = 1 AND q.is_reserved_backup = 0
            GROUP BY c.slug, q.difficulty
            """
        )
        buckets = {
            f"{row['slug']}:{row['difficulty']}": int(row["n"])
            for row in await bucket_cursor.fetchall()
        }
        await bucket_cursor.close()

        operational_missing = [
            f"{slug}:{difficulty}={buckets.get(f'{slug}:{difficulty}', 0)}"
            for slug in CATEGORY_SLUGS
            for difficulty in DIFFICULTIES
            if buckets.get(f"{slug}:{difficulty}", 0) < OPERATIONAL_MIN_PER_BUCKET
        ]
        if operational_missing:
            raise RuntimeError(
                "بنك الأسئلة لا يكفي حتى لمباراة واحدة: " + ", ".join(operational_missing)
            )

        report = {
            "seed_version": version,
            "deterministic_seed": salt,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "invalid": invalid,
            "total_active": total_active,
            "buckets": buckets,
            "network_status": "offline",
            "content_floor_per_bucket": CONTENT_FLOOR_PER_BUCKET,
            "capacity_per_bucket": CAPACITY_PER_BUCKET,
            "meets_content_floor": not inventory["buckets_below_content_floor"],
            "meets_100_match_capacity": not inventory["buckets_below_capacity_gate"],
            "buckets_below_content_floor": inventory["buckets_below_content_floor"],
            "buckets_below_capacity_gate": inventory["buckets_below_capacity_gate"],
            "football_distribution": inventory["football_distribution"],
            "origins": inventory["origins"],
            "generated_at": _utc_now(),
        }
        await db.execute(
            """
            INSERT INTO seed_runs(
                seed_version, deterministic_seed, inserted, updated, skipped, invalid,
                total_active, network_status, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version,
                salt,
                inserted,
                updated,
                skipped,
                invalid,
                total_active,
                "offline",
                json.dumps(report, ensure_ascii=False),
            ),
        )

    return report


async def seed_status(settings: Settings) -> dict:
    async with connect(settings) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions"
            " WHERE is_active = 1 AND is_reserved_backup = 0"
        )
        total = int((await cursor.fetchone())["n"])
        await cursor.close()
        cursor = await db.execute(
            """
            SELECT c.slug, q.difficulty, COUNT(*) AS n
            FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE q.is_active = 1 AND q.is_reserved_backup = 0
            GROUP BY c.slug, q.difficulty
            """
        )
        buckets = {
            f"{row['slug']}:{row['difficulty']}": int(row["n"])
            for row in await cursor.fetchall()
        }
        await cursor.close()
        cursor = await db.execute("SELECT * FROM seed_runs ORDER BY id DESC LIMIT 1")
        last = await cursor.fetchone()
        await cursor.close()

    expected = [f"{slug}:{difficulty}" for slug in CATEGORY_SLUGS for difficulty in DIFFICULTIES]
    operational = min((buckets.get(key, 0) for key in expected), default=0) >= OPERATIONAL_MIN_PER_BUCKET
    return {
        "total_active": total,
        "buckets": buckets,
        "complete": operational,
        "content_floor_complete": all(
            buckets.get(key, 0) >= CONTENT_FLOOR_PER_BUCKET for key in expected
        ),
        "capacity_100_matches": all(
            buckets.get(key, 0) >= CAPACITY_PER_BUCKET for key in expected
        ),
        "last_run": dict(last) if last else None,
    }
