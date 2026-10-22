from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest_asyncio

from app.config import load_settings
from app.db import connect, init_db, transaction
from app.main import create_app
from app.services.seed import seed_database
from app.utils.text import fingerprint

SIX_CATEGORIES = ["flags", "capitals", "ucl", "riddles", "spotdiff", "clubs"]


def auth_headers(
    key: str, admin: bool = False, host: str | None = None, install: str | None = None
) -> dict:
    headers = {"Idempotency-Key": key}
    if admin:
        headers["X-Admin-Token"] = "test-admin-token"
    if host:
        headers["X-Host-Token"] = host
    if install:
        headers["X-Install-Token"] = install
    return headers


async def make_installation(client, key: str = "install-1") -> dict:
    """يسجّل تثبيت جهاز اختباري ويعيد سجله (مع الاعتماد الخام لمرة واحدة)."""
    response = await client.post("/api/v1/installations/register", headers=auth_headers(key))
    assert response.status_code == 201, response.text
    return response.json()


async def make_installation_row(settings, key: str = "install-1") -> tuple[int, str]:
    """تثبيت اختباري على مستوى الخدمة. يعيد (installation_id, credential)."""
    from app.services.identity import register_installation

    result = await register_installation(settings, key)
    return int(result["installation_id"]), result["credential"]


async def hosted_create(settings, payload, key: str) -> dict:
    """create_match مع تثبيت مضيف اختباري (مفتاح مشتق من مفتاح الإنشاء)."""
    from app.services.matches import create_match

    installation_id, _ = await make_installation_row(settings, f"{key}-host")
    return await create_match(settings, payload, key, host_installation_id=installation_id)


def match_headers(key: str, board: dict) -> dict:
    """ترويسات عملية تغيير على مباراة: مفتاح تكرار + توكن مضيفها."""
    return auth_headers(key, host=board["host_token"])


@pytest_asyncio.fixture
async def settings(tmp_path: Path):
    base = load_settings()
    value = replace(
        base,
        database_path=tmp_path / "test-seenjeem.db",
        admin_token="test-admin-token",
        allow_lan_wildcard_origin=False,
        allow_credentials=False,
        seed_version="test-seed-v1",
        seed_random_seed=12345,
    )
    await init_db(value)
    return value


@pytest_asyncio.fixture
async def seeded_settings(settings):
    await seed_database(settings, deterministic_seed=12345)
    return settings


@pytest_asyncio.fixture
async def client(seeded_settings):
    app = create_app(seeded_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def add_test_inventory(settings, *, per_bucket: int = 240) -> dict:
    """أسئلة اصطناعية **للاختبار فقط** لإثبات سلوك الاختيار عند سعة كافية.

    لا تُزرع في قاعدة الإنتاج، وتحمل `verification_status='test_fixture'`
    و`content_origin='generated_puzzle'` حتى لا تُخلط بالمحتوى الحقيقي.
    """
    inserted = 0
    async with transaction(settings) as db:
        cursor = await db.execute("SELECT id, slug FROM categories")
        categories = {row["slug"]: int(row["id"]) for row in await cursor.fetchall()}
        await cursor.close()
        for slug in categories:
            category_id = categories[slug]
            for difficulty in (200, 400, 600):
                for index in range(per_bucket):
                    question = f"[اختبار سعة] {slug} {difficulty} سؤال رقم {index}"
                    answer = str(index)
                    fp = fingerprint(slug, question, answer)
                    group = f"test_fixture:{slug}:{difficulty}:{index}"
                    cursor = await db.execute(
                        """
                        INSERT INTO questions(
                            category_id, difficulty, question_type, question_text,
                            payload_json, answer_text, tolerance, explanation,
                            content_origin, fingerprint, is_active, is_reserved_backup,
                            fact_group_id, source_entity_id, verification_status,
                            content_version, times_played, deck_position
                        ) VALUES (?, ?, 'text', ?, NULL, ?, ?, ?, 'generated_puzzle', ?, 1, 0,
                                  ?, ?, 'test_fixture', 1, 0, ?)
                        ON CONFLICT(fingerprint) DO NOTHING
                        """,
                        (
                            category_id,
                            difficulty,
                            question,
                            answer,
                            answer,
                            "سؤال اختبار سعة فقط.",
                            fp,
                            group,
                            group,
                            index,
                        ),
                    )
                    if cursor.rowcount:
                        inserted += 1
                    await cursor.close()
    return {"inserted": inserted, "per_bucket": per_bucket}


@pytest_asyncio.fixture
async def capacity_settings(settings):
    """قاعدة اختبار معزولة: بنك حقيقي + مخزون اختبار بسعة 100 مباراة."""
    await seed_database(settings, deterministic_seed=12345)
    await add_test_inventory(settings, per_bucket=240)
    return settings
