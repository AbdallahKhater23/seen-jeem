from __future__ import annotations

import pytest

from app.db import transaction
from tests.conftest import auth_headers
from tests.test_api_and_matches import make_match


async def draft_match(client, code: str, powers: list[str], host: str) -> tuple[int, list[dict]]:
    assert len(powers) == 6
    version = 1
    picks = []
    for index, power in enumerate(powers):
        response = await client.post(
            f"/api/v1/matches/{code}/draft/picks",
            json={"power_id": power, "expected_version": version},
            headers=auth_headers(f"draft-{index}-{code[:4]}", host=host),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        picks.append(body["pick"])
        version = body["match"]["version"]
    return version, picks


async def open_tile(client, code: str, tile_key: str, version: int, host: str) -> dict:
    response = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/open",
        json={"expected_version": version},
        headers=auth_headers(f"open-{tile_key}-{version}-{code[:4]}", host=host),
    )
    assert response.status_code == 200, response.text
    return response.json()


def power_order_for_team1(power_id: str) -> list[str]:
    """قوى الفريق الأول في المواضع 0 و3 و4؛ الباقي للفريق الثاني."""
    return [power_id, "trap", "steal", "double", "two_answers", "noise"]


@pytest.mark.asyncio
async def test_draft_follows_snake_order_and_rejects_duplicate_team_power(client):
    board = await make_match(client)
    code = board["match"]["match_code"]
    host = board["host_token"]
    version = 1
    expected_teams = ["team1", "team2", "team2", "team1", "team1", "team2"]
    powers = ["pit", "steal", "switch", "trap", "double", "noise"]

    for index, (power, team) in enumerate(zip(powers, expected_teams, strict=True)):
        response = await client.post(
            f"/api/v1/matches/{code}/draft/picks",
            json={"power_id": power, "expected_version": version},
            headers=auth_headers(f"snake-{index}", host=host),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["pick"]["team"] == team
        assert body["pick"]["pick_index"] == index
        version = body["match"]["version"]

    finished = (await client.get(f"/api/v1/matches/{code}")).json()["draft"]
    assert finished["complete"] is True
    assert finished["current_team"] is None
    assert [pick["power_id"] for pick in finished["picks"]] == powers

    extra = await client.post(
        f"/api/v1/matches/{code}/draft/picks",
        json={"power_id": "pit", "expected_version": version},
        headers=auth_headers("snake-extra", host=host),
    )
    assert extra.status_code == 409
    assert extra.json()["error"]["code"] == "DRAFT_COMPLETE"


@pytest.mark.asyncio
async def test_draft_allows_same_power_on_both_teams_but_not_twice_on_one(client):
    board = await make_match(client, key="draft-duplicates")
    code = board["match"]["match_code"]
    host = board["host_token"]
    version = 1

    first = await client.post(
        f"/api/v1/matches/{code}/draft/picks",
        json={"power_id": "pit", "expected_version": version},
        headers=auth_headers("dup-1", host=host),
    )
    assert first.status_code == 200, first.text
    version = first.json()["match"]["version"]

    shared = await client.post(
        f"/api/v1/matches/{code}/draft/picks",
        json={"power_id": "pit", "expected_version": version},
        headers=auth_headers("dup-2", host=host),
    )
    assert shared.status_code == 200, shared.text
    assert shared.json()["pick"]["team"] == "team2"
    version = shared.json()["match"]["version"]

    duplicate = await client.post(
        f"/api/v1/matches/{code}/draft/picks",
        json={"power_id": "pit", "expected_version": version},
        headers=auth_headers("dup-3", host=host),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "POWER_ALREADY_DRAFTED"


@pytest.mark.asyncio
async def test_activation_enforces_ownership_side_duplicate_and_reveal(client):
    board = await make_match(client, key="power-activation")
    code = board["match"]["match_code"]
    host = board["host_token"]
    tile_key = board["tiles"][0]["tile_key"]
    base = board["tiles"][0]["difficulty"]
    version, _ = await draft_match(
        client, code, ["pit", "steal", "noise", "trap", "double", "switch"], host
    )

    opened = await open_tile(client, code, tile_key, version, host)
    version = opened["match"]["version"]
    assert opened["session"]["active_team"] == "team1"

    activated = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/powers/pit/activate",
        json={"team": "team1", "expected_version": version},
        headers=auth_headers("act-pit", host=host),
    )
    assert activated.status_code == 200, activated.text
    body = activated.json()
    assert body["activation"]["team"] == "team1"
    assert body["tile"]["powers_applied"] == ["pit"]
    version = body["match"]["version"]

    reused = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/powers/pit/activate",
        json={"team": "team1", "expected_version": version},
        headers=auth_headers("act-pit-again", host=host),
    )
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "POWER_ALREADY_USED"

    # مهاجم خارجي يدّعي أنه الفريق الآخر: يُرفض على باب المضيف قبل فحص القوة.
    intruder = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/powers/trap/activate",
        json={"team": "team1", "expected_version": version},
        headers=auth_headers("act-intruder"),
    )
    assert intruder.status_code == 403
    assert intruder.json()["error"]["code"] == "HOST_TOKEN_REQUIRED"

    wrong_side = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/powers/trap/activate",
        json={"team": "team1", "expected_version": version},
        headers=auth_headers("act-trap", host=host),
    )
    assert wrong_side.status_code == 409
    assert wrong_side.json()["error"]["code"] == "POWER_SIDE_NOT_ALLOWED"

    not_owned = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/powers/steal/activate",
        json={"team": "team1", "expected_version": version},
        headers=auth_headers("act-not-owned", host=host),
    )
    assert not_owned.status_code == 409
    assert not_owned.json()["error"]["code"] == "POWER_NOT_OWNED"

    revealed = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/reveal",
        json={"expected_version": version},
        headers=auth_headers("reveal-1", host=host),
    )
    assert revealed.status_code == 200, revealed.text
    version = revealed.json()["match"]["version"]

    after_reveal = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/powers/steal/activate",
        json={"team": "team2", "expected_version": version},
        headers=auth_headers("act-after-reveal", host=host),
    )
    assert after_reveal.status_code == 409
    assert after_reveal.json()["error"]["code"] == "QUESTION_REVEALED"

    # التسجيل يستخدم قوى الخادم، لا قائمة يرسلها العميل.
    resolved = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/resolve",
        json={"outcome": "team1", "powers_applied": ["pit"], "expected_version": version},
        headers=auth_headers("resolve-pit", host=host),
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["match"]["score_team1"] == base
    assert resolved.json()["match"]["score_team2"] == -base


@pytest.mark.asyncio
async def test_resolve_rejects_client_powers_that_were_not_activated(client):
    board = await make_match(client, key="power-mismatch")
    code = board["match"]["match_code"]
    host = board["host_token"]
    tile_key = board["tiles"][0]["tile_key"]
    version, _ = await draft_match(
        client, code, ["double", "trap", "steal", "pit", "two_answers", "noise"], host
    )
    opened = await open_tile(client, code, tile_key, version, host)
    version = opened["match"]["version"]

    resolved = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/resolve",
        json={"outcome": "team1", "powers_applied": ["double"], "expected_version": version},
        headers=auth_headers("resolve-unactivated", host=host),
    )
    assert resolved.status_code == 409
    assert resolved.json()["error"]["code"] == "POWERS_MISMATCH"


@pytest.mark.asyncio
async def test_switch_window_is_enforced_by_the_server(client, settings):
    board = await make_match(client, key="switch-window")
    code = board["match"]["match_code"]
    host = board["host_token"]
    tile_key = board["tiles"][0]["tile_key"]
    version, _ = await draft_match(
        client, code, ["switch", "trap", "steal", "pit", "double", "noise"], host
    )
    opened = await open_tile(client, code, tile_key, version, host)
    version = opened["match"]["version"]

    async with transaction(settings) as db:
        await db.execute(
            "UPDATE match_tiles SET opened_at = datetime('now', '-16 seconds')"
            " WHERE tile_key = ?",
            (tile_key,),
        )

    late = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/powers/switch/activate",
        json={"team": "team1", "expected_version": version},
        headers=auth_headers("switch-late", host=host),
    )
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "POWER_WINDOW_CLOSED"

    # إعادة الفتح لا يجب أن تسمح بإعادة استخدام القوة؛ القوة ما انستهلكت أصلًا.
    async with transaction(settings) as db:
        await db.execute(
            "UPDATE match_tiles SET opened_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')"
            " WHERE tile_key = ?",
            (tile_key,),
        )

    switched = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/powers/switch/activate",
        json={"team": "team1", "expected_version": version},
        headers=auth_headers("switch-in-window", host=host),
    )
    assert switched.status_code == 200, switched.text
    body = switched.json()
    assert body["backup_used"]
    assert body["tile"]["question"]["id"] != opened["tile"]["question"]["id"]
    assert "switch" in body["tile"]["powers_applied"]
    assert body["tile"]["revealed_at"] is None


@pytest.mark.asyncio
async def test_abandon_tile_clears_session_without_playing_tile(client):
    board = await make_match(client, key="tile-abandon")
    code = board["match"]["match_code"]
    host = board["host_token"]
    tile_key = board["tiles"][0]["tile_key"]
    version, _ = await draft_match(
        client, code, ["pit", "trap", "steal", "double", "two_answers", "noise"], host
    )
    opened = await open_tile(client, code, tile_key, version, host)
    version = opened["match"]["version"]

    abandoned = await client.post(
        f"/api/v1/matches/{code}/tiles/{tile_key}/abandon",
        json={"expected_version": version},
        headers=auth_headers("abandon-tile", host=host),
    )
    assert abandoned.status_code == 200, abandoned.text
    body = abandoned.json()
    assert body["tile"]["opened_at"] is None
    assert body["tile"]["revealed_at"] is None
    assert body["tile"]["status"] == "unplayed"

    reopened = await open_tile(client, code, tile_key, body["match"]["version"], host)
    assert reopened["session"]["opened_at"]
