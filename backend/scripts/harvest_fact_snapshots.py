"""حاصد لقطات المصادر للفئات الأربع factual.

اللقطة الناتجة تُحفظ داخل ``app/data/snapshots`` وتُقرأ عند الزرع دون شبكة.
شبكة الإنترنت مطلوبة فقط عند تحديث اللقطة، وليست شرطًا لتشغيل اللعبة.

المصادر:
- AlQuran Cloud: بيانات السور (الاسم، الرقم، عدد الآيات).
- Wikidata SPARQL + wbgetentities: شركات التقنية، ألعاب الفيديو، ألقاب اللاعبين.

كل سجل يحمل QID أو رقم السورة، رابط المصدر، ووقت السحب. لا تُكتب أي أسرار.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "app" / "data" / "snapshots"
USER_AGENT = "SeenJeemTrivia/2.0 (local Arabic trivia game; +https://localhost) httpx/0.27"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
QURAN_URL = "https://api.alquran.cloud/v1/surah"

TARGET_PLATFORMS = {
    "Q10683": "PlayStation 3",
    "Q50107": "PlayStation 4",
    "Q63184502": "PlayStation 5",
    "Q1406": "PC (Windows)",
}
TECH_INDUSTRIES = (
    "Q880371",  # software industry
    "Q21157865",  # technology industry
    "Q56611700",  # internet industry
    "Q132898730",  # computer hardware industry (best effort)
    "Q5358497",  # electronics industry
    "Q2986369",  # semiconductor industry
    "Q941594",  # video game industry
)
# كيانات ليست تقنية بوضوح، أو سنة تأسيسها في Wikidata تعبّر عن إعادة تسمية
#/اندماج ولا تطابق الفهم العام لـ«سنة التأسيس». تُستبعد بدل تمريرها كحقيقة.
BLOCKED_TECH_QIDS = {
    "Q188454",  # Yamaha: Wikidata says 1987, commonly founded 1887
    "Q1063455",  # The Lego Group: toy company, not a technology company
    "Q677085",  # Gen Digital: successor/renamed Symantec, 1982 is predecessor date
}
BLOCKED_PLAYER_QIDS = {
    "Q79983",  # José Mourinho: "Special One" is a managerial nickname
}
BLOCKED_NICKNAME_PARTS = {
    "fuck", "fucking", "shit", "bitch", "sex", "sexual", "porn", "nazi",
    "penis", "dick", "tangas", "puta", "puto", "cabron", "cabrón", "mierda",
    "asshole", "bastard", "whore", "slut",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_arabic_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = text.replace("ٱ", "ا").replace("ﷲ", "الله")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("سورة", "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


class Client:
    def __init__(self) -> None:
        self.http = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(120.0, connect=30.0),
            follow_redirects=True,
        )

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict:
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self.http.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
                if response.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"فشل طلب {url}: {last_error}")

    def sparql(self, query: str) -> list[dict]:
        data = self.get_json(
            SPARQL_ENDPOINT,
            params={"format": "json", "query": query},
        )
        return data.get("results", {}).get("bindings", [])

    def entities(self, qids: Iterable[str], languages: str = "ar|en") -> dict[str, dict]:
        ids = sorted({qid for qid in qids if re.fullmatch(r"Q\d+", qid)})
        result: dict[str, dict] = {}
        for index in range(0, len(ids), 50):
            chunk = ids[index : index + 50]
            data = self.get_json(
                WIKIDATA_API,
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": "labels|claims",
                    "languages": languages,
                    "format": "json",
                },
            )
            result.update(data.get("entities", {}))
        return result


def qid_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def label_of(entity: dict, language: str = "ar") -> str | None:
    labels = entity.get("labels", {})
    value = labels.get(language, {}).get("value")
    if value:
        return value
    return labels.get("en", {}).get("value")


def claim_ids(entity: dict, prop: str) -> list[str]:
    values: set[str] = set()
    for claim in entity.get("claims", {}).get(prop, []):
        try:
            values.add(claim["mainsnak"]["datavalue"]["value"]["id"])
        except (KeyError, TypeError):
            continue
    return sorted(values)


def claim_times(entity: dict, prop: str) -> list[str]:
    values: set[str] = set()
    for claim in entity.get("claims", {}).get(prop, []):
        try:
            raw = claim["mainsnak"]["datavalue"]["value"]["time"]
            values.add(raw.lstrip("+")[:10])
        except (KeyError, TypeError):
            continue
    return sorted(values)


def write_snapshot(name: str, payload: dict) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def harvest_quran(client: Client) -> dict:
    data = client.get_json(QURAN_URL)
    surahs = []
    for item in data.get("data", []):
        number = int(item["number"])
        surahs.append(
            {
                "number": number,
                "name_ar": clean_arabic_name(item["name"]),
                "name_en": item["englishName"],
                "ayahs": int(item["numberOfAyahs"]),
                "revelation": item["revelationType"],
                "source_url": f"https://api.alquran.cloud/v1/surah/{number}",
                "reference_url": f"https://quran.com/{number}",
            }
        )
    surahs.sort(key=lambda item: item["number"])
    if len(surahs) != 114:
        raise RuntimeError(f"عدد السور غير متوقع: {len(surahs)}")
    payload = {
        "snapshot_version": 1,
        "generator": "harvest_fact_snapshots.py",
        "retrieved_at": now_iso(),
        "source": {
            "name": "AlQuran Cloud API",
            "url": QURAN_URL,
            "license": "Quran metadata from AlQuran Cloud; Quran text attribution: Tanzil.net",
            "access": "public JSON API",
        },
        "surahs": surahs,
        "general_facts": general_quran_facts(),
    }
    path = write_snapshot("quran_surahs.json", payload)
    return {"path": str(path), "records": len(surahs), "general_facts": len(payload["general_facts"])}


def general_quran_facts() -> list[dict]:
    """حقائق قرآنية عامة واضحة، كل واحدة بمرجع آية أو بيانات سورة."""
    facts = [
        (200, "كم عدد سور القرآن الكريم؟", "114", "عدد سور القرآن الكريم 114 سورة.", "https://api.alquran.cloud/v1/surah", "quran:count"),
        (200, "ما أول سورة في المصحف؟", "الفاتحة", "أول سورة في ترتيب المصحف هي الفاتحة.", "https://quran.com/1", "quran:first"),
        (200, "ما آخر سورة في المصحف؟", "الناس", "آخر سورة في ترتيب المصحف هي الناس.", "https://quran.com/114", "quran:last"),
        (200, "ما أطول سورة في القرآن الكريم؟", "البقرة", "سورة البقرة أطول سور القرآن، وعدد آياتها 286 آية.", "https://quran.com/2", "quran:longest"),
        (200, "ما أقصر سورة في القرآن الكريم؟", "الكوثر", "سورة الكوثر أقصر سور القرآن، وعدد آياتها 3 آيات.", "https://quran.com/108", "quran:shortest"),
        (200, "في أي سورة توجد آية الكرسي؟", "البقرة", "آية الكرسي هي الآية 255 من سورة البقرة.", "https://quran.com/2/255", "quran:kursi"),
        (400, "ما السورة التي تبدأ بـ«الحمد لله رب العالمين»؟", "الفاتحة", "سورة الفاتحة تبدأ بعد البسملة بـ«الحمد لله رب العالمين».", "https://quran.com/1/2", "quran:fatiha_hamd"),
        (400, "في أي سورة ذُكرت قصة أصحاب الكهف؟", "الكهف", "ذُكرت قصة أصحاب الكهف في سورة الكهف، بدءًا من الآية 9.", "https://quran.com/18/9", "quran:kahf"),
        (400, "في أي سورة ذُكرت قصة يوسف عليه السلام؟", "يوسف", "سورة يوسف تعرض قصة يوسف عليه السلام، ومنها الآية 3.", "https://quran.com/12/3", "quran:yusuf"),
        (400, "في أي سورة ذُكرت قصة موسى والخضر؟", "الكهف", "ذُكرت قصة موسى والخضر في سورة الكهف، بدءًا من الآية 60.", "https://quran.com/18/60", "quran:khidr"),
        (400, "في أي سورة ذُكرت مريم عليها السلام في اسمها؟", "مريم", "سورة مريم هي السورة التي تحمل اسمها، وفيها ذكر مريم عليها السلام.", "https://quran.com/19/16", "quran:maryam"),
        (400, "في أي سورة ذُكرت قصة أصحاب الفيل؟", "الفيل", "ذُكرت قصة أصحاب الفيل في سورة الفيل.", "https://quran.com/105/1", "quran:feel"),
        (600, "في أي سورة ذُكرت قصة سليمان مع الهدهد؟", "النمل", "ذُكرت قصة سليمان مع الهدهد في سورة النمل، بدءًا من الآية 20.", "https://quran.com/27/20", "quran:hudhud"),
        (600, "ما السورة التي تبدأ بـ«تبارك الذي بيده الملك»؟", "الملك", "سورة الملك تبدأ بـ«تبارك الذي بيده الملك».", "https://quran.com/67/1", "quran:mulk"),
        (600, "في أي سورة ذُكرت قصة أصحاب الأخدود؟", "البروج", "ذُكرت قصة أصحاب الأخدود في سورة البروج، بدءًا من الآية 4.", "https://quran.com/85/4", "quran:ukhdud"),
        (600, "ما السورة التي تبدأ بـ«طه»؟", "طه", "سورة طه تبدأ بالحروف «طه».", "https://quran.com/20/1", "quran:taha"),
        (600, "ما السورة التي تبدأ بـ«يس»؟", "يس", "سورة يس تبدأ بالحروف «يس».", "https://quran.com/36/1", "quran:yasin"),
        (600, "في أي سورة ذُكرت قصة بقرة بني إسرائيل؟", "البقرة", "ذُكرت قصة بقرة بني إسرائيل في سورة البقرة، بدءًا من الآية 67.", "https://quran.com/2/67", "quran:baqarah_cow"),
    ]
    return [
        {
            "difficulty": difficulty,
            "question": question,
            "answer": answer,
            "explanation": explanation,
            "source_url": source_url,
            "fact_group_id": group,
        }
        for difficulty, question, answer, explanation, source_url, group in facts
    ]


def harvest_technology(client: Client) -> dict:
    industries = " ".join(f"wd:{qid}" for qid in TECH_INDUSTRIES)
    query = f"""
SELECT ?company ?companyLabel ?founder ?founderLabel ?inception ?country ?countryLabel ?links WHERE {{
  VALUES ?industry {{ {industries} }}
  ?company wdt:P452 ?industry .
  ?company wikibase:sitelinks ?links .
  ?company wdt:P112 ?founder .
  ?founder wdt:P31 wd:Q5 .
  ?company wdt:P571 ?inception .
  ?company wdt:P17 ?country .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ar,en". }}
}} ORDER BY DESC(?links) LIMIT 2000
"""
    rows = client.sparql(query)
    by_company: dict[str, dict] = {}
    for row in rows:
        qid = qid_of(row["company"]["value"])
        record = by_company.setdefault(
            qid,
            {
                "qid": qid,
                "label": row.get("companyLabel", {}).get("value"),
                "links": int(row["links"]["value"]),
                "founders": {},
                "countries": {},
                "inceptions": set(),
            },
        )
        founder_qid = qid_of(row["founder"]["value"])
        record["founders"][founder_qid] = row.get("founderLabel", {}).get("value") or founder_qid
        country_qid = qid_of(row["country"]["value"])
        record["countries"][country_qid] = row.get("countryLabel", {}).get("value") or country_qid
        record["inceptions"].add(row["inception"]["value"][:10])

    candidates = []
    for record in by_company.values():
        if len(record["founders"]) != 1 or len(record["countries"]) != 1:
            continue
        years = {value[:4] for value in record["inceptions"] if len(value) >= 4}
        if len(years) != 1:
            continue
        candidates.append(record)
    candidates.sort(key=lambda item: (-item["links"], item["qid"]))
    selected = candidates[:160]

    refs = {item["qid"] for item in selected}
    for item in selected:
        refs.update(item["founders"].keys())
        refs.update(item["countries"].keys())
    entities = client.entities(refs)

    companies = []
    for item in selected:
        if item["qid"] in BLOCKED_TECH_QIDS:
            continue
        entity = entities.get(item["qid"], {})
        # نستخدم كل ادعاءات P571 لا نسخة SPARQL المفضلة فقط. وجود أكثر من سنة
        # يعني أن التاريخ قد يمثل إعادة تأسيس/اندماج، فنستبعده بدل التخمين.
        years = sorted({value[:4] for value in claim_times(entity, "P571") if len(value) >= 4})
        if len(years) != 1:
            continue
        founder_qid = next(iter(item["founders"]))
        founder_label = label_of(entities.get(founder_qid, {})) or item["founders"][founder_qid]
        founder_en = entities.get(founder_qid, {}).get("labels", {}).get("en", {}).get("value")
        country_qid = next(iter(item["countries"]))
        country_label = label_of(entities.get(country_qid, {})) or item["countries"][country_qid]
        year = years[0]
        companies.append(
            {
                "qid": item["qid"],
                "label_ar": entity.get("labels", {}).get("ar", {}).get("value"),
                "label_en": entity.get("labels", {}).get("en", {}).get("value") or item["label"],
                "founder_qid": founder_qid,
                "founder_label_ar": founder_label,
                "founder_label_en": founder_en,
                "country_qid": country_qid,
                "country_label_ar": country_label,
                "country_label_en": entities.get(country_qid, {}).get("labels", {}).get("en", {}).get("value"),
                "inception_year": year,
                "sitelinks": item["links"],
                "source_url": f"https://www.wikidata.org/wiki/{item['qid']}",
                "claims": {"founder": "P112", "inception": "P571", "country": "P17"},
            }
        )

    payload = {
        "snapshot_version": 1,
        "generator": "harvest_fact_snapshots.py",
        "retrieved_at": now_iso(),
        "source": {
            "name": "Wikidata",
            "url": "https://www.wikidata.org/",
            "sparql_endpoint": SPARQL_ENDPOINT,
            "license": "CC0 1.0 (Wikidata structured data)",
            "access": "public SPARQL + wbgetentities API",
        },
        "filters": {
            "single_human_founder": True,
            "single_country": True,
            "single_inception_year": True,
            "industry_qids": list(TECH_INDUSTRIES),
        },
        "companies": companies,
    }
    path = write_snapshot("technology_companies.json", payload)
    return {"path": str(path), "candidates": len(candidates), "records": len(companies)}


def harvest_videogames(client: Client) -> dict:
    query = """
SELECT DISTINCT ?game ?links WHERE {
  ?game wdt:P31 wd:Q7889 .
  ?game wikibase:sitelinks ?links .
  ?game wdt:P178 ?developer .
  ?game wdt:P123 ?publisher .
  ?game wdt:P577 ?date .
} ORDER BY DESC(?links) LIMIT 400
"""
    rows = client.sparql(query)
    ids = [qid_of(row["game"]["value"]) for row in rows]
    links = {qid_of(row["game"]["value"]): int(row["links"]["value"]) for row in rows}
    entities = client.entities(ids)

    refs: set[str] = set()
    parsed = []
    for qid in ids:
        entity = entities.get(qid, {})
        developers = claim_ids(entity, "P178")
        publishers = claim_ids(entity, "P123")
        platforms = claim_ids(entity, "P400")
        dates = claim_times(entity, "P577")
        refs.update(developers)
        refs.update(publishers)
        refs.update(platforms)
        parsed.append(
            {
                "qid": qid,
                "label_ar": entity.get("labels", {}).get("ar", {}).get("value"),
                "label_en": entity.get("labels", {}).get("en", {}).get("value"),
                "developers": developers,
                "publishers": publishers,
                "platforms": platforms,
                "dates": dates,
                "links": links.get(qid, 0),
            }
        )
    ref_entities = client.entities(refs)

    def ref_label(qid: str) -> str | None:
        return label_of(ref_entities.get(qid, {}))

    games = []
    for item in parsed:
        if len(item["developers"]) != 1 or len(item["publishers"]) != 1:
            continue
        if not item["dates"]:
            continue
        target_platforms = sorted(set(item["platforms"]) & set(TARGET_PLATFORMS))
        if not target_platforms:
            continue
        title_ar = item["label_ar"]
        title_en = item["label_en"]
        if not (title_ar or title_en):
            continue
        developer_label = ref_label(item["developers"][0])
        publisher_label = ref_label(item["publishers"][0])
        if not developer_label or not publisher_label:
            continue
        year = min(item["dates"])[:4]
        games.append(
            {
                "qid": item["qid"],
                "title_ar": title_ar,
                "title_en": title_en,
                "developer_qid": item["developers"][0],
                "developer_label": developer_label,
                "publisher_qid": item["publishers"][0],
                "publisher_label": publisher_label,
                "first_release_date": min(item["dates"]),
                "first_release_year": year,
                "platforms": [TARGET_PLATFORMS[qid] for qid in target_platforms],
                "sitelinks": item["links"],
                "source_url": f"https://www.wikidata.org/wiki/{item['qid']}",
                "claims": {"developer": "P178", "publisher": "P123", "release": "P577", "platform": "P400"},
            }
        )
    games.sort(key=lambda item: (-item["sitelinks"], item["qid"]))
    selected = games[:130]
    payload = {
        "snapshot_version": 1,
        "generator": "harvest_fact_snapshots.py",
        "retrieved_at": now_iso(),
        "source": {
            "name": "Wikidata",
            "url": "https://www.wikidata.org/",
            "sparql_endpoint": SPARQL_ENDPOINT,
            "license": "CC0 1.0 (Wikidata structured data)",
            "access": "public SPARQL + wbgetentities API",
        },
        "filters": {
            "single_developer": True,
            "single_publisher": True,
            "target_platforms": TARGET_PLATFORMS,
            "note": "IGDB was checked and returned 401 without credentials; it is not used.",
        },
        "games": selected,
    }
    path = write_snapshot("videogames.json", payload)
    return {"path": str(path), "candidates": len(games), "records": len(selected), "igdb": "401 unavailable"}


def harvest_nicknames(client: Client) -> dict:
    query = """
SELECT ?player ?playerLabel ?playerEn ?nick ?country ?countryLabel ?position ?positionLabel ?links WHERE {
  ?player wdt:P106 wd:Q937857 .
  ?player wdt:P1449 ?nick .
  ?player wikibase:sitelinks ?links .
  OPTIONAL { ?player wdt:P27 ?country . }
  OPTIONAL { ?player wdt:P413 ?position . }
  OPTIONAL { ?player rdfs:label ?playerEn . FILTER(LANG(?playerEn) = "en") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ar,en". }
} ORDER BY DESC(?links) LIMIT 3000
"""
    rows = client.sparql(query)
    by_player: dict[str, dict] = {}
    for row in rows:
        qid = qid_of(row["player"]["value"])
        record = by_player.setdefault(
            qid,
            {
                "qid": qid,
                "label": row.get("playerLabel", {}).get("value"),
                "label_en": row.get("playerEn", {}).get("value"),
                "links": int(row["links"]["value"]),
                "nicknames": set(),
                "countries": {},
                "positions": {},
            },
        )
        record["nicknames"].add(row["nick"]["value"])
        if "country" in row:
            country_qid = qid_of(row["country"]["value"])
            record["countries"][country_qid] = row.get("countryLabel", {}).get("value") or country_qid
        if "position" in row:
            position_qid = qid_of(row["position"]["value"])
            record["positions"][position_qid] = row.get("positionLabel", {}).get("value") or position_qid

    nickname_owners: dict[str, set[str]] = {}
    for record in by_player.values():
        for nickname in record["nicknames"]:
            nickname_owners.setdefault(nickname.casefold().strip(), set()).add(record["qid"])

    def fold(value: str | None) -> str:
        if not value:
            return ""
        text = unicodedata.normalize("NFKD", value)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return text.casefold()

    def name_tokens(value: str | None) -> set[str]:
        text = fold(value)
        text = re.sub(r"[^\w\u0600-\u06ff]+", " ", text)
        return {token for token in text.split() if len(token) > 1}

    raw = []
    for record in by_player.values():
        if record["qid"] in BLOCKED_PLAYER_QIDS:
            continue
        if len(record["nicknames"]) != 1 or len(record["countries"]) != 1:
            continue
        nickname = next(iter(record["nicknames"])).strip()
        normalized_nick = fold(nickname)
        if len(nickname) < 3 or len(nickname) > 40:
            continue
        if any(character in nickname for character in "\"'«»\n\r\t"):
            continue
        if any(part in normalized_nick for part in BLOCKED_NICKNAME_PARTS):
            continue
        if not any(character.isalpha() for character in nickname):
            continue
        if len(nickname_owners.get(nickname.casefold().strip(), set())) != 1:
            continue
        raw.append(
            {
                "qid": record["qid"],
                "player_ar": record["label"],
                "player_en": record["label_en"],
                "nickname": nickname,
                "country_qid": next(iter(record["countries"])),
                "country_label": next(iter(record["countries"].values())),
                "positions": sorted(record["positions"].values()),
                "sitelinks": record["links"],
                "source_url": f"https://www.wikidata.org/wiki/{record['qid']}",
                "claims": {"nickname": "P1449", "country": "P27", "position": "P413"},
            }
        )
    raw.sort(key=lambda item: (-item["sitelinks"], item["qid"]))
    # نجلب الاسمين العربي والإنجليزي و membership club لكل مرشح. وجود نادٍ
    # واحد على الأقل يستبعد رياضيين من ألعاب أخرى أُضيفوا خطأً ككرة قدم.
    player_entities = client.entities([item["qid"] for item in raw])
    candidates = []
    for item in raw:
        entity = player_entities.get(item["qid"], {})
        if not claim_ids(entity, "P54"):
            continue
        player_ar = entity.get("labels", {}).get("ar", {}).get("value") or item["player_ar"]
        player_en = entity.get("labels", {}).get("en", {}).get("value") or item["player_en"]
        if not (player_ar or player_en):
            continue
        tokens = name_tokens(player_ar) | name_tokens(player_en)
        nickname_tokens = name_tokens(item["nickname"])
        if nickname_tokens and nickname_tokens <= tokens:
            continue
        if fold(item["nickname"]) in {fold(player_ar), fold(player_en)}:
            continue
        # لقب قصير يطابق بادئة/لاحقة اسم اللاعب غالبًا اختصار اسم لا لقبًا.
        folded_nickname = fold(item["nickname"]).replace(" ", "")
        if len(folded_nickname) >= 4 and any(
            folded_nickname in token or token in folded_nickname
            for token in tokens
            if len(token) >= 4
        ):
            continue
        # لغة واحدة فقط: خلط السكريبتين غالبًا اسم منسوخ لا لقب.
        scripts = {
            "arabic" if any("\u0600" <= ch <= "\u06ff" for ch in item["nickname"]) else None,
            "cyrillic" if any("\u0400" <= ch <= "\u04ff" for ch in item["nickname"]) else None,
            "latin" if any("a" <= ch.casefold() <= "z" for ch in item["nickname"]) else None,
        } - {None}
        if len(scripts) > 1:
            continue
        item["player_ar"] = player_ar
        item["player_en"] = player_en
        candidates.append(item)
        if len(candidates) >= 360:
            break
    selected = candidates[:360]
    # درجات الصعوبة: الأكثر شهرة 200، ثم 400، ثم 600 (مع بقاء الحد الأدنى للشهرة).
    for index, item in enumerate(selected):
        item["difficulty"] = 200 if index < 120 else 400 if index < 240 else 600
    payload = {
        "snapshot_version": 1,
        "generator": "harvest_fact_snapshots.py",
        "retrieved_at": now_iso(),
        "source": {
            "name": "Wikidata",
            "url": "https://www.wikidata.org/",
            "sparql_endpoint": SPARQL_ENDPOINT,
            "license": "CC0 1.0 (Wikidata structured data)",
            "access": "public SPARQL + wbgetentities API",
        },
        "filters": {
            "single_clean_nickname": True,
            "single_country": True,
            "unique_nickname_owner": True,
            "name_variant_rejected": True,
            "profanity_rejected": True,
            "note": "Nicknames are P1449 statements; name-like variants and shared nicknames are rejected.",
        },
        "players": selected,
    }
    path = write_snapshot("football_nicknames.json", payload)
    return {"path": str(path), "candidates": len(candidates), "records": len(selected)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Harvest deterministic fact snapshots")
    parser.add_argument("--source", choices=("all", "quran", "technology", "videogames", "nicknames"), default="all")
    args = parser.parse_args()
    client = Client()
    results = {}
    try:
        if args.source in ("all", "quran"):
            results["quran"] = harvest_quran(client)
        if args.source in ("all", "technology"):
            results["technology"] = harvest_technology(client)
        if args.source in ("all", "videogames"):
            results["videogames"] = harvest_videogames(client)
        if args.source in ("all", "nicknames"):
            results["nicknames"] = harvest_nicknames(client)
    finally:
        client.http.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
