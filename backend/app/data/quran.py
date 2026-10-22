"""أسئلة القرآن الكريم من لقطة AlQuran Cloud المحفوظة محليًا باللهجة الخليجية وأسلوب سين جيم.

البيانات مأخوذة من `https://api.alquran.cloud/v1/surah` ومُخزّنة محليًا في
`snapshots/quran_surahs.json` لضمان حتمية التوليد بدون شبكة وقت التشغيل.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SNAPSHOT = Path(__file__).with_name("snapshots") / "quran_surahs.json"
SOURCE_NAME = "AlQuran Cloud API"
LICENSE = "Quran metadata from AlQuran Cloud; Quran text attribution: Tanzil.net"
FAMOUS_FOR_200 = (
    1, 2, 3, 4, 5, 12, 18, 19, 36, 55, 56, 67, 78, 87, 93, 94, 95, 96, 97, 99,
    100, 101, 102, 103, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114,
)
REVELATION_AR = {"Meccan": "مكية", "Medinan": "مدنية"}
SPECIAL_QUESTIONS: list[dict] = [
    {
        "surah": 1,
        "difficulty": 200,
        "question": "أم الكتاب والسبع المثاني اللي نفتتح فيها كل ركعة… شنو أول سورة بالمصحف الشريف؟",
        "answer": "الفاتحة",
        "tolerance": "الفاتحة، سورة الفاتحة",
    },
    {
        "surah": 114,
        "difficulty": 200,
        "question": "من المعوذتين ونختم فيها المصحف الشريف بالترتيب… شنو اسم آخر سورة بالقرآن؟",
        "answer": "الناس",
        "tolerance": "الناس، سورة الناس",
    },
    {
        "surah": 2,
        "difficulty": 200,
        "question": "فيها آية الكرسي وآية الدَّين وعدد آياتها 286… شنو أطول سورة بالقرآن الكريم؟",
        "answer": "البقرة",
        "tolerance": "البقرة، سورة البقرة",
    },
    {
        "surah": 108,
        "difficulty": 200,
        "question": "ثلاث آيات بس وتبشر النبي ﷺ بنهر في الجنة… شنو أقصر سورة بالقرآن الكريم؟",
        "answer": "الكوثر",
        "tolerance": "الكوثر، سورة الكوثر",
    },
    {
        "surah": 9,
        "difficulty": 400,
        "question": "تُعرف ببراءة وتجي بعد الأنفال… شنو السورة الوحيدة بالمصحف اللي ما تبدأ بالبسملة؟",
        "answer": "التوبة",
        "tolerance": "التوبة، سورة التوبة، براءة",
    },
    {
        "surah": 112,
        "difficulty": 400,
        "question": "تعدل ثلث القرآن وتبدأ بـ«قل هو الله أحد» وعدد آياتها 4… أي سورة رقمها 112 بالمصحف؟",
        "answer": "الإخلاص",
        "tolerance": "الإخلاص، الاخلاص، سورة الإخلاص",
    },
]


@lru_cache(maxsize=1)
def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _ordered_surahs_for_200(surahs_by_num: dict[int, dict]) -> list[dict]:
    chosen: list[dict] = []
    seen: set[int] = set()
    for number in FAMOUS_FOR_200:
        if number in surahs_by_num and number not in seen:
            chosen.append(surahs_by_num[number])
            seen.add(number)
    for number in sorted(surahs_by_num):
        if number not in seen:
            chosen.append(surahs_by_num[number])
    return chosen


def _row(surah: dict, checked_at: str | None, *, difficulty: int, question: str, answer: str, tolerance: str | None = None) -> dict:
    revelation_ar = REVELATION_AR.get(surah["revelation"], surah["revelation"])
    return {
        "category": "quran",
        "difficulty": difficulty,
        "question": question,
        "answer": answer,
        "tolerance": tolerance or answer,
        "explanation": (
            f"سورة {surah['name_ar']} رقمها {surah['number']} في المصحف، "
            f"وهي سورة {revelation_ar} عدد آياتها {surah['ayahs']}."
        ),
        "content_origin": "api_sourced",
        "verification_status": "verified_api",
        "source_name": SOURCE_NAME,
        "source_url": surah["source_url"],
        "source_checked_at": checked_at,
        "source_license": LICENSE,
        "source_claim": "surah number, Arabic name, ayah count, revelation type",
        "source_entity_id": f"surah:{surah['number']}",
        "fact_group_id": f"quran:surah:{surah['number']}",
        "fact_type": "quran_surah",
        "fact_payload": {
            "number": surah["number"],
            "name_ar": surah["name_ar"],
            "name_en": surah["name_en"],
            "ayahs": surah["ayahs"],
            "revelation": surah["revelation"],
            "revelation_ar": revelation_ar,
            "source_url": surah["source_url"],
            "reference_url": surah["reference_url"],
        },
    }


def build_rows() -> list[dict]:
    data = _snapshot()
    checked_at = str(data.get("retrieved_at", ""))[:10] or None
    surahs = list(data["surahs"])
    by_num = {int(item["number"]): item for item in surahs}
    ordered_200 = _ordered_surahs_for_200(by_num)

    rows_200: list[dict] = []
    rows_400: list[dict] = []
    rows_600: list[dict] = []

    for item in SPECIAL_QUESTIONS:
        surah = by_num[item["surah"]]
        target = rows_200 if item["difficulty"] == 200 else rows_400
        target.append(
            _row(
                surah,
                checked_at,
                difficulty=item["difficulty"],
                question=item["question"],
                answer=item["answer"],
                tolerance=item["tolerance"],
            )
        )

    for surah in ordered_200:
        if len(rows_200) >= 120:
            break
        revelation_ar = REVELATION_AR[surah["revelation"]]
        name = surah["name_ar"]
        rows_200.append(
            _row(
                surah,
                checked_at,
                difficulty=200,
                question=f"سورة {name} في المصحف الشريف… نزلت بمكة ولا بالمدينة (مكية أم مدنية)؟",
                answer=revelation_ar,
                tolerance=f"{revelation_ar}، سورة {revelation_ar}",
            )
        )

    for surah in ordered_200:
        if len(rows_200) >= 120:
            break
        name = surah["name_ar"]
        rows_200.append(
            _row(
                surah,
                checked_at,
                difficulty=200,
                question=f"في ترتيب المصحف الشريف، السورة اللي رقمها {surah['number']}… شنو اسمها؟",
                answer=name,
                tolerance=f"{name}، سورة {name}",
            )
        )

    for surah in surahs:
        if len(rows_400) >= 120:
            break
        name = surah["name_ar"]
        number = str(surah["number"])
        rows_400.append(
            _row(
                surah,
                checked_at,
                difficulty=400,
                question=f"سورة {name} ({REVELATION_AR[surah['revelation']]}) في المصحف الشريف… جم رقم ترتيبها؟",
                answer=number,
                tolerance=number,
            )
        )

    for surah in ordered_200:
        if len(rows_400) >= 120:
            break
        name = surah["name_ar"]
        revelation_ar = REVELATION_AR[surah["revelation"]]
        rows_400.append(
            _row(
                surah,
                checked_at,
                difficulty=400,
                question=f"سورة {revelation_ar} رقمها {surah['number']} بالمصحف وعدد آياتها {surah['ayahs']}… شنو اسم هالسورة؟",
                answer=name,
                tolerance=f"{name}، سورة {name}",
            )
        )

    for surah in surahs:
        if len(rows_600) >= 120:
            break
        name = surah["name_ar"]
        ayahs = str(surah["ayahs"])
        rows_600.append(
            _row(
                surah,
                checked_at,
                difficulty=600,
                question=f"سورة {name} اللي رقمها {surah['number']} في المصحف… جم عدد آياتها بالضبط؟",
                answer=ayahs,
                tolerance=f"{ayahs}، {ayahs} آية",
            )
        )

    for surah in ordered_200:
        if len(rows_600) >= 120:
            break
        ayahs = str(surah["ayahs"])
        revelation_ar = REVELATION_AR[surah["revelation"]]
        rows_600.append(
            _row(
                surah,
                checked_at,
                difficulty=600,
                question=(
                    f"السورة الـ{revelation_ar} اللي رقمها {surah['number']} في المصحف ({surah['name_ar']})… "
                    f"جم آية فيها؟"
                ),
                answer=ayahs,
                tolerance=f"{ayahs}، {ayahs} آية",
            )
        )

    return rows_200[:120] + rows_400[:120] + rows_600[:120]
