"""فحص حيّ شامل: تسجيل تثبيت ← إنشاء مباراة ← فتح خانة ← تعرّض ← مطابقة تكرار.

يعمل مقابل خادم FastAPI حقيقي عبر HTTP (لا استدعاءات داخلية).
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request

BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8099/api/v1")
DB = os.environ.get("E2E_DATABASE_PATH", "data/_migration_probe.db")
FAILURES: list[str] = []


def call(method, path, body=None, headers=None):
    data = None
    all_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        all_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{BASE}{path}", data=data, headers=all_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(payload)
        except json.JSONDecodeError:
            return exc.code, {"raw": payload}


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" :: {detail}" if detail else ""))
    if not condition:
        FAILURES.append(label)


CATEGORIES = ["flags", "capitals", "ucl", "riddles", "spotdiff", "clubs"]
payload = {
    "team1_name": "فريق الصقور",
    "team2_name": "فريق الذيابة",
    "starting_turn": "team1",
    "category_slugs": CATEGORIES,
}

# 1) تسجيل التثبيت: نفس المفتاح يعيد نفس السجل والاعتماد.
status, reg = call("POST", "/installations/register", headers={"Idempotency-Key": "e2e-install-1"})
check("register installation -> 201", status == 201, str(status))
status, reg2 = call("POST", "/installations/register", headers={"Idempotency-Key": "e2e-install-1"})
check(
    "same idempotency key -> same installation + same credential",
    reg2["installation_id"] == reg["installation_id"]
    and reg2["credential"] == reg["credential"]
    and reg2.get("idempotent_replay") is True,
    f"inst={reg2['installation_id']} shadow={reg2['shadow_user_id']}",
)
check("credential hash never exposed", "credential_hash" not in reg)
credential = reg["credential"]

# 2) إنشاء مباراة بلا ترويسة تثبيت مرفوضة.
status, body = call("POST", "/matches", payload, {"Idempotency-Key": "e2e-noinstall"})
check("create without X-Install-Token -> 403", status == 403, str(status))
check(
    "error code is INSTALL_TOKEN_REQUIRED",
    body.get("error", {}).get("code") == "INSTALL_TOKEN_REQUIRED",
    json.dumps(body.get("error", {}), ensure_ascii=False),
)

# 3) ملف لاعب مسمى + إشراكه.
status, profile = call("POST", "/users", {"username": "e2e-sara", "display_name": "سارة"})
check("create profile -> 201", status == 201, str(status))
status, dup = call("POST", "/users", {"username": "e2e-sara", "display_name": "مكرر"})
check("duplicate username -> 409", status == 409, str(status))

with_profile = dict(payload, team1_user_ids=[profile["id"]])

# 4) إنشاء مباراة باسم الملف.
status, board = call(
    "POST",
    "/matches",
    with_profile,
    {"Idempotency-Key": "e2e-create-1", "X-Install-Token": credential},
)
check("create match with install token -> 201", status == 201, str(status))
check("36 primaries + 18 backups", len(board["tiles"]) == 36 and len(board["backups"]) == 18)
check(
    "participants echo the named profile",
    any(p["user_id"] == profile["id"] for p in board["participants"]),
    json.dumps(board["participants"], ensure_ascii=False),
)
code = board["match"]["match_code"]
host = board["host_token"]
tile = board["tiles"][0]

# 5) فتح خانة = لحظة التعرّض.
status, opened = call(
    "POST",
    f"/matches/{code}/tiles/{tile['tile_key']}/open",
    {"expected_version": 1},
    {"Idempotency-Key": "e2e-open-1", "X-Host-Token": host},
)
check("open tile -> 200", status == 200, str(status))
seen_qid = opened["tile"]["question"]["id"]
version = opened["match"]["version"]

# 6) السجل القاعدي بعد الفتح: الملف + ظلّ الجهاز.
con = sqlite3.connect(DB)
history = con.execute(
    "SELECT user_id, question_id, outcome FROM user_question_history ORDER BY user_id"
).fetchall()
con.close()
check(
    "exposure recorded for profile + shadow user",
    len(history) == 2
    and {row[0] for row in history} == {profile["id"], reg["shadow_user_id"]}
    and all(row[1] == seen_qid and row[2] == "none" for row in history),
    str(history),
)

# 7) إعادة الفتح بنفس المفتاح لا تكرّر السجل.
status, replay = call(
    "POST",
    f"/matches/{code}/tiles/{tile['tile_key']}/open",
    {"expected_version": 1},
    {"Idempotency-Key": "e2e-open-1", "X-Host-Token": host},
)
check("replay open is idempotent", status == 200 and replay.get("idempotent_replay") is True)
con = sqlite3.connect(DB)
count = con.execute("SELECT COUNT(*) FROM user_question_history").fetchone()[0]
con.close()
check("replay did not duplicate history rows", count == 2, f"rows={count}")

# 8) مباراة جديدة على نفس التثبيت: السؤال الذي ظهر يجب ألا يُعاد.
status, board2 = call(
    "POST",
    "/matches",
    with_profile,
    {"Idempotency-Key": "e2e-create-2", "X-Install-Token": credential},
)
check("second match -> 201", status == 201, str(status))
allocated = {t["question"]["id"] for t in board2["tiles"] + board2["backups"]}
check("seen question excluded from next match", seen_qid not in allocated)

# 9) ملف آخر على نفس الجهاز: سجل الجهاز يستبعد السؤال أيضًا.
status, other = call("POST", "/users", {"username": "e2e-omar", "display_name": "عمر"})
status, board3 = call(
    "POST",
    "/matches",
    dict(payload, team1_user_ids=[other["id"]]),
    {"Idempotency-Key": "e2e-create-3", "X-Install-Token": credential},
)
check("other profile on same device -> 201", status == 201, str(status))
allocated3 = {t["question"]["id"] for t in board3["tiles"] + board3["backups"]}
check("device-level history excludes it for a different profile", seen_qid not in allocated3)

# 10) الملف نفسه على تثبيت مختلف: السجل يتبع الملف.
status, reg_b = call("POST", "/installations/register", headers={"Idempotency-Key": "e2e-install-2"})
status, board4 = call(
    "POST",
    "/matches",
    with_profile,
    {"Idempotency-Key": "e2e-create-4", "X-Install-Token": reg_b["credential"]},
)
check("same profile on a different device -> 201", status == 201, str(status))
allocated4 = {t["question"]["id"] for t in board4["tiles"] + board4["backups"]}
check("profile-level history follows the profile", seen_qid not in allocated4)

# 11) تكرار إنشاء بنفس المفتاح يعيد نفس المباراة.
status, again = call(
    "POST",
    "/matches",
    with_profile,
    {"Idempotency-Key": "e2e-create-1", "X-Install-Token": credential},
)
check(
    "idempotent create returns the same match",
    status == 201 and again["match"]["match_code"] == code,
    f"{again['match']['match_code']} vs {code}",
)

print()
if FAILURES:
    print(f"E2E FAILED: {len(FAILURES)} check(s): {FAILURES}")
    raise SystemExit(1)
print("E2E OK: all checks passed")
