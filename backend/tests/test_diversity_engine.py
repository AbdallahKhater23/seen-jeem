"""Synthetic selection attacks; fixtures are not publishable football facts."""

from collections import Counter

import pytest

from app.services.diversity import (
    DiversityProfile, SearchLimitExceeded, hard_keys, select_board,
)


def question(number, **metadata):
    return {
        "id": number, "question_type": "text", "question_text": f"سؤال اختبار {number}",
        "fact_group_id": f"legacy:{number}", "fact_id": f"fact:{number}",
        "event_id": "event:shared", "primary_entity_id": "player:shared",
        "era": "modern_peak", "mechanic": "direct_recall", "quality_score": 3,
        **metadata,
    }


def test_same_fact_different_language_is_hard_duplicate():
    first = question(1, question_text="منو سجل الهدف؟", fact_id="fact:goal")
    translation = question(2, question_text="Who scored?", fact_id="fact:goal")
    pool = [first, translation, question(3)]
    assert select_board({(1, 200): pool}, {1: "ucl"}, salt="fact") is None


def test_same_entity_event_answer_different_facts_remain_eligible():
    pool = [question(n, answer_key="رونالدو") for n in range(3)]
    board = select_board({(1, 200): pool}, {1: "ucl"}, salt="entity")
    assert len(board[(1, 200)]) == 3


def test_prompt_alias_punctuation_and_diacritics_are_hard_duplicates():
    first = question(1, question_text="مَنْ سجل الهدف؟")
    second = question(2, question_text="من سجل الهدف!")
    assert hard_keys(first) & hard_keys(second)
    assert select_board({(1, 200): [first, second, question(3)]}, {1: "ucl"}, salt="prompt") is None


def test_visual_prompts_can_share_wording_with_different_diagrams():
    first = question(1, question_type="flag", question_text="شنو الدولة؟", payload_json='{"flag":"kw"}')
    second = question(2, question_type="flag", question_text="شنو الدولة؟", payload_json='{"flag":"sa"}')
    assert not hard_keys(first) & hard_keys(second)


def test_backtracking_avoids_greedy_false_exhaustion():
    # Crossed fact/group identities are jointly impossible even though each
    # individual bucket has enough rows. Adding an independent B makes it fair.
    a = [question(1, fact_id="x", fact_group_id="y"), question(2, fact_id="z", fact_group_id="w")]
    b = [question(3, fact_id="x", fact_group_id="w"), question(4, fact_id="z", fact_group_id="y")]
    c = [question(5, fact_id="z"), question(6, fact_id="independent")]
    for salt in range(10):
        board = select_board({(1, 200): a, (2, 200): b, (3, 200): c}, {1: "ucl", 2: "ucl", 3: "ucl"}, salt=str(salt), count=1)
        # No combination of A and B above is possible (two cross identities).
        assert board is None
    b.append(question(7))
    board = select_board({(1, 200): a, (2, 200): b, (3, 200): c}, {1: "ucl", 2: "ucl", 3: "ucl"}, salt="fixed", count=1)
    assert board is not None
    assert board[(2, 200)][0]["id"] == 7


def test_diversity_weights_measurably_change_concentration():
    pool = [question(n, event_id="event:dominant") for n in range(20)]
    pool += [question(20 + n, event_id=f"event:{n}") for n in range(8)]
    plain = {"ucl": DiversityProfile(weights={}, randomness=2)}
    diverse = {"ucl": DiversityProfile(weights={"event_id": 10}, randomness=2)}
    concentrations = [[], []]
    for salt in range(20):
        for index, profiles in enumerate((plain, diverse)):
            board = select_board({(1, 200): pool}, {1: "ucl"}, salt=str(salt), count=6, profiles=profiles)
            counts = Counter(q["event_id"] for q in board[(1, 200)])
            concentrations[index].append(max(counts.values()))
    assert sum(concentrations[1]) == 20
    assert sum(concentrations[0]) > sum(concentrations[1])


def test_seed_is_reproducible_but_sessions_vary():
    pool = [question(n) for n in range(30)]
    def selected(salt):
        return [q["id"] for q in select_board({(1, 200): pool}, {1: "ucl"}, salt=salt)[(1, 200)]]
    assert selected("a") == selected("a")
    assert selected("a") != selected("b")


def test_all_54_slots_share_canonical_exclusions():
    pools = {(c, d): [question(c * 10000 + d * 10 + n) for n in range(6)] for c in range(6) for d in (200, 400, 600)}
    for pool in pools.values():
        pool[0]["fact_id"] = "fact:global_shared"
    board = select_board(pools, {c: "ucl" for c in range(6)}, salt="full")
    facts = [q["fact_id"] for pool in board.values() for q in pool]
    assert len(facts) == len(set(facts)) == 54


def test_history_fact_exclusion_applies_across_ids_and_categories():
    pools = {(1, 200): [question(n) for n in range(4)]}
    board = select_board(pools, {1: "ucl"}, salt="seen", forbidden={("fact_id", "fact:0")})
    assert {q["id"] for q in board[(1, 200)]} == {1, 2, 3}


def test_budget_is_not_reported_as_proven_exhaustion():
    with pytest.raises(SearchLimitExceeded):
        select_board({(1, 200): [question(n) for n in range(3)]}, {1: "ucl"}, salt="budget", max_nodes=1)
