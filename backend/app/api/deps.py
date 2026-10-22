"""اعتماديات API المشتركة."""

from __future__ import annotations

from fastapi import Header, Request

from ..config import Settings
from ..utils.errors import AppError


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise AppError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "ترويسة Idempotency-Key مطلوبة لكل عملية تغيير.",
        )
    value = idempotency_key.strip()
    if len(value) > 128:
        raise AppError(400, "IDEMPOTENCY_KEY_INVALID", "مفتاح التكرار أطول من 128 حرفًا.")
    return value


def get_host_token(
    x_host_token: str | None = Header(default=None, alias="X-Host-Token"),
) -> str | None:
    """توكن المضيف اختياري على مستوى الاستخراج؛ الخدمة ترفض غيابه بـ 403."""
    value = (x_host_token or "").strip()
    return value or None


def get_install_token(
    x_install_token: str | None = Header(default=None, alias="X-Install-Token"),
) -> str | None:
    """اعتماد التثبيت اختياري على مستوى الاستخراج؛ الخدمة ترفض غيابه بـ 403."""
    value = (x_install_token or "").strip()
    return value or None


def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    settings: Settings = request.app.state.settings
    if not settings.admin_token:
        raise AppError(
            403,
            "ADMIN_DISABLED",
            "مسار الإدارة معطّل. اضبط ADMIN_TOKEN لتشغيله.",
        )
    if x_admin_token != settings.admin_token:
        raise AppError(403, "ADMIN_FORBIDDEN", "توكن الإدارة غير صحيح.")
