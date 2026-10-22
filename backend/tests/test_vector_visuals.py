"""Synthetic visual fixtures: geometry/security, never historical evidence."""
import json

import pytest

from app.services.vector_visuals import public_visual, validate_visual


def career():
    return {"version": 1, "type": "career_tree", "nodes": [
        {"label": "النادي الأول"}, {"label": "إجابة سرية", "hidden": True},
        {"label": "النادي الثالث", "years": "2010–2012", "loan": True},
    ]}


def lineup():
    return {"version": 1, "type": "lineup_svg", "formation": "4-4-2",
            "schematic": True, "players": [
                {"label": f"لاعب {i}", "x": 10 + i % 4 * 25, "y": 10 + i // 4 * 30,
                 "hidden": i == 10, "number": i + 1} for i in range(11)]}


def test_public_visual_removes_hidden_identity_and_private_solution():
    original = career()
    public = public_visual(original)
    assert "إجابة سرية" not in json.dumps(public, ensure_ascii=False)
    assert public["nodes"][1] == {"hidden": True}
    assert public_visual(original, revealed=True)["nodes"][1]["label"] == "إجابة سرية"
    assert original["nodes"][1]["label"] == "إجابة سرية"
    odd = {"version": 1, "type": "odd_one_out_grid", "items": [
        {"label": f"خيار {i}"} for i in range(4)], "odd_index": 3,
        "common_property": "سبب الإجابة"}
    assert "odd_index" not in public_visual(odd)
    assert "common_property" not in public_visual(odd)
    radar = {"version": 1, "type": "shot_radar", "schematic": True,
        "shot_x": 70, "shot_y": 40, "goal_x": 92, "goal_y": 50,
        "context_label": "نهائي 2002", "answer_label": "إجابة سرية"}
    assert "answer_label" not in public_visual(radar)
    assert public_visual(radar, revealed=True)["answer_label"] == "إجابة سرية"


def test_lineup_projection_removes_hidden_number_too():
    hidden = public_visual(lineup())["players"][-1]
    assert set(hidden) == {"hidden", "x", "y"}


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(version=2), lambda p: p.update(svg="<script>bad</script>"),
    lambda p: p["nodes"][0].update(label="<script>alert(1)</script>"),
    lambda p: p["nodes"][0].update(label="x" * 121),
    lambda p: p["nodes"][0].update(label="bad\u202e"),
    lambda p: p["nodes"][0].update(secret="answer"),
])
def test_rejects_untrusted_or_unsupported_payloads(mutation):
    payload = career()
    mutation(payload)
    with pytest.raises(ValueError):
        validate_visual(payload)


def test_rejects_incomplete_or_invalid_lineup():
    payload = lineup()
    validate_visual(payload)
    payload["players"].pop()
    with pytest.raises(ValueError):
        validate_visual(payload)
    payload = lineup()
    payload["players"][0]["x"] = float("nan")
    with pytest.raises(ValueError):
        validate_visual(payload)


def test_invalid_runtime_payload_fails_closed():
    assert public_visual({"version": 1, "type": "raw_svg"}) is None


def test_question_projection_separates_all_answers_and_sources():
    from app.services.matches import _question_out

    row = {key: "secret" for key in (
        "answer_text", "tolerance", "explanation", "source_name", "source_url",
        "source_checked_at", "source_license", "source_claim", "fact_group_id")}
    row.update(question_id=1, question_category_slug="career", question_category_name="المشوار",
               question_difficulty=400, question_type="text", question_text="منو اللاعب؟",
               flag_code=None, media_url_a=None, media_url_b=None, content_origin="curated",
               payload_json=None, visual_json=json.dumps(career()), revealed_at=None, status="unplayed")
    hidden = _question_out(row)
    assert "secret" not in json.dumps(hidden)
    assert "إجابة سرية" not in json.dumps(hidden, ensure_ascii=False)
    row["revealed_at"] = "2026-10-21"
    answer = _question_out(row)
    assert answer["answer_text"] == "secret"
    assert answer["visual"]["nodes"][1]["label"] == "إجابة سرية"


def test_legacy_idempotency_snapshot_is_redacted_without_changing_reveal_state():
    from app.services.matches import _redact_cached_answers

    snapshot = {"tiles": [{"status": "unplayed", "revealed_at": None, "question": {
        "answer_text": "secret", "tolerance": "alias", "source_claim": "secret",
        "source_url": "https://source/secret", "fact_group_id": "secret", "explanation": "secret",
        "visual": career(), "payload": {"kind": "matchstick", "equation": "1+1=3",
            "solution": "secret", "end": [1], "moves": [1]},
    }}], "backups": [{"status": "unplayed", "question": {"answer_text": "secret"}}]}
    _redact_cached_answers(snapshot)
    assert "secret" not in json.dumps(snapshot)
    assert "إجابة سرية" not in json.dumps(snapshot, ensure_ascii=False)
    # Replaying an already projected public visual preserves it.
    _redact_cached_answers(snapshot)
    assert snapshot["tiles"][0]["question"]["visual"]["nodes"][1] == {"hidden": True}
    revealed = {"tile": {"status": "unplayed", "revealed_at": "2026-10-21", "question": {"answer_text": "authorized"}}}
    _redact_cached_answers(revealed)
    assert revealed["tile"]["question"]["answer_text"] == "authorized"


@pytest.mark.asyncio
async def test_stored_legacy_idempotency_response_cannot_bypass_projection(settings):
    from app.db import transaction
    from app.services.matches import _idempotent_replay

    old = {"tiles": [{"status": "unplayed", "question": {
        "answer_text": "legacy-secret", "source_url": "https://legacy-secret", "visual": career()}}]}
    async with transaction(settings) as db:
        await db.execute("""INSERT INTO idempotency_keys(scope,key,request_hash,status_code,response_json)
            VALUES ('create_match','legacy','hash',201,?)""", (json.dumps(old),))
        replay = await _idempotent_replay(db, "create_match", "legacy", "hash")
        assert replay["idempotent_replay"] is True
        assert "legacy-secret" not in json.dumps(replay)
        assert "إجابة سرية" not in json.dumps(replay, ensure_ascii=False)


@pytest.mark.asyncio
async def test_all_mutation_caches_require_host_even_when_key_and_request_are_known(client, settings):
    from app.db import transaction
    from app.services import matches
    from app.utils.errors import AppError
    from tests.test_api_and_matches import make_match

    board = await make_match(client, key="all-caches-host")
    code, tile = board["match"]["match_code"], board["tiles"][0]["tile_key"]
    simple = {"expected_version": 1}
    cases = [
        (f"draft:{code}", matches.draft_power, [code], {"power_id": "pit"}, {**simple, "power_id": "pit"}),
        (f"open:{code}:{tile}", matches.open_tile, [code, tile], {}, simple),
        (f"reveal:{code}:{tile}", matches.reveal_tile, [code, tile], {}, simple),
        (f"abandon-tile:{code}:{tile}", matches.abandon_tile, [code, tile], {}, simple),
        (f"power:{code}:{tile}:double:team1", matches.activate_power, [code, tile, "double"],
         {"team": "team1"}, {**simple, "team": "team1", "power_id": "double"}),
        (f"resolve:{code}:{tile}", matches.resolve_tile, [code, tile],
         {"outcome": "none", "powers_applied": []}, {**simple, "outcome": "none", "powers_applied": []}),
        (f"reroll:{code}:{tile}", matches.reroll_tile, [code, tile], {}, simple),
        (f"adjust:{code}", matches.adjust_score, [code], {"team": "team1", "delta": 100, "reason": "test"},
         {**simple, "team": "team1", "delta": 100, "reason": "test"}),
        (f"abandon:{code}", matches.abandon_match, [code], {}, simple),
        (f"complete:{code}", matches.complete_match, [code], {}, simple),
    ]
    for index, (scope, service, args, kwargs, request) in enumerate(cases):
        key = f"legacy-host-{index}"
        async with transaction(settings) as db:
            await db.execute("""INSERT INTO idempotency_keys(scope,key,request_hash,status_code,response_json)
                VALUES (?,?,?,200,?)""", (scope, key, matches._hash_payload(scope, request), '{"sentinel":true}'))
        with pytest.raises(AppError) as denied:
            await service(settings, *args, **kwargs, expected_version=1, idempotency_key=key)
        assert denied.value.code == "HOST_TOKEN_REQUIRED", service.__name__
        allowed = await service(settings, *args, **kwargs, expected_version=1,
                                idempotency_key=key, host_token=board["host_token"])
        assert allowed == {"sentinel": True, "idempotent_replay": True}, service.__name__


@pytest.mark.asyncio
async def test_answer_is_hidden_through_open_and_delivered_by_authorized_reveal(client, settings):
    from app.db import transaction
    from tests.conftest import auth_headers
    from tests.test_api_and_matches import make_match
    from tests.test_powers import draft_match, open_tile

    board = await make_match(client, key="secure-visual-flow")
    code = board["match"]["match_code"]
    tile = board["tiles"][0]
    # Attach a synthetic visual to an allocated question; no historical claim.
    async with transaction(settings) as db:
        await db.execute("INSERT INTO football_entities(id,display_name_ar) VALUES ('test:visual','اختبار')")
        await db.execute("INSERT INTO football_facts(id,topic_id,primary_entity_id) VALUES ('test:visual','test','test:visual')")
        await db.execute("""INSERT INTO question_metadata(question_id,fact_id,archetype,template_family,
            quality_score,editorial_note,visual_json) VALUES (?,'test:visual','career_clues','test',1,'test',?)
            ON CONFLICT(question_id) DO UPDATE SET visual_json=excluded.visual_json""",
            (tile["question"]["id"], json.dumps(career(), ensure_ascii=False)))
    refreshed_visual = (await client.get(f"/api/v1/matches/{code}")).json()
    visual_question = next(t for t in refreshed_visual["tiles"] if t["tile_key"] == tile["tile_key"])["question"]
    assert visual_question["visual"]["nodes"][1] == {"hidden": True}
    assert "إجابة سرية" not in json.dumps(refreshed_visual, ensure_ascii=False)
    for candidate in board["tiles"] + board["backups"]:
        assert candidate["question"]["answer_text"] is None
        assert candidate["question"]["source_url"] is None
    version, _ = await draft_match(client, code, ["pit", "trap", "steal", "double", "two_answers", "noise"], board["host_token"])
    opened = await open_tile(client, code, tile["tile_key"], version, board["host_token"])
    assert opened["tile"]["question"]["answer_text"] is None
    url = f"/api/v1/matches/{code}/tiles/{tile['tile_key']}/reveal"
    version = opened["match"]["version"]
    denied = await client.post(url, json={"expected_version": version}, headers=auth_headers("secure-reveal-denied"))
    assert denied.status_code == 403
    revealed = await client.post(url, json={"expected_version": version},
                                 headers=auth_headers("secure-reveal-ok", host=board["host_token"]))
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["tile"]["question"]["answer_text"]
    assert revealed.json()["tile"]["question"]["visual"]["nodes"][1]["label"] == "إجابة سرية"
    stolen_replay = await client.post(url, json={"expected_version": version}, headers=auth_headers("secure-reveal-ok"))
    assert stolen_replay.status_code == 403
    refreshed = (await client.get(f"/api/v1/matches/{code}")).json()
    assert next(t for t in refreshed["tiles"] if t["tile_key"] == tile["tile_key"])["question"]["answer_text"]
    assert all(t["question"]["answer_text"] is None for t in refreshed["backups"])

