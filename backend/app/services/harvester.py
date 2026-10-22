"""خط حصاد خارجي آمن: RestCountries + Wikidata.

المبادئ:
- لا شبكة أثناء توليد البنك المحلي؛ الحصاد اختياري ويُشغَّل يدويًا أو بمهمة.
- كل استجابة تُخزَّن في `.seed_cache/` وتُتحقق قبل الاستخدام.
- فشل مصدر خارجي لا يمسّ الصفوف الموجودة ولا يوقف المباريات.
- Wikidata تُحفظ وقائعها بحالة `needs_review` ولا تُحوَّل لأسئلة تلقائيًا،
  لأن تسمياتها العربية والعلاقات قد تكون ناقصة.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from ..config import Settings
from ..db import connect, init_db, transaction
from ..utils.text import fingerprint

RESTCOUNTRIES_URL = "https://restcountries.com/v3.1/all"
RESTCOUNTRIES_FIELDS = (
    "cca2,name,translations,capital,region,subregion,population,borders,currencies,unMember"
)
WIKIDATA_URL = "https://query.wikidata.org/sparql"
USER_AGENT = (
    "SeenJeemTrivia/2.0 (local Arabic trivia game; +https://localhost) "
    "httpx/0.27"
)
CACHE_TTL = timedelta(hours=24)
CACHE_DIR_NAME = ".seed_cache"
MAX_WIKIDATA_PAGES = 2
WIKIDATA_PAGE_SIZE = 50

WIKIDATA_QUERY = """
SELECT ?player ?playerLabel ?countryLabel WHERE {
  ?player wdt:P106 wd:Q937857 .
  ?player wdt:P27 ?country .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ar,en". }
}
ORDER BY ?player
LIMIT {limit} OFFSET {offset}
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def harvested_flag_difficulty(population: int | None) -> int:
    """درجة علم دولة من الذيل الطويل (خارج المئة المنسّقة للجمهور).

    الإشارة الوحيدة غير الملفّقة للشهرة هي عدد السكان من سجل API المتحقق:
    دول كبيرة (20M+) تُعامل كمعروفة لعموم اللاعبين، والمتوسطة (1M+) وسط،
    والصغيرة (<1M) صعبة فعلًا كتعرّف على علم. السجل بلا سكان يُبقي السلوك
    القديم (200) بدل ادّعاء صعوبة بلا دليل.
    """
    if isinstance(population, int) and not isinstance(population, bool):
        if population >= 20_000_000:
            return 200
        if population >= 1_000_000:
            return 400
        return 600
    return 200


def cache_dir(settings: Settings) -> Path:
    # الكاش يخصّ التطبيق لا قاعدة البيانات، حتى لا يُكتب في جذر القرص
    # عندما تكون قاعدة الاختبار في مجلد مؤقت.
    path = Path(__file__).resolve().parents[2] / CACHE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(settings: Settings, name: str) -> Path:
    return cache_dir(settings) / f"{name}.json"


def _read_cache(settings: Settings, name: str, *, max_age: timedelta = CACHE_TTL) -> dict | None:
    path = _cache_path(settings, name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(data["fetched_at"])
        if datetime.now(timezone.utc) - fetched > max_age:
            return None
        return data
    except (OSError, ValueError, KeyError):
        return None


def _write_cache(settings: Settings, name: str, payload: object) -> None:
    path = _cache_path(settings, name)
    temp = path.with_suffix(".tmp")
    try:
        temp.write_text(
            json.dumps({"fetched_at": _utc_now(), "payload": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
        temp.replace(path)
    except OSError:
        # التخزين المؤقت تحسين لا شرط؛ نواصل بدونه.
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


async def _get_json(
    url: str,
    *,
    params: dict,
    timeout: float = 20.0,
    retries: int = 2,
    headers: dict[str, str] | None = None,
) -> tuple[object | None, str]:
    """GET مع مهلة وإعادة محاولة محدودة؛ يعيد (payload, status)."""
    delay = 0.5
    last = "unreachable"
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, **(headers or {})},
        follow_redirects=True,
    ) as client:
        for attempt in range(retries + 1):
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    return response.json(), "ok"
                if response.status_code == 429:
                    last = "rate_limited"
                elif response.status_code >= 500:
                    last = f"server_{response.status_code}"
                else:
                    return None, f"http_{response.status_code}"
            except (httpx.TimeoutException, httpx.TransportError):
                last = "unreachable"
            except ValueError:
                return None, "malformed_json"
            if attempt < retries:
                await asyncio.sleep(delay)
                delay *= 2
    return None, last


def validate_country_record(item: object) -> dict | None:
    """يقبل فقط سجلًا كاملًا بالمعرّف والاسم العربي والانتماء للأمم المتحدة."""
    if not isinstance(item, dict):
        return None
    code = item.get("cca2")
    if not isinstance(code, str) or len(code) != 2 or not code.isalpha():
        return None
    name = item.get("name")
    common = name.get("common") if isinstance(name, dict) else None
    if not isinstance(common, str) or not common.strip():
        return None
    translations = item.get("translations")
    arabic = None
    if isinstance(translations, dict):
        ara = translations.get("ara")
        if isinstance(ara, dict):
            arabic = ara.get("common")
    if not isinstance(arabic, str) or not arabic.strip():
        return None
    capital = item.get("capital")
    region = item.get("region")
    return {
        "code": code.lower(),
        "name_common": common.strip(),
        "name_ar": arabic.strip(),
        "capital": capital[0] if isinstance(capital, list) and capital and isinstance(capital[0], str) else None,
        "region": region.strip() if isinstance(region, str) else None,
        "subregion": item.get("subregion") if isinstance(item.get("subregion"), str) else None,
        "population": item.get("population") if isinstance(item.get("population"), int) else None,
        "borders": item.get("borders") if isinstance(item.get("borders"), list) else [],
        "un_member": bool(item.get("unMember")),
        "currencies": item.get("currencies") if isinstance(item.get("currencies"), dict) else {},
    }


async def harvest_restcountries(settings: Settings, *, force: bool = False) -> dict:
    cached = None if force else _read_cache(settings, "restcountries")
    if cached:
        payload = cached["payload"]
        status = "restcountries:cached"
    else:
        payload, status = await _get_json(
            RESTCOUNTRIES_URL, params={"fields": RESTCOUNTRIES_FIELDS}
        )
        countries, shape = _country_payload(payload)
        if countries is None:
            # لا نُخزّن استجابة فاشلة في الكاش، ونُبلّغ سبب التعطّل بدقة.
            reason = status if payload is None else shape
            return {
                "source": "restcountries",
                "status": f"restcountries:{reason}",
                "facts": 0,
                "questions": 0,
                "detail": "endpoint returned no usable country list",
            }
        _write_cache(settings, "restcountries", countries)
        status = "restcountries:ok"
    countries, shape = _country_payload(payload)
    if countries is None:
        return {"source": "restcountries", "status": f"restcountries:{shape}", "facts": 0, "questions": 0}
    records = [record for record in (validate_country_record(item) for item in countries) if record]
    if len(records) < 50:
        return {"source": "restcountries", "status": "restcountries:insufficient", "facts": 0, "questions": 0}

    facts = 0
    questions = 0
    async with transaction(settings) as db:
        cursor = await db.execute("SELECT id FROM categories WHERE slug = 'flags'")
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return {"source": "restcountries", "status": "restcountries:no_categories", "facts": 0, "questions": 0}
        flags_category_id = int(row["id"])
        for record in records:
            group = f"country:{record['code']}"
            await db.execute(
                """
                INSERT INTO fact_records(
                    fact_group_id, fact_type, source_name, source_entity_id,
                    source_url, verification_status, payload_json, content_version
                ) VALUES (?, 'country', 'RestCountries v3.1', ?, ?, 'verified_api', ?, 1)
                ON CONFLICT(fact_group_id, fact_type, source_name) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    verification_status = excluded.verification_status,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                """,
                (
                    group,
                    record["code"],
                    f"https://restcountries.com/v3.1/alpha/{record['code']}",
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            facts += 1
            question = "طالع هالعلم عدل… علم أي دولة هذا؟"
            fp = fingerprint("flags", question, record["name_ar"], record["code"])
            deck = zlib.crc32(fp.encode("utf-8")) % 1_000_000
            cursor = await db.execute(
                """
                INSERT INTO questions(
                    category_id, difficulty, question_type, question_text, flag_code,
                    payload_json, answer_text, tolerance, explanation, source_name,
                    source_url, source_checked_at, content_origin, fingerprint,
                    is_active, is_reserved_backup, fact_group_id, source_entity_id,
                    verification_status, content_version, times_played,
                    last_played_match_id, deck_position
                ) VALUES (?, ?, 'flag', ?, ?, NULL, ?, ?, ?, 'RestCountries v3.1',
                          ?, ?, 'api_sourced', ?, 1, 0, ?, ?, 'verified_api', 1, 0, NULL, ?)
                ON CONFLICT(fingerprint) DO NOTHING
                """,
            (
                flags_category_id,
                harvested_flag_difficulty(record["population"]),
                question,
                record["code"],
                    record["name_ar"],
                    f"{record['name_ar']}، {record['code'].upper()}",
                    f"اسم الدولة بالعربية: {record['name_ar']} ({record['name_common']}).",
                    f"https://restcountries.com/v3.1/alpha/{record['code']}",
                    _utc_now()[:10],
                    fp,
                    group,
                    record["code"],
                    deck,
                ),
            )
            if cursor.rowcount:
                questions += 1
            await cursor.close()
        await db.execute(
            """
            INSERT INTO harvester_cursors(
                source_name, category_slug, cursor, last_synced_at, total_harvested
            ) VALUES ('restcountries', 'flags', ?, ?, ?)
            ON CONFLICT(source_name, category_slug) DO UPDATE SET
                cursor = excluded.cursor,
                last_synced_at = excluded.last_synced_at,
                total_harvested = harvester_cursors.total_harvested + ?
            """,
            (str(len(records)), _utc_now(), facts, questions),
        )
    return {
        "source": "restcountries",
        "status": status,
        "facts": facts,
        "questions": questions,
        "records": len(records),
    }


def _country_payload(payload: object) -> tuple[list | None, str]:
    """يدعم غلاف v5 `{success, data}` وقائمة v3.1، ويرفض رسائل الإهمال."""
    if isinstance(payload, list):
        return payload, "ok"
    if isinstance(payload, dict):
        if payload.get("success") is False:
            errors = payload.get("errors")
            first = errors[0].get("message") if isinstance(errors, list) and errors and isinstance(errors[0], dict) else ""
            if "deprecat" in first.lower():
                return None, "deprecated"
            return None, "api_error"
        data = payload.get("data")
        if isinstance(data, list):
            return data, "ok"
        # بعض الإصدارات ترجع قاموس دول مفهرسًا بالرمز.
        if isinstance(data, dict) and data:
            return [value for value in data.values() if isinstance(value, dict)], "ok"
    return None, "malformed"


def _validate_wikidata(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    bindings = results.get("bindings") if isinstance(results, dict) else None
    if not isinstance(bindings, list):
        return []
    players = []
    for item in bindings:
        if not isinstance(item, dict):
            continue
        player = item.get("player", {}).get("value")
        label = item.get("playerLabel", {}).get("value")
        country = item.get("countryLabel", {}).get("value")
        if not isinstance(player, str) or not player.startswith("http"):
            continue
        if not isinstance(label, str) or not label.strip():
            continue
        players.append({"entity": player, "label": label.strip(), "country": country})
    return players


async def harvest_wikidata(settings: Settings, *, force: bool = False) -> dict:
    """يحصد صفحات محدودة ويحفظها كوقائع تحتاج مراجعة بشرية."""
    total_facts = 0
    status = "wikidata:ok"
    seen_entities: set[str] = set()
    async with connect(settings) as db:
        cursor = await db.execute(
            "SELECT cursor FROM harvester_cursors WHERE source_name = 'wikidata' AND category_slug = 'football'"
        )
        row = await cursor.fetchone()
        await cursor.close()
    offset = int(row["cursor"]) if row and str(row["cursor"]).isdigit() else 0

    for page in range(MAX_WIKIDATA_PAGES):
        cache_name = f"wikidata_{offset}_{WIKIDATA_PAGE_SIZE}"
        cached = None if force else _read_cache(settings, cache_name)
        if cached:
            payload = cached["payload"]
            page_status = "cached"
        else:
            # لا نستخدم str.format لأن أقواس SPARQL نفسها أقواس تنسيق.
            query = WIKIDATA_QUERY.replace("{limit}", str(WIKIDATA_PAGE_SIZE)).replace(
                "{offset}", str(offset)
            )
            payload, page_status = await _get_json(
                WIKIDATA_URL,
                params={"format": "json", "query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=30.0,
            )
            if payload is not None:
                _write_cache(settings, cache_name, payload)
        players = _validate_wikidata(payload) if payload is not None else []
        if not players:
            status = "wikidata:partial" if total_facts else f"wikidata:{page_status}"
            break
        async with transaction(settings) as db:
            for player in players:
                if player["entity"] in seen_entities:
                    continue
                seen_entities.add(player["entity"])
                entity_id = player["entity"].rstrip("/").rsplit("/", 1)[-1]
                await db.execute(
                    """
                    INSERT INTO fact_records(
                        fact_group_id, fact_type, source_name, source_entity_id,
                        source_url, verification_status, payload_json, content_version
                    ) VALUES (?, 'player_review', 'Wikidata SPARQL', ?, ?, 'needs_review', ?, 1)
                    ON CONFLICT(fact_group_id, fact_type, source_name) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                    """,
                    (
                        f"wikidata:player:{entity_id}",
                        entity_id,
                        player["entity"],
                        json.dumps(player, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
                total_facts += 1
            offset += len(players)
            await db.execute(
                """
                INSERT INTO harvester_cursors(
                    source_name, category_slug, cursor, last_synced_at, total_harvested
                ) VALUES ('wikidata', 'football', ?, ?, ?)
                ON CONFLICT(source_name, category_slug) DO UPDATE SET
                    cursor = excluded.cursor,
                    last_synced_at = excluded.last_synced_at,
                    total_harvested = harvester_cursors.total_harvested + ?
                """,
                (str(offset), _utc_now(), total_facts, total_facts),
            )
    return {"source": "wikidata", "status": status, "facts": total_facts, "questions": 0}


async def run_harvest(settings: Settings, *, force: bool = False) -> dict:
    await init_db(settings)
    results = []
    # تسلسل مقصود: شبكة واحدة في كل مرة، ومهلات محدودة.
    for handler in (harvest_restcountries, harvest_wikidata):
        try:
            results.append(await handler(settings, force=force))
        except Exception as exc:  # noqa: BLE001 - الفشل الخارجي لا يوقف الآخر
            results.append({"source": handler.__name__, "status": f"error:{type(exc).__name__}", "facts": 0, "questions": 0})
    def _healthy(item: dict) -> bool:
        status = str(item.get("status", ""))
        return status.endswith((":ok", ":cached")) or status in {"ok", "cached"}

    failed = [item for item in results if not _healthy(item)]
    ok = [item for item in results if _healthy(item)]
    status = "partial" if failed and ok else "failed" if failed else "succeeded"
    return {
        "status": status,
        "sources": results,
        "facts": sum(int(item.get("facts", 0)) for item in results),
        "questions": sum(int(item.get("questions", 0)) for item in results),
        "finished_at": _utc_now(),
    }
