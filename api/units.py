from __future__ import annotations

import re
from typing import Any, Dict

M_TO_FT = 3.28084
KMH_TO_MPH = 0.621371
MPS_TO_MPH = 2.23694
_MAP_POINT_KEYS = {"points", "points_a", "points_b", "reference_points", "target_points"}
_UNIT_RANGE_RE = re.compile(
    r"(?P<a>[+-]?\d+(?:\.\d+)?)\s*-\s*(?P<b>[+-]?\d+(?:\.\d+)?)\s*(?P<unit>km/h|m/s|m)\b"
)
_UNIT_SINGLE_RE = re.compile(r"(?P<num>[+-]?\d+(?:\.\d+)?)\s*(?P<unit>km/h|m/s|m)\b")
_RIDER_TEXT_REPLACEMENTS = {
    "line_stddev_delta_m": "line variance delta",
    "line_stddev_m": "line variance",
    "entry_speed_delta_kmh": "entry speed delta",
    "min_speed_delta_kmh": "apex minimum speed delta",
    "exit_speed_delta_kmh": "exit speed delta",
    "apex_delta_m": "apex location",
    "neutral_throttle_dist_m": "neutral throttle distance",
}


def to_feet(value: float) -> float:
    return value * M_TO_FT


def to_mph_from_kmh(value: float) -> float:
    return value * KMH_TO_MPH


def to_mph_from_mps(value: float) -> float:
    return value * MPS_TO_MPH


def _format_unit_value(value: float, unit: str, *, show_plus: bool = False) -> str:
    if unit == "ft":
        text = f"{value:.0f}" if abs(value) >= 10 else f"{value:.1f}"
    else:
        text = f"{value:.1f}"
    if show_plus and value > 0:
        return f"+{text}"
    return text


def _convert_unit_value(value: float, unit: str) -> tuple[float, str]:
    if unit == "km/h":
        return value * KMH_TO_MPH, "mph"
    if unit == "m/s":
        return value * MPS_TO_MPH, "mph"
    if unit == "m":
        return value * M_TO_FT, "ft"
    return value, unit


def _replace_unit_range(match: re.Match[str]) -> str:
    start = float(match.group("a"))
    end = float(match.group("b"))
    unit = match.group("unit")
    converted_start, out_unit = _convert_unit_value(start, unit)
    converted_end, _ = _convert_unit_value(end, unit)
    start_text = _format_unit_value(converted_start, out_unit, show_plus=match.group("a").startswith("+"))
    end_text = _format_unit_value(converted_end, out_unit, show_plus=match.group("b").startswith("+"))
    return f"{start_text}-{end_text} {out_unit}"


def _replace_unit_single(match: re.Match[str]) -> str:
    value = float(match.group("num"))
    unit = match.group("unit")
    converted, out_unit = _convert_unit_value(value, unit)
    number = _format_unit_value(converted, out_unit, show_plus=match.group("num").startswith("+"))
    return f"{number} {out_unit}"


def convert_rider_text(value: Any) -> Any:
    if isinstance(value, str):
        converted = value
        for source, target in _RIDER_TEXT_REPLACEMENTS.items():
            converted = converted.replace(source, target)
        converted = _UNIT_RANGE_RE.sub(_replace_unit_range, converted)
        return _UNIT_SINGLE_RE.sub(_replace_unit_single, converted)
    if isinstance(value, list):
        return [convert_rider_text(item) for item in value]
    if isinstance(value, dict):
        return {key: convert_rider_text(child) for key, child in value.items()}
    return value


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
