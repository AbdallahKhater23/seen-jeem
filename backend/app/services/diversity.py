"""Bounded whole-board selection. Weights are editorial defaults, not fitted results.

Canonical facts, legacy fact groups and normalized text are hard constraints.
Events/entities/eras are soft objectives: sharing an answer is never a duplicate.
Unknown metadata earns no coverage bonus and is never invented.
"""

from __future__ import annotations

import random
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


SUPPORTED_MECHANICS = frozenset({
    "direct_recall", "deduction_trio", "career_path", "connection_puzzle",
    "sequence_reasoning", "odd_one_out", "vector_formation", "visual_identification",
})
CORE_ARCHETYPES = (
    "iconic_goals", "remontada_drama", "lineup_detective", "tactician_bench",
    "career_clues", "iconic_celebrations", "quote_banter", "derby_feuds",
    "player_nicknames", "records_unbroken", "heartbreak_underdog", "what_happened_next",
)


def normalized_prompt(text: str) -> str:
    """Conservative text identity; retain numbers and distinct Arabic letters."""
    value = unicodedata.normalize("NFKC", text).casefold().replace("\u0640", "")
    value = "".join(
        " " if unicodedata.category(ch).startswith("P") else ch
        for ch in value if not unicodedata.category(ch).startswith("M")
    )
    return " ".join(value.split())


@dataclass(frozen=True)
class DiversityProfile:
    weights: dict[str, float] = field(default_factory=lambda: {
        "event_id": 9.0, "primary_entity_id": 4.0, "archetype": 2.5,
        "mechanic": 2.0, "era": 1.1, "tone": 0.6,
        "template_family": 3.0, "topic_id": 1.5, "answer_key": 1.0,
    })
    preferred_eras: tuple[str, ...] = ("golden_era", "modern_peak", "contemporary")
    permitted_archetypes: tuple[str, ...] = CORE_ARCHETYPES
    permitted_mechanics: frozenset[str] = SUPPORTED_MECHANICS
    randomness: float = 2.0
    recent_multiplier: float = 0.35


CATEGORY_PROFILES = {
    "ucl": DiversityProfile(),
    "worldcup": DiversityProfile(weights={
        **DiversityProfile().weights, "event_id": 11.0, "topic_id": 3.0,
    }),
    "career": DiversityProfile(weights={
        **DiversityProfile().weights, "primary_entity_id": 8.0,
    }, permitted_archetypes=("career_clues", "records_unbroken", "what_happened_next", "heartbreak_underdog"),
        permitted_mechanics=SUPPORTED_MECHANICS - {"vector_formation"}),
    "nicknames": DiversityProfile(weights={
        **DiversityProfile().weights, "template_family": 5.0,
    }, permitted_archetypes=("player_nicknames", "career_clues", "derby_feuds"),
        permitted_mechanics=frozenset({"direct_recall", "deduction_trio", "connection_puzzle", "odd_one_out"})),
    "numbers": DiversityProfile(weights={
        **DiversityProfile().weights, "primary_entity_id": 5.0,
    }, permitted_archetypes=("records_unbroken", "career_clues", "what_happened_next", "heartbreak_underdog", "iconic_goals"),
        permitted_mechanics=SUPPORTED_MECHANICS - {"vector_formation"}),
    "football": DiversityProfile(),
    "clubs": DiversityProfile(),
    "arab_ftbl": DiversityProfile(weights={
        **DiversityProfile().weights, "primary_entity_id": 5.0, "event_id": 10.0,
    }),
}
DEFAULT_PROFILE = DiversityProfile()


def hard_keys(question: dict[str, Any]) -> frozenset[tuple[str, Any]]:
    keys = {("id", question["id"])}
    for name in ("fact_id", "fact_group_id"):
        if question.get(name):
            keys.add((name, question[name]))
    # Visual questions can intentionally share a prompt with different diagrams.
    prompt = normalized_prompt(question.get("question_text", ""))
    if prompt:
        stimulus = tuple(question.get(name) or "" for name in (
            "payload_json", "flag_code", "media_url_a", "media_url_b", "visual_json",
        ))
        keys.add(("prompt", (prompt, stimulus) if any(stimulus) else prompt))
    return frozenset(keys)


class SearchLimitExceeded(Exception):
    """No proof of exhaustion: the bounded assignment budget was consumed."""


def select_board(
    pools: dict[tuple[int, int], list[dict]],
    slugs: dict[int, str],
    *,
    salt: str,
    count: int = 3,
    recent: dict[str, Counter] | None = None,
    forbidden: set[tuple[str, Any]] | None = None,
    max_nodes: int = 20_000,
    profiles: dict[str, DiversityProfile] | None = None,
) -> dict[tuple[int, int], list[dict]] | None:
    """Most constrained slot first, with bounded backtracking on hard conflicts.

    All primary and backup slots share one objective and one exclusion set.
    Candidate pools are never truncated (avoids hiding rare feasible choices).
    Callers retain transaction ownership. None proves infeasibility; a budget
    failure is distinguished explicitly so it cannot claim content exhaustion.
    """
    profiles = CATEGORY_PROFILES if profiles is None else profiles
    rng = random.Random(salt)
    jitter = {q["id"]: rng.random() for pool in pools.values() for q in pool}
    identities = {q["id"]: hard_keys(q) for pool in pools.values() for q in pool}
    chosen: dict[tuple[int, int], list[dict]] = {key: [] for key in pools}
    used = set(forbidden or ())
    counts: dict[str, Counter] = {}
    recent = recent or {}
    nodes = 0

    def score(q: dict, profile: DiversityProfile) -> float:
        quality = float(q.get("quality_score") or 0)
        total = quality * 0.5 + jitter[q["id"]] * profile.randomness
        total -= min(float(q.get("times_played") or 0), 20) * 0.05
        for dimension, weight in profile.weights.items():
            value = q.get(dimension)
            if value in (None, "", "unknown", "neutral"):
                continue
            frequency = counts.get(dimension, Counter())[value]
            total += weight * (0.4 if frequency == 0 else -frequency)
            total -= weight * profile.recent_multiplier * recent.get(dimension, Counter())[value]
        if q.get("era") in profile.preferred_eras:
            total += 0.15
        return total

    def visit() -> bool:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise SearchLimitExceeded()
        available = []
        for key, pool in pools.items():
            needed = count - len(chosen[key])
            if not needed:
                continue
            candidates = [q for q in pool if not identities[q["id"]] & used]
            if len(candidates) < needed:
                return False
            # Cheap necessary capacity checks avoid factorial searches when
            # many paraphrases disguise an exhausted canonical fact pool.
            for dimension in ("fact_id", "fact_group_id", "prompt"):
                values = set()
                for q in candidates:
                    value = next((value for name, value in identities[q["id"]]
                                  if name == dimension), ("unknown", q["id"]))
                    values.add(value)
                if len(values) < needed:
                    return False
            available.append((len(candidates) - needed, key, candidates))
        if not available:
            return True
        _, key, candidates = min(available, key=lambda item: (item[0], item[1]))
        profile = profiles.get(slugs[key[0]], DEFAULT_PROFILE)
        candidates.sort(key=lambda q: (-score(q, profile), q["id"]))
        for q in candidates:
            keys = identities[q["id"]]
            used.update(keys)
            chosen[key].append(q)
            for dimension in profile.weights:
                value = q.get(dimension)
                if value:
                    counts.setdefault(dimension, Counter())[value] += 1
            if visit():
                return True
            for dimension in profile.weights:
                value = q.get(dimension)
                if value:
                    counts[dimension][value] -= 1
            chosen[key].pop()
            used.difference_update(keys)
        return False

    return chosen if visit() else None
