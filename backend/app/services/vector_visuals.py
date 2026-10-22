"""Trusted structured diagrams. Validation checks structure, not historical truth.

All layouts are schematic; source verification belongs to the publication gate.
No HTML/SVG markup, external URLs, or freeform attributes are accepted.
"""
from __future__ import annotations

import copy
import json
import math
import unicodedata

SUPPORTED_VISUAL_TYPES = frozenset({"lineup_svg", "career_tree", "odd_one_out_grid", "shot_radar"})
MAX_VISUAL_BYTES = 12000


def _keys(value: object, allowed: set, required: set = frozenset()) -> dict:
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise ValueError("Invalid visual fields")
    return value


def _text(value: object, limit: int = 120) -> None:
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(c in value for c in "<>")
            or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value)):
        raise ValueError("Unsafe or oversized visual text")


def _boolean(item: dict, key: str) -> None:
    if key in item and type(item[key]) is not bool:
        raise ValueError("Visual boolean required")


def validate_visual(payload: object) -> dict:
    """Validate the private authoring payload; return a detached copy."""
    if not isinstance(payload, dict):
        raise ValueError("Visual object required")
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("Invalid visual JSON") from exc
    if len(encoded) > MAX_VISUAL_BYTES or type(payload.get("version")) is not int or payload["version"] != 1:
        raise ValueError("Unsupported or oversized visual")
    kind = payload.get("type")
    if kind not in SUPPORTED_VISUAL_TYPES:
        raise ValueError("Unsupported visual type")
    base = {"version", "type", "title"}
    if "title" in payload:
        _text(payload["title"])
    if kind == "career_tree":
        _keys(payload, base | {"nodes"}, {"nodes"})
        nodes = payload["nodes"]
        if not isinstance(nodes, list) or not 3 <= len(nodes) <= 12:
            raise ValueError("Career needs 3–12 nodes")
        for node in nodes:
            _keys(node, {"label", "years", "loan", "hidden"}, {"label"})
            _text(node["label"])
            if "years" in node:
                _text(node["years"], 30)
            _boolean(node, "loan")
            _boolean(node, "hidden")
        # Identifying the whole player career has no hidden club nodes.
        if sum(bool(n.get("hidden")) for n in nodes) > 3:
            raise ValueError("Too many hidden career nodes")
    elif kind == "lineup_svg":
        _keys(payload, base | {"formation", "schematic", "players"}, {"formation", "schematic", "players"})
        _text(payload["formation"], 30)
        if payload["schematic"] is not True:
            raise ValueError("Historical coordinates must be labelled schematic")
        players = payload["players"]
        if not isinstance(players, list) or len(players) != 11:
            raise ValueError("Lineup needs exactly 11 players")
        for player in players:
            _keys(player, {"label", "x", "y", "number", "hidden"}, {"label", "x", "y"})
            _text(player["label"], 60)
            _boolean(player, "hidden")
            for key in ("x", "y"):
                value = player[key]
                if type(value) not in (int, float) or not math.isfinite(value) or not 5 <= value <= 95:
                    raise ValueError("Invalid pitch position")
            if "number" in player and (type(player["number"]) is not int or not 1 <= player["number"] <= 99):
                raise ValueError("Invalid jersey number")
        if sum(bool(p.get("hidden")) for p in players) != 1:
            raise ValueError("Lineup needs exactly one hidden player")
        if len({(p["x"], p["y"]) for p in players}) != 11:
            raise ValueError("Overlapping lineup positions")
        if len({p["label"] for p in players}) != 11:
            raise ValueError("Duplicate lineup player")
    elif kind == "shot_radar":
        _keys(payload, base | {"schematic", "shot_x", "shot_y", "goal_x", "goal_y", "context_label", "answer_label"},
              {"schematic", "shot_x", "shot_y", "goal_x", "goal_y", "context_label"})
        if payload["schematic"] is not True:
            raise ValueError("Shot radar coordinates must be labelled schematic")
        for key in ("shot_x", "shot_y", "goal_x", "goal_y"):
            value = payload[key]
            if type(value) not in (int, float) or not math.isfinite(value) or not 5 <= value <= 95:
                raise ValueError("Invalid shot radar coordinate")
        if (payload["shot_x"], payload["shot_y"]) == (payload["goal_x"], payload["goal_y"]):
            raise ValueError("Shot and goal coordinates must differ")
        _text(payload["context_label"], 160)
        if "answer_label" in payload:
            _text(payload["answer_label"], 120)
    else:
        _keys(payload, base | {"items", "odd_index", "common_property"}, {"items", "odd_index", "common_property"})
        items = payload["items"]
        if not isinstance(items, list) or len(items) != 4:
            raise ValueError("Odd-one-out needs exactly four items")
        for item in items:
            _keys(item, {"label"}, {"label"})
            _text(item["label"], 60)
        if len({item["label"] for item in items}) != 4:
            raise ValueError("Odd-one-out items must differ")
        if type(payload["odd_index"]) is not int or not 0 <= payload["odd_index"] < 4:
            raise ValueError("Invalid odd item")
        _text(payload["common_property"], 300)
    return copy.deepcopy(payload)


def public_visual(payload: object, *, revealed: bool = False) -> dict | None:
    """Fail closed on corrupt legacy payloads and never serialize hidden identities."""
    try:
        result = validate_visual(payload)
    except ValueError:
        return None
    if revealed:
        return result
    if result["type"] == "career_tree":
        result["nodes"] = [{"hidden": True} if n.get("hidden") else n for n in result["nodes"]]
    elif result["type"] == "lineup_svg":
        result["players"] = [
            {"hidden": True, "x": p["x"], "y": p["y"]} if p.get("hidden") else p
            for p in result["players"]
        ]
    elif result["type"] == "shot_radar":
        result.pop("answer_label", None)
    else:
        result.pop("odd_index")
        result.pop("common_property")
    return result
