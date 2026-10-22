"""قياس خطة الاستعلام واست规模化 السجل الكبير على قاعدة حقيقية.

يشرح خطةEligibilityEHISTORY على قاعدة حقيقية (نسخة من قاعدة الإنتاج) ويقارن
زمن التنفيذ عند سجل صغير مقابل سجل كبير، للتأكد من عدم تدهور تدريجي.
"""

from __future__ import annotations

import asyncio
import pathlib
import shutil
import sqlite3
import sys
import time
from dataclasses import replace

sys.path.insert(0, ".")

from app.config import load_settings
from app.db import connect, init_db
from app.services.selector import bucket_cycle, eligible_questions

SRC = pathlib.Path("data/seenjeem.db")
DST = pathlib.Path("data/_perf_probe.db")


def copy_db() -> None:
    for suffix in ("", "-wal", "-shm"):
        source = pathlib.Path(str(SRC) + suffix)
        if source.exists():
            shutil.copy2(source, pathlib.Path(str(DST) + suffix))


def seed_history(rows: int) -> None:
    """يملأ سجل تعرّض بحجم محدد على-shadow users حقيقيين."""
    con = sqlite3.connect(DST)
    con.execute("PRAGMA foreign_keys = ON")
    users = [r[0] for r in con.execute("SELECT id FROM users LIMIT 50")]
    questions = [r[0] for r in con.execute("SELECT id FROM questions WHERE is_active = 1")]
    if not users or not questions:
        con.close()
        raise SystemExit("need seeded users/questions")
    con.execute("DELETE FROM user_question_history")
    payload = []
    for index in range(rows):
        payload.append(
            (users[index % len(users)], questions[index % len(questions)], None, "none")
        )
    con.executemany(
        "INSERT OR IGNORE INTO user_question_history(user_id, question_id, match_id, outcome)"
        " VALUES (?, ?, ?, ?)",
        payload,
    )
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM user_question_history").fetchone()[0]
    con.close()
    print(f"  history rows = {total}")


async def measure(settings, identities: tuple[int, ...]) -> tuple[float, int, str]:
    async with connect(settings) as db:
        cursor = await db.execute(
            "SELECT id, category_id, difficulty FROM questions"
            " WHERE is_active = 1 AND is_reserved_backup = 0"
            " ORDER BY id LIMIT 1"
        )
        row = await cursor.fetchone()
        await cursor.close()
        cycle = await bucket_cycle(db, int(row["category_id"]), int(row["difficulty"]))
        start = time.perf_counter()
        rows = await eligible_questions(
            db, int(row["category_id"]), int(row["difficulty"]), cycle,
            excluded_user_ids=identities,
        )
        elapsed = (time.perf_counter() - start) * 1000
    con = sqlite3.connect(DST)
    placeholders = ",".join("?" for _ in identities)
    plan = con.execute(
        f"""
        EXPLAIN QUERY PLAN
        SELECT q.id FROM questions q
        WHERE q.category_id = ? AND q.difficulty = ? AND q.is_active = 1
          AND q.is_reserved_backup = 0
          AND NOT EXISTS (
              SELECT 1 FROM user_question_history h
              WHERE h.question_id = q.id AND h.user_id IN ({placeholders})
          )
        """,
        (int(row["category_id"]), int(row["difficulty"]), *identities),
    ).fetchall()
    con.close()
    return elapsed, len(rows), " | ".join(str(item[3]) for item in plan)


async def main() -> None:
    copy_db()
    settings = replace(load_settings(), database_path=DST)
    await init_db(settings)

    con = sqlite3.connect(DST)
    identities = tuple(r[0] for r in con.execute("SELECT id FROM users LIMIT 50"))
    con.close()
    if len(identities) < 2:
        con = sqlite3.connect(DST)
        con.executemany(
            "INSERT INTO users(username, display_name, kind, is_active) VALUES (?, ?, 'named', 1)",
            [(f"perf-{i}", f"لاعب {i}") for i in range(50)],
        )
        con.commit()
        con.close()
        identities = tuple(range(1, 51))

    print("bucket eligibility query (history filter on):")
    for rows in (0, 5_000, 50_000, 200_000):
        seed_history(rows)
        elapsed, count, plan = await measure(settings, identities)
        print(f"  history={rows:>7} -> {elapsed:7.2f} ms, candidates={count}")
        print(f"     plan: {plan}")

    DST.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        pathlib.Path(str(DST) + suffix).unlink(missing_ok=True)


asyncio.run(main())
