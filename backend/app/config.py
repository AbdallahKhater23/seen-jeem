"""إعدادات التطبيق من متغيرات البيئة فقط، بدون أسرار مضمّنة."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Optional local .env; real environment variables still win.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_path: Path = Path(__file__).resolve().parents[1] / "data" / "seenjeem.db"
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    allow_lan_wildcard_origin: bool = False
    allow_credentials: bool = False
    admin_token: str | None = None
    seed_version: str = "2026.10.1"
    seed_random_seed: int = 20261019
    busy_timeout_ms: int = 5000
    max_team_name_length: int = 40

    @property
    def cors_config(self) -> dict:
        """CORS آمن: لا نسمح أبدًا بـ wildcard مع credentials."""
        wildcard_origin = "*" in self.cors_origins
        if "*" in self.cors_origins and not self.allow_lan_wildcard_origin:
            raise ValueError(
                "CORS_ORIGINS=* يتطلب ALLOW_LAN_WILDCARD_ORIGIN=true صراحةً."
            )
        if (self.allow_lan_wildcard_origin or wildcard_origin) and self.allow_credentials:
            raise ValueError(
                "wildcard CORS لا يمكن جمعه مع ALLOW_CREDENTIALS=true."
            )
        if self.allow_lan_wildcard_origin:
            return {
                "allow_origins": ["*"],
                "allow_credentials": False,
                "allow_methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Idempotency-Key", "X-Admin-Token", "X-Host-Token", "X-Install-Token", "X-Requested-With", "X-Account-Required"],
            }
        return {
            "allow_origins": list(self.cors_origins),
            "allow_credentials": self.allow_credentials,
            "allow_methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Idempotency-Key", "X-Admin-Token", "X-Host-Token", "X-Install-Token", "X-Requested-With", "X-Account-Required"],
        }


def load_settings() -> Settings:
    default_db = Path(__file__).resolve().parents[1] / "data" / "seenjeem.db"
    db_path = Path(os.getenv("DATABASE_PATH", str(default_db))).expanduser()
    origins = tuple(
        item.strip()
        for item in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if item.strip()
    )
    return Settings(
        app_env=os.getenv("APP_ENV", "development").strip().lower(),
        api_prefix=os.getenv("API_PREFIX", "/api/v1"),
        database_path=db_path,
        cors_origins=origins or ("http://localhost:5173", "http://127.0.0.1:5173"),
        allow_lan_wildcard_origin=_bool("ALLOW_LAN_WILDCARD_ORIGIN", False),
        allow_credentials=_bool("ALLOW_CREDENTIALS", False),
        admin_token=os.getenv("ADMIN_TOKEN") or None,
        seed_version=os.getenv("SEED_VERSION", "2026.10.1"),
        seed_random_seed=_int("SEED_RANDOM_SEED", 20261019),
        busy_timeout_ms=_int("SQLITE_BUSY_TIMEOUT_MS", 5000),
        max_team_name_length=_int("MAX_TEAM_NAME_LENGTH", 40),
    )
