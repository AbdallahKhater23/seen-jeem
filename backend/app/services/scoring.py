"""حساب النقاط النقي والقابل للاختبار.

الترتيب الحتمي:
1. الجائزة الأساسية/دبل أو ابلع للفريق الفائز.
2. الحفرة تخصم من الخصم عندما يفوز صاحب الدور.
3. الفخ يخصم من صاحب الدور عندما لا يفوز.
4. دبل أو ابلع يخصم من صاحب الدور عندما لا يفوز.
لا تُطبّق أي قوة أكثر من مرة، ولا تُعرف قوة غير معروفة هنا (تُرفض قبل الوصول).
"""

from __future__ import annotations

from typing import Iterable

OUTCOMES = frozenset({"team1", "team2", "none"})
POWER_IDS = frozenset(
    {
        "pit",
        "trap",
        "rest",
        "steal",
        "two_answers",
        "noise",
        "time_break",
        "double",
        "switch",
    }
)


def compute_score_deltas(
    base_points: int,
    outcome: str,
    active_team: str,
    defending_team: str,
    active_powers: Iterable[str] = (),
) -> dict:
    if outcome not in OUTCOMES:
        raise ValueError("نتيجة غير معروفة.")
    if active_team not in {"team1", "team2"} or defending_team not in {"team1", "team2"}:
        raise ValueError("معرّف فريق غير صالح.")
    if active_team == defending_team:
        raise ValueError("الفريق النشط والمدافع لازم يختلفون.")
    powers = set(active_powers)
    unknown = powers - POWER_IDS
    if unknown:
        raise ValueError(f"قوة غير معروفة: {', '.join(sorted(unknown))}")
    if base_points not in {200, 400, 600}:
        raise ValueError("قيمة الخانة لازم تكون 200 أو 400 أو 600.")

    deltas = {active_team: 0, defending_team: 0}
    ledger: list[dict] = []

    def add(team: str, delta: int, reason: str, power: str | None = None) -> None:
        if delta == 0:
            return
        deltas[team] += delta
        entry = {"team": team, "delta": delta, "reason": reason}
        if power:
            entry["power"] = power
        ledger.append(entry)

    active_won = outcome == active_team
    defending_won = outcome == defending_team
    nobody = outcome == "none"

    if active_won:
        if "double" in powers:
            add(active_team, base_points * 2, "فوز صاحب الدور مع دبل أو ابلع", "double")
        else:
            add(active_team, base_points, "جائزة الخانة لصاحب الدور")
        if "pit" in powers:
            add(defending_team, -base_points, "الحفرة: خصم من الفريق المدافع", "pit")
    elif defending_won:
        add(defending_team, base_points, "جائزة الخانة بعد سرقة ناجحة")
        if "double" in powers:
            add(active_team, -base_points, "دبل أو ابلع: خسارة صاحب الدور", "double")
    elif nobody:
        if "double" in powers:
            add(active_team, -base_points, "دبل أو ابلع: لا فائز", "double")

    if not active_won and "trap" in powers:
        add(active_team, -(base_points // 2), "الفخ: نصف قيمة الخانة", "trap")

    return {
        "deltas": deltas,
        "ledger": ledger,
        "winner": active_team if active_won else defending_team if defending_won else None,
    }
