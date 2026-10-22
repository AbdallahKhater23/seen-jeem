"""سجل التعرّض للأسئلة: أول ظهور لكل (لاعب، سؤال).

التعرّض يُسجَّل لحظة الظهور الموثوق (فتح الخانة)، لا لحظة الحجز.
النتيجة تُحدَّث عند الحسم. القيد الفريد قاعدي، وكشف التعارض صريح:
إعادة نفس المباراة عملية آمنة، وتعرّض من مباراة أخرى خطأ مُتحكَّم فيه
لا يُبتلَع بصمت.
"""

from __future__ import annotations

import sqlite3
from sqlite3 import IntegrityError

import aiosqlite

from ..utils.errors import conflict

VALID_OUTCOMES = ("team1", "team2", "none")


async def effective_user_ids(db: aiosqlite.Connection, match_id: int) -> list[int]:
    """الهويات الفعلية للمباراة: المشاركون + ظلّ التثبيت المضيف."""
    cursor = await db.execute(
        "SELECT user_id FROM match_participants WHERE match_id = ? ORDER BY user_id",
        (match_id,),
    )
    ids = [int(row["user_id"]) for row in await cursor.fetchall()]
    await cursor.close()
    cursor = await db.execute(
        "SELECT COALESCE(m.host_user_id, d.shadow_user_id) AS shadow_user_id"
        " FROM matches m LEFT JOIN device_installations d ON d.id = m.host_installation_id"
        " WHERE m.id = ?",
        (match_id,),
    )
    row = await cursor.fetchone()
    await cursor.close()
    if row and row["shadow_user_id"] is not None:
        ids.append(int(row["shadow_user_id"]))
    return sorted(set(ids))


async def record_exposures(
    db: aiosqlite.Connection,
    user_ids: list[int],
    question_id: int,
    match_id: int,
) -> int:
    """يسجّل أول تعرّض. يعيد عدد الصفوف الجديدة (0 عند إعادة نفس المباراة)."""
    if not user_ids:
        raise conflict(
            "EMPTY_IDENTITY_SET",
            "مجموعة الهويات الفعلية فارغة؛ لا يمكن تسجيل التعرّض.",
        )
    inserted = 0
    for user_id in sorted(set(user_ids)):
        try:
            await db.execute(
                "INSERT INTO user_question_history(user_id, question_id, match_id, outcome)"
                " VALUES (?, ?, ?, 'none')",
                (user_id, int(question_id), int(match_id)),
            )
            inserted += 1
        except IntegrityError as exc:
            cursor = await db.execute(
                "SELECT match_id FROM user_question_history WHERE user_id = ? AND question_id = ?",
                (user_id, int(question_id)),
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise conflict(
                    "HISTORY_WRITE_FAILED",
                    "تعذّر تسجيل التعرّض لسبب مرجعي.",
                    user_id=user_id,
                    question_id=int(question_id),
                ) from exc
            if row["match_id"] is not None and int(row["match_id"]) != int(match_id):
                raise conflict(
                    "HISTORY_CONFLICT",
                    "السؤال مسجَّل تعرّضه في مباراة أخرى؛ لا يمكن تقديمه هنا.",
                    user_id=user_id,
                    question_id=int(question_id),
                ) from exc
            # نفس المباراة: إعادة آمنة، يُحافَظ على أول طابع زمني.
    return inserted


async def update_exposure_outcomes(
    db: aiosqlite.Connection,
    user_ids: list[int],
    question_id: int,
    match_id: int,
    outcome: str,
) -> None:
    """يحدّث نتيجة صفوف التعرّض الخاصة بهذه المباراة فقط."""
    if outcome not in VALID_OUTCOMES:
        raise conflict("INVALID_OUTCOME", "نتيجة التعرّض غير صالحة.", outcome=outcome)
    for user_id in sorted(set(user_ids)):
        await db.execute(
            "UPDATE user_question_history SET outcome = ?"
            " WHERE user_id = ? AND question_id = ? AND match_id = ?",
            (outcome, user_id, int(question_id), int(match_id)),
        )


async def history_count(db: aiosqlite.Connection, user_id: int) -> int:
    cursor = await db.execute(
        "SELECT COUNT(*) AS n FROM user_question_history WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    await cursor.close()
    return int(row["n"])
