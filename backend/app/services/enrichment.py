"""تخصيب اختياري من RestCountries، لا يعتمد عليه البنك ولا الاختبارات.

أي فشل شبكي أو 429 أو بيانات مشوّهة يرجع حالة تشخيصية فقط، ولا يرمي استثناءً
يوقف الزرع. لا نكتب أي بيت مجهول المصدر إلى قاعدة البيانات.
"""

from __future__ import annotations

import asyncio

import httpx

URL = "https://restcountries.com/v3.1/all"
PARAMS = {"fields": "cca2,name,capital,region,currencies"}

def _records_from_payload(data: object) -> dict[str, dict]:
    """Keep only validated code/name/capital records; never invent fields."""
    records: dict[str, dict] = {}
    if not isinstance(data, list):
        return records
    for item in data:
        if not isinstance(item, dict):
            continue
        code = item.get("cca2")
        name = item.get("name")
        capital = item.get("capital")
        if not isinstance(code, str) or len(code) != 2 or not code.isalpha():
            continue
        if isinstance(name, dict):
            name = name.get("common") or name.get("official")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(capital, list) or not capital or not isinstance(capital[0], str):
            continue
        records[code.lower()] = {
            "name": name.strip(),
            "capital": capital[0].strip(),
            "region": str(item.get("region") or "").strip(),
        }
    return records


async def enrich_countries(*, timeout: float = 6.0, retries: int = 2) -> dict:
    delay = 0.4
    last_error = "offline"
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": "seenjeem-trivia/1.0 (local seed enrichment)"},
        follow_redirects=True,
    ) as client:
        for attempt in range(retries + 1):
            try:
                response = await client.get(URL, params=PARAMS)
                if response.status_code == 429:
                    last_error = "restcountries:rate_limited"
                elif response.status_code >= 500:
                    last_error = f"restcountries:server_{response.status_code}"
                elif response.status_code != 200:
                    last_error = f"restcountries:http_{response.status_code}"
                else:
                    data = response.json()
                    records = _records_from_payload(data)
                    if not records:
                        last_error = "restcountries:malformed"
                    elif len(records) < 50:
                        last_error = "restcountries:insufficient"
                    else:
                        return {
                            "status": "restcountries:ok",
                            "countries": len(records),
                            "records": records,
                        }
            except (httpx.TimeoutException, httpx.TransportError, ValueError):
                last_error = "restcountries:unreachable"
            if attempt < retries:
                await asyncio.sleep(delay)
                delay *= 2
    return {"status": last_error, "countries": 0}
