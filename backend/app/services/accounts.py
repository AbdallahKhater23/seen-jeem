"""Password accounts with revocable, hashed sessions and durable question history."""
from __future__ import annotations

import asyncio
import hashlib
import secrets
import sqlite3
import time
import unicodedata

from ..config import Settings
from ..db import connect, transaction
from ..utils.errors import AppError, conflict
from .identity import _clean_username, user_out

SESSION_SECONDS = 30 * 24 * 60 * 60
COOKIE_NAME = 'seenjeem_session'


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt),
                            n=2**15, r=8, p=3, maxmem=64 * 1024 * 1024).hex()
    return f'scrypt${salt}${digest}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, _ = encoded.split('$')
        return algorithm == 'scrypt' and secrets.compare_digest(hash_password(password, salt), encoded)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def clean_username(value: str) -> str:
    return _clean_username(unicodedata.normalize('NFKC', value).strip().casefold())


async def throttle(settings: Settings, scopes: list[str], limit: int = 8) -> None:
    """Persist counters before password checks; failed logins cannot roll them back."""
    now = int(time.time())
    blocked = False
    async with transaction(settings) as db:
        await db.execute('DELETE FROM auth_attempts WHERE window_start < ?', (now - 900,))
        for scope in scopes:
            await db.execute(
                'INSERT INTO auth_attempts(scope, attempts, window_start) VALUES (?, 1, ?) '
                'ON CONFLICT(scope) DO UPDATE SET attempts = attempts + 1', (scope, now))
            row = await (await db.execute('SELECT attempts FROM auth_attempts WHERE scope = ?', (scope,))).fetchone()
            blocked = blocked or row['attempts'] > limit
    if blocked:
        raise AppError(429, 'AUTH_RATE_LIMITED', 'محاولات كثيرة. انتظر ١٥ دقيقة ثم حاول مجددًا.')


async def authenticate(settings: Settings, username: str, password: str, *, register: bool,
                       ip: str, previous_token: str | None = None) -> tuple[dict, str]:
    username = clean_username(username)
    await throttle(settings, [f'ip:{ip}'], limit=30)
    await throttle(settings, [f'username:{username}'])
    async with connect(settings) as db:
        row = await (await db.execute('SELECT * FROM users WHERE username = ? COLLATE NOCASE', (username,))).fetchone()
    if register:
        if row:
            # Unprotected old profiles are never silently claimed by new accounts.
            raise conflict('ACCOUNT_USERNAME_TAKEN', 'اسم المستخدم مستخدم. اختَر اسمًا آخر.')
        encoded = await asyncio.to_thread(hash_password, password)
    else:
        # Do comparable hashing work for unknown names to avoid a fast enumeration path.
        encoded = row['password_hash'] if row and row['password_hash'] else None
        valid = await asyncio.to_thread(verify_password, password, encoded or
                                       ('scrypt$' + '00' * 16 + '$' + '00' * 64))
        if not valid or not row or not row['is_active']:
            raise AppError(401, 'INVALID_CREDENTIALS', 'اسم المستخدم أو كلمة المرور غير صحيحة.')
    async with transaction(settings) as db:
        if register:
            try:
                cursor = await db.execute(
                    "INSERT INTO users(username, display_name, kind, password_hash) VALUES (?, ?, 'named', ?)",
                    (username, username, encoded))
            except sqlite3.IntegrityError as exc:
                raise conflict('ACCOUNT_USERNAME_TAKEN', 'اسم المستخدم مستخدم. اختَر اسمًا آخر.') from exc
            row = await (await db.execute('SELECT * FROM users WHERE id = ?', (cursor.lastrowid,))).fetchone()
        if previous_token:
            await db.execute('DELETE FROM account_sessions WHERE token_hash = ?', (token_hash(previous_token),))
        await db.execute('DELETE FROM account_sessions WHERE expires_at <= ?', (int(time.time()),))
        token = secrets.token_urlsafe(32)
        await db.execute('INSERT INTO account_sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)',
                         (token_hash(token), row['id'], int(time.time()) + SESSION_SECONDS))
        await db.execute('DELETE FROM auth_attempts WHERE scope = ?', (f'username:{username}',))
    return await account_summary(settings, int(row['id'])), token


async def session_user(settings: Settings, token: str | None) -> int:
    if token:
        async with connect(settings) as db:
            row = await (await db.execute(
                'SELECT u.id FROM account_sessions s JOIN users u ON u.id = s.user_id '
                'WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1',
                (token_hash(token), int(time.time())))).fetchone()
        if row:
            return int(row['id'])
    raise AppError(401, 'LOGIN_REQUIRED', 'سجّل دخولك لحفظ سجل أسئلتك في حسابك.')


async def account_summary(settings: Settings, user_id: int) -> dict:
    async with connect(settings) as db:
        row = await (await db.execute('SELECT * FROM users WHERE id = ?', (user_id,))).fetchone()
        count = await (await db.execute('SELECT COUNT(*) FROM user_question_history WHERE user_id = ?', (user_id,))).fetchone()
    return {'user': user_out(row), 'questions_seen': count[0]}


async def account_history(settings: Settings, user_id: int, limit: int, offset: int) -> dict:
    async with connect(settings) as db:
        total = await (await db.execute('SELECT COUNT(*) FROM user_question_history WHERE user_id = ?', (user_id,))).fetchone()
        rows = await (await db.execute(
            'SELECT h.question_id, h.played_at, h.outcome, q.question_text, q.difficulty, '
            'c.name_ar AS category_name FROM user_question_history h '
            'JOIN questions q ON q.id = h.question_id JOIN categories c ON c.id = q.category_id '
            'WHERE h.user_id = ? ORDER BY h.played_at DESC, h.id DESC LIMIT ? OFFSET ?',
            (user_id, limit, offset))).fetchall()
    return {'total': total[0], 'items': [dict(row) for row in rows]}
