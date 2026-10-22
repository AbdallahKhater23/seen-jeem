"""تدقيق مدرج الصعوبة 200 < 400 < 600 عبر الفئات.

النموذج ثنائي المحور: مهمة السؤال (القالب) × شهرة الكيان (الجمهور).
200 للمعرفة العامة عند العربي العادي، 400 لمتابع الفئة، 600 للخبير.
"""

from __future__ import annotations

import pytest

from app.db import connect
from app.services import harvester
from app.services.content import build_question_bank
from app.services.harvester import harvested_flag_difficulty
from app.services.seed import seed_database


def _bank_by_category(category: str) -> list[dict]:
    return [row for row in build_question_bank() if row["category"] == category]


def test_clubs_country_is_400_and_league_is_600():
    rows = _bank_by_category("clubs")
    assert rows, "لا توجد أسئلة أندية في البنك"
    by_template: dict[str, set[int]] = {}
    for row in rows:
        if row["question"].startswith("في أي مدينة"):
            by_template.setdefault("city", set()).add(row["difficulty"])
        elif row["question"].startswith("في أي دولة يقع نادي"):
            by_template.setdefault("country", set()).add(row["difficulty"])
        elif row["question"].startswith("في أي دوري"):
            by_template.setdefault("league", set()).add(row["difficulty"])
    assert by_template.get("city") == {200}
    # الدولة أوسع وأسهل من الدوري المحدد: عكس الترتيب القديم المقلوب.
    assert by_template.get("country") == {400}
    assert by_template.get("league") == {600}


def test_worldcup_records_follow_fan_ladder():
    rows = _bank_by_category("worldcup")
    by_question = {row["question"]: row["difficulty"] for row in rows}

    def difficulty_of(substring: str) -> int:
        matches = [difficulty for question, difficulty in by_question.items() if substring in question]
        assert len(matches) == 1, f"توقع سؤال واحد يحوي {substring!r}"
        return matches[0]

    # وقائع نهائي 2022 الشهيرة للجميع (أقيم في قطر) ليست أسئلة خبراء.
    assert difficulty_of("ثلاثية في نهائي كأس العالم 2022") == 200
    assert difficulty_of("أي منتخب فاز بكأس العالم 2022 بركلات الترجيح") == 200
    # سجلات إحصائية للمتابعين والخبراء فقط.
    assert difficulty_of("الهداف التاريخي لكأس العالم بـ16 هدف") == 400
    assert difficulty_of("الكرة الذهبية في مونديال 2022") == 400
    assert difficulty_of("أكبر عدد أهداف في نسخة واحدة") == 600
    assert difficulty_of("سجل 27 هدفًا في نسخة 1954") == 600
    assert difficulty_of("خسر أكبر عدد من نهائيات كأس العالم") == 600


def test_harvested_flag_difficulty_by_population():
    assert harvested_flag_difficulty(300_000_000) == 200
    assert harvested_flag_difficulty(20_000_000) == 200
    assert harvested_flag_difficulty(5_000_000) == 400
    assert harvested_flag_difficulty(1_000_000) == 400
    assert harvested_flag_difficulty(8_000) == 600
    assert harvested_flag_difficulty(0) == 600
    # بلا بيانات سكانية لا ادّعاء: السلوك القديم.
    assert harvested_flag_difficulty(None) == 200
    assert harvested_flag_difficulty(True) == 200


@pytest.mark.asyncio
async def test_harvested_flags_tier_long_tail_not_famous(seeded_settings, monkeypatch):
    async def fake_get(*args, **kwargs):
        rows = []
        for index in range(60):
            code = f"{chr(ord('a') + index // 26)}{chr(ord('a') + index % 26)}"
            item = {
                "cca2": code,
                "name": {"common": f"Testland {index}"},
                "translations": {"ara": {"common": f"دولة اختبار {index}"}},
                "capital": [f"Capital {index}"],
                "region": "Test",
                "unMember": True,
            }
            if index % 3 == 0:
                item["population"] = 300_000_000
            elif index % 3 == 1:
                item["population"] = 5_000_000
            else:
                item["population"] = 8_000
            rows.append(item)
        return rows, "ok"

    monkeypatch.setattr(harvester, "_get_json", fake_get)
    monkeypatch.setattr(harvester, "_write_cache", lambda *args, **kwargs: None)
    result = await harvester.harvest_restcountries(seeded_settings, force=True)
    assert result["questions"] == 60
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT answer_text, difficulty FROM questions"
            " WHERE content_origin = 'api_sourced' AND source_name = 'RestCountries v3.1'"
        )
        found = {row["answer_text"]: int(row["difficulty"]) for row in await cursor.fetchall()}
        await cursor.close()
    assert len(found) == 60
    for index in range(60):
        expected = 200 if index % 3 == 0 else (400 if index % 3 == 1 else 600)
        assert found[f"دولة اختبار {index}"] == expected, f"صف {index}"


@pytest.mark.asyncio
async def test_reseed_converges_changed_difficulty(seeded_settings):
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT fingerprint, difficulty FROM questions"
            " WHERE is_active = 1 AND is_reserved_backup = 0 LIMIT 1"
        )
        row = await cursor.fetchone()
        await cursor.close()
        assert row is not None
        original = int(row["difficulty"])
        mutated = 600 if original == 200 else 200
        await db.execute(
            "UPDATE questions SET difficulty = ? WHERE fingerprint = ?",
            (mutated, row["fingerprint"]),
        )
        await db.commit()
    second = await seed_database(seeded_settings, deterministic_seed=12345)
    assert second["inserted"] == 0
    assert second["updated"] == 1
    assert second["skipped"] == second["total_active"] - 1
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT difficulty FROM questions WHERE fingerprint = ?", (row["fingerprint"],)
        )
        restored = int((await cursor.fetchone())["difficulty"])
        await cursor.close()
    assert restored == original
