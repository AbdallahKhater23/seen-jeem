"""مسارات /api/v1 العامة."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from ...config import Settings
from ...db import connect, database_ready, transaction
from ...models import (
    AdjustmentIn,
    AdjustmentResultOut,
    BoardCreateOut,
    BoardOut,
    CategoryOut,
    DraftPickIn,
    DraftResultOut,
    EventsOut,
    HealthOut,
    MatchCreateIn,
    MatchResultOut,
    PowerActivationIn,
    PowerActivationOut,
    QuestionOut,
    RerollIn,
    RerollResultOut,
    ResolveIn,
    ResolveResultOut,
    SyncJobOut,
    SyncStartOut,
    TileAbandonOut,
    TileOpenOut,
    TileRevealOut,
    VersionIn,
)
from ...schema import SCHEMA_VERSION
from ...services.content import CAPACITY_PER_BUCKET, CATEGORY_SLUGS, DIFFICULTIES
from ...services.identity import load_installation_by_token, touch_installation
from ...services.matches import (
    _question_out,
    abandon_match,
    abandon_tile,
    activate_power,
    adjust_score,
    complete_match,
    create_match,
    draft_power,
    get_match,
    list_events,
    open_tile,
    reroll_tile,
    resolve_tile,
    reveal_tile,
)
from ...services.sync import list_sync_jobs, run_sync_job, start_sync_job
from ...utils.errors import not_found
from ..deps import get_host_token, get_idempotency_key, get_install_token, get_settings
from .accounts import optional_account

router = APIRouter()

ELIGIBLE_CATEGORY_SQL = """
SELECT
    c.id, c.slug, c.name_ar, c.icon, c.sort_order,
    (
        SELECT COUNT(*)
        FROM questions q
        LEFT JOIN question_metadata qm ON qm.question_id = q.id
        LEFT JOIN football_category_policy p ON p.category_id = q.category_id
        JOIN question_buckets b
          ON b.category_id = q.category_id AND b.difficulty = q.difficulty
        WHERE q.category_id = c.id
          AND q.is_active = 1
          AND q.is_reserved_backup = 0
          AND (qm.question_id IS NULL OR qm.review_status = 'published')
          AND (COALESCE(p.verified_only,0) = 0 OR qm.review_status = 'published')
          AND NOT EXISTS (
              SELECT 1 FROM question_usage u
              WHERE u.question_id = q.id AND u.cycle = b.cycle
          )
          AND NOT EXISTS (
              SELECT 1 FROM match_tiles mt
              JOIN matches m ON m.id = mt.match_id
              WHERE mt.question_id = q.id
                AND mt.status = 'unplayed'
                AND m.status = 'active'
          )
    ) AS eligible_count,
    (
        SELECT COUNT(DISTINCT COALESCE(qm.fact_id,q.fact_group_id))
        FROM questions q
        LEFT JOIN question_metadata qm ON qm.question_id = q.id
        LEFT JOIN football_category_policy p ON p.category_id = q.category_id
        WHERE q.category_id = c.id AND q.is_active = 1 AND q.is_reserved_backup = 0
          AND (qm.question_id IS NULL OR qm.review_status = 'published')
          AND (COALESCE(p.verified_only,0) = 0 OR qm.review_status = 'published')
    ) AS fact_groups
FROM categories c
ORDER BY c.sort_order
"""

BUCKET_SQL = """
SELECT c.slug, q.difficulty, COUNT(*) AS n
FROM questions q JOIN categories c ON c.id = q.category_id
LEFT JOIN question_metadata qm ON qm.question_id = q.id
LEFT JOIN football_category_policy p ON p.category_id = q.category_id
WHERE q.is_active = 1 AND q.is_reserved_backup = 0
  AND (qm.question_id IS NULL OR qm.review_status = 'published')
  AND (COALESCE(p.verified_only,0) = 0 OR qm.review_status = 'published')
GROUP BY c.slug, q.difficulty
"""


@router.get("/health", response_model=HealthOut, tags=["system"])
async def health(settings: Settings = Depends(get_settings)) -> dict:
    ready = await database_ready(settings)
    total = 0
    categories = 0
    if ready:
        async with connect(settings) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) AS n FROM questions WHERE is_active = 1 AND is_reserved_backup = 0"
            )
            total = int((await cursor.fetchone())["n"])
            await cursor.close()
            cursor = await db.execute("SELECT COUNT(*) AS n FROM categories")
            categories = int((await cursor.fetchone())["n"])
            await cursor.close()
    return {
        "status": "ok" if ready else "degraded",
        "database": "ready" if ready else "unavailable",
        "schema_version": SCHEMA_VERSION,
        "seed_complete": total > 0 and categories >= len(CATEGORY_SLUGS),
        "categories": categories,
        "total_active": total,
    }


@router.get("/categories", response_model=list[CategoryOut], tags=["catalog"])
async def categories(settings: Settings = Depends(get_settings)) -> list[dict]:
    async with connect(settings) as db:
        cursor = await db.execute(ELIGIBLE_CATEGORY_SQL)
        rows = await cursor.fetchall()
        await cursor.close()
        cursor = await db.execute(BUCKET_SQL)
        counts = {
            f"{row['slug']}:{row['difficulty']}": int(row["n"]) for row in await cursor.fetchall()
        }
        await cursor.close()
    result = []
    for row in rows:
        slug = row["slug"]
        capacity = all(
            counts.get(f"{slug}:{difficulty}", 0) >= CAPACITY_PER_BUCKET
            for difficulty in DIFFICULTIES
        )
        result.append(
            {
                "id": int(row["id"]),
                "slug": slug,
                "name_ar": row["name_ar"],
                "icon": row["icon"],
                "sort_order": int(row["sort_order"]),
                "eligible_count": int(row["eligible_count"] or 0),
                "fact_groups": int(row["fact_groups"] or 0),
                "capacity_100_matches": capacity,
            }
        )
    return result


@router.get("/questions/{question_id}", response_model=QuestionOut, tags=["catalog"])
async def question(question_id: int, settings: Settings = Depends(get_settings)) -> dict:
    async with connect(settings) as db:
        cursor = await db.execute(
            """
            SELECT q.id AS question_id, c.slug AS question_category_slug,
                   c.name_ar AS question_category_name,
                   q.difficulty AS question_difficulty, q.question_type, q.question_text, q.flag_code,
                   q.media_url_a, q.media_url_b, q.payload_json, q.answer_text,
                   q.tolerance, q.explanation, q.source_name, q.source_url,
                   q.source_checked_at, q.source_license, q.source_claim,
                   q.content_origin, q.fact_group_id, qm.visual_json,
                   NULL AS revealed_at, 'unplayed' AS status
            FROM questions q JOIN categories c ON c.id = q.category_id
            LEFT JOIN question_metadata qm ON qm.question_id = q.id
            WHERE q.id = ? AND q.is_active = 1
            """,
            (question_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
    if not row:
        raise not_found("QUESTION_NOT_FOUND", "السؤال غير موجود.")
    # Catalog reads never authorize answer disclosure. Use the exact same
    # projection as an unrevealed match tile to prevent an ID lookup bypass.
    return _question_out(row)


@router.post("/matches", response_model=BoardCreateOut, status_code=201, tags=["matches"])
async def create_match_route(
    payload: MatchCreateIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
    install_token: str | None = Depends(get_install_token),
    account_id: int | None = Depends(optional_account),
) -> dict:
    async with transaction(settings) as db:
        installation = await load_installation_by_token(db, install_token)
        installation_id = int(installation["id"])
        await touch_installation(db, installation_id)
    return await create_match(
        settings, payload, idempotency_key, host_installation_id=installation_id,
        host_user_id=account_id,
    )


@router.get("/matches/{match_code}", response_model=BoardOut, tags=["matches"])
async def get_match_route(
    match_code: str, settings: Settings = Depends(get_settings)
) -> dict:
    return await get_match(settings, match_code)


@router.post(
    "/matches/{match_code}/draft/picks",
    response_model=DraftResultOut,
    tags=["powers"],
)
async def draft_pick_route(
    match_code: str,
    payload: DraftPickIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await draft_power(
        settings,
        match_code,
        power_id=payload.power_id,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.post(
    "/matches/{match_code}/tiles/{tile_key}/open",
    response_model=TileOpenOut,
    tags=["powers"],
)
async def open_tile_route(
    match_code: str,
    tile_key: str,
    payload: VersionIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await open_tile(
        settings,
        match_code,
        tile_key,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.post(
    "/matches/{match_code}/tiles/{tile_key}/reveal",
    response_model=TileRevealOut,
    tags=["powers"],
)
async def reveal_tile_route(
    match_code: str,
    tile_key: str,
    payload: VersionIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await reveal_tile(
        settings,
        match_code,
        tile_key,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.post(
    "/matches/{match_code}/tiles/{tile_key}/abandon",
    response_model=TileAbandonOut,
    tags=["powers"],
)
async def abandon_tile_route(
    match_code: str,
    tile_key: str,
    payload: VersionIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await abandon_tile(
        settings,
        match_code,
        tile_key,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.post(
    "/matches/{match_code}/tiles/{tile_key}/powers/{power_id}/activate",
    response_model=PowerActivationOut,
    tags=["powers"],
)
async def activate_power_route(
    match_code: str,
    tile_key: str,
    power_id: str,
    payload: PowerActivationIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await activate_power(
        settings,
        match_code,
        tile_key,
        power_id,
        team=payload.team,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.post(
    "/matches/{match_code}/tiles/{tile_key}/resolve",
    response_model=ResolveResultOut,
    tags=["matches"],
)
async def resolve_route(
    match_code: str,
    tile_key: str,
    payload: ResolveIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await resolve_tile(
        settings,
        match_code,
        tile_key,
        outcome=payload.outcome,
        powers_applied=payload.powers_applied,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.post(
    "/matches/{match_code}/tiles/{tile_key}/reroll",
    response_model=RerollResultOut,
    tags=["matches"],
)
async def reroll_route(
    match_code: str,
    tile_key: str,
    payload: RerollIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await reroll_tile(
        settings,
        match_code,
        tile_key,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.post(
    "/matches/{match_code}/score-adjustments",
    response_model=AdjustmentResultOut,
    tags=["matches"],
)
async def adjustment_route(
    match_code: str,
    payload: AdjustmentIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await adjust_score(
        settings,
        match_code,
        team=payload.team,
        delta=payload.delta,
        reason=payload.reason,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.post(
    "/matches/{match_code}/abandon",
    response_model=MatchResultOut,
    tags=["matches"],
)
async def abandon_route(
    match_code: str,
    payload: VersionIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await abandon_match(
        settings,
        match_code,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.post(
    "/matches/{match_code}/complete",
    response_model=MatchResultOut,
    tags=["matches"],
)
async def complete_route(
    match_code: str,
    payload: VersionIn,
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
    host_token: str | None = Depends(get_host_token),
) -> dict:
    return await complete_match(
        settings,
        match_code,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key,
        host_token=host_token,
    )


@router.get("/matches/{match_code}/events", response_model=EventsOut, tags=["matches"])
async def events_route(
    match_code: str,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
    settings: Settings = Depends(get_settings),
) -> dict:
    return await list_events(settings, match_code, limit=limit, before_id=before_id)


@router.post("/pool/sync", response_model=SyncStartOut, tags=["pool"])
async def pool_sync(
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    source: str = Query(default="restcountries", pattern="^(restcountries|wikidata|all)$"),
) -> dict:
    """يبدأ مزامنة خلفية ويرجع الحالة الحقيقية، لا ادعاء اكتمال."""
    sources = ["restcountries", "wikidata"] if source == "all" else [source]
    started = []
    for item in sources:
        started.append(await start_sync_job(settings, source=item))
    for job in started:
        if job["accepted"] and job["job_id"] is not None:
            background.add_task(run_sync_job, settings, job["job_id"], force=True)
    accepted = [item for item in started if item["accepted"]]
    if not accepted:
        return {**started[0], "accepted": False, "message": "كل المصادر لديها مزامنة نشطة بالفعل."}
    return {
        "accepted": True,
        "status": "queued",
        "job_id": accepted[0]["job_id"],
        "job_key": accepted[0]["job_key"],
        "message": "تم قبول المزامنة وبدأت بالخلفية. الحالة النهائية تظهر في /pool/sync.",
        "detail": {
            "durable": False,
            "background": True,
            "jobs": started,
        },
    }


@router.get("/pool/sync", response_model=SyncJobOut, tags=["pool"])
async def pool_sync_status(settings: Settings = Depends(get_settings)) -> dict:
    return await list_sync_jobs(settings)
