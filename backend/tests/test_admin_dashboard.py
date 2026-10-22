from __future__ import annotations

import pytest

from tests.test_api_and_matches import make_match
from app.services.content import CATEGORY_SLUGS, DIFFICULTIES


def admin_headers() -> dict:
    return {"X-Admin-Token": "test-admin-token"}


@pytest.mark.asyncio
async def test_admin_dashboard_endpoints_require_token(client):
    for path in (
        "/api/v1/admin/question-bank",
        "/api/v1/admin/seed-history",
        "/api/v1/admin/matches",
    ):
        denied = await client.get(path)
        assert denied.status_code == 403, path
        assert denied.json()["error"]["code"] == "ADMIN_FORBIDDEN", path


@pytest.mark.asyncio
async def test_question_bank_reports_all_categories_and_three_difficulties(client):
    response = await client.get(
        "/api/v1/admin/question-bank", headers=admin_headers()
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["totals"]["questions"] > 0
    assert body["totals"]["buckets"] == len(CATEGORY_SLUGS) * len(DIFFICULTIES)
    assert body["totals"]["eligible"] <= body["totals"]["playable"]
    assert len(body["categories"]) == len(CATEGORY_SLUGS)
    assert len(body["buckets"]) == len(CATEGORY_SLUGS) * len(DIFFICULTIES)
    assert set(body["standards"]) == {
        "operational_min_per_bucket",
        "content_floor_per_bucket",
        "capacity_per_bucket",
    }
    assert {bucket["difficulty"] for bucket in body["buckets"]} == {200, 400, 600}
    for bucket in body["buckets"]:
        assert 0 <= bucket["eligible"] <= bucket["playable"] <= bucket["total"]
        assert bucket["used_current_cycle"] >= 0
        assert bucket["reserved_active"] >= 0
        assert bucket["total_plays"] >= bucket["played_questions"]
    for category in body["categories"]:
        assert set(category["buckets"]) == {"200", "400", "600"}
        assert category["eligible"] == sum(
            bucket["eligible"] for bucket in category["buckets"].values()
        )


@pytest.mark.asyncio
async def test_seed_history_returns_the_seeded_run(client):
    response = await client.get(
        "/api/v1/admin/seed-history?limit=5", headers=admin_headers()
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1
    assert body["runs"]
    run = body["runs"][0]
    assert run["seed_version"]
    assert run["deterministic_seed"] == 12345
    assert run["total_active"] > 0
    assert run["report"]["buckets"]
    assert run["created_at"]


@pytest.mark.asyncio
async def test_admin_matches_and_events_are_inspectable(client):
    board = await make_match(client, key="admin-events")
    code = board["match"]["match_code"]

    listing = await client.get("/api/v1/admin/matches?limit=10", headers=admin_headers())
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] >= 1
    row = next(item for item in body["matches"] if item["match_code"] == code)
    assert row["event_count"] >= 1
    assert row["selected_categories"] == board["match"]["selected_categories"]

    events = await client.get(
        f"/api/v1/admin/matches/{code}/events?limit=50", headers=admin_headers()
    )
    assert events.status_code == 200, events.text
    detail = events.json()
    assert detail["match"]["match_code"] == code
    assert detail["events"]
    assert all(event["event_type"] for event in detail["events"])
    assert all(isinstance(event["payload"], dict) for event in detail["events"])


@pytest.mark.asyncio
async def test_admin_match_filters_and_unknown_match(client):
    board = await make_match(client, key="admin-filter")
    code = board["match"]["match_code"]

    active = await client.get(
        "/api/v1/admin/matches?status=active", headers=admin_headers()
    )
    assert active.status_code == 200
    assert all(item["status"] == "active" for item in active.json()["matches"])
    assert any(item["match_code"] == code for item in active.json()["matches"])

    invalid_status = await client.get(
        "/api/v1/admin/matches?status=unknown", headers=admin_headers()
    )
    assert invalid_status.status_code == 422

    missing = await client.get(
        "/api/v1/admin/matches/NOPE/events", headers=admin_headers()
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "MATCH_NOT_FOUND"
