"""مسارات إدارة محمية بتوكن، وليست مفتوحة على LAN افتراضيًا."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...config import Settings
from ...models import (
    AdminMatchesOut,
    AdminMatchEventsOut,
    AdminQuestionBankOut,
    AdminSeedHistoryOut,
    SeedStatusOut,
)
from ...services.admin import match_events, question_bank, recent_matches, seed_history
from ...services.seed import seed_status
from ..deps import get_settings, require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/admin/seed-status", response_model=SeedStatusOut, tags=["admin"])
async def admin_seed_status(settings: Settings = Depends(get_settings)) -> dict:
    return await seed_status(settings)


@router.get(
    "/admin/question-bank", response_model=AdminQuestionBankOut, tags=["admin"]
)
async def admin_question_bank(settings: Settings = Depends(get_settings)) -> dict:
    """توازن البنك: لكل فئة/صعوبة المؤهل والمستخدم والمحجوز والمخزون."""
    return await question_bank(settings)


@router.get("/admin/seed-history", response_model=AdminSeedHistoryOut, tags=["admin"])
async def admin_seed_history(
    limit: int = Query(default=20, ge=1, le=100),
    settings: Settings = Depends(get_settings),
) -> dict:
    return await seed_history(settings, limit=limit)


@router.get("/admin/matches", response_model=AdminMatchesOut, tags=["admin"])
async def admin_matches(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(
        default=None, pattern="^(active|completed|abandoned)$"
    ),
    settings: Settings = Depends(get_settings),
) -> dict:
    return await recent_matches(settings, limit=limit, status=status)


@router.get(
    "/admin/matches/{match_code}/events",
    response_model=AdminMatchEventsOut,
    tags=["admin"],
)
async def admin_match_events(
    match_code: str,
    limit: int = Query(default=100, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
    settings: Settings = Depends(get_settings),
) -> dict:
    return await match_events(
        settings, match_code, limit=limit, before_id=before_id
    )
