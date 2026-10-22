"""مشاهد «طلع الفرق» الإجرائية: 12 مشهدًا × 12 مرساة = 144 مرساة.

كل مشهد يعرّف 12 عنصرًا قابلًا للتغيير بأحد أنواع التحوّل الأربعة:
color, missing, scale, flip. المواضع تُحسب حتميًا على شبكة 4×3 مع إزاحة
ثابتة لكل مشهد، فتنتج 220 تركيبة (C(12,3)) لكل مشهد، أي 2,640 لغزًا.
المحتوى مولّد إجرائيًا بالكامل، ويُوسَم بذلك صراحةً.
"""

from __future__ import annotations

from itertools import combinations

SCENE_VERSION = 1
ANCHORS_PER_SCENE = 12
DIFFS_PER_PUZZLE = 3

MUTATION_TYPES = ("color", "missing", "scale", "flip")

# أنواع العنصر تُرسم في الواجهة كأشكال هندسية بسيطة داخل خلفية المشهد.
SHAPES = ("circle", "square", "triangle", "star", "diamond", "ring")

PALETTE = (
    "#38bdf8", "#f59e0b", "#34d399", "#f472b6",
    "#a78bfa", "#fb7185", "#facc15", "#22d3ee",
)

SCENES: list[dict] = [
    {
        "sceneId": "pitch",
        "title": "ملعب كورة",
        "background": "#0b3d2e",
        "accent": "#4ade80",
        "anchors": [
            "الكرة", "الراية", "الحارس", "الشبكة", "خط المنتصف", "المدرج",
            "اللوحة الإعلانية", "المدرب", "الكرسي الاحتياطي", "ساعة الملعب",
            "قارورة الماء", "الكاميرا",
        ],
    },
    {
        "sceneId": "locker",
        "title": "غرفة الملابس",
        "background": "#1e293b",
        "accent": "#fbbf24",
        "anchors": [
            "القميص", "الحذاء", "الخزانة", "المنشفة", "الكرسي", "الساعة",
            "زجاجة الماء", "الشعار", "المصباح", "الحقيبة", "الشراب", "المرآة",
        ],
    },
    {
        "sceneId": "ucl_stage",
        "title": "منصة دوري الأبطال",
        "background": "#172554",
        "accent": "#93c5fd",
        "anchors": [
            "الكأس", "النجمة", "المنصة", "الأعلام", "الكشاف", "الستارة",
            "الشعار", "الميدالية", "الورود", "الكاميرا", "الجمهور", "السجادة",
        ],
    },
    {
        "sceneId": "diwaniya",
        "title": "ديوانية",
        "background": "#3f2d1d",
        "accent": "#f59e0b",
        "anchors": [
            "الدلة", "الفناجين", "السجاد", "المسند", "التبّاخة", "المبخر",
            "النجفة", "النافذة", "الرف", "الساعة", "الورد", "المرايا",
        ],
    },
    {
        "sceneId": "towers",
        "title": "كورنيش أبراج الكويت",
        "background": "#0c4a6e",
        "accent": "#67e8f9",
        "anchors": [
            "البرج الرئيسي", "الكرة الزرقاء", "السارية", "النخلة", "الشاطئ",
            "المركب", "الشمس", "الطائر", "الحاجز", "المصباح", "المقعد", "السحابة",
        ],
    },
    {
        "sceneId": "studio",
        "title": "استوديو البث",
        "background": "#312e81",
        "accent": "#c4b5fd",
        "anchors": [
            "الكاميرا", "الشاشة", "المذيع", "الميكروفون", "الإضاءة", "الطاولة",
            "الشعار", "الساعة", "الكرسي", "السماعة", "الخلفية", "الأوراق",
        ],
    },
    {
        "sceneId": "var_room",
        "title": "غرفة تقنية الفيديو",
        "background": "#111827",
        "accent": "#f87171",
        "anchors": [
            "الشاشة الكبيرة", "الشاشة الصغيرة", "الحكم", "الماوس", "لوحة التحكم",
            "الكاميرا", "الساعة", "السماعة", "الكرسي", "المصباح", "الأوراق", "الهاتف",
        ],
    },
    {
        "sceneId": "desert_camp",
        "title": "مخيّم بالبر",
        "background": "#78350f",
        "accent": "#fcd34d",
        "anchors": [
            "الخيمة", "الجمل", "النار", "الدلة", "السجاد", "الهلال",
            "النجوم", "النخلة", "الصخرة", "السيارة", "الفانوس", "الرمل",
        ],
    },
    {
        "sceneId": "arcade",
        "title": "أركيد قديم",
        "background": "#3b0764",
        "accent": "#f0abfc",
        "anchors": [
            "الجهاز", "العصا", "الشاشة", "الأزرار", "التذكرة", "المصباح",
            "اللوحة", "الكرسي", "الساعة", "العملة", "السماعة", "الباب",
        ],
    },
    {
        "sceneId": "cafe",
        "title": "مقهى خارجي",
        "background": "#14532d",
        "accent": "#86efac",
        "anchors": [
            "الطاولة", "الكرسي", "المظلة", "الفنجان", "النادل", "المنيو",
            "النبتة", "المصباح", "اللافتة", "الدراجة", "الطائر", "الساعة",
        ],
    },
    {
        "sceneId": "airport",
        "title": "بوابة المطار",
        "background": "#1e3a8a",
        "accent": "#bfdbfe",
        "anchors": [
            "الطائرة", "الحقيبة", "الشاشة", "المقعد", "الممر", "الرحلة",
            "البوابة", "الكاميرا", "الساعة", "المصباح", "القهوة", "الطفل",
        ],
    },
    {
        "sceneId": "market",
        "title": "سوق شعبي",
        "background": "#7c2d12",
        "accent": "#fdba74",
        "anchors": [
            "الفانوس", "الصندوق", "المظلة", "الرمان", "البائع", "الميزان",
            "السلة", "اللافتة", "العربة", "القط", "الفلفل", "الساعة",
        ],
    },
]


def _anchor(scene_index: int, index: int) -> dict:
    """هندسة حتمية على شبكة 4×3 مع إزاحة ثابتة لكل مشهد."""
    col = index % 4
    row = index // 4
    jitter_x = (scene_index * 7 + index * 11) % 9 - 4
    jitter_y = (scene_index * 5 + index * 13) % 9 - 4
    return {
        "id": f"a{index + 1}",
        "label": SCENES[scene_index]["anchors"][index],
        "x": 56 + col * 96 + jitter_x,
        "y": 52 + row * 96 + jitter_y,
        "w": 30 + (index * 13 + scene_index * 7) % 26,
        "h": 30 + (index * 17 + scene_index * 5) % 22,
        "shape": SHAPES[(index + scene_index) % len(SHAPES)],
        "color": PALETTE[(index * 3 + scene_index) % len(PALETTE)],
        "mutation": MUTATION_TYPES[(index + scene_index) % len(MUTATION_TYPES)],
    }


def scene_anchors(scene_index: int) -> list[dict]:
    return [_anchor(scene_index, index) for index in range(ANCHORS_PER_SCENE)]


def mutation_payload(anchor: dict) -> dict:
    """بيانات التحوّل الحتمية المرتبطة بمرساة واحدة."""
    mutation = anchor["mutation"]
    if mutation == "color":
        return {"id": anchor["id"], "type": "color", "from": anchor["color"], "to": "#f43f5e"}
    if mutation == "missing":
        return {"id": anchor["id"], "type": "missing"}
    if mutation == "scale":
        return {"id": anchor["id"], "type": "scale", "scale": 1.45}
    return {"id": anchor["id"], "type": "flip", "axis": "x"}


def _subtlety(scene_index: int, anchors: list[dict], combo: tuple[int, int, int]) -> int:
    """درجة دقة محسوبة من الحجم والموقع ونوع التحوّل (ليست عشوائية)."""
    weights = {"color": 2, "missing": 3, "scale": 2, "flip": 3}
    score = 0
    for index in combo:
        anchor = anchors[index]
        size = min(anchor["w"], anchor["h"])
        # المراسي الصغيرة أصعب، والبعيدة عن المركز أصعب قليلًا.
        score += 3 if size < 34 else 1
        score += 1 if abs(anchor["x"] - 200) > 110 or abs(anchor["y"] - 150) > 80 else 0
        score += weights[anchor["mutation"]]
    score += scene_index % 3
    return score


def build_spotdiff_puzzles() -> list[dict]:
    """يولّد كل التركيبات الـ220 لكل مشهد، مرتبة بحتمية حسب الصعوبة."""
    puzzles: list[dict] = []
    for scene_index, scene in enumerate(SCENES):
        anchors = scene_anchors(scene_index)
        scored = []
        for combo in combinations(range(ANCHORS_PER_SCENE), DIFFS_PER_PUZZLE):
            scored.append((_subtlety(scene_index, anchors, combo), combo))
        scored.sort(key=lambda item: (item[0], item[1]))
        total = len(scored)
        for rank, (score, combo) in enumerate(scored):
            # تقسيم ثلاثي متوازن: الأسهل 200، الوسط 400، الأدق 600.
            difficulty = 200 if rank < total / 3 else 400 if rank < (2 * total) / 3 else 600
            chosen = [anchors[index] for index in combo]
            puzzles.append(
                {
                    "sceneId": scene["sceneId"],
                    "sceneTitle": scene["title"],
                    "sceneVersion": SCENE_VERSION,
                    "combo": [anchor["id"] for anchor in chosen],
                    "anchors": anchors,
                    "mutations": [mutation_payload(anchor) for anchor in chosen],
                    "differences": [
                        {
                            "id": anchor["id"],
                            "label": f"{anchor['label']} ({_mutation_label(anchor['mutation'])})",
                            "x": anchor["x"],
                            "y": anchor["y"],
                            "r": max(anchor["w"], anchor["h"]) // 2 + 14,
                            "mutation": anchor["mutation"],
                        }
                        for anchor in chosen
                    ],
                    "difficulty": difficulty,
                    "subtlety": score,
                    "variantSeed": scene_index * 10000 + rank,
                    "labels": [anchor["label"] for anchor in chosen],
                }
            )
    return puzzles


def _mutation_label(mutation: str) -> str:
    return {
        "color": "تغيّر اللون",
        "missing": "اختفى",
        "scale": "تغيّر الحجم",
        "flip": "انقلب اتجاهه",
    }[mutation]
