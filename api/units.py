from __future__ import annotations

from typing import Any, Dict

M_TO_FT = 3.28084
KMH_TO_MPH = 0.621371
MPS_TO_MPH = 2.23694


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


def convert_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    if not evidence:
        return {}
    converted = dict(evidence)
    meter_keys = {
        "brake_point_delta_m",
        "pickup_delta_m",
        "neutral_throttle_dist_m",
        "line_stddev_m",
        "line_stddev_delta_m",
        "apex_stddev_m",
        "apex_recommend_m",
        "apex_bias_m",
        "apex_delta_m",
        "decel_dist_m",
        "gps_accuracy_m",
    }
    kmh_keys = {
        "entry_speed_delta_kmh",
        "min_speed_delta_kmh",
        "exit_speed_delta_kmh",
        "neutral_speed_delta_kmh",
        "speed_noise_sigma_kmh",
    }
    mps_keys = {
        "gps_speed_accuracy_mps",
    }

    for key in meter_keys:
        if key in converted:
            converted[key] = _convert_value(converted[key], to_feet)
    for key in kmh_keys:
        if key in converted:
            converted[key] = _convert_value(converted[key], to_mph_from_kmh)
    for key in mps_keys:
        if key in converted:
            converted[key] = _convert_value(converted[key], to_mph_from_mps)
    return converted


def convert_compare_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return payload
    converted = dict(payload)
    comparison = dict(converted.get("comparison") or {})
    brake_points = comparison.get("brake_points")
    if isinstance(brake_points, list):
        updated = []
        for point in brake_points:
            if not isinstance(point, dict):
                updated.append(point)
                continue
            updated_point = dict(point)
            if "delta_m" in updated_point:
                updated_point["delta_m"] = _convert_value(updated_point["delta_m"], to_feet)
            updated.append(updated_point)
        comparison["brake_points"] = updated
        converted["comparison"] = comparison
    return converted
