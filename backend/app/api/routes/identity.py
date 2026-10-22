"""مسارات الهوية: ملفات اللاعبين وتسجيل التثبيت.

نموذج الثقة موثق في `app/services/identity.py`: شاشة مشتركة، والخادم
مرجع العضوية والسجل. لا تُكشف الاعتمادات الخام إلا مرة واحدة عند التسجيل.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...config import Settings
from ...db import transaction
from ...models import (
    InstallationOut,
    InstallationRegisterOut,
    UserCreateIn,
    UserOut,
)
from ...services.identity import (
    create_profile,
    installation_out,
    list_profiles,
    load_installation_by_token,
    register_installation,
    touch_installation,
)
from ..deps import get_idempotency_key, get_install_token, get_settings

router = APIRouter()


@router.post("/users", response_model=UserOut, status_code=201, tags=["identity"])
async def create_user_route(
    payload: UserCreateIn, settings: Settings = Depends(get_settings)
) -> dict:
    return await create_profile(
        settings, username=payload.username, display_name=payload.display_name
    )


@router.get("/users", response_model=list[UserOut], tags=["identity"])
async def list_users_route(settings: Settings = Depends(get_settings)) -> list[dict]:
    return await list_profiles(settings)


@router.post(
    "/installations/register",
    response_model=InstallationRegisterOut,
    status_code=201,
    tags=["identity"],
)
async def register_installation_route(
    settings: Settings = Depends(get_settings),
    idempotency_key: str = Depends(get_idempotency_key),
) -> dict:
    return await register_installation(settings, idempotency_key)


@router.get("/installations/me", response_model=InstallationOut, tags=["identity"])
async def installation_me_route(
    settings: Settings = Depends(get_settings),
    install_token: str | None = Depends(get_install_token),
) -> dict:
    async with transaction(settings) as db:
        row = await load_installation_by_token(db, install_token)
        await touch_installation(db, int(row["id"]))
        return installation_out(row)
