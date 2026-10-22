"""الهوية: ملفات لاعبين مسماة، وتثبيتات أجهزة باعتماد عشوائي، وظلال للأجهزة.

نموذج ملفات الضيوف: شاشة تلفاز مشتركة — اختيار ملف ضيف لا يتطلب كلمة سر،
والخادم هو المرجع الوحيد للعضوية والسجل. الهوية الجهازية اعتماد عالي
الإنتروبيا صادر من الخادم (لا بصمات متصفح غازية)، يُحفظ كبصمة SHA-256 فقط.

الحسابات بكلمات المرور وجلساتها معرّفة في services/accounts.py؛ ولا تُعرض
ضمن قائمة ملفات الضيوف، ولا يمكن إسنادها للمباراة بمجرد إرسال معرّفها.

حدّ متبقٍ موثق: حماية مستوى الجهاز بقدر بقاء الاعتماد وربطه الخادمي؛
مسح الاعتماد من المتصفح أو سرقته عبر XSS يضعف الضمان (انظر الواجهة).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from sqlite3 import IntegrityError

import aiosqlite

from ..config import Settings
from ..db import connect, transaction
from ..utils.errors import bad_request, conflict, forbidden, not_found

MAX_USERNAME_LENGTH = 32
MAX_DISPLAY_NAME_LENGTH = 40
MAX_PARTICIPANTS_PER_TEAM = 8


def _hash_credential(credential: str) -> str:
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()


def user_out(row: sqlite3.Row) -> dict:
    return {
        "id": int(row["id"]),
        "username": row["username"],
        "display_name": row["display_name"],
        "kind": row["kind"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def installation_out(row: sqlite3.Row, *, include_shadow: bool = True) -> dict:
    payload = {
        "installation_id": int(row["id"]),
        "install_code": row["install_code"],
        "created_at": row["created_at"],
        "last_seen_at": row["last_seen_at"],
        "revoked": bool(row["revoked"]),
    }
    if include_shadow:
        payload["shadow_user_id"] = int(row["shadow_user_id"])
    return payload


def _clean_username(username: str | None) -> str:
    value = (username or "").strip()
    if not value:
        raise bad_request("INVALID_USERNAME", "اسم المستخدم لا يمكن أن يكون فارغًا.")
    if len(value) > MAX_USERNAME_LENGTH:
        raise bad_request(
            "INVALID_USERNAME",
            f"اسم المستخدم أطول من {MAX_USERNAME_LENGTH} حرفًا.",
        )
    if any(ord(char) < 32 for char in value):
        raise bad_request("INVALID_USERNAME", "اسم المستخدم يحتوي محارف غير صالحة.")
    return value


def _clean_display_name(display_name: str | None) -> str:
    value = (display_name or "").strip()
    if not value:
        raise bad_request("INVALID_DISPLAY_NAME", "الاسم المعروض لا يمكن أن يكون فارغًا.")
    if len(value) > MAX_DISPLAY_NAME_LENGTH:
        raise bad_request(
            "INVALID_DISPLAY_NAME",
            f"الاسم المعروض أطول من {MAX_DISPLAY_NAME_LENGTH} حرفًا.",
        )
    return value


async def create_profile(
    settings: Settings, *, username: str, display_name: str | None = None
) -> dict:
    """ينشئ ملف لاعب مسمى. الاسم الفريد محجوز قاعديًا ضد السباق."""
    clean_username = _clean_username(username)
    clean_display = _clean_display_name(display_name or clean_username)
    async with transaction(settings) as db:
        cursor = await db.execute('SELECT 1 FROM users WHERE username = ? COLLATE NOCASE', (clean_username,))
        existing = await cursor.fetchone()
        await cursor.close()
        if existing:
            raise conflict('PROFILE_USERNAME_TAKEN', 'اسم المستخدم محجوز لملف آخر.')
        try:
            cursor = await db.execute(
                "INSERT INTO users(username, display_name, kind, is_active)"
                " VALUES (?, ?, 'named', 1)",
                (clean_username, clean_display),
            )
            user_id = int(cursor.lastrowid)
            await cursor.close()
        except IntegrityError as exc:
            raise conflict(
                "PROFILE_USERNAME_TAKEN",
                "اسم المستخدم محجوز لملف آخر.",
                username=clean_username,
            ) from exc
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        await cursor.close()
        return user_out(row)


async def list_profiles(settings: Settings) -> list[dict]:
    async with connect(settings) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE kind = 'named' AND is_active = 1 AND password_hash IS NULL ORDER BY id"
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [user_out(row) for row in rows]


async def _load_installation_row(
    db: aiosqlite.Connection, credential_hash: str
) -> sqlite3.Row | None:
    cursor = await db.execute(
        "SELECT * FROM device_installations WHERE credential_hash = ?",
        (credential_hash,),
    )
    row = await cursor.fetchone()
    await cursor.close()
    return row


async def register_installation(settings: Settings, idempotency_key: str) -> dict:
    """يسجّل تثبيت جهاز مع ظلّه. نفس مفتاح التكرار يعيد نفس الاعتماد."""
    scope = "install-register"
    async with transaction(settings) as db:
        cursor = await db.execute(
            "SELECT request_hash, response_json FROM idempotency_keys WHERE scope = ? AND key = ?",
            (scope, idempotency_key),
        )
        existing = await cursor.fetchone()
        await cursor.close()
        if existing:
            payload = json.loads(existing["response_json"])
            payload["idempotent_replay"] = True
            return payload
        for _ in range(3):
            install_code = secrets.token_urlsafe(6)
            credential = secrets.token_urlsafe(32)
            try:
                cursor = await db.execute(
                    "INSERT INTO users(username, display_name, kind, is_active)"
                    " VALUES (NULL, 'لاعب الجهاز', 'shadow', 1)"
                )
                shadow_id = int(cursor.lastrowid)
                await cursor.close()
                cursor = await db.execute(
                    "INSERT INTO device_installations(install_code, credential_hash, shadow_user_id)"
                    " VALUES (?, ?, ?)",
                    (install_code, _hash_credential(credential), shadow_id),
                )
                installation_id = int(cursor.lastrowid)
                await cursor.close()
                break
            except IntegrityError:
                continue
        else:
            raise conflict(
                "INSTALLATION_CONFLICT",
                "تعذّر إنشاء سجل تثبيت فريد؛ أعد المحاولة.",
            )
        cursor = await db.execute(
            "SELECT * FROM device_installations WHERE id = ?", (installation_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        response = {
            **installation_out(row),
            "credential": credential,
            "idempotent_replay": False,
        }
        try:
            await db.execute(
                "INSERT INTO idempotency_keys(scope, key, request_hash, status_code, response_json)"
                " VALUES (?, ?, ?, ?, ?)",
                (scope, idempotency_key, _hash_credential(credential), 201,
                 json.dumps(response, ensure_ascii=False)),
            )
        except IntegrityError:
            # متسابق لحظي بنفس المفتاح سبقنا والتزم أولًا: نتراجع عن صفوفنا
            # ونعيد استجابته المخزنة (تحمل نفس الاعتماد لنفس المفتاح).
            await db.rollback()
            cursor = await db.execute(
                "SELECT response_json FROM idempotency_keys WHERE scope = ? AND key = ?",
                (scope, idempotency_key),
            )
            winner = await cursor.fetchone()
            await cursor.close()
            if winner is None:
                raise conflict(
                    "INSTALLATION_CONFLICT",
                    "تعذّر إنشاء سجل تثبيت فريد؛ أعد المحاولة.",
                )
            payload = json.loads(winner["response_json"])
            payload["idempotent_replay"] = True
            return payload
        return response


async def load_installation_by_token(
    db: aiosqlite.Connection, credential: str | None
) -> sqlite3.Row:
    """يحلّ اعتماد التثبيت إلى سجله. لا يقبل معرّفًا عدديًا من العميل."""
    if not credential:
        raise forbidden("INSTALL_TOKEN_REQUIRED", "العملية تتطلب ترويسة X-Install-Token.")
    row = await _load_installation_row(db, _hash_credential(credential))
    if not row:
        raise forbidden("INSTALL_TOKEN_INVALID", "اعتماد التثبيت غير معروف.")
    if int(row["revoked"]):
        raise forbidden("INSTALL_TOKEN_REVOKED", "اعتماد التثبيت مسحوب.")
    return row


async def touch_installation(db: aiosqlite.Connection, installation_id: int) -> None:
    await db.execute(
        "UPDATE device_installations SET last_seen_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')"
        " WHERE id = ?",
        (installation_id,),
    )


async def validate_participant_ids(
    db: aiosqlite.Connection, user_ids: list[int]
) -> list[int]:
    """يدقق عضوية المشاركين: وجود، نشاط، إزالة تكرار. لا يثق بالعميل."""
    cleaned: list[int] = []
    for value in user_ids:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise bad_request(
                "INVALID_PARTICIPANT", "معرّف المشارك يجب أن يكون عددًا صحيحًا موجبًا."
            )
        if value not in cleaned:
            cleaned.append(value)
    for user_id in cleaned:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            raise not_found(
                "PARTICIPANT_NOT_FOUND",
                "مشارك غير مسجّل في هالمباراة.",
                user_id=user_id,
            )
        if not int(row["is_active"]):
            raise conflict(
                "PARTICIPANT_INACTIVE",
                "مشارك موقوف لا يمكن إشراكه.",
                user_id=user_id,
            )
        if row['password_hash']:
            raise forbidden('ACCOUNT_PARTICIPANT_FORBIDDEN',
                            'الحساب يُربط بالمباراة من جلسة تسجيل الدخول فقط.')
    return cleaned
