"""Ranking logic for trackside insights."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def insight_score(time_gain_s: float, confidence: float) -> float:
    """Score by time gain * confidence with severity bonus."""
    severity_bonus = 0.2 if time_gain_s >= 0.15 else 0.0
    return time_gain_s * confidence * (1.0 + severity_bonus)


def rank_insights(
    insights: Iterable[Dict[str, Any]],
    *,
    min_count: int = 3,
    max_count: int = 5,
    min_confidence: float = 0.5,
    max_per_corner: int = 2,
) -> List[Dict[str, Any]]:
    """Select top insights by gain * confidence with corner diversity."""

    items = [dict(item) for item in insights]
    if not items:
        return []

    filtered = [item for item in items if _get_confidence(item) >= min_confidence]
    if len(filtered) >= min_count:
        candidates = filtered
    else:
        candidates = items

    for item in candidates:
        time_gain = _get_time_gain(item)
        confidence = _get_confidence(item)
        item["score"] = insight_score(time_gain, confidence)

    candidates.sort(key=lambda item: item.get("score", 0.0), reverse=True)

    selected: List[Dict[str, Any]] = []
    per_corner: Dict[Optional[str], int] = {}

    def can_take(item: Dict[str, Any]) -> bool:
        corner_id = _corner_key(item)
        if corner_id is None:
            return True
        return per_corner.get(corner_id, 0) < max_per_corner

    for item in candidates:
        if len(selected) >= max_count:
            break
        if not can_take(item):
            continue
        selected.append(item)
        corner_id = _corner_key(item)
        if corner_id is not None:
            per_corner[corner_id] = per_corner.get(corner_id, 0) + 1

    if len(selected) < min_count and candidates is not items:
        remaining = [item for item in items if item not in selected]
        for item in remaining:
            if len(selected) >= max_count:
                break
            if not can_take(item):
                continue
            selected.append(item)
            corner_id = _corner_key(item)
            if corner_id is not None:
                per_corner[corner_id] = per_corner.get(corner_id, 0) + 1

    return selected


def _get_time_gain(item: Dict[str, Any]) -> float:
    for key in ("time_gain_s", "gain_s", "time_gain", "gain"):
        if key in item and item[key] is not None:
            try:
                return float(item[key])
            except (TypeError, ValueError):
                continue
    return 0.0


def _get_confidence(item: Dict[str, Any]) -> float:
    if "confidence" in item and item["confidence"] is not None:
        try:
            return float(item["confidence"])
        except (TypeError, ValueError):
            pass
    return 0.0


def _corner_key(item: Dict[str, Any]) -> Optional[str]:
    corner_id = item.get("corner_id") or item.get("corner")
    if corner_id is None:
        return None
    return str(corner_id)
