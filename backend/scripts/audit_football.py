"""Read-only, reproducible football-bank audit. Never opens SQLite for writing.

Usage: python scripts/audit_football.py --database data/seenjeem.db --output ../reports/football-baseline.json
Era/template/subject findings are heuristics, not verified content metadata.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import unicodedata

FOOTBALL = ('football', 'ucl', 'worldcup', 'career', 'clubs', 'arab_ftbl', 'numbers', 'nicknames')


def normalize(value: str) -> str:
    value = unicodedata.normalize('NFKC', value or '').casefold()
    value = re.sub(r'[\u064b-\u065f\u0670\u0640]', '', value)
    value = value.translate(str.maketrans('أإآى٠١٢٣٤٥٦٧٨٩', 'اااي0123456789'))
    return ' '.join(re.sub(r'[^\w\s]', ' ', value).split())


def entropy(counts: Counter) -> float:
    total = sum(counts.values())
    return round(-sum((n / total) * math.log2(n / total) for n in counts.values()), 4) if total else 0.0


def duplicates(values: list[str]) -> dict:
    counts = Counter(v for v in values if v)
    repeated = {k: n for k, n in counts.items() if n > 1}
    return {'known': sum(counts.values()), 'distinct': len(counts), 'excess_rows': sum(n - 1 for n in repeated.values()),
            'rate': round(sum(n - 1 for n in repeated.values()) / len(values), 6) if values else 0,
            'top_repeated': Counter(repeated).most_common(12)}


def audit(database: Path) -> dict:
    # mode=ro is mandatory: auditing must never migrate, seed, or reserve questions.
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(r) for r in connection.execute('SELECT q.*, c.slug, c.name_ar FROM questions q JOIN categories c ON c.id=q.category_id WHERE q.is_active=1') if r['slug'] in FOOTBALL]
        schema = {r['name']: r['sql'] for r in connection.execute("SELECT name,sql FROM sqlite_master WHERE type IN ('table','index') AND sql IS NOT NULL")}
        foreign_keys = [tuple(r) for r in connection.execute('PRAGMA foreign_key_check')]
        version = connection.execute('PRAGMA user_version').fetchone()[0]
    summaries = {}
    for slug in FOOTBALL:
        bank = [r for r in rows if r['slug'] == slug]
        templates = Counter(' '.join(re.sub(r'\d+', '<number>', normalize(r['question_text'])).split()[:4]) for r in bank)
        eras = Counter()
        for row in bank:
            years = [int(y) for y in re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', row['question_text'])]
            year = years[0] if len(set(years)) == 1 else None
            eras['unknown' if year is None else 'classic' if year < 1990 else 'golden_era' if year <= 2005 else 'modern_peak' if year <= 2018 else 'contemporary'] += 1
        summaries[slug] = {'label': bank[0]['name_ar'] if bank else None, 'active': len(bank),
            'difficulty': dict(Counter(r['difficulty'] for r in bank)), 'formats': dict(Counter(r['question_type'] for r in bank)),
            'exact_text': duplicates([normalize(r['question_text']) for r in bank]),
            'answers': duplicates([normalize(r['answer_text']) for r in bank]),
            'legacy_fact_groups': duplicates([r.get('fact_group_id') for r in bank]),
            'verification_status': dict(Counter(r.get('verification_status') for r in bank)),
            'missing_source_url': sum(not r.get('source_url') for r in bank),
            'missing_source_claim': sum(not r.get('source_claim') for r in bank),
            'missing_checked_at': sum(not r.get('source_checked_at') for r in bank),
            'source_names': Counter(r.get('source_name') for r in bank).most_common(),
            'source_entity_ids': Counter(r.get('source_entity_id') for r in bank if r.get('source_entity_id')).most_common(12),
            'template_prefix_heuristic': templates.most_common(12), 'template_entropy_heuristic': entropy(templates),
            'era_first_explicit_year_heuristic': dict(eras),
            'external_media_references': sum(any(str(r.get(k) or '').startswith(('http:', 'https:')) for k in ('media_url_a','media_url_b')) for r in bank),
            'samples': [{k: r.get(k) for k in ('id','difficulty','question_text','answer_text','fact_group_id','source_url')} for r in bank[:3]]}
    normalized_snapshot = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return {'generated_at': datetime.now(timezone.utc).isoformat(), 'database': str(database.resolve()),
        'read_only': True, 'sqlite_schema_version': version, 'active_football_rows_sha256': hashlib.sha256(normalized_snapshot).hexdigest(),
        'methodology': {'deterministic': 'Stored active counts, normalized exact text, answer repetition, legacy fact groups, source presence, format counts, foreign keys.',
            'heuristic': 'First four normalized words with digits masked approximate templates. Era uses one unambiguous explicit 1900–2099 question year; all others unknown. Source entity IDs are legacy IDs, not validated canonical subjects.',
            'not_measured': 'Truth/ambiguity, canonical fact/event duplication, perceived similarity, source validity, actual historical-era and primary-entity distribution require editorial verification; missing provenance is not proof that a fact is false. External media URLs are not fetched by this audit.'},
        'total_active_football': len(rows), 'categories': summaries, 'foreign_key_violations': foreign_keys,
        'schema': schema}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=Path('data/seenjeem.db'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.database)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + '\n', encoding='utf-8')
    else:
        print(rendered)
