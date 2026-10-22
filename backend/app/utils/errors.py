"""أخطاء التطبيق الموحّدة."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


def not_found(code: str, message: str, **details: Any) -> AppError:
    return AppError(404, code, message, details or None)


def conflict(code: str, message: str, **details: Any) -> AppError:
    return AppError(409, code, message, details or None)


def bad_request(code: str, message: str, **details: Any) -> AppError:
    return AppError(400, code, message, details or None)


def forbidden(code: str, message: str, **details: Any) -> AppError:
    return AppError(403, code, message, details or None)


def unprocessable(code: str, message: str, **details: Any) -> AppError:
    return AppError(422, code, message, details or None)
