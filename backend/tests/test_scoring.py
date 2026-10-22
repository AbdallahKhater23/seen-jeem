from __future__ import annotations

import pytest

from app.services.scoring import compute_score_deltas


def score(outcome, powers=(), base=400):
    return compute_score_deltas(base, outcome, "team1", "team2", powers)


def test_plain_outcomes():
    active = score("team1")
    assert active["deltas"] == {"team1": 400, "team2": 0}
    assert active["winner"] == "team1"
    steal = score("team2")
    assert steal["deltas"] == {"team1": 0, "team2": 400}
    assert steal["winner"] == "team2"
    nobody = score("none")
    assert nobody["deltas"] == {"team1": 0, "team2": 0}
    assert nobody["winner"] is None


def test_pit_only_on_active_win():
    win = score("team1", ["pit"])
    assert win["deltas"] == {"team1": 400, "team2": -400}
    loss = score("team2", ["pit"])
    assert loss["deltas"] == {"team1": 0, "team2": 400}
    assert not any(entry.get("power") == "pit" for entry in loss["ledger"])


def test_trap_only_when_active_does_not_win():
    steal = score("team2", ["trap"])
    assert steal["deltas"] == {"team1": -200, "team2": 400}
    nobody = score("none", ["trap"])
    assert nobody["deltas"] == {"team1": -200, "team2": 0}
    win = score("team1", ["trap"])
    assert win["deltas"] == {"team1": 400, "team2": 0}


def test_double_outcomes_and_steal():
    win = score("team1", ["double"])
    assert win["deltas"] == {"team1": 800, "team2": 0}
    loss = score("team2", ["double"])
    assert loss["deltas"] == {"team1": -400, "team2": 400}
    nobody = score("none", ["double"])
    assert nobody["deltas"] == {"team1": -400, "team2": 0}


def test_double_plus_pit_and_trap_stack_deterministically():
    combo = score("team1", ["double", "pit"])
    assert combo["deltas"] == {"team1": 800, "team2": -400}
    assert [entry["power"] for entry in combo["ledger"] if entry.get("power")] == ["double", "pit"]
    combo_loss = score("team2", ["double", "trap"])
    assert combo_loss["deltas"] == {"team1": -600, "team2": 400}  # -base و-نصف base معًا
    assert [entry["power"] for entry in combo_loss["ledger"] if entry.get("power")] == ["double", "trap"]


def test_rest_steal_noise_time_break_two_answers_and_switch_do_not_change_points():
    for power in ("rest", "steal", "noise", "time_break", "two_answers", "switch"):
        assert score("team1", [power])["deltas"] == {"team1": 400, "team2": 0}


@pytest.mark.parametrize(
    "args",
    [
        ("bad", (), 400),
        ("team1", ("unknown",), 400),
        ("team1", (), 300),
    ],
)
def test_invalid_inputs_raise(args):
    outcome, powers, base = args
    with pytest.raises(ValueError):
        compute_score_deltas(base, outcome, "team1", "team2", powers)
