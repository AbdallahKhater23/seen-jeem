"""Explicit editorial publication, canonical identity and context-specific answers.

No network or model generation occurs during gameplay. Source assertions are
editorial attestations, not an automated proof of football truth. Unknown legacy
rows are never silently promoted. A batch either publishes in full or rolls back.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from datetime import date
from urllib.parse import urlsplit

from ..db import transaction
from ..utils.text import fingerprint

FOOTBALL_CATEGORIES = frozenset({
    'football', 'ucl', 'worldcup', 'career', 'clubs', 'arab_ftbl', 'numbers', 'nicknames',
})
ARCHETYPES = frozenset({
    'iconic_goals', 'remontada_drama', 'lineup_detective', 'tactician_bench',
    'career_clues', 'iconic_celebrations', 'quote_banter', 'derby_feuds',
    'player_nicknames', 'records_unbroken', 'heartbreak_underdog', 'what_happened_next',
})
MECHANICS = frozenset({'direct_recall', 'deduction_trio', 'career_path',
    'vector_formation', 'odd_one_out', 'connection_puzzle', 'sequence_reasoning',
    'visual_identification'})
TONES = frozenset({'hype', 'humor_banter', 'nostalgia', 'debate_provoking', 'surprise', 'neutral'})
TOLERANCES = frozenset({'exact', 'name_alias', 'ordered_sequence', 'unordered_set'})
IDENTITY_RE = re.compile(r'^[a-z_]+:[a-z0-9][a-z0-9_:-]*$')
DIACRITICS = re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')
DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')


def normalize_football_answer(value: str) -> str:
    """Comparison only: preserve distinct ة/ه and ؤ/و names; no fuzzy matching."""
    text = unicodedata.normalize('NFKC', value).casefold().translate(DIGITS)
    text = DIACRITICS.sub('', text).replace('ـ', '')
    text = text.translate(str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي'}))
    text = ''.join(' ' if unicodedata.category(ch).startswith('P') else ch for ch in text)
    return ' '.join(text.split())


def accepts_answer(value: str, answer: str, aliases: list[str], tolerance_type: str) -> bool:
    if tolerance_type not in TOLERANCES:
        raise ValueError('unsupported tolerance_type')
    if not all(isinstance(v, str) for v in [value, answer, *aliases]):
        return False
    if tolerance_type in {'ordered_sequence', 'unordered_set'}:
        def parts(s):
            return [normalize_football_answer(p) for p in re.split(r'[,،;؛|]', s) if p.strip()]
        actual, expected = parts(value), parts(answer)
        return actual == expected if tolerance_type == 'ordered_sequence' else Counter(actual) == Counter(expected)
    # A score's hyphen is significant; punctuation normalization must not
    # collapse an exact historical score into a different numeric answer.
    if re.fullmatch(r'[\d٠-٩۰-۹\s:–-]+', answer):
        def number(s):
            return unicodedata.normalize('NFKC', s).translate(DIGITS).replace(' ', '').replace('–', '-')
        return number(value) == number(answer)
    expected = [answer] + (aliases if tolerance_type == 'name_alias' else [])
    return normalize_football_answer(value) in {normalize_football_answer(v) for v in expected}


def era_for_year(year: int | None) -> str:
    if year is None:
        return 'unknown'
    if year < 1990:
        return 'classic'
    if year <= 2005:
        return 'golden_era'
    if year <= 2018:
        return 'modern_peak'
    return 'contemporary'


def _text(value, name, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{name}: required text, maximum {maximum}')
    if any(unicodedata.category(ch).startswith('C') for ch in value) or '<' in value or '>' in value:
        raise ValueError(f'{name}: unsafe text')


def validate_candidate(row: dict) -> None:
    """Hard publication gates. Quality scoring cannot override these checks."""
    if row.get('accuracy_pass') is not True:
        raise ValueError('accuracy review required')
    if row.get('ambiguity_pass') is not True:
        raise ValueError('ambiguity review required')
    if row.get('dialect') != 'khaleeji':
        raise ValueError('Khaleeji editorial review required')
    if row.get('category') not in FOOTBALL_CATEGORIES or row.get('difficulty') not in (200, 400, 600):
        raise ValueError('invalid category/difficulty')
    if row.get('type', 'text') != 'text':
        raise ValueError('curated football uses text plus structured visuals')
    for key, maximum in [('question', 320), ('answer', 160), ('entity_name', 120),
                         ('editorial_note', 1200), ('source_name', 160), ('source_claim', 1800), ('template_family', 100)]:
        _text(row.get(key), key, maximum)
    for key in ('fact_id', 'topic_id', 'entity_id'):
        if not isinstance(row.get(key), str) or not IDENTITY_RE.fullmatch(row[key]):
            raise ValueError(f'invalid {key}')
    if row['entity_id'] == 'entity:general':
        raise ValueError('placeholder entity')
    if row.get('event_id') and not IDENTITY_RE.fullmatch(row['event_id']):
        raise ValueError('invalid event_id')
    year = row.get('event_year')
    if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1850 <= year <= date.today().year):
        raise ValueError('invalid event_year')
    # Multi-era careers use an explicitly chosen decisive event year, or unknown.
    if row.get('era') != era_for_year(year):
        raise ValueError('era does not agree with verified primary year')
    if row.get('archetype') not in ARCHETYPES or row.get('mechanic') not in MECHANICS or row.get('tone') not in TONES:
        raise ValueError('unsupported editorial dimension')
    from .diversity import CATEGORY_PROFILES
    profile = CATEGORY_PROFILES[row['category']]
    if row['archetype'] not in profile.permitted_archetypes or row['mechanic'] not in profile.permitted_mechanics:
        raise ValueError('category profile does not permit this presentation')
    if row.get('tolerance_type', 'name_alias') not in TOLERANCES:
        raise ValueError('unsupported tolerance_type')
    aliases = row.get('aliases', [])
    if not isinstance(aliases, list) or len(aliases) > 16:
        raise ValueError('invalid aliases')
    for alias in aliases:
        _text(alias, 'alias', 160)
        if normalize_football_answer(alias) in {'ronaldo', 'رونالدو'}:
            raise ValueError('ambiguous Ronaldo alias needs explicit context')
    entities = row.get('secondary_entities', [])
    if not isinstance(entities, list) or len(entities) > 24 or any(not isinstance(e, str) or not IDENTITY_RE.fullmatch(e) for e in entities):
        raise ValueError('invalid secondary_entities')
    source = urlsplit(row.get('source_url', ''))
    if source.scheme != 'https' or not source.hostname or source.username or source.password or len(row['source_url']) > 2048:
        raise ValueError('invalid source_url')
    for field in ('source_checked_at', 'record_as_of_date'):
        if row.get(field):
            checked = date.fromisoformat(row[field][:10])
            if checked > date.today():
                raise ValueError(f'{field}: future date')
        elif field == 'source_checked_at':
            raise ValueError('source_checked_at required')
    for key in ('quality_score', 'difficulty_confidence'):
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f'invalid {key}')
    visual = row.get('visual')
    if visual:
        from .vector_visuals import validate_visual
        validate_visual(visual)
    expected_type = {
        'vector_formation': 'lineup_svg',
        'career_path': 'career_tree',
        'odd_one_out': 'odd_one_out_grid',
        'visual_identification': 'shot_radar',
    }.get(row['mechanic'])
    if expected_type and (not visual or visual.get('type') != expected_type):
        raise ValueError('mechanic requires matching supported visual')


def classify_collision(a: dict, b: dict) -> str:
    """Explain collisions without conflating same answer and semantic duplicate.

    Token Jaccard is a review hint only; canonical facts provide the hard gate.
    Cross-language duplicates require canonical editorial identity.
    """
    text_a, text_b = (normalize_football_answer(r.get('question', r.get('question_text', ''))) for r in (a, b))
    if text_a and text_a == text_b:
        return 'exact_duplicate'
    for key, label in [('fact_id', 'same_fact'), ('event_id', 'same_event')]:
        if a.get(key) and a.get(key) == b.get(key):
            return label
    tokens_a, tokens_b = set(text_a.split()), set(text_b.split())
    if min(len(tokens_a), len(tokens_b)) >= 5 and len(tokens_a & tokens_b) / len(tokens_a | tokens_b) >= .85:
        return 'paraphrase_duplicate'
    for key, label in [('answer', 'same_answer'), ('entity_id', 'same_primary_entity'),
        ('template_family', 'same_template_family'), ('archetype', 'same_archetype'), ('topic_id', 'similar_topic')]:
        if a.get(key) and a.get(key) == b.get(key):
            return label
    return 'independent'


async def publish_candidates(settings, rows: list[dict], *, verified_only=False) -> dict:
    """Idempotent insert. Existing question bytes/history/difficulties never change.

    Explicit verified_only policy hides legacy from future allocation in affected
    categories. Already allocated matches continue reading original question IDs.
    """
    for row in rows:
        validate_candidate(row)
    inserted = 0
    canonical_facts = {}
    for row in rows:
        identity = (row.get('event_id'), row['topic_id'], row['entity_id'])
        if row['fact_id'] in canonical_facts and canonical_facts[row['fact_id']] != identity:
            raise ValueError('conflicting canonical fact identity')
        canonical_facts[row['fact_id']] = identity
    async with transaction(settings) as db:
        categories = {r['slug']: r['id'] for r in await (await db.execute('SELECT id,slug FROM categories')).fetchall()}
        for row in rows:
            if row['category'] not in categories:
                raise ValueError(f"category not installed: {row['category']}")
            await db.execute('INSERT INTO football_entities(id,display_name_ar,aliases_json) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING',
                (row['entity_id'], row['entity_name'], json.dumps(row.get('aliases', []), ensure_ascii=False)))
            if row.get('event_id'):
                await db.execute('INSERT INTO football_events(id,label,event_year) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING',
                    (row['event_id'], row.get('event_label') or row['event_id'], row.get('event_year')))
                event = await (await db.execute('SELECT event_year FROM football_events WHERE id=?', (row['event_id'],))).fetchone()
                if event['event_year'] != row.get('event_year'):
                    raise ValueError('conflicting canonical event year')
            await db.execute('INSERT INTO football_facts(id,event_id,topic_id,primary_entity_id) VALUES (?,?,?,?) ON CONFLICT(id) DO NOTHING',
                (row['fact_id'], row.get('event_id'), row['topic_id'], row['entity_id']))
            fact = await (await db.execute('SELECT event_id,topic_id,primary_entity_id FROM football_facts WHERE id=?', (row['fact_id'],))).fetchone()
            if tuple(fact) != canonical_facts[row['fact_id']]:
                raise ValueError('conflicting stored canonical fact')
            fp = fingerprint(row['category'], row['question'], row['answer'])
            prior = await (await db.execute('SELECT id FROM questions WHERE fingerprint=?', (fp,))).fetchone()
            if prior:
                metadata = await (await db.execute('SELECT fact_id FROM question_metadata WHERE question_id=?', (prior['id'],))).fetchone()
                if not metadata or metadata['fact_id'] != row['fact_id']:
                    raise ValueError('existing question requires explicit editorial migration')
                continue
            cur = await db.execute('''INSERT INTO questions(
                category_id,difficulty,question_type,question_text,answer_text,tolerance,explanation,
                source_name,source_url,source_checked_at,source_license,source_claim,content_origin,
                fingerprint,fact_group_id,source_entity_id,verification_status,deck_position)
                VALUES (?,?,'text',?,?,?,?,?,?,?,?,?,'curated',?,?,?,'verified_editorial',?)''', (
                categories[row['category']], row['difficulty'], row['question'], row['answer'],
                '، '.join([row['answer'], *row.get('aliases', [])]), row['source_claim'],
                row['source_name'], row['source_url'], row['source_checked_at'],
                'Original question and diagrams; factual reference only; source media not copied', row['source_claim'],
                fp, row['fact_id'], row['entity_id'], int(fp[:8], 16)))
            question_id = cur.lastrowid
            await cur.close()
            await db.execute('''INSERT INTO question_metadata(
                question_id,fact_id,era,archetype,mechanic,tone,template_family,secondary_entities_json,
                quality_score,difficulty_confidence,editorial_note,aliases_json,tolerance_type,
                record_as_of_date,visual_json,review_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'published')''', (
                question_id, row['fact_id'], row['era'], row['archetype'], row['mechanic'], row['tone'],
                row['template_family'], json.dumps(row.get('secondary_entities', [])), row['quality_score'],
                row['difficulty_confidence'], row['editorial_note'], json.dumps(row.get('aliases', []), ensure_ascii=False),
                row.get('tolerance_type', 'name_alias'), row.get('record_as_of_date'),
                json.dumps(row['visual'], ensure_ascii=False) if row.get('visual') else None))
            await db.execute('INSERT INTO content_reviews(question_id,content_version,decision,rubric_json) VALUES (?,1,\'published\',?)',
                (question_id, json.dumps({k: row[k] for k in ('accuracy_pass','ambiguity_pass','dialect',
                    'quality_score','difficulty_confidence','editorial_note','source_url','source_claim')}, ensure_ascii=False)))
            inserted += 1
        if verified_only:
            for slug in {r['category'] for r in rows}:
                await db.execute('INSERT INTO football_category_policy(category_id,verified_only) VALUES (?,1) ON CONFLICT(category_id) DO UPDATE SET verified_only=1', (categories[slug],))
    return {'inserted': inserted, 'skipped': len(rows) - inserted, 'candidates': len(rows),
        'unique_facts': len(canonical_facts), 'verified_only': verified_only}
