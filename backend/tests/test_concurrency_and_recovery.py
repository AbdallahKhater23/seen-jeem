from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.db import connect
from app.models import MatchCreateIn
from app.services import harvester
from app.services.harvester import harvest_restcountries, harvest_wikidata, run_harvest
from app.services.matches import resolve_tile
from app.services.sync import (
    list_sync_jobs,
    recover_interrupted_jobs,
    run_sync_job,
    start_sync_job,
)
from tests.conftest import SIX_CATEGORIES, hosted_create


async def fake_country_payload(count: int = 60):
    rows = []
    for index in range(count):
        code = f"{chr(ord('a') + index // 26)}{chr(ord('a') + index % 26)}"
        rows.append(
            {
                "cca2": code,
                "name": {"common": f"Testland {index}"},
                "translations": {"ara": {"common": f"دولة اختبار {index}"}},
                "capital": [f"Capital {index}"],
                "region": "Test",
                "subregion": "Test",
                "population": 1000 + index,
                "borders": [],
                "currencies": {},
                "unMember": True,
            }
        )
    return rows


@pytest.mark.asyncio
async def test_sync_jobs_deduplicate_and_stale_jobs_fail(seeded_settings, monkeypatch):
    first = await start_sync_job(seeded_settings, source="restcountries")
    assert first["accepted"] is True
    assert first["status"] == "queued"
    second = await start_sync_job(seeded_settings, source="restcountries")
    assert second["accepted"] is False
    assert second["detail"]["deduplicated"] is True

    stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    async with connect(seeded_settings) as db:
        await db.execute(
            "UPDATE sync_jobs SET status = 'running', started_at = ? WHERE id = ?",
            (stale, first["job_id"]),
        )
        await db.commit()
    recovered = await recover_interrupted_jobs(seeded_settings)
    assert recovered == 1
    jobs = await list_sync_jobs(seeded_settings)
    job = next(item for item in jobs["jobs"] if item["id"] == first["job_id"])
    assert job["status"] == "failed"
    assert "interrupted" in (job["error"] or "")
    fresh = await start_sync_job(seeded_settings, source="restcountries")
    assert fresh["accepted"] is True


@pytest.mark.asyncio
async def test_run_sync_job_records_failure_without_corrupting_questions(
    seeded_settings, monkeypatch
):
    async def broken_harvest(settings, *, force=False):
        raise RuntimeError("upstream offline")

    monkeypatch.setattr("app.services.sync.run_harvest", broken_harvest)
    job = await start_sync_job(seeded_settings, source="restcountries")
    result = await run_sync_job(seeded_settings, job["job_id"])
    assert result["status"] == "failed"
    jobs = await list_sync_jobs(seeded_settings)
    stored = next(item for item in jobs["jobs"] if item["id"] == job["job_id"])
    assert stored["status"] == "failed"
    assert "RuntimeError" in (stored["error"] or "")
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions"
            " WHERE content_origin = 'api_sourced' AND source_name = 'RestCountries v3.1'"
        )
        assert (await cursor.fetchone())["n"] == 0
        await cursor.close()


@pytest.mark.asyncio
async def test_restcountries_success_is_verified_and_idempotent(seeded_settings, monkeypatch):
    payload = await fake_country_payload(60)

    async def fake_get(*args, **kwargs):
        return payload, "ok"

    monkeypatch.setattr(harvester, "_get_json", fake_get)
    monkeypatch.setattr(harvester, "_write_cache", lambda *args, **kwargs: None)
    first = await harvest_restcountries(seeded_settings, force=True)
    assert first["status"] == "restcountries:ok"
    assert first["facts"] == 60
    assert first["questions"] >= 50
    added = first["questions"]

    second = await harvest_restcountries(seeded_settings, force=True)
    assert second["questions"] == 0, "إعادة الحصاد لا تُكرر الأسئلة"

    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions"
            " WHERE content_origin = 'api_sourced' AND source_name = 'RestCountries v3.1'"
        )
        assert (await cursor.fetchone())["n"] == added
        await cursor.close()
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM fact_records"
            " WHERE verification_status = 'verified_api' AND source_name = 'RestCountries v3.1'"
        )
        assert (await cursor.fetchone())["n"] == 60
        await cursor.close()
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions"
            " WHERE content_origin = 'api_sourced' AND source_name = 'RestCountries v3.1'"
            " AND verification_status = 'verified_api' AND fact_group_id IS NOT NULL"
        )
        assert (await cursor.fetchone())["n"] == added
        await cursor.close()


@pytest.mark.asyncio
async def test_restcountries_deprecated_and_malformed_are_safe(seeded_settings, monkeypatch):
    async def deprecated(*args, **kwargs):
        return {"success": False, "errors": [{"message": "This API version has been deprecated."}]}, "ok"

    monkeypatch.setattr(harvester, "_get_json", deprecated)
    monkeypatch.setattr(harvester, "_write_cache", lambda *args, **kwargs: None)
    result = await harvest_restcountries(seeded_settings, force=True)
    assert result["status"] == "restcountries:deprecated"
    assert result["facts"] == 0

    async def malformed(*args, **kwargs):
        return {"unexpected": True}, "ok"

    monkeypatch.setattr(harvester, "_get_json", malformed)
    result = await harvest_restcountries(seeded_settings, force=True)
    assert result["status"] == "restcountries:malformed"

    async def timeout(*args, **kwargs):
        return None, "unreachable"

    monkeypatch.setattr(harvester, "_get_json", timeout)
    result = await harvest_restcountries(seeded_settings, force=True)
    assert result["status"] == "restcountries:unreachable"


@pytest.mark.asyncio
async def test_wikidata_failure_keeps_existing_bank_intact(seeded_settings, monkeypatch):
    async with connect(seeded_settings) as db:
        cursor = await db.execute("SELECT COUNT(*) AS n FROM questions")
        before = (await cursor.fetchone())["n"]
        await cursor.close()

    async def forbidden(*args, **kwargs):
        return None, "http_403"

    monkeypatch.setattr(harvester, "_get_json", forbidden)
    result = await harvest_wikidata(seeded_settings, force=True)
    assert result["status"] == "wikidata:http_403"
    assert result["facts"] == 0

    async with connect(seeded_settings) as db:
        cursor = await db.execute("SELECT COUNT(*) AS n FROM questions")
        assert (await cursor.fetchone())["n"] == before
        await cursor.close()
        cursor = await db.execute("SELECT COUNT(*) AS n FROM fact_records")
        assert (await cursor.fetchone())["n"] > 0
        await cursor.close()


@pytest.mark.asyncio
async def test_run_harvest_marks_partial_when_one_source_fails(seeded_settings, monkeypatch):
    payload = await fake_country_payload(60)

    async def fake_get(url, **kwargs):
        if "restcountries" in url:
            return payload, "ok"
        return None, "http_403"

    monkeypatch.setattr(harvester, "_get_json", fake_get)
    monkeypatch.setattr(harvester, "_write_cache", lambda *args, **kwargs: None)
    report = await run_harvest(seeded_settings, force=True)
    assert report["status"] == "partial"
    assert report["questions"] >= 50


@pytest.mark.asyncio
async def test_interrupted_match_keeps_played_usage_and_releases_unplayed(seeded_settings):
    board = await hosted_create(
        seeded_settings,
        MatchCreateIn(
            team1_name="أ",
            team2_name="ب",
            starting_turn="team1",
            category_slugs=SIX_CATEGORIES,
        ),
        "interrupt-create",
    )
    code = board["match"]["match_code"]
    host = board["host_token"]
    tile = board["tiles"][0]
    await resolve_tile(
        seeded_settings,
        code,
        tile["tile_key"],
        outcome="team1",
        powers_applied=[],
        expected_version=1,
        idempotency_key="interrupt-resolve",
        host_token=host,
    )
    # محاكاة توقف العملية: المباراة تبقى نشطة وتحجز بقية الأسئلة مؤقتًا.
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) AS n FROM match_tiles mt JOIN matches m ON m.id = mt.match_id
            WHERE m.status = 'active' AND mt.status = 'unplayed'
            """
        )
        assert (await cursor.fetchone())["n"] == 53
        await cursor.close()
    async with connect(seeded_settings) as db:
        await db.execute(
            "UPDATE matches SET status = 'abandoned' WHERE match_code = ?", (code,)
        )
        await db.commit()
    async with connect(seeded_settings) as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) AS n FROM match_tiles mt JOIN matches m ON m.id = mt.match_id
            WHERE m.status = 'active' AND mt.status = 'unplayed'
            """
        )
        assert (await cursor.fetchone())["n"] == 0
        await cursor.close()
        cursor = await db.execute(
            "SELECT times_played FROM questions WHERE id = ?", (tile["question"]["id"],)
        )
        assert (await cursor.fetchone())["times_played"] == 1
        await cursor.close()
