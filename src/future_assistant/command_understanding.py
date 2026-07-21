"""Conservative normalization and typo recovery for user commands."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TypeVar

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_CHARACTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ک": "ك", "ی": "ي"})
_CORRECTIONS = {
    "دكرني": "ذكرني",
    "يويتوب": "يوتيوب",
    "يوتوب": "يوتيوب",
    "يوتويب": "يوتيوب",
    "دقايق": "دقائق",
    "دقيقه": "دقيقة",
    "ساعه": "ساعة",
    "ثانيه": "ثانية",
    "الساعه": "الساعة",
    "بكره": "بكرا",
}

_Value = TypeVar("_Value")


def normalize_command(value: str) -> str:
    value = _ARABIC_DIACRITICS.sub("", value).replace("ـ", "")
    value = value.translate(_DIGITS).translate(_CHARACTERS)
    tokens = value.casefold().strip().split()
    return " ".join(_CORRECTIONS.get(token, token) for token in tokens)


def _distance(left: str, right: str, limit: int) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    previous = list(range(len(right) + 1))
    for index, left_character in enumerate(left, start=1):
        current = [index]
        row_minimum = index
        for right_index, right_character in enumerate(right, start=1):
            current_distance = min(
                previous[right_index] + 1,
                current[right_index - 1] + 1,
                previous[right_index - 1] + (left_character != right_character),
            )
            current.append(current_distance)
            row_minimum = min(row_minimum, current_distance)
        if row_minimum > limit:
            return limit + 1
        previous = current
    return previous[-1]


def resolve_allowlisted_alias(mapping: Mapping[str, _Value], value: str) -> _Value | None:
    """Resolve only an exact or uniquely close alias already in an allow-list."""

    normalized = normalize_command(value)
    exact = mapping.get(normalized)
    if exact is not None:
        return exact
    if not 4 <= len(normalized) <= 48:
        return None

    limit = 1 if len(normalized) <= 7 else 2
    candidates: list[tuple[int, str]] = []
    for candidate in mapping:
        distance = _distance(normalized, candidate, limit)
        if distance <= limit:
            candidates.append((distance, candidate))
    candidates.sort(key=lambda item: (item[0], len(item[1]), item[1]))
    if not candidates:
        return None
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    return mapping[candidates[0][1]]
