"""Helpers for rider-facing corner identity labels."""

from __future__ import annotations

import re
from typing import Optional

_TURN_TOKEN_RE = re.compile(r"(?i)\b(?:turn|t)\s*0*(\d+)\b")


def rider_corner_label(
    candidate: object,
    *,
    fallback_internal_id: object = None,
    apex_m: Optional[object] = None,
    turn_sign: Optional[int] = None,
) -> str:
    """Return a deterministic rider-facing corner label.

    Preference order:
    1) Explicit rider-facing candidate label (e.g. "T3", "Turn 5", "hairpin").
    2) Turn token parsed from internal identifiers (e.g. "track:CW:T3" -> "T3").
    3) Human-readable fallback phrasing from direction/apex context.
    """
    preferred = _normalize_candidate(candidate)
    if preferred:
        return preferred

    token_label = _turn_token_label(fallback_internal_id)
    if token_label:
        return token_label

    apex_value = _as_float(apex_m)
    return _fallback_phrase(apex_value, turn_sign)


def _normalize_candidate(value: object) -> Optional[str]:
    text = _clean_text(value)
    if not text:
        return None

    token_label = _turn_token_label(text)
    if token_label:
        return token_label

    if ":" in text:
        # Colon-delimited values are usually internal IDs. Only tokenized turns are allowed.
        return None

    lowered = text.lower()
    if lowered.startswith("segment"):
        return None
    return text


def _turn_token_label(value: object) -> Optional[str]:
    text = _clean_text(value)
    if not text:
        return None

    for part in re.split(r"[:/|]", text):
        match = _TURN_TOKEN_RE.search(part)
        if not match:
            continue
        try:
            turn_no = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if turn_no <= 0:
            continue
        return f"T{turn_no}"
    return None


def _fallback_phrase(apex_m: Optional[float], turn_sign: Optional[int]) -> str:
    if turn_sign is not None:
        if turn_sign < 0:
            direction = "left-hander"
        elif turn_sign > 0:
            direction = "right-hander"
        else:
            direction = "corner"
    else:
        direction = "corner"

    if apex_m is None:
        return direction

    rounded = int(round(apex_m))
    return f"{direction} near {rounded} m"


def _clean_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = " ".join(text.replace("_", " ").split())
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"none", "null", "nan"}:
        return None
    return text


def _as_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
