"""خدمات المباراة: كل تغيير متعدد الخطوات داخل معاملة واحدة.

التخصيص يحجز 36 سؤالًا أساسيًا + 18 احتياطيًا (سؤالان + احتياطي لكل
فئة/قيمة). الاحتياطي مرتبط بدلوه، فلا يمكن أن يخالف الفئة أو القيمة.
الحجز يُحرَّر تلقائيًا عندما تخرج المباراة من حالة `active`، دون أن يزيد
عدّاد الاستخدام إلا عند لعب الخانة فعليًا.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import secrets
import sqlite3
from typing import Any

import aiosqlite

from ..config import Settings
from ..db import connect, transaction
from ..models import MatchCreateIn
from ..utils.errors import bad_request, conflict, forbidden, not_found
from .history import (
    effective_user_ids,
    record_exposures,
    update_exposure_outcomes,
)
from .identity import MAX_PARTICIPANTS_PER_TEAM, validate_participant_ids
from ..utils.text import normalize_team_name
from .scoring import POWER_IDS, compute_score_deltas
from .selector import Allocation, allocate_match
from .vector_visuals import public_visual

SELECTED_CATEGORY_COUNT = 6
PRIMARY_TILE_COUNT = 36
BACKUP_COUNT = 18
DRAFT_PICK_COUNT = 6
DRAFTABLE_POWER_IDS = POWER_IDS - {"rest", "time_break"}
POWER_SIDES = {
    "pit": "active",
    "double": "active",
    "two_answers": "active",
    "switch": "active",
    "steal": "defending",
    "trap": "defending",
    "noise": "defending",
}
NOISE_SECONDS = 12
SWITCH_WINDOW_MS = 15000


def _other(team: str) -> str:
    return "team2" if team == "team1" else "team1"


def _clean_team_participants(raw: list, team: str) -> list[int]:
    """فحص شكلي لقائمة المشاركين قبل التحقق القاعدي داخل المعاملة."""
    values = list(raw or [])
    if len(values) > MAX_PARTICIPANTS_PER_TEAM:
        raise bad_request(
            "PARTICIPANT_TEAM_FULL",
            f"الفريق الواحد يستوعب {MAX_PARTICIPANTS_PER_TEAM} مشاركين حدًا أقصى.",
            team=team,
        )
    ids: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise bad_request(
                "INVALID_PARTICIPANT",
                "معرّف المشارك يجب أن يكون عددًا صحيحًا موجبًا.",
                team=team,
            )
        if value not in ids:
            ids.append(value)
    return ids


def _hash_host_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _verify_host(match: sqlite3.Row, host_token: str | None) -> None:
    """يثبت أن الطلب صادر عن مضيف المباراة قبل أي تغيير.

    التوكن يُصدر مرة واحدة عند الإنشاء ويُحفظ كبصمة SHA-256 فقط؛
    المقارنة بزمن ثابت. `team` المرسل من العميل غير موثوق وحده،
    فالمضيف (شاشة التلفاز) هو الطرف الوحيد المخوّل بالتغيير.
    """
    try:
        stored = match["host_token_hash"]
    except (IndexError, KeyError):
        stored = None
    if not stored:
        raise forbidden(
            "HOST_TOKEN_UNSET",
            "هالمباراة أُنشئت قبل حماية المضيف؛ ابدأ مباراة جديدة.",
        )
    if not host_token:
        raise forbidden(
            "HOST_TOKEN_REQUIRED",
            "عملية التغيير تحتاج ترويسة X-Host-Token.",
        )
    if not hmac.compare_digest(_hash_host_token(host_token), stored):
        raise forbidden("HOST_TOKEN_INVALID", "توكن المضيف غير صحيح.")


def _match_out(row: sqlite3.Row) -> dict:
    try:
        selected = json.loads(row["selected_categories_json"])
    except (TypeError, ValueError, IndexError):
        selected = []
    return {
        "match_code": row["match_code"],
        "team1_name": row["team1_name"],
        "team2_name": row["team2_name"],
        "score_team1": int(row["score_team1"]),
        "score_team2": int(row["score_team2"]),
        "current_turn": row["current_turn"],
        "status": row["status"],
        "winner": row["winner"],
        "coin_toss_winner": row["coin_toss_winner"],
        "version": int(row["version"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "selected_categories": selected if isinstance(selected, list) else [],
    }


def _json_or_none(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except (TypeError, ValueError):
        return None


def _json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _question_out(row: sqlite3.Row) -> dict:
    revealed = bool(row["revealed_at"]) or row["status"] == "played"
    payload = _json_or_none(row["payload_json"])
    if payload and not revealed and payload.get("kind") == "matchstick":
        payload = {key: value for key, value in payload.items() if key not in {"solution", "end", "moves"}}
    if payload and not revealed and payload.get("kind") == "reverse":
        # مؤشر السؤال الصحيح ينكشف مع الجواب فقط، مو مع البطاقة.
        payload = {key: value for key, value in payload.items() if key != "correct_index"}
    result = {
        "id": int(row["question_id"]),
        "category_slug": row["question_category_slug"],
        "category_name": row["question_category_name"],
        "difficulty": int(row["question_difficulty"]),
        "question_type": row["question_type"],
        "question_text": row["question_text"],
        "flag_code": row["flag_code"],
        "media_url_a": row["media_url_a"],
        "media_url_b": row["media_url_b"],
        "payload": payload,
        "answer_text": row["answer_text"] if revealed else None,
        "tolerance": row["tolerance"] if revealed else None,
        "explanation": row["explanation"] if revealed else None,
        "source_name": row["source_name"] if revealed else None,
        "source_url": row["source_url"] if revealed else None,
        "source_checked_at": row["source_checked_at"] if revealed else None,
        "source_license": row["source_license"] if revealed else None,
        "source_claim": row["source_claim"] if revealed else None,
        "content_origin": row["content_origin"],
        "fact_group_id": row["fact_group_id"] if revealed else None,
        "visual": public_visual(_json_or_none(row["visual_json"]), revealed=revealed),
    }
    return result


def _tile_out(row: sqlite3.Row) -> dict:
    return {
        "tile_key": row["tile_key"],
        "category_slug": row["tile_category_slug"],
        "difficulty": row["tile_difficulty"],
        "is_backup": bool(row["is_backup"]),
        "status": row["status"],
        "outcome": row["outcome"],
        "delta_team1": int(row["delta_team1"]),
        "delta_team2": int(row["delta_team2"]),
        "powers_applied": _json_list(row["powers_applied_json"]),
        "question": _question_out(row),
        "answered_at": row["answered_at"],
        "opened_at": row["opened_at"],
        "revealed_at": row["revealed_at"],
        "active_team": row["active_team"],
        "noise_until": row["noise_until"],
        "compatible_categories": _json_list(row["compatible_categories_json"]),
        "compatible_difficulties": [
            int(item) for item in _json_list(row["compatible_difficulties_json"])
        ],
        "allocation_cycle": int(row["allocation_cycle"]),
    }


TILE_SELECT = """
SELECT
    mt.tile_key, mt.status, mt.outcome, mt.delta_team1, mt.delta_team2,
    mt.powers_applied_json, mt.is_backup, mt.answered_at, mt.allocation_cycle,
    mt.opened_at, mt.revealed_at, mt.active_team, mt.noise_until,
    mt.compatible_categories_json, mt.compatible_difficulties_json,
    mt.category_id AS tile_category_id, mt.difficulty AS tile_difficulty,
    c.slug AS tile_category_slug,
    q.id AS question_id, q.difficulty AS question_difficulty,
    q.question_type, q.question_text, q.flag_code, q.media_url_a, q.media_url_b,
    q.payload_json, q.answer_text, q.tolerance, q.explanation, q.source_name,
    q.source_url, q.source_checked_at, q.source_license, q.source_claim,
    q.content_origin, q.fact_group_id, qm.visual_json,
    qc.slug AS question_category_slug, qc.name_ar AS question_category_name
FROM match_tiles mt
JOIN questions q ON q.id = mt.question_id
LEFT JOIN question_metadata qm ON qm.question_id = q.id
JOIN categories qc ON qc.id = q.category_id
LEFT JOIN categories c ON c.id = mt.category_id
WHERE mt.match_id = ?
"""


async def _load_match(db: aiosqlite.Connection, match_code: str) -> sqlite3.Row:
    cursor = await db.execute("SELECT * FROM matches WHERE match_code = ?", (match_code,))
    row = await cursor.fetchone()
    await cursor.close()
    if not row:
        raise not_found("MATCH_NOT_FOUND", "المباراة غير موجودة.")
    return row


async def _load_tile(db: aiosqlite.Connection, match_id: int, tile_key: str) -> sqlite3.Row:
    cursor = await db.execute(TILE_SELECT + " AND mt.tile_key = ?", (match_id, tile_key))
    row = await cursor.fetchone()
    await cursor.close()
    if not row:
        raise not_found("TILE_NOT_FOUND", "الخانة غير موجودة في هالمباراة.")
    return row


def _draft_order(first_team: str) -> list[str]:
    second = _other(first_team)
    return [first_team, second, second, first_team, first_team, second]


async def _draft_out(db: aiosqlite.Connection, match: sqlite3.Row) -> dict:
    cursor = await db.execute(
        """
        SELECT team_key, power_id, pick_index, drafted_at, used_at, used_tile_key
        FROM match_powers WHERE match_id = ? ORDER BY pick_index
        """,
        (match["id"],),
    )
    rows = await cursor.fetchall()
    await cursor.close()
    order = _draft_order(match["coin_toss_winner"])
    picks = [
        {
            "team": row["team_key"],
            "power_id": row["power_id"],
            "pick_index": int(row["pick_index"]),
            "drafted_at": row["drafted_at"],
            "used_at": row["used_at"],
            "used_tile_key": row["used_tile_key"],
        }
        for row in rows
    ]
    complete = len(picks) >= DRAFT_PICK_COUNT
    return {
        "order": order,
        "picks": picks,
        "current_team": None if complete else order[len(picks)],
        "complete": complete,
        "remaining": max(0, DRAFT_PICK_COUNT - len(picks)),
    }


async def _participants_out(db: aiosqlite.Connection, match_id: int) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT p.team_key, u.id, u.username, u.display_name, u.kind
        FROM match_participants p JOIN users u ON u.id = p.user_id
        WHERE p.match_id = ? ORDER BY p.team_key, u.id
        """,
        (match_id,),
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return [
        {
            "user_id": int(row["id"]),
            "username": row["username"],
            "display_name": row["display_name"],
            "kind": row["kind"],
            "team": row["team_key"],
        }
        for row in rows
    ]


async def _board(db: aiosqlite.Connection, match_code: str) -> dict:
    match = await _load_match(db, match_code)
    cursor = await db.execute(
        TILE_SELECT + " ORDER BY mt.is_backup ASC, mt.tile_key ASC",
        (match["id"],),
    )
    rows = await cursor.fetchall()
    await cursor.close()
    tiles = [_tile_out(row) for row in rows if not row["is_backup"]]
    backups = [_tile_out(row) for row in rows if row["is_backup"]]
    return {
        "match": _match_out(match),
        "tiles": tiles,
        "backups": backups,
        "draft": await _draft_out(db, match),
        "participants": await _participants_out(db, int(match["id"])),
    }


def _hash_payload(scope: str, payload: dict) -> str:
    encoded = json.dumps(
        {"scope": scope, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _redact_cached_answers(value: Any) -> None:
    """Upgrade old idempotency snapshots without revealing later game state.

    Existing caches can predate server-side answer separation. Use the snapshot's
    reveal state rather than today's tile state, preserving replay semantics.
    """
    if isinstance(value, list):
        for item in value:
            _redact_cached_answers(item)
    elif isinstance(value, dict):
        question = value.get("question")
        if isinstance(question, dict) and not (value.get("revealed_at") or value.get("status") == "played"):
            for key in list(question):
                if key in {"answer_text", "tolerance", "explanation", "fact_group_id"} or key.startswith("source_"):
                    question[key] = None
            raw = question.get("payload")
            if isinstance(raw, dict) and raw.get("kind") == "matchstick":
                for key in ("solution", "end", "moves"):
                    raw.pop(key, None)
            visual = question.get("visual")
            if isinstance(visual, dict):
                # Public snapshots already omit private labels. Reinsert harmless
                # placeholders solely for structural validation, then project again.
                if visual.get("type") == "career_tree" and isinstance(visual.get("nodes"), list):
                    for node in visual["nodes"]:
                        if isinstance(node, dict) and node.get("hidden"):
                            node["label"] = "?"
                if visual.get("type") == "lineup_svg" and isinstance(visual.get("players"), list):
                    for index, player in enumerate(visual["players"]):
                        if isinstance(player, dict) and player.get("hidden"):
                            player["label"] = f"?{index}"
                if visual.get("type") == "odd_one_out_grid":
                    visual.setdefault("odd_index", 0)
                    visual.setdefault("common_property", "?")
                question["visual"] = public_visual(visual)
        for item in value.values():
            _redact_cached_answers(item)


async def _idempotent_replay(
    db: aiosqlite.Connection, scope: str, key: str, request_hash: str
) -> dict | None:
    cursor = await db.execute(
        "SELECT request_hash, status_code, response_json FROM idempotency_keys WHERE scope = ? AND key = ?",
        (scope, key),
    )
    row = await cursor.fetchone()
    await cursor.close()
    if not row:
        return None
    if row["request_hash"] != request_hash:
        raise conflict("IDEMPOTENCY_KEY_REUSED", "نفس مفتاح التكرار استُخدم بطلب مختلف.")
    payload = json.loads(row["response_json"])
    _redact_cached_answers(payload)
    payload["idempotent_replay"] = True
    return payload


async def _store_idempotent(
    db: aiosqlite.Connection,
    scope: str,
    key: str,
    request_hash: str,
    status_code: int,
    response: dict,
) -> None:
    await db.execute(
        """
        INSERT INTO idempotency_keys(scope, key, request_hash, status_code, response_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (scope, key, request_hash, status_code, json.dumps(response, ensure_ascii=False)),
    )


async def _event(
    db: aiosqlite.Connection,
    match_id: int,
    event_type: str,
    request_key: str | None,
    payload: dict,
) -> None:
    await db.execute(
        """
        INSERT INTO match_events(match_id, event_type, request_key, payload_json)
        VALUES (?, ?, ?, ?)
        """,
        (match_id, event_type, request_key, json.dumps(payload, ensure_ascii=False)),
    )


async def _selected_categories(
    db: aiosqlite.Connection, slugs: list[str]
) -> list[dict]:
    cursor = await db.execute(
        "SELECT id, slug, name_ar FROM categories WHERE slug IN ("
        + ",".join("?" for _ in slugs)
        + ")",
        tuple(slugs),
    )
    rows = await cursor.fetchall()
    await cursor.close()
    by_slug = {row["slug"]: dict(row) for row in rows}
    missing = [slug for slug in slugs if slug not in by_slug]
    if missing:
        raise conflict(
            "UNKNOWN_CATEGORY",
            "في فئة غير معروفة بالطلب.",
            categories=missing,
        )
    return [by_slug[slug] for slug in slugs]


async def _insert_allocation(
    db: aiosqlite.Connection,
    *,
    match_id: int,
    allocation: Allocation,
) -> None:
    for index, question_id in enumerate(allocation.primary_ids, start=1):
        await db.execute(
            """
            INSERT INTO match_tiles(
                match_id, tile_key, category_id, difficulty, question_id,
                is_backup, status, allocation_cycle
            ) VALUES (?, ?, ?, ?, ?, 0, 'unplayed', ?)
            """,
            (
                match_id,
                f"{allocation.slug}-{allocation.difficulty}-{index}",
                allocation.category_id,
                allocation.difficulty,
                question_id,
                allocation.cycle,
            ),
        )
    await db.execute(
        """
        INSERT INTO match_tiles(
            match_id, tile_key, category_id, difficulty, question_id, is_backup,
            status, compatible_categories_json, compatible_difficulties_json,
            allocation_cycle
        ) VALUES (?, ?, ?, ?, ?, 1, 'unplayed', ?, ?, ?)
        """,
        (
            match_id,
            f"backup-{allocation.slug}-{allocation.difficulty}",
            allocation.category_id,
            allocation.difficulty,
            allocation.backup_id,
            json.dumps([allocation.slug], ensure_ascii=False),
            json.dumps([allocation.difficulty]),
            allocation.cycle,
        ),
    )


async def create_match(
    settings: Settings,
    payload: MatchCreateIn,
    idempotency_key: str,
    *,
    rng: random.Random | None = None,
    host_installation_id: int | None = None,
    host_user_id: int | None = None,
) -> dict:
    try:
        team1 = normalize_team_name(payload.team1_name, settings.max_team_name_length)
        team2 = normalize_team_name(payload.team2_name, settings.max_team_name_length)
    except ValueError as exc:
        raise bad_request("INVALID_TEAM_NAME", str(exc)) from exc
    if team1 == team2:
        raise bad_request("DUPLICATE_TEAM_NAMES", "أسماء الفريقين لازم تكون مختلفة.")

    slugs = [slug.strip() for slug in payload.category_slugs]
    if len(set(slugs)) != SELECTED_CATEGORY_COUNT:
        raise bad_request(
            "INVALID_CATEGORY_SELECTION",
            "لازم تختار ست فئات مختلفة بالضبط.",
            selected=slugs,
        )
    if host_installation_id is None:
        raise forbidden(
            "INSTALL_TOKEN_REQUIRED",
            "إنشاء المباراة يتطلب ترويسة X-Install-Token لربط التثبيت المضيف.",
        )
    team1_ids = _clean_team_participants(payload.team1_user_ids, "team1")
    team2_ids = _clean_team_participants(payload.team2_user_ids, "team2")
    overlap = set(team1_ids) & set(team2_ids)
    if overlap:
        raise conflict(
            "PARTICIPANT_TEAM_CONFLICT",
            "مشارك لا يمكن أن يكون في الفريقين معًا.",
            user_ids=sorted(overlap),
        )

    random_source = rng or random.Random()
    starting_turn = payload.starting_turn or payload.coin_toss_winner or random_source.choice(
        ["team1", "team2"]
    )
    scope = "create_match"
    request_hash = _hash_payload(
        scope,
        {
            "team1_name": team1,
            "team2_name": team2,
            "starting_turn": starting_turn,
            "category_slugs": slugs,
            "team1_user_ids": team1_ids,
            "team2_user_ids": team2_ids,
            "host_installation_id": host_installation_id,
            "host_user_id": host_user_id,
        },
    )

    async with transaction(settings) as db:
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay

        categories = await _selected_categories(db, slugs)
        if len(categories) != SELECTED_CATEGORY_COUNT:
            raise conflict(
                "CATEGORIES_NOT_SEEDED",
                "الفئات غير مكتملة على الخادم. شغّل seed_data.py أولًا.",
            )

        match_code = secrets.token_urlsafe(12)
        while True:
            cursor = await db.execute("SELECT 1 FROM matches WHERE match_code = ?", (match_code,))
            exists = await cursor.fetchone()
            await cursor.close()
            if not exists:
                break
            match_code = secrets.token_urlsafe(12)

        cursor = await db.execute(
            "SELECT shadow_user_id FROM device_installations WHERE id = ?",
            (host_installation_id,),
        )
        installation = await cursor.fetchone()
        await cursor.close()
        if not installation:
            raise conflict(
                "INSTALL_TOKEN_INVALID",
                "التثبيت المضيف غير معروف.",
            )
        participant_ids = await validate_participant_ids(db, team1_ids + team2_ids)
        if host_user_id is not None:
            cursor = await db.execute(
                'SELECT id FROM users WHERE id = ? AND password_hash IS NOT NULL AND is_active = 1',
                (host_user_id,),
            )
            if await cursor.fetchone() is None:
                raise forbidden('ACCOUNT_INVALID', 'الحساب غير متاح.')
            await cursor.close()
        host_identity = host_user_id if host_user_id is not None else int(installation['shadow_user_id'])
        effective_ids = sorted(set(participant_ids + [host_identity]))
        if not effective_ids:
            raise conflict(
                "EMPTY_IDENTITY_SET",
                "تعذّر تحديد أي هوية فعلية للمباراة.",
            )

        host_token = secrets.token_urlsafe(32)
        cursor = await db.execute(
            """
            INSERT INTO matches(
                match_code, team1_name, team2_name, current_turn, coin_toss_winner,
                status, version, selected_categories_json, host_token_hash,
                host_installation_id, host_user_id
            ) VALUES (?, ?, ?, ?, ?, 'active', 1, ?, ?, ?, ?)
            """,
            (
                match_code,
                team1,
                team2,
                starting_turn,
                starting_turn,
                json.dumps(slugs, ensure_ascii=False),
                _hash_host_token(host_token),
                host_installation_id,
                host_user_id,
            ),
        )
        match_id = int(cursor.lastrowid)
        await cursor.close()
        for user_id in team1_ids:
            await db.execute(
                "INSERT INTO match_participants(match_id, user_id, team_key)"
                " VALUES (?, ?, 'team1')",
                (match_id, user_id),
            )
        for user_id in team2_ids:
            await db.execute(
                "INSERT INTO match_participants(match_id, user_id, team_key)"
                " VALUES (?, ?, 'team2')",
                (match_id, user_id),
            )

        allocation = await allocate_match(
            db,
            settings,
            categories=categories,
            salt=f"{settings.seed_random_seed}:{idempotency_key}",
            excluded_user_ids=tuple(effective_ids),
        )
        for bucket in allocation.allocations:
            await _insert_allocation(db, match_id=match_id, allocation=bucket)

        await _event(
            db,
            match_id,
            "match_created",
            idempotency_key,
            {
                "starting_turn": starting_turn,
                "team1_name": team1,
                "team2_name": team2,
                "category_slugs": slugs,
                "cooldown_relaxations": allocation.relaxations,
                "team1_user_ids": team1_ids,
                "team2_user_ids": team2_ids,
                "effective_identity_count": len(effective_ids),
                "host_installation_id": host_installation_id,
            },
        )
        board = await _board(db, match_code)
        response = {
            "match": board["match"],
            "tiles": board["tiles"],
            "backups": board["backups"],
            "draft": board["draft"],
            "participants": board["participants"],
            # يُكشف مرة واحدة فقط عند الإنشاء؛ القراءات اللاحقة لا تعيده أبدًا.
            "host_token": host_token,
        }
        await _store_idempotent(db, scope, idempotency_key, request_hash, 201, response)
        return response


async def get_match(settings: Settings, match_code: str) -> dict:
    async with connect(settings) as db:
        return await _board(db, match_code)


async def _db_now(db: aiosqlite.Connection) -> str:
    cursor = await db.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now') AS now")
    row = await cursor.fetchone()
    await cursor.close()
    return row["now"]


async def _elapsed_ms(db: aiosqlite.Connection, opened_at: str | None) -> int:
    if not opened_at:
        return 0
    cursor = await db.execute(
        "SELECT (julianday('now') - julianday(?)) * 86400000.0 AS ms",
        (opened_at,),
    )
    row = await cursor.fetchone()
    await cursor.close()
    return max(0, int(round(float(row["ms"] or 0))))


def _session_out(row: sqlite3.Row) -> dict:
    return {
        "opened_at": row["opened_at"],
        "revealed_at": row["revealed_at"],
        "active_team": row["active_team"],
        "noise_until": row["noise_until"],
    }


async def draft_power(
    settings: Settings,
    match_code: str,
    *,
    power_id: str,
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    """تسجيل اختيار واحد بترتيب السحب الثعباني على الخادم."""
    scope = f"draft:{match_code}"
    request_hash = _hash_payload(
        scope, {"power_id": power_id, "expected_version": expected_version}
    )
    if power_id not in DRAFTABLE_POWER_IDS:
        raise bad_request("UNKNOWN_POWER", "في قوة غير معروفة بالطلب.", power=power_id)

    async with transaction(settings) as db:
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        draft = await _draft_out(db, match)
        if draft["complete"]:
            raise conflict("DRAFT_COMPLETE", "السحب مكتمل؛ ما في اختيار إضافي.")
        team = draft["current_team"]
        cursor = await db.execute(
            "SELECT 1 FROM match_powers WHERE match_id = ? AND team_key = ? AND power_id = ?",
            (match["id"], team, power_id),
        )
        already = await cursor.fetchone()
        await cursor.close()
        if already:
            raise conflict(
                "POWER_ALREADY_DRAFTED",
                "هالقوة انسحبت من قبل لنفس الفريق.",
                team=team,
                power=power_id,
            )
        pick_index = len(draft["picks"])
        await db.execute(
            """
            INSERT INTO match_powers(match_id, team_key, power_id, pick_index)
            VALUES (?, ?, ?, ?)
            """,
            (match["id"], team, power_id, pick_index),
        )
        await db.execute(
            "UPDATE matches SET version = version + 1,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (match["id"],),
        )
        await _event(
            db,
            int(match["id"]),
            "power_drafted",
            f"draft:{idempotency_key}",
            {"team": team, "power_id": power_id, "pick_index": pick_index},
        )
        updated_match = await _load_match(db, match_code)
        updated_draft = await _draft_out(db, updated_match)
        pick = next(
            item for item in updated_draft["picks"] if item["pick_index"] == pick_index
        )
        response = {
            "match": _match_out(updated_match),
            "draft": updated_draft,
            "pick": pick,
            "idempotent_replay": False,
        }
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def _load_active_for_update(
    db: aiosqlite.Connection, match_code: str, expected_version: int
) -> sqlite3.Row:
    match = await _load_match(db, match_code)
    if match["status"] != "active":
        raise conflict("MATCH_NOT_ACTIVE", "المباراة منتهية أو متروكة.", status=match["status"])
    if int(match["version"]) != int(expected_version):
        raise conflict(
            "STALE_MATCH_VERSION",
            "نسخة المباراة تغيّرت؛ حدّث الحالة قبل المحاولة.",
            expected_version=expected_version,
            current_version=int(match["version"]),
        )
    return match


async def open_tile(
    settings: Settings,
    match_code: str,
    tile_key: str,
    *,
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    """يفتح جلسة سؤال على الخادم حتى تُحسب نوافذ القوى من ساعة الخادم."""
    scope = f"open:{match_code}:{tile_key}"
    request_hash = _hash_payload(scope, {"expected_version": expected_version})
    async with transaction(settings) as db:
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        tile = await _load_tile(db, int(match["id"]), tile_key)
        if tile["is_backup"]:
            raise bad_request("TILE_NOT_PLAYABLE", "صفوف الاحتياط ما تُفتح كخانات أساسية.")
        if tile["status"] != "unplayed":
            raise conflict("TILE_ALREADY_PLAYED", "هالخانة انلعبت أو انستبدلت من قبل.")
        if tile["opened_at"] and not tile["revealed_at"]:
            raise conflict("TILE_ALREADY_OPEN", "هالخانة مفتوحة بالفعل.")
        cursor = await db.execute(
            """
            SELECT tile_key FROM match_tiles
            WHERE match_id = ? AND is_backup = 0 AND status = 'unplayed'
              AND opened_at IS NOT NULL AND revealed_at IS NULL
            LIMIT 1
            """,
            (match["id"],),
        )
        other_open = await cursor.fetchone()
        await cursor.close()
        if other_open and other_open["tile_key"] != tile_key:
            raise conflict(
                "ANOTHER_TILE_OPEN",
                "في سؤال مفتوح بالمباراة. أظهروا إجابته أو اتركوها أولًا.",
                tile_key=other_open["tile_key"],
            )
        now = await _db_now(db)
        await db.execute(
            """
            UPDATE match_tiles
            SET opened_at = ?, revealed_at = NULL, active_team = ?,
                noise_until = NULL, powers_applied_json = NULL, answered_at = NULL
            WHERE match_id = ? AND tile_key = ?
            """,
            (now, match["current_turn"], match["id"], tile_key),
        )
        # لحظة الظهور الموثوق: يُسجَّل التعرّض لكل الهويات الفعلية هنا،
        # لا عند الحجز ولا عند الحسم.
        await record_exposures(
            db,
            await effective_user_ids(db, int(match["id"])),
            int(tile["question_id"]),
            int(match["id"]),
        )
        await db.execute(
            "UPDATE matches SET version = version + 1,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (match["id"],),
        )
        await _event(
            db,
            int(match["id"]),
            "tile_opened",
            f"open:{idempotency_key}",
            {
                "tile_key": tile_key,
                "active_team": match["current_turn"],
                "question_id": int(tile["question_id"]),
            },
        )
        updated_match = await _load_match(db, match_code)
        updated_tile = await _load_tile(db, int(match["id"]), tile_key)
        response = {
            "match": _match_out(updated_match),
            "tile": _tile_out(updated_tile),
            "session": _session_out(updated_tile),
            "idempotent_replay": False,
        }
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def reveal_tile(
    settings: Settings,
    match_code: str,
    tile_key: str,
    *,
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    """يوقف نافذة القوى على الخادم بإظهار الإجابة."""
    scope = f"reveal:{match_code}:{tile_key}"
    request_hash = _hash_payload(scope, {"expected_version": expected_version})
    async with transaction(settings) as db:
        # A cached reveal contains the answer too; authenticate before replay.
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        tile = await _load_tile(db, int(match["id"]), tile_key)
        if tile["is_backup"] or tile["status"] != "unplayed":
            raise conflict("TILE_NOT_PLAYABLE", "هالخانة مو قابلة للعب.")
        if not tile["opened_at"]:
            raise conflict("TILE_NOT_OPEN", "افتحوا الخانة قبل إظهار الإجابة.")
        if tile["revealed_at"]:
            raise conflict("QUESTION_ALREADY_REVEALED", "الإجابة ظاهرة بالفعل.")
        now = await _db_now(db)
        await db.execute(
            "UPDATE match_tiles SET revealed_at = ? WHERE match_id = ? AND tile_key = ?",
            (now, match["id"], tile_key),
        )
        await db.execute(
            "UPDATE matches SET version = version + 1,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (match["id"],),
        )
        await _event(
            db,
            int(match["id"]),
            "tile_revealed",
            f"reveal:{idempotency_key}",
            {"tile_key": tile_key},
        )
        updated_match = await _load_match(db, match_code)
        updated_tile = await _load_tile(db, int(match["id"]), tile_key)
        response = {
            "match": _match_out(updated_match),
            "tile": _tile_out(updated_tile),
            "session": _session_out(updated_tile),
            "idempotent_replay": False,
        }
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def abandon_tile(
    settings: Settings,
    match_code: str,
    tile_key: str,
    *,
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    """يغلق جلسة السؤال دون لعب الخانة ودون استهلاك القوى المفعّلة."""
    scope = f"abandon-tile:{match_code}:{tile_key}"
    request_hash = _hash_payload(scope, {"expected_version": expected_version})
    async with transaction(settings) as db:
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        tile = await _load_tile(db, int(match["id"]), tile_key)
        if tile["is_backup"] or tile["status"] != "unplayed":
            raise conflict("TILE_NOT_PLAYABLE", "هالخانة مو قابلة للعب.")
        if not tile["opened_at"]:
            raise conflict("TILE_NOT_OPEN", "ما في جلسة سؤال مفتوحة.")
        await db.execute(
            """
            UPDATE match_tiles
            SET opened_at = NULL, revealed_at = NULL, active_team = NULL,
                noise_until = NULL, powers_applied_json = NULL
            WHERE match_id = ? AND tile_key = ?
            """,
            (match["id"], tile_key),
        )
        await db.execute(
            "UPDATE matches SET version = version + 1,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (match["id"],),
        )
        await _event(
            db,
            int(match["id"]),
            "tile_abandoned",
            f"abandon-tile:{idempotency_key}",
            {"tile_key": tile_key},
        )
        updated_match = await _load_match(db, match_code)
        updated_tile = await _load_tile(db, int(match["id"]), tile_key)
        response = {
            "match": _match_out(updated_match),
            "tile": _tile_out(updated_tile),
            "idempotent_replay": False,
        }
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def activate_power(
    settings: Settings,
    match_code: str,
    tile_key: str,
    power_id: str,
    *,
    team: str,
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    """يفعّل قوة يملكها الفريق داخل نافذتها الزمنية على الخادم."""
    scope = f"power:{match_code}:{tile_key}:{power_id}:{team}"
    request_hash = _hash_payload(
        scope, {"team": team, "power_id": power_id, "expected_version": expected_version}
    )
    if power_id not in POWER_SIDES:
        raise bad_request("UNKNOWN_POWER", "في قوة غير معروفة بالطلب.", power=power_id)
    if team not in {"team1", "team2"}:
        raise bad_request("INVALID_TEAM", "الفريق لازم يكون team1 أو team2.")

    async with transaction(settings) as db:
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        tile = await _load_tile(db, int(match["id"]), tile_key)
        if tile["is_backup"] or tile["status"] != "unplayed":
            raise conflict("TILE_NOT_PLAYABLE", "هالخانة مو قابلة للعب.")
        if not tile["opened_at"]:
            raise conflict("TILE_NOT_OPEN", "افتحوا الخانة قبل تفعيل القوة.")
        if tile["revealed_at"]:
            raise conflict("QUESTION_REVEALED", "ما تنفع القوى بعد إظهار الإجابة.")

        cursor = await db.execute(
            """
            SELECT power_id, used_at FROM match_powers
            WHERE match_id = ? AND team_key = ? AND power_id = ?
            """,
            (match["id"], team, power_id),
        )
        owned = await cursor.fetchone()
        await cursor.close()
        if not owned:
            raise conflict(
                "POWER_NOT_OWNED",
                "هالقوة مو من اختيار هالفريق بهالمباراة.",
                team=team,
                power=power_id,
            )
        if owned["used_at"]:
            raise conflict(
                "POWER_ALREADY_USED",
                "هالقوة استُخدمت من قبل بهالمباراة.",
                team=team,
                power=power_id,
            )

        active_team = tile["active_team"] or match["current_turn"]
        side = POWER_SIDES[power_id]
        if (side == "active" and team != active_team) or (
            side == "defending" and team == active_team
        ):
            raise conflict(
                "POWER_SIDE_NOT_ALLOWED",
                "هالقوة للفريق الآخر في هالسؤال.",
                team=team,
                active_team=active_team,
                power=power_id,
            )

        elapsed_ms = await _elapsed_ms(db, tile["opened_at"])
        if power_id == "switch" and elapsed_ms > SWITCH_WINDOW_MS:
            raise conflict(
                "POWER_WINDOW_CLOSED",
                "مرّت أول 15 ثانية من السؤال، ما تقدر تبدّل الميدان.",
                elapsed_ms=elapsed_ms,
                window_ms=SWITCH_WINDOW_MS,
            )
        if power_id == "noise" and tile["noise_until"]:
            cursor = await db.execute(
                "SELECT (julianday(?) - julianday('now')) * 86400.0 AS seconds",
                (tile["noise_until"],),
            )
            remaining = float((await cursor.fetchone())["seconds"] or 0)
            await cursor.close()
            if remaining > 0:
                raise conflict("POWER_ALREADY_ACTIVE", "التشويش شغّال بالفعل.")

        now = await _db_now(db)
        backup_used = None
        switched = False
        if power_id == "switch":
            cursor = await db.execute(
                """
                SELECT tile_key, question_id FROM match_tiles
                WHERE match_id = ? AND is_backup = 1 AND status = 'unplayed'
                  AND category_id = ? AND difficulty = ?
                ORDER BY tile_key LIMIT 1
                """,
                (match["id"], tile["tile_category_id"], tile["tile_difficulty"]),
            )
            backup = await cursor.fetchone()
            await cursor.close()
            if not backup:
                raise conflict("BACKUP_EXHAUSTED", "ما بقى سؤال احتياطي متوافق لهذه الخانة.")
            await db.execute(
                """
                UPDATE match_tiles
                SET question_id = ?, rerolled_from_question_id = ?
                WHERE match_id = ? AND tile_key = ?
                """,
                (backup["question_id"], tile["question_id"], match["id"], tile_key),
            )
            await db.execute(
                "UPDATE match_tiles SET status = 'rerolled',"
                " answered_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')"
                " WHERE match_id = ? AND tile_key = ?",
                (match["id"], backup["tile_key"]),
            )
            backup_used = backup["tile_key"]
            switched = True

        powers = _json_list(tile["powers_applied_json"])
        if power_id not in powers:
            powers.append(power_id)
        next_active_team = team if power_id == "steal" else active_team
        noise_until = tile["noise_until"]
        if power_id == "noise":
            cursor = await db.execute(
                "SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now',?) AS until",
                (f"+{NOISE_SECONDS} seconds",),
            )
            noise_until = (await cursor.fetchone())["until"]
            await cursor.close()
        if switched:
            noise_until = None

        await db.execute(
            """
            UPDATE match_tiles
            SET powers_applied_json = ?, active_team = ?, noise_until = ?,
                opened_at = ?, revealed_at = NULL
            WHERE match_id = ? AND tile_key = ?
            """,
            (
                json.dumps(powers, ensure_ascii=False),
                next_active_team,
                noise_until,
                now if switched else tile["opened_at"],
                match["id"],
                tile_key,
            ),
        )
        if switched:
            # سؤال التبديل ظاهر فورًا فيُسجَّل تعرّضه؛ القديم سُجِّل عند فتحه.
            await record_exposures(
                db,
                await effective_user_ids(db, int(match["id"])),
                int(backup["question_id"]),
                int(match["id"]),
            )
        await db.execute(
            """
            UPDATE match_powers SET used_at = ?, used_tile_key = ?
            WHERE match_id = ? AND team_key = ? AND power_id = ?
            """,
            (now, tile_key, match["id"], team, power_id),
        )
        await db.execute(
            "UPDATE matches SET version = version + 1,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (match["id"],),
        )
        activation = {
            "power_id": power_id,
            "team": team,
            "activated_at": now,
            "elapsed_ms": elapsed_ms,
            "active_team": next_active_team,
            "noise_until": noise_until,
            "switched": switched,
        }
        await _event(
            db,
            int(match["id"]),
            "power_activated",
            f"power:{idempotency_key}",
            {
                "tile_key": tile_key,
                **activation,
                "backup_used": backup_used,
            },
        )
        updated_match = await _load_match(db, match_code)
        updated_tile = await _load_tile(db, int(match["id"]), tile_key)
        response = {
            "match": _match_out(updated_match),
            "tile": _tile_out(updated_tile),
            "activation": activation,
            "backup_used": backup_used,
            "idempotent_replay": False,
        }
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def resolve_tile(
    settings: Settings,
    match_code: str,
    tile_key: str,
    *,
    outcome: str,
    powers_applied: list[str],
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    scope = f"resolve:{match_code}:{tile_key}"
    request_hash = _hash_payload(
        scope,
        {
            "outcome": outcome,
            "powers_applied": powers_applied,
            "expected_version": expected_version,
        },
    )
    unknown = set(powers_applied) - POWER_IDS
    if unknown:
        raise bad_request("UNKNOWN_POWER", "في قوة غير معروفة بالطلب.", powers=sorted(unknown))

    async with transaction(settings) as db:
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        tile = await _load_tile(db, int(match["id"]), tile_key)
        if tile["is_backup"]:
            raise bad_request("TILE_NOT_PLAYABLE", "صفوف الاحتياط ما تُلعب كخانات أساسية.")
        if tile["status"] != "unplayed":
            raise conflict("TILE_ALREADY_PLAYED", "هالخانة انلعبت أو انستبدلت من قبل.")
        if outcome not in {"team1", "team2", "none"}:
            raise bad_request("INVALID_OUTCOME", "النتيجة لازم تكون team1 أو team2 أو none.")

        # القوى المطبّقة تأتي من سجل التفعيل على الخادم، لا من جسم الطلب.
        server_powers = _json_list(tile["powers_applied_json"])
        if sorted(set(powers_applied)) != sorted(set(server_powers)):
            raise conflict(
                "POWERS_MISMATCH",
                "القوى المرسلة لا تطابق تفعيلات الخادم.",
                requested=sorted(set(powers_applied)),
                activated=sorted(set(server_powers)),
            )
        powers_applied = server_powers

        active_team = match["current_turn"]
        defending_team = _other(active_team)
        scoring = compute_score_deltas(
            base_points=int(tile["tile_difficulty"]),
            outcome=outcome,
            active_team=active_team,
            defending_team=defending_team,
            active_powers=powers_applied,
        )
        delta1 = int(scoring["deltas"]["team1"])
        delta2 = int(scoring["deltas"]["team2"])
        new_score1 = int(match["score_team1"]) + delta1
        new_score2 = int(match["score_team2"]) + delta2

        resolved_request_id = f"resolve:{tile_key}:{idempotency_key}"
        await db.execute(
            """
            UPDATE match_tiles
            SET status = 'played', outcome = ?, delta_team1 = ?, delta_team2 = ?,
                powers_applied_json = ?, answered_at = strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                opened_at = NULL, revealed_at = NULL, active_team = NULL,
                noise_until = NULL, resolved_request_id = ?
            WHERE match_id = ? AND tile_key = ?
            """,
            (
                outcome,
                delta1,
                delta2,
                json.dumps(powers_applied, ensure_ascii=False),
                resolved_request_id,
                match["id"],
                tile_key,
            ),
        )

        # الاستخدام يُسجَّل بدورة الحجز نفسها، لا بالدورة الحالية للدلو، حتى لا
        # يفتح استنفاد دلو آخر الباب لإعادة السؤال داخل دورته الأصلية.
        cycle = int(tile["allocation_cycle"])
        await db.execute(
            "INSERT INTO question_usage(question_id, cycle) VALUES (?, ?)"
            " ON CONFLICT(question_id, cycle) DO NOTHING",
            (tile["question_id"], cycle),
        )
        await db.execute(
            """
            UPDATE questions
            SET times_played = times_played + 1, last_played_match_id = ?
            WHERE id = ?
            """,
            (match["id"], tile["question_id"]),
        )
        # نتيجة التعرّض تُحدَّث عند الحسم؛ صفوف الأسئلة المستبدلة مسبقًا
        # تبقى 'none' (ظهرت دون حسم) وهو السلوك الموثق.
        await update_exposure_outcomes(
            db,
            await effective_user_ids(db, int(match["id"])),
            int(tile["question_id"]),
            int(match["id"]),
            outcome,
        )

        played_cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM match_tiles WHERE match_id = ? AND is_backup = 0 AND status = 'played'",
            (match["id"],),
        )
        played = int((await played_cursor.fetchone())["n"])
        await played_cursor.close()
        next_status = "completed" if played >= PRIMARY_TILE_COUNT else "active"
        winner = None
        if next_status == "completed":
            if new_score1 > new_score2:
                winner = "team1"
            elif new_score2 > new_score1:
                winner = "team2"
            else:
                winner = "tie"

        await db.execute(
            """
            UPDATE matches
            SET score_team1 = ?, score_team2 = ?, current_turn = ?, status = ?,
                winner = ?, version = version + 1,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE id = ?
            """,
            (
                new_score1,
                new_score2,
                _other(active_team),
                next_status,
                winner,
                match["id"],
            ),
        )

        await _event(
            db,
            int(match["id"]),
            "tile_resolved",
            resolved_request_id,
            {
                "tile_key": tile_key,
                "question_id": int(tile["question_id"]),
                "outcome": outcome,
                "active_team": active_team,
                "powers_applied": powers_applied,
                "deltas": scoring["deltas"],
                "ledger": scoring["ledger"],
                "score_team1": new_score1,
                "score_team2": new_score2,
            },
        )
        updated_match = await _load_match(db, match_code)
        updated_tile = await _load_tile(db, int(match["id"]), tile_key)
        response = {
            "match": _match_out(updated_match),
            "tile": _tile_out(updated_tile),
            "score_ledger": scoring["ledger"],
            "idempotent_replay": False,
        }
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def reroll_tile(
    settings: Settings,
    match_code: str,
    tile_key: str,
    *,
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    scope = f"reroll:{match_code}:{tile_key}"
    request_hash = _hash_payload(scope, {"expected_version": expected_version})
    async with transaction(settings) as db:
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        tile = await _load_tile(db, int(match["id"]), tile_key)
        if tile["is_backup"]:
            raise bad_request("TILE_NOT_PLAYABLE", "لا يمكن استبدال صف احتياطي.")
        if tile["status"] != "unplayed":
            raise conflict("TILE_ALREADY_PLAYED", "الخانة انلعبت، ما نقدر نبدّل سؤالها.")

        cursor = await db.execute(
            """
            SELECT tile_key, question_id, allocation_cycle
            FROM match_tiles
            WHERE match_id = ? AND is_backup = 1 AND status = 'unplayed'
              AND category_id = ? AND difficulty = ?
            ORDER BY tile_key
            LIMIT 1
            """,
            (match["id"], tile["tile_category_id"], tile["tile_difficulty"]),
        )
        chosen = await cursor.fetchone()
        await cursor.close()
        if not chosen:
            raise conflict("BACKUP_EXHAUSTED", "ما بقى سؤال احتياطي متوافق لهذه الخانة.")

        old_question_id = int(tile["question_id"])
        was_open = tile["opened_at"] is not None
        await db.execute(
            """
            UPDATE match_tiles
            SET question_id = ?, rerolled_from_question_id = ?,
                outcome = NULL, delta_team1 = 0, delta_team2 = 0,
                powers_applied_json = NULL, answered_at = NULL,
                opened_at = strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                revealed_at = NULL, active_team = ?, noise_until = NULL
            WHERE match_id = ? AND tile_key = ?
            """,
            (chosen["question_id"], old_question_id, match["current_turn"], match["id"], tile_key),
        )
        # السؤال الجديد ظاهر فورًا فيُسجَّل؛ القديم يُسجَّل فقط إن كان مفتوحًا
        # (ظهر فعلًا)، وإلا بقي مجرد حجز غير مرئي.
        identities = await effective_user_ids(db, int(match["id"]))
        if was_open and int(chosen["question_id"]) != old_question_id:
            await record_exposures(db, identities, old_question_id, int(match["id"]))
        await record_exposures(
            db, identities, int(chosen["question_id"]), int(match["id"])
        )
        await db.execute(
            """
            UPDATE match_tiles
            SET status = 'rerolled',
                answered_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE match_id = ? AND tile_key = ?
            """,
            (match["id"], chosen["tile_key"]),
        )
        await db.execute(
            "UPDATE matches SET version = version + 1,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (match["id"],),
        )
        await _event(
            db,
            int(match["id"]),
            "tile_rerolled",
            f"reroll:{tile_key}:{idempotency_key}",
            {
                "tile_key": tile_key,
                "from_question_id": old_question_id,
                "to_question_id": int(chosen["question_id"]),
                "backup_tile": chosen["tile_key"],
            },
        )
        updated_match = await _load_match(db, match_code)
        updated_tile = await _load_tile(db, int(match["id"]), tile_key)
        response = {
            "match": _match_out(updated_match),
            "tile": _tile_out(updated_tile),
            "backup_used": chosen["tile_key"],
            "idempotent_replay": False,
        }
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def adjust_score(
    settings: Settings,
    match_code: str,
    *,
    team: str,
    delta: int,
    reason: str,
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    scope = f"adjust:{match_code}"
    request_hash = _hash_payload(
        scope,
        {"team": team, "delta": delta, "reason": reason, "expected_version": expected_version},
    )
    async with transaction(settings) as db:
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        if team not in {"team1", "team2"}:
            raise bad_request("INVALID_TEAM", "الفريق لازم يكون team1 أو team2.")
        if delta not in {-100, 100}:
            raise bad_request("INVALID_ADJUSTMENT", "التعديل اليدوي ±100 فقط.")
        column = "score_team1" if team == "team1" else "score_team2"
        await db.execute(
            f"UPDATE matches SET {column} = {column} + ?, version = version + 1,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (delta, match["id"]),
        )
        await db.execute(
            "INSERT INTO score_adjustments(match_id, request_id, team_key, delta, reason)"
            " VALUES (?, ?, ?, ?, ?)",
            (match["id"], idempotency_key, team, delta, reason),
        )
        await _event(
            db,
            int(match["id"]),
            "score_adjusted",
            f"adjust:{idempotency_key}",
            {"team": team, "delta": delta, "reason": reason},
        )
        updated = await _load_match(db, match_code)
        response = {
            "match": _match_out(updated),
            "adjustment": {
                "team": team,
                "delta": delta,
                "reason": reason,
                "request_id": idempotency_key,
            },
            "idempotent_replay": False,
        }
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def abandon_match(
    settings: Settings,
    match_code: str,
    *,
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    scope = f"abandon:{match_code}"
    request_hash = _hash_payload(scope, {"expected_version": expected_version})
    async with transaction(settings) as db:
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        # لا نستخدم الخانات غير الملعوبة، فتخرج تلقائيًا من حجز الاختيار لأن
        # استعلام الحجز يشترط matches.status = 'active'.
        await db.execute(
            "UPDATE matches SET status = 'abandoned', version = version + 1,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (match["id"],),
        )
        await _event(db, int(match["id"]), "match_abandoned", f"abandon:{idempotency_key}", {})
        updated = await _load_match(db, match_code)
        response = {"match": _match_out(updated), "idempotent_replay": False}
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def complete_match(
    settings: Settings,
    match_code: str,
    *,
    expected_version: int,
    idempotency_key: str,
    host_token: str | None = None,
) -> dict:
    scope = f"complete:{match_code}"
    request_hash = _hash_payload(scope, {"expected_version": expected_version})
    async with transaction(settings) as db:
        _verify_host(await _load_match(db, match_code), host_token)
        replay = await _idempotent_replay(db, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        match = await _load_active_for_update(db, match_code, expected_version)
        _verify_host(match, host_token)
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM match_tiles WHERE match_id = ? AND is_backup = 0 AND status = 'played'",
            (match["id"],),
        )
        played = int((await cursor.fetchone())["n"])
        await cursor.close()
        if played < PRIMARY_TILE_COUNT:
            raise conflict(
                "MATCH_NOT_COMPLETE",
                "ما تنتهي المباراة قبل لعب كل الخانات الـ36.",
                played=played,
                required=PRIMARY_TILE_COUNT,
            )
        winner = (
            "team1"
            if match["score_team1"] > match["score_team2"]
            else "team2"
            if match["score_team2"] > match["score_team1"]
            else "tie"
        )
        await db.execute(
            "UPDATE matches SET status = 'completed', winner = ?, version = version + 1,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (winner, match["id"]),
        )
        await _event(
            db, int(match["id"]), "match_completed", f"complete:{idempotency_key}", {"winner": winner}
        )
        updated = await _load_match(db, match_code)
        response = {"match": _match_out(updated), "idempotent_replay": False}
        await _store_idempotent(db, scope, idempotency_key, request_hash, 200, response)
        return response


async def list_events(
    settings: Settings, match_code: str, *, limit: int = 50, before_id: int | None = None
) -> dict:
    async with connect(settings) as db:
        match = await _load_match(db, match_code)
        params: list[Any] = [match["id"]]
        sql = "SELECT * FROM match_events WHERE match_id = ?"
        if before_id:
            sql += " AND id < ?"
            params.append(before_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        await cursor.close()
        events = []
        for row in rows:
            events.append(
                {
                    "id": int(row["id"]),
                    "event_type": row["event_type"],
                    "request_key": row["request_key"],
                    "payload": _json_or_none(row["payload_json"]) or {},
                    "created_at": row["created_at"],
                }
            )
        next_before = events[-1]["id"] if len(events) == limit else None
        return {"events": events, "next_before_id": next_before}
