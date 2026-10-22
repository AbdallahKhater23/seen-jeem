"""مصنع بنك الأسئلة الحتمي للفئات الاثنتي عشرة.

المبدأ: نُخزّن وقائع (facts) بهوية مجموعة `fact_group_id`، ثم نُصرّف منها أسئلة.
- `curated`: من سجلات محلية منسّقة (دول، أندية، مسيرات، نهائيات، معلومات عامة).
- `generated_puzzle`: ألغاز رقمية ومشاهد فروقات مولّدة إجرائيًا، موسومة بوضوح.

لا ندّعي أن المحتوى المنسّق مسحوب من API، ولا نولّد حقائق وهمية لملء العدّاد.
التقرير (`inventory_report`) يبيّن المخزون الفعلي والفجوة تجاه أهداف السعة.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from ..data.arab_football import ARAB_FACTS
from ..data.careers import CAREERS
from ..data.clubs import CLUBS
from ..data.countries import COUNTRIES
from ..data.football_facts import FOOTBALL_FACTS
from ..data.general_knowledge import GENERAL_FACTS
from ..data import matchstick, nicknames, quran, reverse, technology, videogames
from ..data.records import RECORD_FACTS
from ..data.spotdiff import build_spotdiff_puzzles
from ..data.ucl import UCL_FINALS
from ..data.worldcup import FACTS_200, FACTS_400, FACTS_600, TOURNAMENTS
from ..utils.text import normalize_answer, normalize_text

# ── الحدود المعيارية ────────────────────────────────────────────────────────
# الحد الأدنى التشغيلي: يكفي 3 أسئلة لكل دلو (أساسيان + احتياطي) مع 9 مجموعات
# واقعية مختلفة على الأقل لكل فئة، وهي الشروط الصلبة لإنشاء مباراة واحدة.
OPERATIONAL_MIN_PER_BUCKET = 9
# أهداف المحتوى من المواصفة، تُقاس وتُبلَّغ ولا تُزيَّف.
CONTENT_FLOOR_PER_BUCKET = 120
CAPACITY_PER_BUCKET = 201
RIDDLES_PER_BUCKET = 240

CATEGORIES: list[dict] = [
    {"slug": "flags", "name_ar": "أعلام ودول", "icon": "Flag", "sort_order": 1},
    {"slug": "capitals", "name_ar": "عواصم وجغرافيا", "icon": "MapPin", "sort_order": 2},
    {"slug": "football", "name_ar": "كورة عالمية وأوروبية", "icon": "Trophy", "sort_order": 3},
    {"slug": "ucl", "name_ar": "دوري أبطال أوروبا", "icon": "Star", "sort_order": 4},
    {"slug": "worldcup", "name_ar": "كأس العالم", "icon": "Globe", "sort_order": 5},
    {"slug": "career", "name_ar": "مسيرة لاعب", "icon": "UserCheck", "sort_order": 6},
    {"slug": "clubs", "name_ar": "أندية وديربيات", "icon": "Shield", "sort_order": 7},
    {"slug": "arab_ftbl", "name_ar": "كورة عربية وخليجية", "icon": "Award", "sort_order": 8},
    {"slug": "numbers", "name_ar": "أرقام قياسية كروية", "icon": "Hash", "sort_order": 9},
    {"slug": "riddles", "name_ar": "ألغاز وفوازير", "icon": "HelpCircle", "sort_order": 10},
    {"slug": "general", "name_ar": "معلومات عامة وعلوم", "icon": "Lightbulb", "sort_order": 11},
    {"slug": "spotdiff", "name_ar": "طلع الفرق", "icon": "Eye", "sort_order": 12},
    {"slug": "quran", "name_ar": "القرآن الكريم", "icon": "BookOpen", "sort_order": 13},
    {"slug": "nicknames", "name_ar": "ألقاب اللاعبين", "icon": "Tag", "sort_order": 14},
    {"slug": "technology", "name_ar": "معلومات تقنية", "icon": "Cpu", "sort_order": 15},
    {"slug": "videogames", "name_ar": "ألعاب الفيديو", "icon": "Gamepad2", "sort_order": 16},
    {"slug": "matchstick", "name_ar": "ألغاز أعواد الثقاب", "icon": "Activity", "sort_order": 17},
    {"slug": "reverse", "name_ar": "أسئلة معكوسة", "icon": "RotateCcw", "sort_order": 18},
]
CATEGORY_SLUGS = tuple(item["slug"] for item in CATEGORIES)
DIFFICULTIES = (200, 400, 600)
FOOTBALL_CATEGORIES = frozenset(
    {"football", "ucl", "worldcup", "career", "clubs", "arab_ftbl", "numbers"}
)
API_CATEGORIES = frozenset({"quran", "nicknames", "technology", "videogames"})
PROVENANCE_CATEGORIES = API_CATEGORIES | {"matchstick"}

SOURCE_NAME = "حزمة بيانات محلية منسّقة"
SOURCE_CHECKED_AT = "2026-10-20"
PROCEDURAL_SOURCE = "مولّد إجرائي حتمي"
MATCHSTICK_SOURCE = "محرك أعواد الثقاب الحتمي"


def _arabic_digits(value: int | str) -> str:
    return str(value).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def _numeric_tolerance(value: int) -> str:
    return f"{value}، {_arabic_digits(value)}"


def _q(**kwargs: Any) -> dict:
    """صف سؤال كامل مع افتراضات المصدر والتحقق."""
    row = {
        "category": None,
        "difficulty": None,
        "type": "text",
        "question": None,
        "answer": None,
        "tolerance": None,
        "explanation": None,
        "flag_code": None,
        "payload": None,
        "source_name": None,
        "source_url": None,
        "source_checked_at": None,
        "source_license": None,
        "source_claim": None,
        "content_origin": "curated",
        "verification_status": "curated",
        "fact_group_id": None,
        "source_entity_id": None,
        "fact_type": "entity",
        "fact_payload": None,
        "football_scope": None,
    }
    row.update(kwargs)
    if not row["tolerance"]:
        row["tolerance"] = row["answer"]
    if row["category"] in FOOTBALL_CATEGORIES and not row["football_scope"]:
        row["football_scope"] = "arab" if row["category"] == "arab_ftbl" else "global"
    if row["content_origin"] == "curated":
        row["source_name"] = row["source_name"] or SOURCE_NAME
        row["source_checked_at"] = row["source_checked_at"] or SOURCE_CHECKED_AT
        row["source_license"] = row["source_license"] or "internal curated dataset"
        row["source_claim"] = row["source_claim"] or "curated fact"
    elif row["content_origin"] == "api_sourced":
        row["source_name"] = row["source_name"] or "API snapshot"
        if row["verification_status"] == "curated":
            row["verification_status"] = "verified_api"
    else:
        row["source_name"] = row["source_name"] or PROCEDURAL_SOURCE
        row["source_license"] = row["source_license"] or "internal generator"
        row["source_claim"] = row["source_claim"] or "deterministic procedural generation"
        if row["verification_status"] == "curated":
            row["verification_status"] = "procedural"
    return row


# ── الجغرافيا: أعلام وعواصم ────────────────────────────────────────────────
def _flags_rows() -> list[dict]:
    rows: list[dict] = []
    for country in COUNTRIES:
        code = country["code"]
        fact_group = f"country:{code}"
        fact = {
            "code": code,
            "name": country["name"],
            "capital": country["capital"],
            "continent": country["continent"],
            "currency": country["currency"],
        }
        rows.append(
            _q(
                category="flags",
                difficulty=200,
                type="flag",
                question="هالعلم المرسوم قدامك يخص أي دولة؟",
                answer=country["name"],
                tolerance=f"{country['name']}، {code.upper()}",
                explanation=f"هذا علم {country['name']}، وعاصمتها {country['capital']}.",
                flag_code=code,
                fact_group_id=fact_group,
                source_entity_id=code,
                fact_type="country",
                fact_payload=fact,
            )
        )
        rows.append(
            _q(
                category="flags",
                difficulty=400,
                question=f"دولة {country['name']} وعاصمتها {country['capital']}… صايرة بأي قارة؟",
                answer=country["continent"],
                explanation=f"{country['name']} تقع في {country['continent']}.",
                fact_group_id=fact_group,
                source_entity_id=code,
                fact_type="country",
                fact_payload=fact,
            )
        )
        rows.append(
            _q(
                category="flags",
                difficulty=600,
                question=f"في {country['name']}، شنو اسم العملة الرسمية اللي يتعاملون فيها؟",
                answer=country["currency"],
                explanation=f"العملة الرسمية في {country['name']} هي {country['currency']}.",
                fact_group_id=fact_group,
                source_entity_id=code,
                fact_type="country",
                fact_payload=fact,
            )
        )
    return rows


def _capitals_rows() -> list[dict]:
    rows: list[dict] = []
    for country in COUNTRIES:
        code = country["code"]
        fact_group = f"country:{code}"
        fact = {
            "code": code,
            "name": country["name"],
            "capital": country["capital"],
            "continent": country["continent"],
        }
        rows.append(
            _q(
                category="capitals",
                difficulty=200,
                question=f"عاصمتها {country['capital']}… أي دولة نقصد؟",
                answer=country["name"],
                explanation=f"{country['capital']} عاصمة {country['name']}.",
                fact_group_id=fact_group,
                source_entity_id=code,
                fact_type="country",
                fact_payload=fact,
            )
        )
        rows.append(
            _q(
                category="capitals",
                difficulty=400,
                question=f"دولة {country['name']} في {country['continent']}… شنو عاصمتها؟",
                answer=country["capital"],
                explanation=f"عاصمة {country['name']} هي {country['capital']}.",
                fact_group_id=fact_group,
                source_entity_id=code,
                fact_type="country",
                fact_payload=fact,
            )
        )
        rows.append(
            _q(
                category="capitals",
                difficulty=600,
                question=f"عاصمة {country['name']} ({country['capital']})… تقع بأي قارة؟",
                answer=country["continent"],
                explanation=f"{country['capital']} تقع في {country['continent']}.",
                fact_group_id=fact_group,
                source_entity_id=code,
                fact_type="country",
                fact_payload=fact,
            )
        )
    return rows


# ── الأندية ────────────────────────────────────────────────────────────────
def _clubs_rows() -> list[dict]:
    rows: list[dict] = []
    for club in CLUBS:
        slug = "club:" + normalize_text(club["name"]).replace(" ", "_")
        fact = dict(club)
        rows.extend(
            [
                _q(
                    category="clubs",
                    difficulty=200,
                    question=f"في أي مدينة صاير معقل نادي {club['name']}؟",
                    answer=club["city"],
                    explanation=f"{club['name']} يقع في {club['city']}.",
                    fact_group_id=slug,
                    source_entity_id=club["name"],
                    fact_type="club",
                    fact_payload=fact,
                ),
                _q(
                    category="clubs",
                    difficulty=400,
                    question=f"في أي دولة يقع نادي {club['name']} اللي معقله بمدينة {club['city']}؟",
                    answer=club["country"],
                    explanation=f"{club['name']} يلعب في {club['league']} ضمن {club['country']}.",
                    fact_group_id=slug,
                    source_entity_id=club["name"],
                    fact_type="club",
                    fact_payload=fact,
                ),
                _q(
                    category="clubs",
                    difficulty=600,
                    question=f"في أي دوري ينافس نادي {club['name']} العريق؟",
                    answer=club["league"],
                    explanation=f"{club['name']} من أندية {club['league']}.",
                    fact_group_id=slug,
                    source_entity_id=club["name"],
                    fact_type="club",
                    fact_payload=fact,
                ),
            ]
        )
    return rows


# ── المسيرات ───────────────────────────────────────────────────────────────
def _career_rows() -> list[dict]:
    rows: list[dict] = []
    for career in CAREERS:
        player = career["player"]
        full = [
            {"club": stop[0], "years": stop[1], "loan": bool(stop[2]) if len(stop) > 2 else False}
            for stop in career["stops"]
        ]
        first, last = full[0], full[-1]
        group = "player:" + normalize_text(player).replace(" ", "_")
        fact = {"player": player, "stops": full}
        rows.extend(
            [
                _q(
                    category="career",
                    difficulty=200,
                    type="career",
                    question=f"لاعب بدأ مع {first['club']} ووصل إلى {last['club']}… منو هو؟",
                    answer=player,
                    explanation=f"المحطتان تطابقان مسيرة {player}.",
                    payload={"career": [first, last]},
                    fact_group_id=group,
                    source_entity_id=player,
                    fact_type="career",
                    fact_payload=fact,
                ),
                _q(
                    category="career",
                    difficulty=400,
                    type="career",
                    question="تتبّع محطات هاللاعب بالترتيب… منو هو؟",
                    answer=player,
                    explanation=f"هذه محطات {player}.",
                    payload={"career": full},
                    fact_group_id=group,
                    source_entity_id=player,
                    fact_type="career",
                    fact_payload=fact,
                ),
            ]
        )
        if len(full) >= 3:
            index = len(full) // 2
            rows.append(
                _q(
                    category="career",
                    difficulty=600,
                    type="career",
                    question=(
                        f"لاعب انتقل من {full[index - 1]['club']} إلى {full[index]['club']} "
                        f"في {full[index]['years']}… منو هو؟"
                    ),
                    answer=player,
                    explanation=f"هذا الانتقال من مسيرة {player}.",
                    payload={"career": full[: index + 1]},
                    fact_group_id=group,
                    source_entity_id=player,
                    fact_type="career",
                    fact_payload=fact,
                )
            )
    return rows


# ── كأس العالم ─────────────────────────────────────────────────────────────
def _worldcup_rows() -> list[dict]:
    rows: list[dict] = []
    for event in TOURNAMENTS:
        year = event["year"]
        group = f"worldcup:{year}"
        fact = dict(event)
        rows.extend(
            [
                _q(
                    category="worldcup",
                    difficulty=200,
                    question=f"مونديال {year} في {event['host']}… منو خذ الكأس بعد ما غلب {event['runner_up']}؟",
                    answer=event["winner"],
                    explanation=f"فاز منتخب {event['winner']} بلقب {year}.",
                    fact_group_id=group, source_entity_id=str(year), fact_type="tournament", fact_payload=fact,
                ),
                _q(
                    category="worldcup",
                    difficulty=200,
                    question=f"نسخة مونديال {year} اللي توج فيها {event['winner']}… صارت بأي دولة؟",
                    answer=event["host"],
                    explanation=f"استضافت {event['host']} مونديال {year}.",
                    fact_group_id=group, source_entity_id=str(year), fact_type="tournament", fact_payload=fact,
                ),
                _q(
                    category="worldcup",
                    difficulty=400,
                    question=f"بنهائي مونديال {year} قدّام {event['winner']}… أي منتخب طلع وصيف؟",
                    answer=event["runner_up"],
                    explanation=f"خسر {event['runner_up']} النهائي أمام {event['winner']}.",
                    fact_group_id=group, source_entity_id=str(year), fact_type="tournament", fact_payload=fact,
                ),
                _q(
                    category="worldcup",
                    difficulty=400,
                    question=f"نهائي مونديال {year} بمدينة {event['city']}… انلعب على أي ملعب؟",
                    answer=event["venue"],
                    explanation=f"احتضن {event['venue']} نهائي {year}.",
                    fact_group_id=group, source_entity_id=str(year), fact_type="tournament", fact_payload=fact,
                ),
                _q(
                    category="worldcup",
                    difficulty=600,
                    question=f"بمونديال {year} في {event['host']}… منو طلع هدّاف البطولة؟",
                    answer=event["top_scorer"],
                    explanation=f"تصدّر {event['top_scorer']} هدافي مونديال {year}.",
                    fact_group_id=group, source_entity_id=str(year), fact_type="tournament", fact_payload=fact,
                ),
                _q(
                    category="worldcup",
                    difficulty=600,
                    question=f"نهائي مونديال {year} بين {event['winner']} و{event['runner_up']}… جم انتهت نتيجته؟",
                    answer=event["score"],
                    tolerance=event["score"].replace("–", "-"),
                    explanation=f"انتهى نهائي {year} بنتيجة {event['score']}.",
                    fact_group_id=group, source_entity_id=str(year), fact_type="tournament", fact_payload=fact,
                ),
            ]
        )
    for difficulty, facts in ((200, FACTS_200), (400, FACTS_400), (600, FACTS_600)):
        for index, fact in enumerate(facts):
            rows.append(
                _q(
                    category="worldcup",
                    difficulty=difficulty,
                    question=fact["q"],
                    answer=fact["a"],
                    explanation=fact["e"],
                    fact_group_id=f"worldcup_fact:{difficulty}:{index}",
                    source_entity_id=f"fact-{difficulty}-{index}",
                    fact_type="record",
                    fact_payload={"q": fact["q"], "a": fact["a"]},
                )
            )
    return rows


# ── دوري الأبطال ───────────────────────────────────────────────────────────
def _ucl_rows() -> list[dict]:
    rows: list[dict] = []
    for final in UCL_FINALS:
        year = final["year"]
        group = f"ucl_final:{year}"
        fact = dict(final)
        rows.extend(
            [
                _q(category="ucl", difficulty=200,
                   question=f"بنهائي أبطال أوروبا {year} قدّام {final['runner_up']}… منو رفع الكأس؟", answer=final["winner"],
                   explanation=f"بطل نسخة {year} هو {final['winner']}.",
                   fact_group_id=group, source_entity_id=str(year), fact_type="ucl_final", fact_payload=fact),
                _q(category="ucl", difficulty=400,
                   question=f"خسر نهائي الأبطال {year} قدّام {final['winner']} بنتيجة {final['score']}… أي نادي؟", answer=final["runner_up"],
                   explanation=f"خسر {final['runner_up']} نهائي {year}.",
                   fact_group_id=group, source_entity_id=str(year), fact_type="ucl_final", fact_payload=fact),
                _q(category="ucl", difficulty=400,
                   question=f"نهائي أبطال أوروبا {year} على {final['venue']}… بأي مدينة انلعب؟", answer=final["city"],
                   explanation=f"أقيم نهائي {year} في {final['city']}.",
                   fact_group_id=group, source_entity_id=str(year), fact_type="ucl_final", fact_payload=fact),
                _q(category="ucl", difficulty=600,
                   question=f"بمدينة {final['city']} سنة {year}… شنو اسم الملعب اللي استضاف نهائي الأبطال؟", answer=final["venue"],
                   explanation=f"احتضن {final['venue']} نهائي {year}.",
                   fact_group_id=group, source_entity_id=str(year), fact_type="ucl_final", fact_payload=fact),
            ]
        )
    return rows


# ── الحقائق المنسّقة ───────────────────────────────────────────────────────
def _curated_rows(category: str, facts: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for index, fact in enumerate(facts):
        group = f"{category}:" + fact.get("group", f"fact_{index}")
        rows.append(
            _q(
                category=category,
                difficulty=fact["d"],
                question=fact["q"],
                answer=fact["a"],
                explanation=fact["e"],
                fact_group_id=group,
                source_entity_id=fact.get("group", f"{category}-{index}"),
                fact_type="curated_fact",
                fact_payload={"question": fact["q"], "answer": fact["a"]},
                football_scope=fact.get("scope"),
            )
        )
    return rows


# ── الألغاز الإجرائية ──────────────────────────────────────────────────────
def _sequence_question(index: int) -> dict:
    start = 2 + (index * 3) % 41
    step = 2 + (index * 5) % 13
    values = [start + step * i for i in range(5)]
    answer = values[-1] + step
    shown = "، ".join(str(value) for value in values)
    return _q(
        category="riddles", difficulty=200,
        question=f"كمّل المتسلسلة على نفس النمط: {shown}، ؟",
        answer=str(answer), tolerance=_numeric_tolerance(answer),
        explanation=f"كل حد يزيد {step} عن اللي قبله، فالرقم التالي {answer}.",
        content_origin="generated_puzzle", payload={"kind": "sequence", "seed": index},
        fact_group_id=f"riddle:sequence:{index}",
    )


def _proportion_question(index: int) -> dict:
    unit = 2 + index % 17
    count_a, count_b = 3 + index % 4, 7 + index % 5
    total = unit * count_a
    answer = unit * count_b
    return _q(
        category="riddles", difficulty=400,
        question=f"لو {count_a} أقلام سعرها {total} درهم، جم يطلع سعر {count_b} أقلام بنفس الحسبة؟",
        answer=str(answer), tolerance=_numeric_tolerance(answer),
        explanation=f"سعر القلم {unit} درهم، و{count_b} أقلام تساوي {answer} درهمًا.",
        content_origin="generated_puzzle", payload={"kind": "proportion", "seed": index},
        fact_group_id=f"riddle:proportion:{index}",
    )


def _age_question(index: int) -> dict:
    difference = 2 + index % 11
    base = 10 + (index * 3) % 41
    older = base + difference
    total = older + base
    return _q(
        category="riddles", difficulty=600,
        question=f"أحمد أكبر من سالم بـ{difference} سنين، ومجموع أعمارهم {total} سنة… جم عمر أحمد؟",
        answer=str(older), tolerance=_numeric_tolerance(older),
        explanation=f"عمر سالم = ({total} − {difference}) ÷ 2 = {base}، وعمر أحمد = {older}.",
        content_origin="generated_puzzle", payload={"kind": "age", "seed": index},
        fact_group_id=f"riddle:age:{index}",
    )


def _riddle_rows() -> list[dict]:
    rows: list[dict] = []
    for index in range(RIDDLES_PER_BUCKET):
        rows.append(_sequence_question(index))
    for index in range(RIDDLES_PER_BUCKET):
        rows.append(_proportion_question(index))
    for index in range(RIDDLES_PER_BUCKET):
        rows.append(_age_question(index))
    return rows


# ── فروقات إجرائية ─────────────────────────────────────────────────────────
def _spotdiff_rows() -> list[dict]:
    rows: list[dict] = []
    for puzzle in build_spotdiff_puzzles():
        labels = "، ".join(puzzle["labels"])
        rows.append(
            _q(
                category="spotdiff",
                difficulty=puzzle["difficulty"],
                type="spot_diff",
                question=(
                    f"لقّط الفروقات الثلاثة في مشهد «{puzzle['sceneTitle']}» "
                    f"(نسخة {puzzle['variantSeed']})."
                ),
                answer=f"ثلاثة فروقات: {labels}",
                tolerance="ثلاثة فروقات صحيحة",
                explanation=f"الفروقات: {labels}.",
                content_origin="generated_puzzle",
                payload={
                    "sceneId": puzzle["sceneId"],
                    "sceneVersion": puzzle["sceneVersion"],
                    "variantSeed": puzzle["variantSeed"],
                    "combo": puzzle["combo"],
                    "anchors": puzzle["anchors"],
                    "mutations": puzzle["mutations"],
                    "differences": puzzle["differences"],
                    "subtlety": puzzle["subtlety"],
                },
                fact_group_id=f"spotdiff:{puzzle['sceneId']}:" + "-".join(puzzle["combo"]),
                fact_type="spotdiff_puzzle",
                fact_payload={"sceneId": puzzle["sceneId"], "combo": puzzle["combo"]},
            )
        )
    return rows


# ── الفئات الجديدة: مصادر API ولغز أعواد إجرائي ─────────────────────────────
def _module_rows(module: Any) -> list[dict]:
    return [_q(**row) for row in module.build_rows()]


# ── التجميع والتحقق ────────────────────────────────────────────────────────
def build_question_bank() -> list[dict]:
    rows = (
        _flags_rows()
        + _capitals_rows()
        + _football_rows()
        + _ucl_rows()
        + _worldcup_rows()
        + _career_rows()
        + _clubs_rows()
        + _curated_rows("arab_ftbl", ARAB_FACTS)
        + _curated_rows("numbers", RECORD_FACTS)
        + _curated_rows("general", GENERAL_FACTS)
        + _riddle_rows()
        + _spotdiff_rows()
        + _module_rows(quran)
        + _module_rows(nicknames)
        + _module_rows(technology)
        + _module_rows(videogames)
        + _module_rows(matchstick)
    )
    # البطاقات المعكوسة تُشتق من البنك نفسه: الجواب معروض والاختيارات أسئلة.
    rows = rows + _reverse_rows(rows)
    validate_question_bank(rows)
    return rows


def _reverse_rows(rows: list[dict]) -> list[dict]:
    labels = {item["slug"]: item["name_ar"] for item in CATEGORIES}
    return [_q(**row) for row in reverse.build_rows(rows, labels)]


def _football_rows() -> list[dict]:
    """حقائق كرة عالمية منسّقة (الفئة football)."""
    return _curated_rows("football", FOOTBALL_FACTS)


def inventory_report(rows: list[dict] | None = None) -> dict:
    """يقيس المخزون الفعلي مقابل الحدود المعيارية بلا أي تضخيم."""
    rows = rows if rows is not None else build_question_bank()
    buckets: dict[str, int] = {}
    groups: dict[str, set[str]] = {}
    football = {"global": 0, "arab": 0}
    origins: dict[str, int] = {}
    for row in rows:
        key = f"{row['category']}:{row['difficulty']}"
        buckets[key] = buckets.get(key, 0) + 1
        groups.setdefault(row["category"], set()).add(row["fact_group_id"])
        origins[row["content_origin"]] = origins.get(row["content_origin"], 0) + 1
        if row.get("football_scope") in football:
            football[row["football_scope"]] += 1

    expected = [f"{slug}:{difficulty}" for slug in CATEGORY_SLUGS for difficulty in DIFFICULTIES]
    missing = {key: buckets.get(key, 0) for key in expected if buckets.get(key, 0) < CONTENT_FLOOR_PER_BUCKET}
    capacity = {key: buckets.get(key, 0) for key in expected if buckets.get(key, 0) < CAPACITY_PER_BUCKET}
    football_total = football["global"] + football["arab"]
    return {
        "total": len(rows),
        "buckets": dict(sorted(buckets.items())),
        "categories": {
            slug: {
                "total": sum(buckets.get(f"{slug}:{d}", 0) for d in DIFFICULTIES),
                "fact_groups": len(groups.get(slug, set())),
                "bucket_min": min(buckets.get(f"{slug}:{d}", 0) for d in DIFFICULTIES),
            }
            for slug in CATEGORY_SLUGS
        },
        "origins": origins,
        "football_distribution": {
            "global": football["global"],
            "arab": football["arab"],
            "arab_percent": round(football["arab"] / football_total * 100, 2) if football_total else 0.0,
            "target_arab_percent": 15.0,
        },
        "content_floor_per_bucket": CONTENT_FLOOR_PER_BUCKET,
        "capacity_per_bucket": CAPACITY_PER_BUCKET,
        "buckets_below_content_floor": missing,
        "buckets_below_capacity_gate": capacity,
        "meets_content_floor": not missing,
        "meets_100_match_capacity": not capacity,
    }


def validate_question_bank(rows: list[dict]) -> dict:
    errors: list[str] = []
    counts: dict[tuple[str, int], int] = {}
    groups: dict[str, set[str]] = {}
    fingerprints: set[str] = set()
    country_codes = {country["code"] for country in COUNTRIES}
    for row in rows:
        category, difficulty = row.get("category"), row.get("difficulty")
        if category not in CATEGORY_SLUGS:
            errors.append(f"فئة غير معروفة: {category}")
        if difficulty not in DIFFICULTIES:
            errors.append(f"قيمة غير معروفة: {difficulty}")
        if not row.get("question") or not row.get("answer"):
            errors.append("سؤال أو إجابة فاضية.")
        if not row.get("fact_group_id"):
            errors.append("سؤال بدون fact_group_id.")
        if row.get("type") not in {"flag", "text", "career", "spot_diff"}:
            errors.append(f"نوع سؤال غير معروف: {row.get('type')}")
        if category == "matchstick":
            payload = row.get("payload") or {}
            if payload.get("kind") != "matchstick":
                errors.append("سؤال أعواد بدون payload.kind=matchstick.")
            else:
                for issue in matchstick.validate_puzzle(payload, strict=False):
                    errors.append(f"لغز أعواد غير صالح: {issue}")
        if category == "reverse":
            payload = row.get("payload") or {}
            options = payload.get("options")
            if payload.get("kind") != "reverse":
                errors.append("سؤال معكوس بدون payload.kind=reverse.")
            elif not isinstance(options, list) or len(options) != reverse.OPTION_COUNT:
                errors.append("سؤال معكوس لازم 4 اختيارات.")
            elif len(set(options)) != reverse.OPTION_COUNT:
                errors.append("اختيارات السؤال المعكوس مكررة.")
            elif payload.get("correct_index") not in range(reverse.OPTION_COUNT):
                errors.append("مؤشر الجواب الصحيح خارج الاختيارات.")
            elif options[payload["correct_index"]] != row.get("answer"):
                errors.append("جواب السؤال المعكوس لا يطابق الاختيار الصحيح.")
            elif not payload.get("answer"):
                errors.append("سؤال معكوس بدون نص الجواب.")
        if category in PROVENANCE_CATEGORIES:
            if not row.get("source_name"):
                errors.append(f"مصدر ناقص في {category}.")
            if not row.get("source_claim"):
                errors.append(f"ادعاء المصدر ناقص في {category}.")
            if not row.get("source_license"):
                errors.append(f"ترخيص المصدر ناقص في {category}.")
            if category in API_CATEGORIES:
                if not row.get("source_url") or not str(row["source_url"]).startswith("http"):
                    errors.append(f"رابط مصدر غير صالح في {category}.")
                if not row.get("source_entity_id"):
                    errors.append(f"معرّف كيان المصدر ناقص في {category}.")
                if not row.get("source_checked_at"):
                    errors.append(f"تاريخ تحقق المصدر ناقص في {category}.")
                if row.get("content_origin") not in {"api_sourced", "curated"}:
                    errors.append(f"أصل محتوى غير متوقع في {category}: {row.get('content_origin')}.")
        if row.get("type") == "flag" and (
            not row.get("flag_code")
            or len(row["flag_code"]) != 2
            or row["flag_code"] not in country_codes
        ):
            errors.append("سؤال علم بدون رمز ISO صالح.")
        if row.get("type") == "career":
            stops = (row.get("payload") or {}).get("career")
            if not isinstance(stops, list) or len(stops) < 2:
                errors.append("سؤال مسيرة يحتاج محطتين على الأقل.")
        if row.get("type") == "spot_diff":
            payload = row.get("payload") or {}
            diffs = payload.get("differences")
            if not isinstance(diffs, list) or len(diffs) != 3:
                errors.append("سؤال فروقات لازم يحتوي 3 فروقات.")
            if not payload.get("sceneId") or not payload.get("mutations"):
                errors.append("سؤال فروقات بدون sceneId أو mutations.")
            anchors = payload.get("anchors") or []
            if len(anchors) != 12:
                errors.append("مشهد فروقات لازم يعرّف 12 مرساة.")
            anchor_ids = {anchor.get("id") for anchor in anchors}
            for diff in diffs or []:
                if diff.get("id") not in anchor_ids:
                    errors.append("فرق يشير لمرساة غير معرّفة.")
        key = (category, difficulty)
        counts[key] = counts.get(key, 0) + 1
        groups.setdefault(category, set()).add(row["fact_group_id"])
        fingerprint_key = "\n".join(
            [str(category), normalize_text(row["question"]), normalize_answer(row["answer"]), str(row.get("flag_code") or "")]
        )
        if fingerprint_key in fingerprints:
            errors.append(f"سؤال مكرر: {row['question'][:40]}")
        fingerprints.add(fingerprint_key)

    for category in CATEGORY_SLUGS:
        if len(groups.get(category, set())) < OPERATIONAL_MIN_PER_BUCKET:
            errors.append(
                f"مجموعات واقعية غير كافية في {category}: "
                f"{len(groups.get(category, set()))} < {OPERATIONAL_MIN_PER_BUCKET}"
            )
        for difficulty in DIFFICULTIES:
            count = counts.get((category, difficulty), 0)
            if count < OPERATIONAL_MIN_PER_BUCKET:
                errors.append(f"مخزون غير كافٍ {category}/{difficulty}: {count} < {OPERATIONAL_MIN_PER_BUCKET}")
    if errors:
        raise ValueError("فشل التحقق من بنك الأسئلة:\n- " + "\n- ".join(errors[:40]))
    return {
        "total": len(rows),
        "buckets": {f"{key[0]}:{key[1]}": value for key, value in sorted(counts.items())},
        "fact_groups": {category: len(values) for category, values in sorted(groups.items())},
    }


def content_fingerprint() -> str:
    """بصمة إصدار المحتوى الحتمية تعتمد على الأسئلة نفسها لا على وقت التشغيل."""
    rows = build_question_bank()
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: (item["category"], item["difficulty"], item["question"])):
        digest.update(row["question"].encode("utf-8"))
        digest.update(row["answer"].encode("utf-8"))
        digest.update(row["fact_group_id"].encode("utf-8"))
    return digest.hexdigest()[:16]
