from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from app.data import matchstick
from app.schema import SCHEMA_VERSION
from app.services.content import (
    API_CATEGORIES,
    CATEGORY_SLUGS,
    DIFFICULTIES,
    build_question_bank,
    inventory_report,
)

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "backend" / "data" / "seenjeem.db"
REPORT_DIR = ROOT / "backend" / "data" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

NEW_CATEGORIES = ("quran", "nicknames", "technology", "videogames", "matchstick")


def live_snapshot() -> dict:
    db = sqlite3.connect(LIVE)
    db.row_factory = sqlite3.Row
    try:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_issues = [dict(row) for row in db.execute("PRAGMA foreign_key_check").fetchall()]
        categories = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        questions = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        facts = db.execute("SELECT COUNT(*) FROM fact_records").fetchone()[0]
        matches = db.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        fingerprints = db.execute("SELECT COUNT(DISTINCT fingerprint) FROM questions").fetchone()[0]
        null_license = db.execute(
            "SELECT COUNT(*) FROM questions WHERE source_license IS NULL"
        ).fetchone()[0]
        null_claim = db.execute(
            "SELECT COUNT(*) FROM questions WHERE source_claim IS NULL"
        ).fetchone()[0]
        cursor = db.execute(
            """
            SELECT c.slug, q.difficulty, COUNT(*) AS n
            FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE c.slug IN ('quran','nicknames','technology','videogames','matchstick')
            GROUP BY c.slug, q.difficulty ORDER BY c.slug, q.difficulty
            """
        )
        new_buckets = {
            f"{row['slug']}:{row['difficulty']}": int(row["n"])
            for row in cursor.fetchall()
        }
        cursor = db.execute(
            """
            SELECT c.slug, q.source_name, q.source_url, q.source_entity_id,
                   q.source_checked_at, q.source_license, q.source_claim
            FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE c.slug IN ('quran','nicknames','technology','videogames','matchstick')
            """
        )
        new_rows = [dict(row) for row in cursor.fetchall()]
        return {
            "path": str(LIVE),
            "user_version": int(version),
            "integrity_check": integrity,
            "foreign_key_issues": foreign_key_issues,
            "categories": int(categories),
            "questions": int(questions),
            "fact_records": int(facts),
            "matches": int(matches),
            "distinct_fingerprints": int(fingerprints),
            "new_bucket_counts": new_buckets,
            "new_question_rows": len(new_rows),
            "new_question_rows_missing_license": sum(1 for row in new_rows if not row["source_license"]),
            "new_question_rows_missing_claim": sum(1 for row in new_rows if not row["source_claim"]),
            "legacy_question_rows_without_license": int(null_license),
            "legacy_question_rows_without_claim": int(null_claim),
        }
    finally:
        db.close()


def main() -> None:
    started = time.time()
    rows = build_question_bank()
    inventory = inventory_report(rows)
    new_rows = [row for row in rows if row["category"] in NEW_CATEGORIES]
    api_rows = [row for row in new_rows if row["category"] in API_CATEGORIES]
    matchstick_rows = [row for row in new_rows if row["category"] == "matchstick"]

    api_missing = [
        row["fact_group_id"]
        for row in api_rows
        if not all(
            (
                row.get("source_name"),
                row.get("source_url"),
                row.get("source_entity_id"),
                row.get("source_checked_at"),
                row.get("source_license"),
                row.get("source_claim"),
            )
        )
    ]
    matchstick_missing = [
        row["fact_group_id"]
        for row in matchstick_rows
        if not all(
            (
                row.get("source_name"),
                row.get("source_url"),
                row.get("source_checked_at"),
                row.get("source_license"),
                row.get("source_claim"),
                (row.get("payload") or {}).get("kind") == "matchstick",
            )
        )
    ]

    puzzles = matchstick.generate_puzzles()
    strict_failures = []
    segment_conservation_failures = []
    for puzzle in puzzles:
        issues = matchstick.validate_puzzle(puzzle, strict=True)
        if issues:
            strict_failures.append({"equation": puzzle.get("equation"), "issues": issues})
        if sum(len(part) for part in puzzle["start"]) != sum(len(part) for part in puzzle["end"]):
            segment_conservation_failures.append(puzzle.get("equation"))

    per_difficulty = Counter(int(puzzle["difficulty"]) for puzzle in puzzles)
    new_buckets = {
        key: count
        for key, count in inventory["buckets"].items()
        if key.split(":", 1)[0] in NEW_CATEGORIES
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "bank": {
            "total": inventory["total"],
            "categories": len(CATEGORY_SLUGS),
            "buckets": len(inventory["buckets"]),
            "new_categories": {
                slug: inventory["categories"][slug] for slug in NEW_CATEGORIES
            },
            "new_buckets": dict(sorted(new_buckets.items())),
            "all_new_buckets_are_120": all(count == 120 for count in new_buckets.values())
            and len(new_buckets) == len(NEW_CATEGORIES) * len(DIFFICULTIES),
            "origins": inventory["origins"],
            "existing_buckets_below_content_floor": inventory["buckets_below_content_floor"],
            "existing_buckets_below_capacity_gate": inventory["buckets_below_capacity_gate"],
            "meets_content_floor": inventory["meets_content_floor"],
            "meets_100_match_capacity": inventory["meets_100_match_capacity"],
        },
        "matchstick": {
            "total": len(puzzles),
            "per_difficulty": {str(key): value for key, value in sorted(per_difficulty.items())},
            "strict_validation_passed": len(puzzles) - len(strict_failures),
            "strict_validation_failures": strict_failures,
            "segment_conservation_failures": segment_conservation_failures,
            "unique_equations": len({puzzle["equation"] for puzzle in puzzles}),
        },
        "provenance": {
            "new_question_rows": len(new_rows),
            "api_question_rows": len(api_rows),
            "matchstick_question_rows": len(matchstick_rows),
            "api_rows_missing_fields": api_missing,
            "matchstick_rows_missing_fields": matchstick_missing,
        },
        "live_db": live_snapshot(),
        "elapsed_seconds": round(time.time() - started, 2),
    }

    json_path = REPORT_DIR / "seenjeem-expansion-report.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown = f"""# تقرير توسعة SEEN JEEM

- تاريخ التوليد: {report['generated_at']}
- إصدار المخطط: {report['schema_version']}
- إجمالي بنك الأسئلة: {report['bank']['total']}
- الفئات: {report['bank']['categories']} — الدلاء: {report['bank']['buckets']}

## الدلاء الجديدة

| الفئة | 200 | 400 | 600 |
|---|---:|---:|---:|
| quran | {new_buckets.get('quran:200', 0)} | {new_buckets.get('quran:400', 0)} | {new_buckets.get('quran:600', 0)} |
| nicknames | {new_buckets.get('nicknames:200', 0)} | {new_buckets.get('nicknames:400', 0)} | {new_buckets.get('nicknames:600', 0)} |
| technology | {new_buckets.get('technology:200', 0)} | {new_buckets.get('technology:400', 0)} | {new_buckets.get('technology:600', 0)} |
| videogames | {new_buckets.get('videogames:200', 0)} | {new_buckets.get('videogames:400', 0)} | {new_buckets.get('videogames:600', 0)} |
| matchstick | {new_buckets.get('matchstick:200', 0)} | {new_buckets.get('matchstick:400', 0)} | {new_buckets.get('matchstick:600', 0)} |

## التحقق الصارم من الأعواد

- الإجمالي: {report['matchstick']['total']}
- نجح التحقق الصارم: {report['matchstick']['strict_validation_passed']}
- فشل: {len(strict_failures)}
- فشل حفظ القطع: {len(segment_conservation_failures)}
- معادلات فريدة: {report['matchstick']['unique_equations']}

## المصدر

- أسئلة API: {report['provenance']['api_question_rows']}، حقول ناقصة: {len(api_missing)}
- أسئلة الأعواد: {report['provenance']['matchstick_question_rows']}، حقول ناقصة: {len(matchstick_missing)}

## قاعدة البيانات الحية

- الإصدار: {report['live_db']['user_version']}
- الفئات: {report['live_db']['categories']}
- الأسئلة: {report['live_db']['questions']}
- الوقائع: {report['live_db']['fact_records']}
- المباريات: {report['live_db']['matches']}
- بصمات فريدة: {report['live_db']['distinct_fingerprints']}
- سلامة SQLite: {report['live_db']['integrity_check']}
- انتهاكات المفاتيح الأجنبية: {len(report['live_db']['foreign_key_issues'])}
- صفوف جديدة بلا ترخيص: {report['live_db']['new_question_rows_missing_license']}
- صفوف قديمة بلا ترخيص (محفوظة كما هي): {report['live_db']['legacy_question_rows_without_license']}

## القيود المعلنة

- {len(inventory['buckets_below_content_floor'])} دلوًا قديمًا ما زالت تحت حد 120 سؤالًا؛ لم تُضخّم ولم تُحذف.
- {report['live_db']['legacy_question_rows_without_license']} صف سؤال قديم محفوظ بلا ترخيص/ادعاء لأن ترخيصه الأصلي غير معروف؛ لم يُختلق.
- ألعاب الفيديو تعتمد على لقطة Wikidata لأن IGDB يتطلب بيانات اعتماد غير متاحة.
"""
    markdown_path = REPORT_DIR / "seenjeem-expansion-report.md"
    markdown_path.write_text(markdown, encoding="utf-8")

    print(json.dumps({
        "json": str(json_path),
        "markdown": str(markdown_path),
        "bank_total": report["bank"]["total"],
        "new_buckets_all_120": report["bank"]["all_new_buckets_are_120"],
        "matchstick_total": report["matchstick"]["total"],
        "matchstick_strict_passed": report["matchstick"]["strict_validation_passed"],
        "matchstick_failures": len(strict_failures),
        "api_missing": len(api_missing),
        "matchstick_missing": len(matchstick_missing),
        "live": report["live_db"],
        "elapsed_seconds": report["elapsed_seconds"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
