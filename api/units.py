from __future__ import annotations

from typing import Any, Dict

M_TO_FT = 3.28084
KMH_TO_MPH = 0.621371
MPS_TO_MPH = 2.23694
_MAP_POINT_KEYS = {"points", "points_a", "points_b", "reference_points", "target_points"}


def to_feet(value: float) -> float:
    return value * M_TO_FT


def to_mph_from_kmh(value: float) -> float:
    return value * KMH_TO_MPH


def to_mph_from_mps(value: float) -> float:
    return value * MPS_TO_MPH


def _convert_value(value: Any, fn) -> Any:
    if value is None:
        return None
    try:
        return fn(float(value))
    except (TypeError, ValueError):
        return value


def imperial_unit_contract() -> Dict[str, str]:
    return {
        "system": "imperial",
        "distance": "ft",
        "speed": "mph",
        "time": "s",
    }


def _convert_map_point(point: Any) -> Any:
    if not isinstance(point, (list, tuple)):
        return point
    converted = list(point)
    for idx in range(min(3, len(converted))):
        converted[idx] = _convert_value(converted[idx], to_feet)
    return converted


def _convert_units_tree(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {child_key: _convert_units_tree(child_value, key=child_key) for child_key, child_value in value.items()}
    if isinstance(value, list):
        if key in _MAP_POINT_KEYS:
            return [_convert_map_point(item) for item in value]
        return [_convert_units_tree(item, key=key) for item in value]
    if key is None:
        return value
    if key.endswith("_m"):
        return _convert_value(value, to_feet)
    if key.endswith("_kmh"):
        return _convert_value(value, to_mph_from_kmh)
    if key.endswith("_mps"):
        return _convert_value(value, to_mph_from_mps)
    return value


def convert_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    if not evidence:
        return {}
    return _convert_units_tree(dict(evidence))


def convert_compare_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return payload
    converted = dict(payload)
    comparison = dict(converted.get("comparison") or {})
    converted["comparison"] = _convert_units_tree(comparison)
    converted["units"] = "imperial"
    converted["unit_contract"] = imperial_unit_contract()
    return converted


def convert_map_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return payload
    converted = _convert_units_tree(dict(payload))
    converted["units"] = "imperial"
    converted["unit_contract"] = imperial_unit_contract()
    return converted
