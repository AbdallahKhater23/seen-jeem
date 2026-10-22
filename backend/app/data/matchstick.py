"""محرك ألغاز أعواد الثقاب: توليد حتمي، حلّال كامل، وتحقق ميكانيكي.

المصدر الوحيد لخريطة القطع هو ``shared/matchstick_segments.json``، ويقرأه
أيضًا renderer الواجهة عبر alias في Vite. لذلك لا يمكن أن تختلف أشكال
الرموز بين Python وReact.

كل لغز يخزّن تمثيلًا صريحًا للرموز والقطع قبل وبعد، وخطة النقل الكاملة.
التحقق لا يثق بالـ payload: يعيد تطبيق النقل، يحسب المعادلة، يتأكد من أن
البداية خاطئة والحل صحيح، ويتأكد أن عدد الحركات الدنيا يساوي العدد المطلوب
وأن الحل وحيد داخل فضاء الرموز المدعوم.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator

GENERATOR_VERSION = 1
PUZZLES_PER_TIER = 120
TIERS = (200, 400, 600)
SOURCE_URL = "internal://seenjeem/matchstick-generator/v1"
SOURCE_CHECKED_AT = "2026-10-20"
OPS_ALL = ("+", "-", "×")
OPS_BASIC = ("+", "-")

_SEGMENT_PATH = Path(__file__).resolve().parents[3] / "shared" / "matchstick_segments.json"
with _SEGMENT_PATH.open("r", encoding="utf-8") as handle:
    _SEGMENTS = json.load(handle)

DIGITS: dict[str, frozenset[str]] = {
    symbol: frozenset(segments) for symbol, segments in _SEGMENTS["digits"].items()
}
OPERATORS: dict[str, frozenset[str]] = {
    symbol: frozenset(segments) for symbol, segments in _SEGMENTS["operators"].items()
}
SYMBOLS: dict[str, frozenset[str]] = {**DIGITS, **OPERATORS}
KIND: dict[str, str] = {
    **{symbol: "digit" for symbol in DIGITS},
    **{symbol: "operator" for symbol in OPERATORS},
}
UNIVERSE: dict[str, frozenset[str]] = {
    "digit": frozenset("abcdefg"),
    "operator": frozenset(("mh", "pv", "x1", "x2", "e1", "e2")),
}


def _find(table: dict[str, frozenset[str]], segments: frozenset[str]) -> str | None:
    return next((symbol for symbol, candidate in table.items() if candidate == segments), None)


def parse_equation(state: Iterable[str]) -> tuple[int, str, int, int] | None:
    """يفكّ ``A op B = C`` ويعيد None لأي صيغة غير مدعومة."""
    symbols = tuple(state)
    if symbols.count("=") != 1:
        return None
    eq_index = symbols.index("=")
    left, right = symbols[:eq_index], symbols[eq_index + 1 :]
    if not left or not right:
        return None
    op_positions = [index for index, symbol in enumerate(left) if symbol in ("+", "-", "×")]
    if len(op_positions) != 1:
        return None
    op_index = op_positions[0]
    a_text = "".join(left[:op_index])
    b_text = "".join(left[op_index + 1 :])
    c_text = "".join(right)
    if not a_text or not b_text or not c_text:
        return None
    if any(not part.isdigit() for part in (a_text, b_text, c_text)):
        return None
    if any(len(part) > 1 and part[0] == "0" for part in (a_text, b_text, c_text)):
        return None
    try:
        a, b, c = int(a_text), int(b_text), int(c_text)
    except ValueError:
        return None
    return a, left[op_index], b, c


def evaluate(state: Iterable[str]) -> bool | None:
    parsed = parse_equation(state)
    if parsed is None:
        return None
    a, op, b, c = parsed
    if op == "+":
        return a + b == c
    if op == "-":
        return a - b == c
    if op == "×":
        return a * b == c
    return None


def apply_move(
    state: tuple[str, ...], source: int, segment: str, destination: int, target: str
) -> tuple[str, ...] | None:
    """ينفّذ نقلة عود واحدة إن كانت قانونية، وإلا يعيد None.

    العود يُزال من رمز ويُوضع في قطعة فارغة. إذا كان المصدر والهدف نفس الرمز
    فالرمز الناتج وحده هو الذي يجب أن يكون صالحًا (مثل 6 → 0). إذا اختلفا
    فيجب أن يبقى رمز المصدر صالحًا بعد الإزالة وأن يصبح رمز الهدف صالحًا.
    """
    if source == destination and segment == target:
        return None
    if not (0 <= source < len(state) and 0 <= destination < len(state)):
        return None
    source_symbol = state[source]
    destination_symbol = state[destination]
    source_kind = KIND.get(source_symbol)
    destination_kind = KIND.get(destination_symbol)
    if source_kind is None or destination_kind is None:
        return None
    source_segments = SYMBOLS[source_symbol]
    destination_segments = SYMBOLS[destination_symbol]
    if segment not in source_segments:
        return None
    if source == destination:
        if target in source_segments or target not in UNIVERSE[source_kind]:
            return None
        table = DIGITS if source_kind == "digit" else OPERATORS
        replacement = _find(table, (source_segments - {segment}) | {target})
        if replacement is None:
            return None
        updated = list(state)
        updated[source] = replacement
        return tuple(updated)
    if target in destination_segments or target not in UNIVERSE[destination_kind]:
        return None
    source_table = DIGITS if source_kind == "digit" else OPERATORS
    destination_table = DIGITS if destination_kind == "digit" else OPERATORS
    source_replacement = _find(source_table, source_segments - {segment})
    destination_replacement = _find(destination_table, destination_segments | {target})
    if source_replacement is None or destination_replacement is None:
        return None
    updated = list(state)
    updated[source] = source_replacement
    updated[destination] = destination_replacement
    return tuple(updated)


def neighbor_states(state: tuple[str, ...]) -> Iterator[tuple[tuple[str, ...], tuple[int, str, int, str]]]:
    """يولّد كل الحركات القانونية لعود واحد بترتيب حتمي."""
    for source, symbol in enumerate(state):
        source_kind = KIND.get(symbol)
        if source_kind is None:
            continue
        for segment in sorted(SYMBOLS[symbol]):
            for destination, destination_symbol in enumerate(state):
                destination_kind = KIND.get(destination_symbol)
                if destination_kind is None:
                    continue
                for target in sorted(UNIVERSE[destination_kind]):
                    updated = apply_move(state, source, segment, destination, target)
                    if updated is not None:
                        yield updated, (source, segment, destination, target)


def solutions_at(state: tuple[str, ...], depth: int) -> dict[tuple[str, ...], list[tuple[int, str, int, str]]]:
    """كل حالات الحل الصحيحة على عمق محدد، مفتاحها الحالة الناتجة."""
    if depth == 1:
        found: dict[tuple[str, ...], list[tuple[int, str, int, str]]] = {}
        for updated, move in neighbor_states(state):
            if evaluate(updated) is True:
                found.setdefault(updated, [move])
        return found
    if depth == 2:
        found = {}
        for middle, first_move in neighbor_states(state):
            for updated, second_move in neighbor_states(middle):
                if evaluate(updated) is True:
                    found.setdefault(updated, [first_move, second_move])
        return found
    raise ValueError("depth must be 1 or 2")


def _iter_candidates(
    max_digits: int,
    operators: tuple[str, ...],
    *,
    min_two_digit: bool,
    max_gap: int,
) -> Iterator[tuple[str, ...]]:
    """يولّد معادلات خاطئة مرتبة من الأسهل إلى الأصعب."""
    limit = 10 ** max_digits
    for total_digits in range(3, max_digits * 3 + 1):
        for a in range(1, limit):
            if len(str(a)) > total_digits - 2:
                continue
            for b in range(1, limit):
                for c in range(1, limit):
                    if len(str(a)) + len(str(b)) + len(str(c)) != total_digits:
                        continue
                    if min_two_digit and max(a, b, c) < 10:
                        continue
                    for operator in operators:
                        true_value = a + b if operator == "+" else a - b if operator == "-" else a * b
                        if true_value < 1 or abs(c - true_value) > max_gap:
                            continue
                        state = tuple(f"{a}{operator}{b}={c}")
                        if evaluate(state) is False:
                            yield state


def _moves_json(moves: list[tuple[int, str, int, str]]) -> list[dict]:
    return [
        {
            "from": {"symbol": source, "segment": segment},
            "to": {"symbol": destination, "segment": target},
        }
        for source, segment, destination, target in moves
    ]


def _segments_for_state(state: tuple[str, ...]) -> list[list[str]]:
    return [sorted(SYMBOLS[symbol]) for symbol in state]


def _accepted_puzzle(
    state: tuple[str, ...],
    moves: list[tuple[int, str, int, str]],
    moves_required: int,
    difficulty: int,
) -> dict | None:
    solution_state = state
    for source, segment, destination, target in moves:
        solution_state = apply_move(solution_state, source, segment, destination, target)  # type: ignore[assignment]
        if solution_state is None:
            return None
    if evaluate(state) is not False or evaluate(solution_state) is not True:
        return None
    if moves_required == 2 and solutions_at(state, 1):
        return None
    expected = solutions_at(state, moves_required)
    if len(expected) != 1 or solution_state not in expected:
        return None
    solution = "".join(solution_state)
    return {
        "kind": "matchstick",
        "version": 1,
        "generator_version": GENERATOR_VERSION,
        "difficulty": difficulty,
        "equation": "".join(state),
        "solution": solution,
        "moves_required": moves_required,
        "moves": _moves_json(moves),
        "symbols": list(state),
        "start": _segments_for_state(state),
        "end": _segments_for_state(solution_state),
    }


def _generate_tier_200(used: set[str]) -> list[dict]:
    accepted: list[dict] = []
    for state in _iter_candidates(1, OPS_BASIC, min_two_digit=False, max_gap=3):
        equation = "".join(state)
        if equation in used:
            continue
        solutions = solutions_at(state, 1)
        if len(solutions) != 1:
            continue
        solution_state, moves = next(iter(solutions.items()))
        puzzle = _accepted_puzzle(state, moves, 1, 200)
        if puzzle is None:
            continue
        accepted.append(puzzle)
        used.add(equation)
        if len(accepted) >= PUZZLES_PER_TIER:
            break
    return accepted


def _generate_tier_400(used: set[str]) -> list[dict]:
    accepted: list[dict] = []
    # 40 لغزًا بضرب مضمون، ثم الباقي جمع/طرح. كلها بأعداد من خانتين.
    for operators, quota in ((("×",), 40), (OPS_BASIC, PUZZLES_PER_TIER - 40)):
        taken = 0
        for state in _iter_candidates(2, operators, min_two_digit=True, max_gap=20):
            equation = "".join(state)
            if equation in used:
                continue
            solutions = solutions_at(state, 1)
            if len(solutions) != 1:
                continue
            _, moves = next(iter(solutions.items()))
            puzzle = _accepted_puzzle(state, moves, 1, 400)
            if puzzle is None:
                continue
            accepted.append(puzzle)
            used.add(equation)
            taken += 1
            if taken >= quota:
                break
    return accepted


def _generate_tier_600(used: set[str]) -> list[dict]:
    accepted: list[dict] = []
    for state in _iter_candidates(2, OPS_ALL, min_two_digit=True, max_gap=20):
        equation = "".join(state)
        if equation in used:
            continue
        if solutions_at(state, 1):
            continue
        solutions = solutions_at(state, 2)
        if len(solutions) != 1:
            continue
        _, moves = next(iter(solutions.items()))
        puzzle = _accepted_puzzle(state, moves, 2, 600)
        if puzzle is None:
            continue
        accepted.append(puzzle)
        used.add(equation)
        if len(accepted) >= PUZZLES_PER_TIER:
            break
    return accepted


@lru_cache(maxsize=1)
def generate_puzzles() -> tuple[dict, ...]:
    """يولّد 120 لغزًا لكل قيمة، حتميًا، بلا تكرار معادلة بين القيم."""
    used: set[str] = set()
    puzzles: list[dict] = []
    puzzles.extend(_generate_tier_200(used))
    puzzles.extend(_generate_tier_400(used))
    puzzles.extend(_generate_tier_600(used))
    return tuple(puzzles)


def validate_puzzle(payload: dict, *, strict: bool = True) -> list[str]:
    """تحقق مستقل عن أي payload مخزّن. يعيد قائمة أخطاء فارغة عند السلامة.

    ``strict=False`` يفحص البنية والحساب والقطع دون إعادة بحث الحل الوحيد؛
    يُستخدم أثناء بناء البنك لأن المولّد نفسه لا يقبل لغزًا غير وحيد الحل.
    """
    errors: list[str] = []
    required = {
        "kind", "version", "equation", "solution", "moves_required",
        "moves", "symbols", "start", "end", "difficulty",
    }
    if not isinstance(payload, dict):
        return ["payload ليس كائنًا"]
    missing = required - set(payload)
    if missing:
        return [f"حقول ناقصة: {', '.join(sorted(missing))}"]
    if payload.get("kind") != "matchstick":
        errors.append("kind غير matchstick")
    if payload.get("version") != 1:
        errors.append("version غير مدعوم")
    symbols = payload.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        return errors + ["symbols مفقودة"]
    if any(symbol not in SYMBOLS for symbol in symbols):
        return errors + ["رمز غير مدعوم في symbols"]
    if payload.get("equation") != "".join(symbols):
        errors.append("equation لا تطابق symbols")
    start = payload.get("start")
    end = payload.get("end")
    if not isinstance(start, list) or not isinstance(end, list) or len(start) != len(symbols) or len(end) != len(symbols):
        return errors + ["start/end بطول غير مطابق"]
    start_state: list[str] = []
    end_state: list[str] = []
    for index, symbol in enumerate(symbols):
        if set(start[index]) != set(SYMBOLS[symbol]):
            errors.append(f"قطع البداية لا تطابق الرمز {symbol} في الموضع {index}")
        table = DIGITS if KIND[symbol] == "digit" else OPERATORS
        start_symbol = _find(table, frozenset(start[index]))
        end_symbol = _find(table, frozenset(end[index]))
        if start_symbol is None:
            errors.append(f"قطع البداية لا تشكّل رمزًا في الموضع {index}")
        else:
            start_state.append(start_symbol)
        if end_symbol is None:
            errors.append(f"قطع النهاية لا تشكّل رمزًا في الموضع {index}")
        else:
            end_state.append(end_symbol)
    if len(start_state) == len(symbols) and evaluate(tuple(start_state)) is not False:
        errors.append("المعادلة الابتدائية ليست خاطئة")
    if len(end_state) == len(symbols) and evaluate(tuple(end_state)) is not True:
        errors.append("المعادلة النهائية ليست صحيحة")
    if len(end_state) == len(symbols) and payload.get("solution") != "".join(end_state):
        errors.append("solution لا يطابق تمثيل end")
    moves = payload.get("moves")
    required_moves = payload.get("moves_required")
    if required_moves not in (1, 2) or not isinstance(moves, list) or len(moves) != required_moves:
        errors.append("عدد الحركات لا يطابق moves_required")
        return errors
    if payload.get("difficulty") in (200, 400) and required_moves != 1:
        errors.append("لغز 200/400 يجب أن يكون حركة واحدة")
    if payload.get("difficulty") == 600 and required_moves != 2:
        errors.append("لغز 600 يجب أن يكون حركتين")
    state = tuple(symbols)
    for index, move in enumerate(moves):
        try:
            source = int(move["from"]["symbol"])
            segment = move["from"]["segment"]
            destination = int(move["to"]["symbol"])
            target = move["to"]["segment"]
        except (KeyError, TypeError, ValueError):
            errors.append(f"حركة {index} غير مكتملة")
            return errors
        updated = apply_move(state, source, segment, destination, target)
        if updated is None:
            errors.append(f"حركة {index} غير قانونية")
            return errors
        state = updated
    if [sorted(SYMBOLS[symbol]) for symbol in state] != [sorted(segments) for segments in end]:
        errors.append("تطبيق الحركات لا ينتج end")
    if sum(len(segments) for segments in start) != sum(len(segments) for segments in end):
        errors.append("عدد الأعواد غير محفوظ")
    if strict:
        if required_moves == 2 and solutions_at(tuple(symbols), 1):
            errors.append("يوجد حل بحركة واحدة رغم أن المطلوب حركتان")
        expected = solutions_at(tuple(symbols), required_moves)
        if len(expected) != 1:
            errors.append(f"الحل ليس وحيدًا: {len(expected)} حالة")
        elif tuple(state) not in expected:
            errors.append("الحل المخزّن ليس ضمن الحلول المتوقعة")
    return errors


def _spaced(equation: str) -> str:
    return equation.replace("=", " = ").replace("+", " + ").replace("-", " - ").replace("×", " × ")


def build_rows() -> list[dict]:
    """صفوف أسئلة جاهزة لـ content._q (المفاتيح تطابق عقد السؤال)."""
    rows: list[dict] = []
    for puzzle in generate_puzzles():
        difficulty = int(puzzle["difficulty"])
        moves = int(puzzle["moves_required"])
        move_word = "عود واحد" if moves == 1 else "عودين"
        rows.append(
            {
                "category": "matchstick",
                "difficulty": difficulty,
                "type": "text",
                "question": f"المعادلة {puzzle['equation']} فيها غلطة… حرّك {move_word} بس وخَلّها تضبط!",
                "answer": puzzle["solution"],
                "tolerance": f"{puzzle['solution']}، {_spaced(puzzle['solution'])}",
                "explanation": (
                    f"الحل الصحيح هو {puzzle['solution']}، "
                    f"ويتطلب نقل {moves} من الأعواد مع الحفاظ على عددها."
                ),
                "content_origin": "generated_puzzle",
                "payload": puzzle,
                "source_name": "محرك أعواد الثقاب الحتمي",
                "source_url": SOURCE_URL,
                "source_checked_at": SOURCE_CHECKED_AT,
                "source_license": "internal deterministic generator",
                "source_claim": "procedural matchstick solver with unique-solution check",
                "source_entity_id": f"matchstick:{puzzle['equation']}",
                "fact_group_id": f"matchstick:{puzzle['equation']}",
                "fact_type": "matchstick_puzzle",
                "fact_payload": {
                    "equation": puzzle["equation"],
                    "solution": puzzle["solution"],
                    "moves_required": moves,
                },
                "verification_status": "procedural",
            }
        )
    return rows


def puzzle_count_by_difficulty() -> dict[int, int]:
    counts = {tier: 0 for tier in TIERS}
    for puzzle in generate_puzzles():
        counts[int(puzzle["difficulty"])] += 1
    return counts
