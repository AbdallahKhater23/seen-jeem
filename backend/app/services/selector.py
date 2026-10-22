"""Transactional eligibility and whole-board diversity allocation.

The caller owns BEGIN IMMEDIATE and allocation persistence. Selection never
commits, records a question as seen, or changes existing participant history.
Legacy records remain compatible; new metadata must pass publication review.
"""

from __future__ import annotations

import json
import random
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

import aiosqlite

from ..config import Settings
from ..utils.errors import conflict
from .diversity import (
    CATEGORY_PROFILES, DEFAULT_PROFILE, SearchLimitExceeded, hard_keys,
    normalized_prompt, select_board,
)
from .vector_visuals import validate_visual

PRIMARIES_PER_BUCKET = 2
BACKUPS_PER_BUCKET = 1
ALLOCATION_PER_BUCKET = PRIMARIES_PER_BUCKET + BACKUPS_PER_BUCKET
COOLDOWN_MATCHES = 5


@dataclass
class Allocation:
    category_id: int
    slug: str
    difficulty: int
    primary_ids: list[int]
    backup_id: int
    cycle: int
    relaxed: bool = False


@dataclass
class AllocationResult:
    allocations: list[Allocation] = field(default_factory=list)
    relaxations: list[str] = field(default_factory=list)

    @property
    def groups(self) -> set[str]:
        return set()


async def bucket_cycle(db: aiosqlite.Connection, category_id: int, difficulty: int) -> int:
    cursor = await db.execute(
        "SELECT cycle FROM question_buckets WHERE category_id = ? AND difficulty = ?",
        (category_id, difficulty),
    )
    row = await cursor.fetchone()
    await cursor.close()
    if row:
        return int(row["cycle"])
    await db.execute(
        "INSERT INTO question_buckets(category_id, difficulty, cycle) VALUES (?, ?, 1)",
        (category_id, difficulty),
    )
    return 1


async def eligible_questions(
    db: aiosqlite.Connection,
    category_id: int,
    difficulty: int,
    cycle: int,
    excluded_user_ids: tuple[int, ...] = (),
) -> list[sqlite3.Row]:
    history_filter = ""
    params: list[int] = [category_id, difficulty, cycle]
    if excluded_user_ids:
        placeholders = ",".join("?" for _ in excluded_user_ids)
        history_filter = (
            "AND NOT EXISTS (SELECT 1 FROM user_question_history h "
            f"WHERE h.question_id = q.id AND h.user_id IN ({placeholders}))"
        )
        params.extend(excluded_user_ids)
    cursor = await db.execute(
        """
        SELECT q.id, q.fact_group_id, q.times_played, q.deck_position,
               q.question_text, q.question_type, q.payload_json, q.flag_code,
               q.media_url_a, q.media_url_b, qm.visual_json,
               q.answer_text AS answer_key,
               qm.fact_id, qm.era, qm.archetype, qm.mechanic, qm.tone,
               qm.template_family, qm.quality_score, qm.review_status,
               f.event_id, f.topic_id, f.primary_entity_id
        FROM questions q
        LEFT JOIN question_metadata qm ON qm.question_id = q.id
        LEFT JOIN football_facts f ON f.id = qm.fact_id
        LEFT JOIN football_category_policy policy ON policy.category_id = q.category_id
        WHERE q.category_id = ? AND q.difficulty = ? AND q.is_active = 1
          AND q.is_reserved_backup = 0
          AND (qm.question_id IS NULL OR qm.review_status = 'published')
          AND (COALESCE(policy.verified_only, 0) = 0 OR qm.review_status = 'published')
          AND NOT EXISTS (
              SELECT 1 FROM question_usage u
              WHERE u.question_id = q.id AND u.cycle = ?
          )
          AND NOT EXISTS (
              SELECT 1 FROM match_tiles mt
              JOIN matches m ON m.id = mt.match_id
              JOIN questions reserved_q ON reserved_q.id = mt.question_id
              LEFT JOIN question_metadata reserved_qm ON reserved_qm.question_id = reserved_q.id
              WHERE mt.status = 'unplayed' AND m.status = 'active'
                AND (mt.question_id = q.id
                     OR (qm.fact_id IS NOT NULL AND reserved_qm.fact_id = qm.fact_id))
          )
        """ + history_filter + " ORDER BY q.times_played, q.deck_position, q.id",
        tuple(params),
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return rows


async def recent_cooldown_groups(db: aiosqlite.Connection, limit: int = COOLDOWN_MATCHES) -> set[str]:
    cursor = await db.execute(
        """
        SELECT DISTINCT q.fact_group_id
        FROM match_tiles mt JOIN matches m ON m.id = mt.match_id
        JOIN questions q ON q.id = mt.question_id
        WHERE mt.status = 'played' AND q.fact_group_id IS NOT NULL
          AND m.id IN (SELECT id FROM matches WHERE status = 'completed'
                       ORDER BY updated_at DESC, id DESC LIMIT ?)
        """, (limit,),
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return {row["fact_group_id"] for row in rows}


async def _participant_context(db, user_ids):
    """Seen identities are hard; recent event/entity exposure is a soft cost."""
    forbidden = set()
    recent: dict[str, Counter] = {}
    if not user_ids:
        return forbidden, recent
    placeholders = ",".join("?" for _ in user_ids)
    cursor = await db.execute(
        """
        SELECT q.id, q.question_text, q.question_type, q.payload_json, q.fact_group_id,
               q.flag_code, q.media_url_a, q.media_url_b, qm.visual_json,
               qm.fact_id FROM user_question_history h JOIN questions q ON q.id=h.question_id
        LEFT JOIN question_metadata qm ON qm.question_id=q.id
        WHERE h.user_id IN (""" + placeholders + ")", tuple(user_ids),
    )
    for row in await cursor.fetchall():
        forbidden.update(hard_keys(dict(row)))
    await cursor.close()
    cursor = await db.execute(
        """
        SELECT qm.archetype, qm.mechanic, qm.era, qm.tone, qm.template_family,
               f.event_id, f.primary_entity_id, f.topic_id
        FROM user_question_history h JOIN question_metadata qm ON qm.question_id=h.question_id
        LEFT JOIN football_facts f ON f.id=qm.fact_id
        WHERE h.user_id IN (""" + placeholders + ") ORDER BY h.rowid DESC LIMIT 108",
        tuple(user_ids),
    )
    for row in await cursor.fetchall():
        for key in row.keys():
            if row[key]:
                recent.setdefault(key, Counter())[row[key]] += 1
    await cursor.close()
    return forbidden, recent


async def _reshuffle_bucket(db, category_id, difficulty, cycle, salt):
    cursor = await db.execute(
        "SELECT id FROM questions WHERE category_id = ? AND difficulty = ?"
        " AND is_active = 1 AND is_reserved_backup = 0 ORDER BY id",
        (category_id, difficulty),
    )
    ids = [int(row["id"]) for row in await cursor.fetchall()]
    await cursor.close()
    random.Random(f"{salt}:{category_id}:{difficulty}:{cycle}").shuffle(ids)
    await db.executemany(
        "UPDATE questions SET deck_position = ? WHERE id = ?",
        [(position, question_id) for position, question_id in enumerate(ids)],
    )


async def _allocate(
    db, settings, *, slots, salt, excluded_user_ids, used_groups, cooldown_groups,
):
    forbidden, recent = await _participant_context(db, excluded_user_ids)
    forbidden.update(("fact_group_id", group) for group in used_groups)
    slugs = {category_id: slug for category_id, slug, _ in slots}
    cycles = {}
    pools = {}

    async def load(key):
        category_id, difficulty = key
        rows = await eligible_questions(db, category_id, difficulty, cycles[key], excluded_user_ids)
        profile = CATEGORY_PROFILES.get(slugs[category_id], DEFAULT_PROFILE)
        result = []
        for row in rows:
            q = dict(row)
            # Absent metadata is explicitly legacy, not silently "verified".
            if q["review_status"] is not None:
                if q["mechanic"] not in profile.permitted_mechanics:
                    continue
                if profile.permitted_archetypes and q["archetype"] not in profile.permitted_archetypes:
                    continue
                if q["visual_json"]:
                    try:
                        visual = validate_visual(json.loads(q["visual_json"]))
                    except (TypeError, ValueError):
                        continue
                    if q["mechanic"] == "vector_formation" and visual["type"] != "lineup_svg":
                        continue
                    if q["mechanic"] == "visual_identification" and visual["type"] != "shot_radar":
                        continue
                elif q["mechanic"] in {"vector_formation", "visual_identification"}:
                    continue
            if hard_keys(q) & forbidden:
                continue
            q["answer_key"] = normalized_prompt(q["answer_key"])
            result.append(q)
        pools[key] = result

    for category_id, _, difficulty in slots:
        key = category_id, difficulty
        cycles[key] = await bucket_cycle(db, *key)
        await load(key)

    def search(allow_cooldown):
        candidates = pools if allow_cooldown else {
            key: [q for q in pool if q["fact_group_id"] not in cooldown_groups]
            for key, pool in pools.items()
        }
        try:
            return select_board(candidates, slugs, salt=salt, recent=recent, forbidden=forbidden)
        except SearchLimitExceeded:
            raise conflict(
                "ALLOCATION_SEARCH_LIMIT", "تعقّد توزيع الأسئلة، جرّب مرة ثانية.",
                required=len(slots) * ALLOCATION_PER_BUCKET,
            ) from None

    chosen = search(False)
    if chosen is None:
        chosen = search(True)
    # Advance exhausted cycles first; canonical/history/reservation exclusions
    # remain hard even when the deck cycle resets.
    if chosen is None:
        exhausted = set()
        for key, pool in pools.items():
            if len({q["fact_group_id"] for q in pool}) < ALLOCATION_PER_BUCKET:
                exhausted.add(key)
        # A second wave handles cross-bucket conflicts after individually
        # exhausted buckets recover. Every bucket advances at most once.
        waves = [exhausted, set(pools) - exhausted] if exhausted else [set(pools)]
        for refreshed in waves:
            if not refreshed:
                continue
            for key in refreshed:
                cycles[key] += 1
                await db.execute(
                    "UPDATE question_buckets SET cycle=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')"
                    " WHERE category_id=? AND difficulty=?", (cycles[key], *key),
                )
                await _reshuffle_bucket(db, *key, cycles[key], salt)
                await load(key)
            chosen = search(False)
            if chosen is None:
                chosen = search(True)
            if chosen is not None:
                break
    if chosen is None:
        key = min(pools, key=lambda item: len(pools[item]))
        raise conflict(
            "INSUFFICIENT_QUESTIONS", "ما في أسئلة كافية ومتنوعة عقب استبعاد سجل المشاركين.",
            bucket=f"{slugs[key[0]]}:{key[1]}", available=len(pools[key]),
            required=ALLOCATION_PER_BUCKET, excluded_identities=len(excluded_user_ids),
            reason="whole_board_hard_constraints",
        )
    result = AllocationResult()
    for category_id, slug, difficulty in slots:
        key = category_id, difficulty
        selected = chosen[key]
        relaxed = any(q["fact_group_id"] in cooldown_groups for q in selected)
        result.allocations.append(Allocation(
            category_id, slug, difficulty,
            [int(q["id"]) for q in selected[:PRIMARIES_PER_BUCKET]],
            int(selected[PRIMARIES_PER_BUCKET]["id"]), cycles[key], relaxed,
        ))
        used_groups.update(q["fact_group_id"] for q in selected if q["fact_group_id"])
        if relaxed:
            result.relaxations.append(f"{slug}:{difficulty}")
    return result


async def allocate_bucket(
    db: aiosqlite.Connection, settings: Settings, *, category_id: int, slug: str,
    difficulty: int, used_groups: set[str], cooldown_groups: set[str], salt: str,
    excluded_user_ids: tuple[int, ...] = (),
) -> Allocation:
    result = await _allocate(
        db, settings, slots=[(category_id, slug, difficulty)], salt=salt,
        excluded_user_ids=excluded_user_ids, used_groups=used_groups,
        cooldown_groups=cooldown_groups,
    )
    return result.allocations[0]


async def allocate_match(
    db: aiosqlite.Connection, settings: Settings, *, categories: list[dict], salt: str,
    excluded_user_ids: tuple[int, ...] = (),
) -> AllocationResult:
    """Allocate all 36 primary + 18 backup slots in one constrained assignment."""
    return await _allocate(
        db, settings,
        slots=[(int(c["id"]), c["slug"], d) for c in categories for d in (200, 400, 600)],
        salt=salt, excluded_user_ids=excluded_user_ids, used_groups=set(),
        cooldown_groups=await recent_cooldown_groups(db),
    )
