"""Account endpoints. Cookies stay HttpOnly; mutations require a custom CSRF header."""
from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from ...config import Settings
from ...db import transaction
from ...services.accounts import (
    COOKIE_NAME, SESSION_SECONDS, account_history, account_summary,
    authenticate, session_user, token_hash,
)
from ...utils.errors import forbidden
from ..deps import get_settings

router = APIRouter(prefix='/auth', tags=['accounts'])


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class Registration(Credentials):
    password: str = Field(min_length=10, max_length=128)


def require_account_csrf(request: Request) -> None:
    if request.headers.get('X-Requested-With') != 'SeenJeem':
        raise forbidden('CSRF_REQUIRED', 'أعد تحميل الصفحة وحاول مجددًا.')
    origin = request.headers.get('origin')
    if origin:
        allowed = set(request.app.state.settings.cors_origins)
        allowed.add(str(request.base_url).rstrip('/'))
        if origin not in allowed:
            raise forbidden('CSRF_ORIGIN', 'مصدر الطلب غير مسموح.')


async def current_account(request: Request, settings: Settings = Depends(get_settings)) -> int:
    return await session_user(settings, request.cookies.get(COOKIE_NAME))


async def optional_account(request: Request, settings: Settings = Depends(get_settings)) -> int | None:
    if COOKIE_NAME not in request.cookies:
        if request.headers.get('X-Account-Required') == '1':
            return await session_user(settings, None)
        return None
    require_account_csrf(request)
    # Expired cookies must never silently create a guest match and lose account history.
    return await session_user(settings, request.cookies.get(COOKIE_NAME))


async def sign_in(payload: Credentials, request: Request, response: Response,
                  settings: Settings, *, register: bool) -> dict:
    require_account_csrf(request)
    result, token = await authenticate(settings, payload.username, payload.password,
        register=register, ip=request.client.host if request.client else 'unknown',
        previous_token=request.cookies.get(COOKIE_NAME))
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=settings.app_env == 'production', samesite='strict', path='/api/v1')
    response.headers['Cache-Control'] = 'no-store'
    return result


@router.post('/register', status_code=201)
async def register(payload: Registration, request: Request, response: Response,
                   settings: Settings = Depends(get_settings)):
    return await sign_in(payload, request, response, settings, register=True)


@router.post('/login')
async def login(payload: Credentials, request: Request, response: Response,
                settings: Settings = Depends(get_settings)):
    return await sign_in(payload, request, response, settings, register=False)


@router.post('/logout')
async def logout(request: Request, response: Response, settings: Settings = Depends(get_settings)):
    require_account_csrf(request)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        async with transaction(settings) as db:
            await db.execute('DELETE FROM account_sessions WHERE token_hash = ?', (token_hash(token),))
    response.delete_cookie(COOKIE_NAME, path='/api/v1')
    response.headers['Cache-Control'] = 'no-store'
    return {'ok': True}


@router.get('/me')
async def me(response: Response, user_id: int = Depends(current_account),
             settings: Settings = Depends(get_settings)):
    response.headers['Cache-Control'] = 'no-store'
    return await account_summary(settings, user_id)


@router.get('/history')
async def history(response: Response, limit: int = Query(20, ge=1, le=100),
                  offset: int = Query(0, ge=0), user_id: int = Depends(current_account),
                  settings: Settings = Depends(get_settings)):
    response.headers['Cache-Control'] = 'no-store'
    return await account_history(settings, user_id, limit, offset)
