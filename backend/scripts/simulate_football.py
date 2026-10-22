"""Reproducible allocations on a disposable snapshot of the real repository DB.

The source database is opened mode=ro. No synthetic football facts are inserted.
Legacy comparison replays the original ordered, unique-fact-group bucket policy;
it is an algorithm replay, not a recorded historical match or a human playtest.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import closing
from dataclasses import replace
import itertools
import json
import math
from pathlib import Path
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import load_settings
from app.db import init_db, transaction
from app.services.diversity import DiversityProfile, select_board
from app.services.football_content import FOOTBALL_CATEGORIES, publish_candidates
from app.services.selector import allocate_match, bucket_cycle, eligible_questions
from scripts.publish_football import sqlite_backup


def distribution(values):
    counts = Counter(v for v in values if v and v != 'unknown')
    total = sum(counts.values())
    return {'counts': dict(counts), 'known': total, 'distinct': len(counts),
        'max_concentration': max(counts.values(), default=0),
        'entropy_bits': round(-sum(n / total * math.log2(n / total) for n in counts.values()), 4) if total else None}


def board_metrics(rows):
    result = {'questions': len(rows), 'unique_question_ids': len({q['id'] for q in rows}),
        'duplicate_facts': len([q for q in rows if q.get('fact_id')]) - len({q['fact_id'] for q in rows if q.get('fact_id')})}
    for field in ('event_id', 'primary_entity_id', 'archetype', 'mechanic', 'era', 'template_family', 'answer_key'):
        result[field] = distribution([q.get(field) for q in rows])
    return result


async def pools_for(db, categories):
    pools = {}
    for c in categories:
        for d in (200, 400, 600):
            cycle = await bucket_cycle(db, c['id'], d)
            pools[c['id'], d] = [dict(r) for r in await eligible_questions(db, c['id'], d, cycle)]
    return pools


async def scenario(settings, categories, name, seen_fraction=0, participants=1):
    async with transaction(settings) as db:
        users = []
        for i in range(participants):
            cur = await db.execute("INSERT INTO users(display_name,kind) VALUES (?,'named')", (f'simulation {name} {i}',))
            users.append(cur.lastrowid)
        if name in {'returning', 'multiple_histories'}:
            previous = []
            for i in range(participants):
                historical = await allocate_match(db, settings, categories=categories, salt=f'previous:{name}:{i}')
                previous.append([qid for a in historical.allocations for qid in a.primary_ids])
            for user, exposed in zip(users, previous):
                await db.executemany('INSERT INTO user_question_history(user_id,question_id) VALUES (?,?)', [(user, qid) for qid in exposed])
        elif seen_fraction:
            ids = [r[0] for r in await (await db.execute('SELECT question_id FROM question_metadata ORDER BY question_id')).fetchall()]
            count = int(len(ids) * seen_fraction)
            for i, user in enumerate(users):
                # Multiple people cover different windows of the actual bank.
                exposed = (ids[i * count:] + ids[:i * count])[:count]
                await db.executemany('INSERT INTO user_question_history(user_id,question_id) VALUES (?,?)', [(user, qid) for qid in exposed])
        start = time.perf_counter()
        try:
            allocation = await allocate_match(db, settings, categories=categories, salt=name, excluded_user_ids=tuple(users))
        except Exception as exc:
            from app.utils.errors import AppError
            if not isinstance(exc, AppError):
                raise
            result = {'scenario': name, 'error': exc.code, 'details': exc.details}
        else:
            ids = [qid for a in allocation.allocations for qid in a.primary_ids]
            placeholders = ','.join('?' for _ in ids)
            rows = [dict(r) for r in await (await db.execute('''SELECT q.id,q.difficulty,q.answer_text AS answer_key,
                qm.fact_id,qm.era,qm.archetype,qm.mechanic,qm.template_family,
                f.event_id,f.primary_entity_id FROM questions q JOIN question_metadata qm ON qm.question_id=q.id
                JOIN football_facts f ON f.id=qm.fact_id WHERE q.id IN (''' + placeholders + ')', ids)).fetchall()]
            result = {'scenario': name, **board_metrics(rows), 'reserved_total': sum(len(a.primary_ids) + 1 for a in allocation.allocations),
                'difficulty_counts': dict(Counter(r['difficulty'] for r in rows))}
        result['allocation_ms'] = round((time.perf_counter() - start) * 1000, 3)
    return result


async def run(source, runs):
    from app.data.football_curated import FOOTBALL_CURATED
    with tempfile.TemporaryDirectory(prefix='seenjeem-football-') as temporary:
        snapshot = Path(temporary) / 'snapshot.db'
        sqlite_backup(source, snapshot)
        settings = replace(load_settings(), database_path=snapshot)
        await init_db(settings)
        publication = await publish_candidates(settings, FOOTBALL_CURATED, verified_only=True)
        async with transaction(settings) as db:
            categories = [dict(r) for r in await (await db.execute('SELECT id,slug FROM categories ORDER BY sort_order')).fetchall() if r['slug'] in FOOTBALL_CATEGORIES]
            raw_pools = await pools_for(db, categories)
            # Choose a representative six-category board only if hard-feasible.
            feasible = []
            failed = []
            for combination in itertools.combinations(categories, 6):
                ids = {c['id'] for c in combination}
                pools = {k: v for k, v in raw_pools.items() if k[0] in ids}
                chosen = select_board(pools, {c['id']: c['slug'] for c in combination}, salt='feasibility')
                (feasible if chosen else failed).append([c['slug'] for c in combination])
            if not feasible:
                return {'publication': publication, 'feasible_combinations': [], 'failed_combinations': failed,
                    'status': 'INSUFFICIENT_VALIDATED_CONTENT'}
            selected_slugs = feasible[0]
            selected = [c for c in categories if c['slug'] in selected_slugs]
            pools = {k: v for k, v in raw_pools.items() if k[0] in {c['id'] for c in selected}}
            # Same published candidates, weights disabled: isolates score effect.
            blank = {c['slug']: DiversityProfile(weights={}, preferred_eras=()) for c in selected}
            measurements = {'weighted': [], 'weights_disabled': []}
            latencies = []
            sample = None
            tracemalloc.start()
            for i in range(runs):
                for mode, profiles in [('weighted', None), ('weights_disabled', blank)]:
                    start = time.perf_counter()
                    chosen = select_board(pools, {c['id']: c['slug'] for c in selected}, salt=f'measure:{i}', profiles=profiles)
                    elapsed = (time.perf_counter() - start) * 1000
                    if chosen is None:
                        raise RuntimeError('Previously feasible candidate pool became impossible')
                    rows = [q for questions in chosen.values() for q in questions[:2]]
                    measurements[mode].append(board_metrics(rows))
                    if mode == 'weighted':
                        latencies.append(elapsed)
                        if sample is None:
                            sample = [{'category': next(c['slug'] for c in selected if c['id'] == key[0]),
                                'difficulty': key[1], 'id': q['id'], 'question': q['question_text'],
                                'answer': q['answer_key'], 'fact_id': q['fact_id'], 'event_id': q['event_id'],
                                'archetype': q['archetype'], 'mechanic': q['mechanic'], 'era': q['era'],
                                'source_url': (await (await db.execute('SELECT source_url FROM questions WHERE id=?', (q['id'],))).fetchone())[0]}
                                for key, questions in chosen.items() for q in questions[:2]]
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        scenarios = []
        for name, fraction, n in [('fresh', 0, 1), ('returning', .25, 1), ('highly_active', .9, 1), ('multiple_histories', .25, 2), ('exhausted', 1, 1)]:
            scenarios.append(await scenario(settings, selected, name, fraction, n))
        with closing(sqlite3.connect(snapshot)) as db:
            integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
            foreign_keys = db.execute('PRAGMA foreign_key_check').fetchall()
        return {'workload': 'real repository snapshot + inspected editorial additions; all writes disposable',
            'environment': {'python': platform.python_version(), 'os': platform.platform(), 'cpu': platform.processor()},
            'publication': publication, 'runs': runs, 'feasible_combinations': feasible, 'failed_combinations': failed,
            'measurements': measurements, 'latency_with_tracemalloc_ms': {'median': round(statistics.median(latencies), 3), 'max': round(max(latencies), 3)},
            'selection_peak_traced_bytes': peak_bytes, 'sample_36_tile_board': sample, 'scenarios': scenarios,
            'integrity_check': integrity, 'foreign_key_violations': foreign_keys,
            'limitations': ['Weights-disabled comparison is an ablation, not a measured legacy board.',
                'Returning/multiple histories use 36 questions from previously allocated boards; exposure is simulated.',
                'Highly active history covers 90% of real question IDs; no human playtest is claimed.',
                'Allocation scenario time excludes history setup; includes allocation SQL and metrics retrieval.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.runs <= 100:
        parser.error('--runs must be 1..100')
    result = asyncio.run(run(args.database, args.runs))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'publication': result.get('publication'), 'feasible_six_category_boards': len(result.get('feasible_combinations', [])),
        'failed_six_category_boards': len(result.get('failed_combinations', [])),
        'latency_ms': result.get('latency_with_tracemalloc_ms'), 'peak_bytes': result.get('selection_peak_traced_bytes'),
        'scenarios': [{k: s[k] for k in ('scenario','questions','duplicate_facts','error','allocation_ms') if k in s} for s in result.get('scenarios', [])]}, indent=2))
