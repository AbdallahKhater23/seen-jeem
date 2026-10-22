"""تطبيع النصوص وبصمة المحتوى لمنع التكرار."""

from __future__ import annotations

import hashlib
import re
import unicodedata

TATWEEL = "\u0640"
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """NFKC + إزالة التطويل + توحيد المسافات، مع الحفاظ على التشكيل."""
    if not isinstance(value, str):
        raise TypeError("normalize_text expects a string")
    text = unicodedata.normalize("NFKC", value)
    text = text.replace(TATWEEL, "")
    text = CONTROL_RE.sub("", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def normalize_answer(value: str) -> str:
    """تطبيع إضافي للإجابات: حروف صغيرة وتوحيد الألف/الياء للمقارنة فقط."""
    text = normalize_text(value).casefold()
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    return WHITESPACE_RE.sub(" ", text).strip()


def fingerprint(
    category_slug: str,
    question_text: str,
    answer_text: str,
    flag_code: str | None = None,
) -> str:
    canonical = "\n".join(
        [
            normalize_text(category_slug).casefold(),
            normalize_text(question_text),
            normalize_text(answer_text),
            normalize_text(flag_code or "").casefold(),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_team_name(value: str, max_length: int = 40) -> str:
    if not isinstance(value, str):
        raise ValueError("اسم الفريق لازم يكون نصًا.")
    text = normalize_text(value)
    if not text:
        raise ValueError("اسم الفريق ما يقدر يكون فاضي.")
    if len(text) > max_length:
        raise ValueError(f"اسم الفريق أطول من {max_length} حرف.")
    if any(unicodedata.category(ch).startswith("C") for ch in text):
        raise ValueError("اسم الفريق فيه رموز تحكم غير مسموحة.")
    return text
