"""Replace superseded question wording with the current bank, safely and reversibly.

Dry run (read-only): python scripts/supersede_content.py --database data/seenjeem.db
Apply: add --apply. A consistent SQLite backup is mandatory before any write.

What it does on --apply:
1. Runs the idempotent seeder so every current-bank question exists (new rows only).
2. Deactivates (never deletes) active rows whose fingerprints are no longer part of
   the current question bank, so stale wording leaves rotation while history,
   matches and usage ledgers stay intact.
3. Rows allocated to active matches are kept by default. `--include-match-allocated`
   retires them too; deactivation never deletes a row, and an in-flight tile still
   resolves because resolution reads the question by id without an `is_active` filter.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import load_settings
from app.db import connect, init_db, transaction
from app.services.content import build_question_bank
from app.services.seed import seed_database
from app.utils.text import fingerprint
from scripts.publish_football import sqlite_backup


def current_fingerprints() -> set[str]:
    return {
        fingerprint(row["category"], row["question"], row["answer"], row.get("flag_code"))
        for row in build_question_bank()
    }


async def inspect(settings, include_match_allocated: bool = False) -> dict:
    bank = current_fingerprints()
    async with connect(settings) as db:
        cursor = await db.execute(
            """
            SELECT q.id, q.fingerprint, c.slug
            FROM questions q JOIN categories c ON c.id = q.category_id
            WHERE q.is_active = 1
            """
        )
        rows = await cursor.fetchall()
        await cursor.close()
        cursor = await db.execute(
            """
            SELECT DISTINCT mt.question_id
            FROM match_tiles mt JOIN matches m ON m.id = mt.match_id
            WHERE m.status = 'active'
            """
        )
        protected = {int(row["question_id"]) for row in await cursor.fetchall()}
        await cursor.close()
    superseded = [row for row in rows if row["fingerprint"] not in bank]
    deactivatable = [
        row
        for row in superseded
        if include_match_allocated or int(row["id"]) not in protected
    ]
    return {
        "active_total": len(rows),
        "current_bank_size": len(bank),
        "superseded": len(superseded),
        "protected_by_active_matches": len(superseded) - len(deactivatable),
        "deactivatable": len(deactivatable),
        "by_category": dict(sorted(Counter(row["slug"] for row in deactivatable).items())),
        "ids": [int(row["id"]) for row in deactivatable],
    }


async def run(database: Path, apply: bool, include_match_allocated: bool = False) -> dict:
    settings = replace(load_settings(), database_path=database.resolve())
    report = {"mode": "apply" if apply else "dry_run", "database": str(database.resolve())}
    if apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = database.with_name(database.stem + f".pre-supersede-{stamp}.db")
        sqlite_backup(database, backup)
        report["backup"] = str(backup)
        seed = await seed_database(settings, deterministic_seed=None)
        report["seed"] = {
            key: seed[key] for key in ("inserted", "updated", "skipped", "total_active")
        }
    plan = await inspect(settings, include_match_allocated)
    report["plan"] = {key: value for key, value in plan.items() if key != "ids"}
    if apply and plan["ids"]:
        async with transaction(settings) as db:
            await db.executemany(
                "UPDATE questions SET is_active = 0 WHERE id = ?",
                [(question_id,) for question_id in plan["ids"]],
            )
        report["deactivated"] = len(plan["ids"])
        after = await inspect(settings, include_match_allocated)
        report["remaining_superseded_active"] = after["superseded"]
        async with connect(settings) as db:
            cursor = await db.execute("PRAGMA integrity_check")
            report["integrity_check"] = (await cursor.fetchone())[0]
            await cursor.close()
            cursor = await db.execute("PRAGMA foreign_key_check")
            report["foreign_key_violations"] = [tuple(r) for r in await cursor.fetchall()]
            await cursor.close()
            cursor = await db.execute(
                "SELECT COUNT(*) AS n FROM questions WHERE is_active = 1"
            )
            report["active_after"] = int((await cursor.fetchone())["n"])
            await cursor.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--include-match-allocated",
        action="store_true",
        help="also retire superseded rows held by active matches (never deletes rows)",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(run(args.database, args.apply, args.include_match_allocated)),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
