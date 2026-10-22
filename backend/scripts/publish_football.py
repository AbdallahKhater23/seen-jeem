"""Review first, then explicitly publish a verified editorial bank.

Dry run (read-only): python scripts/publish_football.py --database data/seenjeem.db
Apply: add --apply --verified-only. A consistent SQLite backup is mandatory.
Existing questions, matches, histories and allocated difficulties are immutable.
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
from app.db import init_db
from app.services.football_content import publish_candidates, validate_candidate


def sqlite_backup(source: Path, destination: Path) -> None:
    if destination.exists() or source.resolve() == destination.resolve():
        raise ValueError('Backup destination must be a new, distinct file')
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(destination)) as target:
            src.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed')


async def main():
    from app.data.football_curated import FOOTBALL_CURATED
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--verified-only', action='store_true')
    args = parser.parse_args()
    for row in FOOTBALL_CURATED:
        validate_candidate(row)
    counts = Counter(f"{r['category']}:{r['difficulty']}" for r in FOOTBALL_CURATED)
    report = {'mode': 'apply' if args.apply else 'dry_run', 'candidates': len(FOOTBALL_CURATED),
        'unique_facts': len({r['fact_id'] for r in FOOTBALL_CURATED}), 'buckets': dict(sorted(counts.items())),
        'verified_only': args.verified_only, 'missing_required_slots': {k: v for k, v in counts.items() if v < 3}}
    # Validate the target is a real existing repository database without startup migrations.
    with closing(sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('SELECT id,question_text FROM questions LIMIT 1').fetchone()
        report['before_counts'] = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            for table in ('questions', 'matches', 'match_tiles', 'user_question_history')}
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = args.database.with_name(args.database.stem + f'.pre-football-{stamp}.db')
        sqlite_backup(args.database, backup)
        settings = replace(load_settings(), database_path=args.database.resolve())
        await init_db(settings)
        report['publication'] = await publish_candidates(settings, FOOTBALL_CURATED, verified_only=args.verified_only)
        report['backup'] = str(backup)
        with closing(sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            report['integrity_check'] = db.execute('PRAGMA integrity_check').fetchone()[0]
            report['foreign_key_violations'] = db.execute('PRAGMA foreign_key_check').fetchall()
            report['after_counts'] = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                for table in report['before_counts']}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
