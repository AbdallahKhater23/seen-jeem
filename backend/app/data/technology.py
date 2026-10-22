"""أسئلة معلومات تقنية من لقطة شركات التقنية على Wikidata باللهجة الخليجية وأسلوب سين جيم.

كل شركة في `snapshots/technology_companies.json` تملك:
- بلدًا واحدًا (P17)
- مؤسسًا بشريًا واحدًا (P112) لتجنّب غموض الشركات متعددة المؤسسين
- سنة تأسيس واحدة (P571)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SNAPSHOT = Path(__file__).with_name("snapshots") / "technology_companies.json"
SOURCE_NAME = "Wikidata"
LICENSE = "CC0 1.0 (Wikidata structured data)"


@lru_cache(maxsize=1)
def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _companies() -> list[dict]:
    data = _snapshot()
    companies = list(data["companies"])
    companies.sort(key=lambda item: (-int(item.get("sitelinks", 0)), item["qid"]))
    return companies[:120]


def _company_name(company: dict) -> str:
    ar = company.get("label_ar")
    en = company.get("label_en")
    if ar and en and ar.casefold() != en.casefold():
        return f"{ar} ({en})"
    return ar or en or company["qid"]


def _founder_tolerance(company: dict) -> str:
    ar = company.get("founder_label_ar")
    en = company.get("founder_label_en")
    if ar and en and ar.casefold() != en.casefold():
        return f"{ar}، {en}"
    return ar or en or ""


def _country_tolerance(company: dict) -> str:
    ar = company.get("country_label_ar")
    en = company.get("country_label_en")
    if ar and en and ar.casefold() != en.casefold():
        return f"{ar}، {en}"
    return ar or en or ""


def build_rows() -> list[dict]:
    data = _snapshot()
    checked_at = str(data.get("retrieved_at", ""))[:10] or None
    rows: list[dict] = []
    for company in _companies():
        display = _company_name(company)
        country = company["country_label_ar"]
        founder = company["founder_label_ar"]
        year = str(company["inception_year"])
        common = {
            "category": "technology",
            "content_origin": "api_sourced",
            "verification_status": "verified_api",
            "source_name": SOURCE_NAME,
            "source_url": company["source_url"],
            "source_checked_at": checked_at,
            "source_license": LICENSE,
            "source_claim": "P17 country, P112 founder, P571 inception",
            "source_entity_id": company["qid"],
            "fact_group_id": f"tech:company:{company['qid']}",
            "fact_type": "tech_company",
            "fact_payload": {
                "qid": company["qid"],
                "label_ar": company.get("label_ar"),
                "label_en": company.get("label_en"),
                "founder_qid": company["founder_qid"],
                "founder_label_ar": founder,
                "founder_label_en": company.get("founder_label_en"),
                "country_qid": company["country_qid"],
                "country_label_ar": country,
                "country_label_en": company.get("country_label_en"),
                "inception_year": year,
                "sitelinks": company.get("sitelinks"),
                "claims": company.get("claims", {}),
                "source_url": company["source_url"],
            },
        }
        explanation = f"تأسست شركة {display} في {country} سنة {year} على يد {founder}."
        rows.append(
            {
                **common,
                "difficulty": 200,
                "question": f"شركة التقنية {display} اللي أسسها {founder}… انطلقت من أي دولة؟",
                "answer": country,
                "tolerance": _country_tolerance(company),
                "explanation": explanation,
            }
        )
        rows.append(
            {
                **common,
                "difficulty": 400,
                "question": f"شركة التقنية {display} اللي تأسست في {country} سنة {year}… منو مؤسسها؟",
                "answer": founder,
                "tolerance": _founder_tolerance(company),
                "explanation": explanation,
            }
        )
        rows.append(
            {
                **common,
                "difficulty": 600,
                "question": f"على يد {founder} في {country}… بأي سنة تأسست شركة التقنية {display}؟",
                "answer": year,
                "tolerance": year,
                "explanation": explanation,
            }
        )
    return rows
