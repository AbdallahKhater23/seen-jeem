"""Publication, migration and fair answer guarantees on isolated databases."""
import json
import sqlite3
from dataclasses import replace

import pytest

from app.config import Settings
from app.db import connect, init_db, transaction


def candidate(**changes):
    row = dict(
        category='ucl', difficulty=200, type='text',
        question='منو صاحب هالمقصية في نهائي دوري الأبطال 2018؟',
        answer='غاريث بيل', aliases=['Gareth Bale', 'جاريث بيل'],
        fact_id='fact:ucl_2018_final_bale_bicycle', event_id='event:ucl_2018_final',
        event_label='نهائي دوري الأبطال 2018', event_year=2018,
        topic_id='competition:uefa_champions_league',
        entity_id='player:gareth_bale', entity_name='غاريث بيل', secondary_entities=[],
        era='modern_peak', archetype='iconic_goals', mechanic='direct_recall',
        tone='hype', template_family='identify_iconic_goal', quality_score=.85,
        difficulty_confidence=.9, editorial_note='لقطة مشهورة، والإجابة محددة.',
        source_name='UEFA', source_url='https://www.uefa.com/test-source/',
        source_claim='Bale scored a bicycle kick in the 2018 final.',
        source_checked_at='2026-10-21', accuracy_pass=True, ambiguity_pass=True,
        dialect='khaleeji', tolerance_type='name_alias',
    )
    row.update(changes)
    return row


@pytest.mark.asyncio
async def test_v8_migration_is_additive_and_idempotent(settings):
    async with connect(settings) as db:
        tables = {r[0] for r in await (await db.execute("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        assert {'football_entities', 'football_events', 'football_facts', 'question_metadata',
                'football_category_policy', 'content_reviews'} <= tables
        await db.execute("INSERT INTO users(display_name,kind) VALUES ('قديم','named')")
        await db.commit()
    await init_db(settings)
    await init_db(settings)
    async with connect(settings) as db:
        assert (await (await db.execute("SELECT COUNT(*) FROM users WHERE display_name='قديم'")).fetchone())[0] == 1
        assert await (await db.execute('PRAGMA foreign_key_check')).fetchall() == []
        assert (await (await db.execute('SELECT COUNT(*) FROM question_metadata')).fetchone())[0] == 0


@pytest.mark.asyncio
async def test_publication_rejects_invalid_batch_and_is_idempotent(settings):
    from app.services.football_content import publish_candidates
    async with transaction(settings) as db:
        await db.execute("INSERT INTO categories(slug,name_ar,icon) VALUES ('ucl','أبطال أوروبا','Star')")
    with pytest.raises(ValueError, match='accuracy'):
        await publish_candidates(settings, [candidate(), candidate(fact_id='fact:bad', accuracy_pass=False)])
    async with connect(settings) as db:
        assert (await (await db.execute('SELECT COUNT(*) FROM questions')).fetchone())[0] == 0
    first = await publish_candidates(settings, [candidate()])
    second = await publish_candidates(settings, [candidate()])
    assert first['inserted'] == 1 and second['inserted'] == 0
    async with connect(settings) as db:
        assert (await (await db.execute('SELECT COUNT(*) FROM question_metadata')).fetchone())[0] == 1
        assert (await (await db.execute('SELECT COUNT(*) FROM content_reviews')).fetchone())[0] == 1
        assert await (await db.execute('PRAGMA foreign_key_check')).fetchall() == []


@pytest.mark.asyncio
async def test_conflicting_event_year_rolls_back_publication(settings):
    from app.services.football_content import publish_candidates
    async with transaction(settings) as db:
        await db.execute("INSERT INTO categories(slug,name_ar,icon) VALUES ('ucl','أبطال أوروبا','Star')")
    with pytest.raises(ValueError, match='event year'):
        await publish_candidates(settings, [candidate(), candidate(fact_id='fact:another',
            question='منو صاحب الهدف الثاني بهالنهائي؟', event_year=2022, era='contemporary')])
    async with connect(settings) as db:
        assert (await (await db.execute('SELECT COUNT(*) FROM questions')).fetchone())[0] == 0


@pytest.mark.parametrize('changes', [
    {'era':'classic'}, {'source_url':'javascript:alert(1)'}, {'ambiguity_pass':False},
    {'entity_id':'entity:general'}, {'mechanic':'made_up'}, {'question':'س' * 321},
    {'dialect':'formal'}, {'aliases':['رونالدو'], 'answer':'كريستيانو رونالدو'},
])
def test_publication_gates(changes):
    from app.services.football_content import validate_candidate
    with pytest.raises(ValueError):
        validate_candidate(candidate(**changes))


def test_arabic_answer_matching_is_context_specific():
    from app.services.football_content import accepts_answer
    assert accepts_answer('كْرِيسـتيانو رُونالدو', 'كريستيانو رونالدو', [], 'name_alias')
    assert accepts_answer('CR7', 'كريستيانو رونالدو', ['CR7'], 'name_alias')
    assert not accepts_answer('Ronaldo', 'كريستيانو رونالدو', ['CR7'], 'name_alias')
    assert accepts_answer('٢٠١٨', '2018', [], 'exact')
    assert not accepts_answer('2-0', '2-1', [], 'exact')
    assert accepts_answer('ميلان، إنتر', 'إنتر، ميلان', [], 'unordered_set')
    assert not accepts_answer('ميلان، إنتر', 'إنتر، ميلان', [], 'ordered_sequence')


@pytest.mark.asyncio
async def test_public_catalog_does_not_leak_answers(client):
    async with connect(client._transport.app.state.settings) as db:
        row = await (await db.execute('SELECT id,answer_text FROM questions LIMIT 1')).fetchone()
    response = await client.get(f'/api/v1/questions/{row[0]}')
    assert response.status_code == 200
    data = response.json()
    assert data['answer_text'] is None and data['tolerance'] is None
    assert data['fact_group_id'] is None and data['source_url'] is None


def test_semantic_collisions_do_not_equate_shared_answers_with_same_facts():
    from app.services.football_content import classify_collision
    first = candidate()
    assert classify_collision(first, candidate(question='Who scored the 2018 final bicycle kick?')) == 'same_fact'
    assert classify_collision(first, candidate(question='منو سجل هدف ثاني؟', fact_id='fact:other')) == 'same_event'
    other = candidate(question='منو انتقل لريال مدريد؟', fact_id='fact:other', event_id='event:transfer')
    assert classify_collision(first, other) == 'same_answer'
    assert classify_collision(first, dict(other, answer='غاريث آخر', entity_id='player:other',
        archetype='career_clues', template_family='transfer_clue', topic_id='topic:other')) == 'independent'


@pytest.mark.asyncio
async def test_reseed_preserves_difficulty_of_allocated_active_question(seeded_settings, monkeypatch):
    from app.models import MatchCreateIn
    from app.services import seed
    from tests.conftest import hosted_create, SIX_CATEGORIES
    board = await hosted_create(seeded_settings, MatchCreateIn(
        team1_name='الأول', team2_name='الثاني', category_slugs=SIX_CATEGORIES), 'preserve-active')
    question_id = board['tiles'][0]['question']['id']
    async with connect(seeded_settings) as db:
        stored = await (await db.execute('SELECT fingerprint,difficulty FROM questions WHERE id=?', (question_id,))).fetchone()
    rows = seed.build_question_bank()
    from app.utils.text import fingerprint
    for row in rows:
        if fingerprint(row['category'], row['question'], row['answer'], row.get('flag_code')) == stored['fingerprint']:
            row['difficulty'] = 600 if stored['difficulty'] == 200 else 200
    monkeypatch.setattr(seed, 'build_question_bank', lambda: rows)
    await seed.seed_database(seeded_settings)
    async with connect(seeded_settings) as db:
        after = await (await db.execute('SELECT difficulty FROM questions WHERE id=?', (question_id,))).fetchone()
    assert after['difficulty'] == stored['difficulty']
