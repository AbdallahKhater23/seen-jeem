"""أسئلة ألقاب لاعبي كرة القدم من لقطة Wikidata المحفوظة محليًا باللهجة الخليجية وأسلوب سين جيم.

اللقب مصدره خاصية P1449، ويجب أن يكون فريدًا للمالك في بيانات Wikidata، وألا
يكون مجرد اسم أو جزء من اسم اللاعب، وألا يحتوي ألفاظًا غير لائقة. لكل لاعب
سؤالان عن اللقب/اللاعب وسؤال ثالث يضيف الدولة كسياق وأصعبية أعلى.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SNAPSHOT = Path(__file__).with_name("snapshots") / "football_nicknames.json"
SOURCE_NAME = "Wikidata"
LICENSE = "CC0 1.0 (Wikidata structured data)"


@lru_cache(maxsize=1)
def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _players() -> list[dict]:
    data = _snapshot()
    players = list(data["players"])
    players.sort(
        key=lambda item: (
            int(item.get("difficulty", 600)),
            -int(item.get("sitelinks", 0)),
            item["qid"],
        )
    )
    return players


def _display_name(player: dict) -> str:
    return player.get("player_ar") or player.get("player_en") or player["qid"]


def _tolerance_names(player: dict) -> str:
    arabic = player.get("player_ar")
    english = player.get("player_en")
    if arabic and english and english.casefold() != arabic.casefold():
        return f"{arabic}، {english}"
    return arabic or english or player["qid"]


def build_rows() -> list[dict]:
    data = _snapshot()
    checked_at = str(data.get("retrieved_at", ""))[:10] or None
    rows: list[dict] = []
    for player in _players():
        name = _display_name(player)
        nickname = player["nickname"]
        country = player["country_label"]
        positions = player.get("positions") or []
        difficulty = int(player["difficulty"])
        common = {
            "category": "nicknames",
            "content_origin": "api_sourced",
            "verification_status": "verified_api",
            "source_name": SOURCE_NAME,
            "source_url": player["source_url"],
            "source_checked_at": checked_at,
            "source_license": LICENSE,
            "source_claim": "P1449 nickname, P27 country, P413 position",
            "source_entity_id": player["qid"],
            "fact_group_id": f"nickname:{player['qid']}",
            "fact_type": "player_nickname",
            "fact_payload": {
                "qid": player["qid"],
                "player_ar": player.get("player_ar"),
                "player_en": player.get("player_en"),
                "nickname": nickname,
                "country_qid": player["country_qid"],
                "country_label": country,
                "positions": positions,
                "sitelinks": player.get("sitelinks"),
                "claims": player.get("claims", {}),
                "source_url": player["source_url"],
            },
        }
        position_text = (
            f" ويلعب في مركز {'، '.join(positions)}." if positions else "."
        )
        explanation = f"{name} لاعب كرة قدم من {country}، ويُعرف بلقب «{nickname}»{position_text}"
        if difficulty == 200:
            rows.append(
                {
                    **common,
                    "difficulty": 200,
                    "question": f"الجمهور والمعلقين يعرفون نجم {country} ({name}) بلقب مميز بالملاعب… شنو هاللقب؟",
                    "answer": nickname,
                    "explanation": explanation,
                }
            )
        elif difficulty == 400:
            rows.append(
                {
                    **common,
                    "difficulty": 400,
                    "question": f"في عالم الكورة ينادونه بلقب «{nickname}»… منو هاللاعب؟",
                    "answer": name,
                    "tolerance": _tolerance_names(player),
                    "explanation": explanation,
                }
            )
        else:
            rows.append(
                {
                    **common,
                    "difficulty": 600,
                    "question": f"لاعب من {country} اشتهر بالملاعب بلقب «{nickname}»… منو هو؟",
                    "answer": name,
                    "tolerance": _tolerance_names(player),
                    "explanation": explanation,
                }
            )
    return rows
