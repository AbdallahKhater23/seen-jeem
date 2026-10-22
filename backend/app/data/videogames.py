"""أسئلة ألعاب الفيديو من لقطة Wikidata المحفوظة محليًا باللهجة الخليجية وأسلوب سين جيم.

نطاق الاختيار: ألعاب شهيرة صدرت على الحاسب الشخصي أو PlayStation 3/4/5، ولكل
لعبة مطوّر واحد وناشر واحد وسنة إصدار أولى محددة في بيانات Wikidata.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SNAPSHOT = Path(__file__).with_name("snapshots") / "videogames.json"
SOURCE_NAME = "Wikidata"
LICENSE = "CC0 1.0 (Wikidata structured data)"


@lru_cache(maxsize=1)
def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _games() -> list[dict]:
    data = _snapshot()
    games = list(data["games"])
    games.sort(key=lambda item: (-int(item.get("sitelinks", 0)), item["qid"]))
    return games[:120]


def _game_title(game: dict) -> str:
    ar = game.get("title_ar")
    en = game.get("title_en")
    if ar and en and ar.casefold() != en.casefold():
        return f"{ar} ({en})"
    return ar or en or game["qid"]


def build_rows() -> list[dict]:
    data = _snapshot()
    checked_at = str(data.get("retrieved_at", ""))[:10] or None
    rows: list[dict] = []
    for game in _games():
        title = _game_title(game)
        developer = game["developer_label"]
        publisher = game["publisher_label"]
        year = str(game["first_release_year"])
        platforms = "، ".join(game.get("platforms") or [])
        common = {
            "category": "videogames",
            "content_origin": "api_sourced",
            "verification_status": "verified_api",
            "source_name": SOURCE_NAME,
            "source_url": game["source_url"],
            "source_checked_at": checked_at,
            "source_license": LICENSE,
            "source_claim": "P178 developer, P123 publisher, P577 publication date, P400 platform",
            "source_entity_id": game["qid"],
            "fact_group_id": f"videogame:{game['qid']}",
            "fact_type": "videogame",
            "fact_payload": {
                "qid": game["qid"],
                "title_ar": game.get("title_ar"),
                "title_en": game.get("title_en"),
                "developer_qid": game["developer_qid"],
                "developer_label": developer,
                "publisher_qid": game["publisher_qid"],
                "publisher_label": publisher,
                "first_release_date": game["first_release_date"],
                "first_release_year": year,
                "platforms": game.get("platforms", []),
                "sitelinks": game.get("sitelinks"),
                "claims": game.get("claims", {}),
                "source_url": game["source_url"],
            },
        }
        explanation = (
            f"لعبة {title} طوّرها {developer} ونشرها {publisher}، "
            f"وصدرت أول مرة سنة {year} على منصات منها: {platforms}."
        )
        rows.append(
            {
                **common,
                "difficulty": 200,
                "question": f"لعبة الفيديو الشهيرة {title} اللي صدرت سنة {year}… منو الاستوديو اللي طوّرها؟",
                "answer": developer,
                "tolerance": developer,
                "explanation": explanation,
            }
        )
        rows.append(
            {
                **common,
                "difficulty": 400,
                "question": f"لعبة {title} اللي طوّرها {developer}… أي شركة تولّت نشرها؟",
                "answer": publisher,
                "tolerance": publisher,
                "explanation": explanation,
            }
        )
        rows.append(
            {
                **common,
                "difficulty": 600,
                "question": f"من تطوير {developer} ونشر {publisher}… بأي سنة نزلت لعبة {title} لأول مرة؟",
                "answer": year,
                "tolerance": year,
                "explanation": explanation,
            }
        )
    return rows
