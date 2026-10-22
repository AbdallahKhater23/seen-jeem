"""بطاقات الأسئلة المعكوسة: المحتوى، السرية قبل الكشف، وواجهة الفئة."""
from __future__ import annotations

import collections
import json

import pytest

from app.services.content import build_question_bank
from app.services.matches import _question_out

OPTION_COUNT = 4


@pytest.fixture(scope="module")
def reverse_rows() -> list[dict]:
    return [row for row in build_question_bank() if row["category"] == "reverse"]


def test_reverse_bank_has_full_buckets(reverse_rows):
    counts = collections.Counter(row["difficulty"] for row in reverse_rows)
    assert counts == {200: 120, 400: 120, 600: 120}
    for difficulty in (200, 400, 600):
        groups = {row["fact_group_id"] for row in reverse_rows if row["difficulty"] == difficulty}
        assert len(groups) >= 100


def test_every_card_has_four_distinct_options_and_one_correct(reverse_rows):
    for row in reverse_rows:
        payload = row["payload"]
        options = payload["options"]
        assert payload["kind"] == "reverse"
        assert len(options) == OPTION_COUNT
        assert len(set(options)) == OPTION_COUNT
        assert 0 <= payload["correct_index"] < OPTION_COUNT
        assert options[payload["correct_index"]] == row["answer"]
        assert row["question"].endswith("؟")
        assert payload["answer"] in row["question"]


def test_correct_option_never_echoes_the_answer(reverse_rows):
    for row in reverse_rows:
        assert row["payload"]["answer"] not in row["answer"], row["question"]


def test_cards_are_khaleeji_and_carry_source_claims(reverse_rows):
    for row in reverse_rows:
        assert row["source_claim"] and "reverse card" in row["source_claim"]
        assert "شنو" in row["question"] or "أي سؤال" in row["question"] or "اختار" in row["question"]


def _payload_row(payload: dict, revealed: bool) -> dict:
    return {
        "question_id": 7,
        "question_category_slug": "reverse",
        "question_category_name": "أسئلة معكوسة",
        "question_difficulty": 400,
        "question_type": "text",
        "question_text": "الجواب «ميروسلاف كلوزه»… أي سؤال من هالاختيارات يوصّل له؟",
        "flag_code": None,
        "media_url_a": None,
        "media_url_b": None,
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "answer_text": "منو الهداف التاريخي لكأس العالم بـ16 هدف؟",
        "tolerance": "منو الهداف التاريخي لكأس العالم بـ16 هدف؟",
        "explanation": "شرح",
        "source_name": "حزمة بيانات محلية منسّقة",
        "source_url": None,
        "source_checked_at": "2026-10-20",
        "source_license": "internal curated dataset",
        "source_claim": "reverse card derived from curated fact worldcup:wc_top_scorer_klose",
        "content_origin": "curated",
        "fact_group_id": "reverse:worldcup:wc_top_scorer_klose",
        "revealed_at": "2026-10-21T00:00:00.000Z" if revealed else None,
        "status": "played" if revealed else "unplayed",
        "visual_json": None,
    }


def test_correct_index_is_hidden_until_reveal():
    payload = {
        "kind": "reverse",
        "answer": "ميروسلاف كلوزه",
        "options": ["أ", "ب", "ج", "د"],
        "correct_index": 2,
    }

    hidden = _question_out(_payload_row(payload, revealed=False))
    assert hidden["payload"]["options"] == ["أ", "ب", "ج", "د"]
    assert "correct_index" not in hidden["payload"]
    assert hidden["answer_text"] is None

    shown = _question_out(_payload_row(payload, revealed=True))
    assert shown["payload"]["correct_index"] == 2
    assert shown["answer_text"] == "منو الهداف التاريخي لكأس العالم بـ16 هدف؟"


@pytest.mark.asyncio
async def test_reverse_category_is_served_after_seed(seeded_settings):
    from app.db import connect

    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT slug, name_ar, icon FROM categories WHERE slug = 'reverse'"
        )
        row = await cursor.fetchone()
        await cursor.close()
        assert row is not None
        assert row["name_ar"] == "أسئلة معكوسة"
        assert row["icon"] == "RotateCcw"

        cursor = await db.execute(
            """
            SELECT COUNT(*) AS n FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE c.slug = 'reverse' AND q.is_active = 1
            """
        )
        assert (await cursor.fetchone())["n"] == 360
        await cursor.close()
