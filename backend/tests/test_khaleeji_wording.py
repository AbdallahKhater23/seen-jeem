"""حماية لهجة الأسئلة: كل نص سؤال لازم يكون باللهجة الخليجية لا بالفصحى.

القاعدة عملية وقابلة للقياس: إذا ظهر في نص السؤال ضمير وصل فصيح (الذي/التي)
أو استفهام فصيح (ما هو، ما هي، من هو، كم عدد، هل) فالأسئلة رجعت للفصحى.
"""
from __future__ import annotations

import re

import pytest

from app.data.backups import BACKUPS
from app.services.content import build_question_bank

# أنماط فصحى صريحة. «التي» داخل «التين» ليست ضمير وصل، لذلك نطلب فاصلًا بعدها.
FORBIDDEN = {
    "ضمير الوصل «الذي»": re.compile(r"(?<![\u0621-\u064A])الذي(?![\u0621-\u064A])"),
    "ضمير الوصل «التي»": re.compile(r"(?<![\u0621-\u064A])التي(?![\u0621-\u064A])"),
    "استفهام «ما هو/ما هي»": re.compile(r"ما\s+(هو|هي)"),
    "استفهام «من هو/من هي»": re.compile(r"من\s+(هو|هي)"),
    "استفهام «كم عدد»": re.compile(r"كم\s+عدد"),
    "أداة استفهام «هل»": re.compile(r"(^|\s)هل(\s|$)"),
    "فعل «يُعرف به»": re.compile(r"يُ?عرف\s+به"),
    "تنوين «نادٍ»": re.compile(r"نادٍ"),
    "استفهام «من فاز/من سجل»": re.compile(r"من\s+(فاز|سجل)"),
    "استفهام «ما اسم/ما الدولة/ما المدينة»": re.compile(r"ما\s+(اسم|الدولة|المدينة|الفريق|النادي)"),
}


def _violations(text: str) -> list[str]:
    return [label for label, pattern in FORBIDDEN.items() if pattern.search(text)]


def test_question_bank_uses_khaleeji_wording():
    rows = build_question_bank()
    assert rows, "بنك الأسئلة فاضي"
    offenders = [
        f"{row['category']}/{row['difficulty']}: {row['question']}"
        for row in rows
        if _violations(row["question"])
    ]
    assert offenders == [], "أسئلة بالفصحى:\n" + "\n".join(offenders[:20])


def test_backup_questions_use_khaleeji_wording():
    offenders = [row["question"] for row in BACKUPS if _violations(row["question"])]
    assert offenders == [], "أسئلة احتياطي بالفصحى:\n" + "\n".join(offenders)


@pytest.mark.asyncio
async def test_seeded_database_serves_only_khaleeji_questions(seeded_settings):
    from app.db import connect

    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            """
            SELECT q.question_text FROM questions q
            WHERE q.is_active = 1 AND q.is_reserved_backup = 0
            """
        )
        rows = await cursor.fetchall()
        await cursor.close()

    assert len(rows) == len(build_question_bank())
    offenders = [row["question_text"] for row in rows if _violations(row["question_text"])]
    assert offenders == [], "أسئلة فعالة بالفصحى:\n" + "\n".join(offenders[:20])
