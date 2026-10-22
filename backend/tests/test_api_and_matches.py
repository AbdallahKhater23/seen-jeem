from __future__ import annotations

import json

import pytest

from app.config import Settings
from app.db import connect
from app.schema import SCHEMA_VERSION
from app.services.content import CATEGORY_SLUGS
from tests.conftest import SIX_CATEGORIES, auth_headers, make_installation, match_headers


async def make_match(client, key="create-1", install=None, **overrides):
    install_credential = install
    if install_credential is None:
        registration = await make_installation(client, f"{key}-install")
        install_credential = registration["credential"]
    payload = {
        "team1_name": "فريق الصقور",
        "team2_name": "فريق الذيابة",
        "starting_turn": "team1",
        "category_slugs": list(SIX_CATEGORIES),
    }
    payload.update(overrides)
    response = await client.post(
        "/api/v1/matches",
        json=payload,
        headers=auth_headers(key, install=install_credential),
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_health_and_categories_contract(client):
    health = await client.get("/api/v1/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    # الإصدار يأتي من مصدر الحقيقة في التطبيق، لا من رقم مكتوب هنا:
    # أي هجرة تالية تضافية لا تُفشل العقد.
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["categories"] == len(CATEGORY_SLUGS)
    assert body["total_active"] > 0

    response = await client.get("/api/v1/categories")
    assert response.status_code == 200
    rows = response.json()
    assert [row["slug"] for row in rows] == list(CATEGORY_SLUGS)
    assert len(rows) == len(CATEGORY_SLUGS)
    for row in rows:
        assert row["name_ar"]
        assert row["icon"]
        assert isinstance(row["eligible_count"], int)
        assert row["eligible_count"] >= 0
        assert isinstance(row["capacity_100_matches"], bool)
    riddle = next(row for row in rows if row["slug"] == "riddles")
    assert riddle["capacity_100_matches"] is True
    general = next(row for row in rows if row["slug"] == "general")
    assert general["capacity_100_matches"] is False


@pytest.mark.asyncio
async def test_create_match_contract_and_board_hydration(client):
    board = await make_match(client)
    # توكن المضيف يُكشف مرة واحدة عند الإنشاء، ولا يظهر في أي قراءة لاحقة.
    assert isinstance(board["host_token"], str) and len(board["host_token"]) >= 32
    assert board["match"]["version"] == 1
    assert board["match"]["current_turn"] == "team1"
    assert board["match"]["selected_categories"] == SIX_CATEGORIES
    assert len(board["tiles"]) == 36
    assert len(board["backups"]) == 18
    assert board["draft"]["complete"] is False
    assert board["draft"]["current_team"] == "team1"
    assert len(board["draft"]["order"]) == 6
    assert all(tile["allocation_cycle"] >= 1 for tile in board["tiles"])
    assert all(tile["question"]["fact_group_id"] is None for tile in board["tiles"])
    assert all(tile["question"]["answer_text"] is None for tile in board["tiles"] + board["backups"])

    refreshed = await client.get(f"/api/v1/matches/{board['match']['match_code']}")
    assert refreshed.status_code == 200
    assert refreshed.json()["match"]["selected_categories"] == SIX_CATEGORIES
    assert len(refreshed.json()["backups"]) == 18
    assert "host_token" not in refreshed.json()

    question_id = board["tiles"][0]["question"]["id"]
    detail = await client.get(f"/api/v1/questions/{question_id}")
    assert detail.status_code == 200
    assert detail.json()["fact_group_id"] is None
    assert detail.json()["answer_text"] is None


@pytest.mark.asyncio
async def test_starting_turn_is_persisted(client):
    board = await make_match(client, key="turn-team2", starting_turn="team2")
    assert board["match"]["current_turn"] == "team2"
    assert board["match"]["coin_toss_winner"] == "team2"


@pytest.mark.asyncio
async def test_idempotency_replay_and_payload_conflict(client):
    registration = await make_installation(client, "same-create-install")
    install = registration["credential"]
    first = await make_match(client, key="same-create", install=install)
    second = await make_match(client, key="same-create", install=install)
    assert first["match"]["match_code"] == second["match"]["match_code"]
    conflict = await client.post(
        "/api/v1/matches",
        json={
            "team1_name": "اسم مختلف",
            "team2_name": "فريق الذيابة",
            "starting_turn": "team1",
            "category_slugs": list(SIX_CATEGORIES),
        },
        headers=auth_headers("same-create", install=install),
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.asyncio
async def test_resolve_and_reroll_endpoints(client):
    board = await make_match(client)
    code = board["match"]["match_code"]
    tile = board["tiles"][0]
    host = board["host_token"]
    reroll = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile['tile_key']}/reroll",
        json={"expected_version": 1},
        headers=auth_headers("api-reroll", host=host),
    )
    assert reroll.status_code == 200, reroll.text
    new_question = reroll.json()["tile"]["question"]["id"]
    assert new_question != tile["question"]["id"]

    resolved = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile['tile_key']}/resolve",
        json={"outcome": "team1", "powers_applied": [], "expected_version": 2},
        headers=auth_headers("api-resolve", host=host),
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["match"]["score_team1"] == tile["difficulty"]
    assert resolved.json()["tile"]["question"]["id"] == new_question

    duplicate = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile['tile_key']}/resolve",
        json={"outcome": "team1", "powers_applied": [], "expected_version": 3},
        headers=auth_headers("api-resolve-2", host=host),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "TILE_ALREADY_PLAYED"


@pytest.mark.asyncio
async def test_score_adjustment_is_idempotent(client):
    board = await make_match(client)
    code = board["match"]["match_code"]
    body = {"team": "team2", "delta": 100, "reason": "تصحيح", "expected_version": 1}
    host = board["host_token"]
    first = await client.post(
        f"/api/v1/matches/{code}/score-adjustments",
        json=body,
        headers=auth_headers("adj-1", host=host),
    )
    assert first.status_code == 200
    assert first.json()["match"]["score_team2"] == 100
    replay = await client.post(
        f"/api/v1/matches/{code}/score-adjustments",
        json=body,
        headers=auth_headers("adj-1", host=host),
    )
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["match"]["score_team2"] == 100
    mismatch = await client.post(
        f"/api/v1/matches/{code}/score-adjustments",
        json={**body, "delta": -100},
        headers=auth_headers("adj-1", host=host),
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.asyncio
async def test_full_match_via_api_completes(client):
    board = await make_match(client)
    code = board["match"]["match_code"]
    host = board["host_token"]
    for index in range(36):
        fresh = (await client.get(f"/api/v1/matches/{code}")).json()
        tile = next(tile for tile in fresh["tiles"] if tile["status"] == "unplayed")
        response = await client.post(
            f"/api/v1/matches/{code}/tiles/{tile['tile_key']}/resolve",
            json={
                "outcome": "none",
                "powers_applied": [],
                "expected_version": fresh["match"]["version"],
            },
            headers=auth_headers(f"full-{index}", host=host),
        )
        assert response.status_code == 200, response.text
    final = (await client.get(f"/api/v1/matches/{code}")).json()
    assert final["match"]["status"] == "completed"
    assert final["match"]["winner"] == "tie"
    events = await client.get(f"/api/v1/matches/{code}/events?limit=200")
    assert len(events.json()["events"]) >= 37


@pytest.mark.asyncio
async def test_match_mutations_require_host_token(client):
    board = await make_match(client, key="host-guard")
    code = board["match"]["match_code"]
    host = board["host_token"]
    tile = board["tiles"][0]

    # القراءة تبقى عامة: اللوحة والأحداث بدون توكن.
    assert (await client.get(f"/api/v1/matches/{code}")).status_code == 200
    assert (await client.get(f"/api/v1/matches/{code}/events")).status_code == 200

    # بدون توكن: 403 على كل عملية تغيير.
    naked = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile['tile_key']}/reroll",
        json={"expected_version": 1},
        headers=auth_headers("host-naked"),
    )
    assert naked.status_code == 403
    assert naked.json()["error"]["code"] == "HOST_TOKEN_REQUIRED"

    # توكن خطأ: 403 أيضًا، ولا يتسرب أي تغيير.
    forged = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile['tile_key']}/reroll",
        json={"expected_version": 1},
        headers=auth_headers("host-forged", host="forged-token-value"),
    )
    assert forged.status_code == 403
    assert forged.json()["error"]["code"] == "HOST_TOKEN_INVALID"

    # المضيف الشرعي يعبر بنجاح.
    admitted = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile['tile_key']}/reroll",
        json={"expected_version": 1},
        headers=auth_headers("host-admitted", host=host),
    )
    assert admitted.status_code == 200, admitted.text


@pytest.mark.asyncio
async def test_abandoned_match_rejects_mutations(client):
    board = await make_match(client)
    code = board["match"]["match_code"]
    host = board["host_token"]
    abandoned = await client.post(
        f"/api/v1/matches/{code}/abandon",
        json={"expected_version": 1},
        headers=auth_headers("abandon-1", host=host),
    )
    assert abandoned.status_code == 200
    assert abandoned.json()["match"]["status"] == "abandoned"
    tile = board["tiles"][0]
    response = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile['tile_key']}/resolve",
        json={"outcome": "team1", "powers_applied": [], "expected_version": 2},
        headers=auth_headers("after-abandon", host=host),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MATCH_NOT_ACTIVE"


@pytest.mark.asyncio
async def test_pool_sync_endpoint_reports_truthful_state(client, monkeypatch):
    import app.api.routes.public as public_module

    async def fake_run(settings, job_id, *, force=True):
        return {"job_id": job_id, "status": "succeeded", "sources": []}

    monkeypatch.setattr(public_module, "run_sync_job", fake_run)
    response = await client.post("/api/v1/pool/sync", params={"source": "restcountries"})
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["status"] == "queued"
    assert body["detail"]["durable"] is False

    status = await client.get("/api/v1/pool/sync")
    assert status.status_code == 200
    assert status.json()["jobs"]
    assert status.json()["durable"] is False


@pytest.mark.asyncio
async def test_error_shapes_and_admin_contract(client):
    unknown = await client.get("/api/v1/no-such-route")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "NOT_FOUND"
    missing = await client.get("/api/v1/matches/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "MATCH_NOT_FOUND"
    invalid = await client.post(
        "/api/v1/matches",
        json={"team1_name": "", "team2_name": "ب"},
        headers=auth_headers("invalid-body"),
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    denied = await client.get("/api/v1/admin/seed-status")
    assert denied.status_code == 403
    allowed = await client.get(
        "/api/v1/admin/seed-status", headers={"X-Admin-Token": "test-admin-token"}
    )
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["complete"] is True
    assert body["capacity_100_matches"] is False
    assert body["total_active"] > 0


def test_cors_rejects_wildcard_with_credentials():
    safe = Settings(allow_lan_wildcard_origin=True, allow_credentials=False)
    assert safe.cors_config["allow_origins"] == ["*"]
    with pytest.raises(ValueError):
        _ = Settings(allow_lan_wildcard_origin=True, allow_credentials=True).cors_config
    with pytest.raises(ValueError):
        _ = Settings(cors_origins=("*",)).cors_config
