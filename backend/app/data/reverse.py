"""بطاقات الأسئلة المعكوسة: نعرض الجواب، والفرقة تختار السؤال الصحيح.

الفكرة من «سين جيم»: بدل ما نسأل ونجاوب، نقلب الاتجاه — البطاقة تعرض النتيجة
النهائية (الجواب)، والاختيارات الأربعة نصوص أسئلة. الفريق يختار السؤال اللي
يوصّل لهذا الجواب.

- حتمية: كل شيء مشتق من بصمة مجموعة الحقيقة، فإعادة التوليد تعطي نفس البطاقات.
- لا حقائق جديدة: الجواب ونصوص الأسئلة كلها من البنك المنسّق نفسه.
- المشتّتات من نفس الصعوبة، وجوابها مختلف عن الجواب الصحيح حتى ما يصير للبطاقة
  أكثر من جواب صحيح.
"""

from __future__ import annotations

import hashlib
from typing import Any

PER_BUCKET = 120
OPTION_COUNT = 4
MAX_OPTION_CHARS = 78
MAX_ANSWER_CHARS = 40

# فئات تُشتق منها البطاقات المعكوسة: محتوى كروي منسّق، بلا ألغاز أو مشاهد.
SOURCE_CATEGORIES = frozenset(
    {"football", "ucl", "worldcup", "career", "clubs", "arab_ftbl", "numbers", "nicknames"}
)

STEMS = (
    "الجواب «{answer}»… أي سؤال من هالاختيارات يوصّل له؟",
    "هالجواب «{answer}»… شنو السؤال اللي يناسبه؟",
    "قلبنا السؤال… الجواب «{answer}» واختار السؤال الصح.",
    "الجواب «{answer}»… أي سؤال يطلع لنا هالنتيجة؟",
    "بدون ما نسأل: الجواب «{answer}»… اختار السؤال اللي يوصّل له.",
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalized(value: str) -> str:
    return " ".join(value.replace("ـ", "").split()).strip().lower()


def _eligible(row: dict[str, Any]) -> bool:
    if row["type"] != "text" or row.get("payload"):
        return False
    if row["category"] not in SOURCE_CATEGORIES:
        return False
    if len(row["question"]) > MAX_OPTION_CHARS:
        return False
    if len(row["answer"]) > MAX_ANSWER_CHARS:
        return False
    if row["answer"].strip().isdigit():
        return False
    # لو السؤال يذكر الجواب بنفسه، البطاقة المعكوسة تصير بلا تحدي.
    if _normalized(row["answer"]) in _normalized(row["question"]):
        return False
    return row["question"].strip().endswith("؟")


def _usable_distractor(candidate: dict[str, Any], correct: dict[str, Any], chosen: list[dict]) -> bool:
    """المشتّت لازم يكون سؤالًا مختلفًا وجوابه مختلف بوضوح عن الجواب الصحيح."""
    if candidate["fact_group_id"] == correct["fact_group_id"]:
        return False
    if candidate["question"] == correct["question"]:
        return False
    wanted, offered = _normalized(correct["answer"]), _normalized(candidate["answer"])
    if not offered or wanted == offered:
        return False
    # «ريال مدريد» و«ريال مدريد الإسباني» جواب واحد بصياغتين: نرفض التضمين.
    if wanted in offered or offered in wanted:
        return False
    for item in chosen:
        if item["question"] == candidate["question"]:
            return False
        other = _normalized(item["answer"])
        if other == offered or other in offered or offered in other:
            return False
    return True


def _options(correct: dict[str, Any], pool: list[dict], salt: str) -> tuple[list[str], int] | None:
    """يختار 3 مشتّتات ويخلط الاختيارات ترتيبًا حتميًا."""
    same_category = [row for row in pool if row["category"] == correct["category"]]
    others = [row for row in pool if row["category"] != correct["category"]]
    candidates = [
        row
        for row in sorted(same_category + others, key=lambda item: _digest(f"{salt}|{item['fact_group_id']}"))
        if row is not correct
    ]
    chosen: list[dict] = []
    for row in candidates:
        if _usable_distractor(row, correct, chosen):
            chosen.append(row)
        if len(chosen) == OPTION_COUNT - 1:
            break
    if len(chosen) < OPTION_COUNT - 1:
        return None

    options = [correct["question"]] + [row["question"] for row in chosen]
    order = sorted(range(OPTION_COUNT), key=lambda index: _digest(f"{salt}|option|{index}"))
    shuffled = [options[index] for index in order]
    return shuffled, shuffled.index(correct["question"])


def build_rows(
    source_rows: list[dict[str, Any]], category_labels: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """يبني بطاقات معكوسة حتمية من بنك الأسئلة المنسّق."""
    labels = category_labels or {}
    pools: dict[int, list[dict[str, Any]]] = {}
    for row in source_rows:
        if _eligible(row):
            pools.setdefault(int(row["difficulty"]), []).append(row)

    rows: list[dict[str, Any]] = []
    used_prompts: set[str] = set()
    for difficulty in sorted(pools):
        pool = sorted(
            pools[difficulty],
            key=lambda item: _digest(f"reverse-order|{difficulty}|{item['fact_group_id']}"),
        )
        used_groups: set[str] = set()
        taken = 0
        for row in pool:
            if taken >= PER_BUCKET:
                break
            group = str(row["fact_group_id"])
            if group in used_groups:
                continue
            options = _options(row, pool, f"reverse|{group}")
            if options is None:
                continue
            texts, correct_index = options
            if len(set(texts)) != OPTION_COUNT:
                continue
            suffix = f" — فئة {labels[row['category']]}" if labels.get(row["category"]) else ""
            prompt = None
            base = int(_digest(f"{difficulty}|{group}")[:8], 16)
            for offset in range(len(STEMS)):
                stem = STEMS[(base + offset) % len(STEMS)]
                candidate = stem.format(answer=row["answer"]) + suffix
                if candidate not in used_prompts:
                    prompt = candidate
                    break
            if prompt is None:
                continue

            used_prompts.add(prompt)
            used_groups.add(group)
            taken += 1
            rows.append(
                {
                    "category": "reverse",
                    "difficulty": difficulty,
                    "type": "text",
                    "question": prompt,
                    "answer": texts[correct_index],
                    "tolerance": texts[correct_index],
                    "explanation": f"الجواب «{row['answer']}» يجي من سؤال: {texts[correct_index]}",
                    "payload": {
                        "kind": "reverse",
                        "answer": row["answer"],
                        "options": texts,
                        "correct_index": correct_index,
                    },
                    "content_origin": "curated",
                    "verification_status": "curated",
                    "fact_group_id": f"reverse:{group}",
                    "source_entity_id": row.get("source_entity_id") or group,
                    "fact_type": "derived_reverse",
                    "fact_payload": {"answer": row["answer"], "source_fact_group": group},
                    "source_name": row.get("source_name"),
                    "source_url": row.get("source_url"),
                    "source_license": row.get("source_license"),
                    "source_claim": f"reverse card derived from curated fact {group}",
                }
            )
    return rows
