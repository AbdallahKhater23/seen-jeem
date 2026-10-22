"""Manifest contracts, not a substitute for the recorded source/editorial review."""
from collections import Counter

from app.data.football_curated import FOOTBALL_CURATED
from app.services.football_content import FOOTBALL_CATEGORIES, validate_candidate


def test_every_curated_question_passes_publication_and_profile_gates():
    for row in FOOTBALL_CURATED:
        validate_candidate(row)


def test_bank_can_supply_two_rounds_without_relabeling_duplicate_facts():
    counts = Counter((r['category'], r['difficulty']) for r in FOOTBALL_CURATED)
    for slug in FOOTBALL_CATEGORIES:
        for points in (200, 400, 600):
            assert counts[slug, points] >= 5
    assert len({r['fact_id'] for r in FOOTBALL_CURATED}) == len(FOOTBALL_CURATED)
    assert all(r['dialect'] == 'khaleeji' for r in FOOTBALL_CURATED)


def test_curated_formats_and_historical_records_are_explicit():
    assert len({r['archetype'] for r in FOOTBALL_CURATED}) >= 8
    assert len({r['mechanic'] for r in FOOTBALL_CURATED}) >= 5
    assert {'career_tree','odd_one_out_grid'} <= {r['visual']['type'] for r in FOOTBALL_CURATED if r.get('visual')}
    # Records are bounded by a verified historical year; they do not assert a
    # mutable current record without a retrieval/as-of policy.
    assert all(r['event_year'] is not None or r.get('record_as_of_date') for r in FOOTBALL_CURATED if r['category'] == 'numbers')
