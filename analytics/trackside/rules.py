"""Trackside insight rules for per-segment comparisons.

This module expects per-segment metrics already computed for a target lap
and a reference lap. It applies the Trackside rules to produce insight
objects suitable for ranking and UI display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


KMH_TO_MS = 1000.0 / 3600.0


@dataclass(frozen=True)
class Insight:
    rule_id: str
    title: str
    detail: str
    corner_id: Optional[str]
    segment_id: Optional[str]
    time_gain_s: float
    confidence: float
    confidence_label: str
    evidence: Dict[str, Any]
    comparison: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "detail": self.detail,
            "corner_id": self.corner_id,
            "segment_id": self.segment_id,
            "time_gain_s": self.time_gain_s,
            "confidence": self.confidence,
            "confidence_label": self.confidence_label,
            "evidence": self.evidence,
            "comparison": self.comparison,
        }


def generate_insights(
    segments: Iterable[Dict[str, Any]],
    comparison_label: str,
) -> List[Dict[str, Any]]:
    """Generate per-segment insights from segment comparisons.

    Expected segment structure (per item, minimal keys):
    - segment_id, corner_id (optional)
    - target: dict of metrics for target lap
    - reference: dict of metrics for reference lap
    - quality: optional dict for gps/imu quality fields
    """

    insights: List[Insight] = []
    for segment in segments:
        target = segment.get("target", {}) or {}
        reference = segment.get("reference", {}) or {}

        quality = _extract_quality(segment, target)
        time_delta_s = _segment_time_delta(target, reference)
        time_gain_s = max(0.0, time_delta_s or 0.0)

        common = {
            "corner_id": _as_str(segment.get("corner_id")),
            "segment_id": _as_str(segment.get("segment_id")),
        }

        insights.extend(
            _rule_early_braking(segment, target, reference, quality, time_gain_s, comparison_label, common)
        )
        insights.extend(
            _rule_late_throttle(segment, target, reference, quality, time_gain_s, comparison_label, common)
        )
        insights.extend(
            _rule_neutral_throttle(segment, target, reference, quality, time_gain_s, comparison_label, common)
        )
        insights.extend(
            _rule_line_inconsistency(segment, target, reference, quality, time_gain_s, comparison_label, common)
        )
        insights.extend(
            _rule_corner_speed_loss(segment, target, reference, quality, time_gain_s, comparison_label, common)
        )
        insights.extend(
            _rule_exit_speed(segment, target, reference, quality, time_gain_s, comparison_label, common)
        )
        insights.extend(
            _rule_entry_speed(segment, target, reference, quality, time_gain_s, comparison_label, common)
        )
        insights.extend(
            _rule_steering_smoothness(segment, target, reference, quality, time_gain_s, comparison_label, common)
        )

    return [item.to_dict() for item in insights]


def _rule_early_braking(
    segment: Dict[str, Any],
    target: Dict[str, Any],
    reference: Dict[str, Any],
    quality: Dict[str, Any],
    time_gain_s: float,
    comparison_label: str,
    common: Dict[str, Optional[str]],
) -> List[Insight]:
    brake_target = _get_float(target, "brake_point_dist_m")
    brake_ref = _get_float(reference, "brake_point_dist_m")
    if brake_target is None or brake_ref is None:
        return []

    delta_m = brake_target - brake_ref
    time_delta_s = _segment_time_delta(target, reference)
    if delta_m <= -10.0 and (time_delta_s or 0.0) >= 0.08:
        confidence = _confidence_score(quality)
        evidence = {"brake_point_delta_m": delta_m, "segment_time_delta_s": time_delta_s}
        return [
            _build_insight(
                "early_braking",
                "Brake later into the corner",
                "Brake point is earlier than reference with time loss in the segment.",
                time_gain_s,
                confidence,
                evidence,
                comparison_label,
                common,
            )
        ]
    return []


def _rule_late_throttle(
    segment: Dict[str, Any],
    target: Dict[str, Any],
    reference: Dict[str, Any],
    quality: Dict[str, Any],
    time_gain_s: float,
    comparison_label: str,
    common: Dict[str, Optional[str]],
) -> List[Insight]:
    pickup_target = _get_float(target, "throttle_pickup_dist_m")
    pickup_ref = _get_float(reference, "throttle_pickup_dist_m")
    pickup_time_target = _get_float(target, "throttle_pickup_time_s")
    pickup_time_ref = _get_float(reference, "throttle_pickup_time_s")
    using_proxy = bool(_get_flag(target, segment, "using_speed_proxy"))

    if pickup_target is None and (pickup_time_target is None or pickup_time_ref is None):
        return []

    later_by_m = None
    later_by_s = None
    if pickup_target is not None and pickup_ref is not None:
        later_by_m = pickup_target - pickup_ref
    if pickup_time_target is not None and pickup_time_ref is not None:
        later_by_s = pickup_time_target - pickup_time_ref

    if (later_by_m is not None and later_by_m >= 12.0) or (later_by_s is not None and later_by_s >= 0.12):
        confidence = _confidence_score(quality, using_speed_proxy=using_proxy)
        evidence = {"pickup_delta_m": later_by_m, "pickup_delta_s": later_by_s}
        detail = "Throttle pickup is later than reference after the apex."
        return [
            _build_insight(
                "late_throttle_pickup",
                "Get back to power sooner",
                detail,
                time_gain_s,
                confidence,
                evidence,
                comparison_label,
                common,
            )
        ]
    return []


def _rule_neutral_throttle(
    segment: Dict[str, Any],
    target: Dict[str, Any],
    reference: Dict[str, Any],
    quality: Dict[str, Any],
    time_gain_s: float,
    comparison_label: str,
    common: Dict[str, Optional[str]],
) -> List[Insight]:
    neutral_s = _get_float(target, "neutral_throttle_s")
    neutral_m = _get_float(target, "neutral_throttle_dist_m")
    speed_delta = _get_float(target, "neutral_speed_delta_kmh")
    time_delta_s = _segment_time_delta(target, reference)
    speed_delta = abs(speed_delta) if speed_delta is not None else None

    if neutral_s is None and neutral_m is None:
        return []

    long_enough = (neutral_s is not None and neutral_s >= 1.0) or (
        neutral_m is not None and neutral_m >= 15.0
    )
    speed_flat = speed_delta is not None and speed_delta < 1.0

    if long_enough and speed_flat and (time_delta_s or 0.0) >= 0.05:
        confidence = _confidence_score(
            quality,
            speed_noise_sigma_kmh=_get_float(target, "speed_noise_sigma_kmh"),
        )
        evidence = {
            "neutral_throttle_s": neutral_s,
            "neutral_throttle_dist_m": neutral_m,
            "neutral_speed_delta_kmh": speed_delta,
            "segment_time_delta_s": time_delta_s,
        }
        return [
            _build_insight(
                "neutral_throttle",
                "Stop coasting here",
                "Sustained neutral throttle with flat speed in the segment.",
                time_gain_s,
                confidence,
                evidence,
                comparison_label,
                common,
            )
        ]
    return []


def _rule_line_inconsistency(
    segment: Dict[str, Any],
    target: Dict[str, Any],
    reference: Dict[str, Any],
    quality: Dict[str, Any],
    time_gain_s: float,
    comparison_label: str,
    common: Dict[str, Optional[str]],
) -> List[Insight]:
    stddev_target = _get_float(target, "line_stddev_m")
    stddev_ref = _get_float(reference, "line_stddev_m")
    if stddev_target is None:
        return []

    delta = None
    if stddev_ref is not None:
        delta = stddev_target - stddev_ref

    if stddev_target > 1.5 or (delta is not None and delta >= 0.6):
        confidence = _confidence_score(quality)
        evidence = {"line_stddev_m": stddev_target, "line_stddev_delta_m": delta}
        return [
            _build_insight(
                "line_inconsistency",
                "Use a tighter, repeatable line",
                "Line variance is higher than reference through the segment.",
                time_gain_s,
                confidence,
                evidence,
                comparison_label,
                common,
            )
        ]
    return []


def _rule_corner_speed_loss(
    segment: Dict[str, Any],
    target: Dict[str, Any],
    reference: Dict[str, Any],
    quality: Dict[str, Any],
    time_gain_s: float,
    comparison_label: str,
    common: Dict[str, Optional[str]],
) -> List[Insight]:
    min_speed_target = _get_float(target, "min_speed_kmh")
    min_speed_ref = _get_float(reference, "min_speed_kmh")
    if min_speed_target is None or min_speed_ref is None:
        return []

    delta = min_speed_target - min_speed_ref
    if delta <= -3.0:
        apex_target = _get_float(target, "apex_dist_m")
        apex_ref = _get_float(reference, "apex_dist_m")
        apex_delta = abs(apex_target - apex_ref) if apex_target is not None and apex_ref is not None else None
        confidence = _confidence_score(quality, apex_delta_m=apex_delta)
        evidence = {"min_speed_delta_kmh": delta, "apex_delta_m": apex_delta}
        return [
            _build_insight(
                "corner_speed_loss",
                "Carry more minimum speed",
                "Minimum speed at apex is lower than reference.",
                time_gain_s,
                confidence,
                evidence,
                comparison_label,
                common,
            )
        ]
    return []


def _rule_exit_speed(
    segment: Dict[str, Any],
    target: Dict[str, Any],
    reference: Dict[str, Any],
    quality: Dict[str, Any],
    time_gain_s: float,
    comparison_label: str,
    common: Dict[str, Optional[str]],
) -> List[Insight]:
    exit_speed_target = _get_float(target, "exit_speed_30m_kmh")
    exit_speed_ref = _get_float(reference, "exit_speed_30m_kmh")
    accel_target = _get_float(target, "inline_acc_rise_g")
    accel_ref = _get_float(reference, "inline_acc_rise_g")
    using_proxy = bool(_get_flag(target, segment, "using_speed_proxy"))

    if exit_speed_target is None or exit_speed_ref is None:
        return []

    speed_delta = exit_speed_target - exit_speed_ref
    accel_delta = None
    if accel_target is not None and accel_ref is not None:
        accel_delta = accel_target - accel_ref

    if speed_delta <= -3.0 and (accel_delta is None or accel_delta <= -0.02):
        confidence = _confidence_score(quality, using_speed_proxy=using_proxy)
        evidence = {"exit_speed_delta_kmh": speed_delta, "inline_acc_rise_delta_g": accel_delta}
        return [
            _build_insight(
                "exit_speed",
                "Improve exit speed",
                "Exit speed and acceleration after the apex are lower than reference.",
                time_gain_s,
                confidence,
                evidence,
                comparison_label,
                common,
            )
        ]
    return []


def _rule_entry_speed(
    segment: Dict[str, Any],
    target: Dict[str, Any],
    reference: Dict[str, Any],
    quality: Dict[str, Any],
    time_gain_s: float,
    comparison_label: str,
    common: Dict[str, Optional[str]],
) -> List[Insight]:
    entry_speed_target = _get_float(target, "entry_speed_kmh")
    entry_speed_ref = _get_float(reference, "entry_speed_kmh")
    brake_target = _get_float(target, "brake_point_dist_m")
    brake_ref = _get_float(reference, "brake_point_dist_m")

    if entry_speed_target is None or entry_speed_ref is None:
        return []

    speed_delta = entry_speed_target - entry_speed_ref
    brake_ok = True
    if brake_target is not None and brake_ref is not None:
        brake_ok = brake_target <= brake_ref + 0.01

    if speed_delta <= -3.0 and brake_ok:
        confidence = _confidence_score(quality)
        evidence = {"entry_speed_delta_kmh": speed_delta, "brake_point_delta_m": _delta(brake_target, brake_ref)}
        return [
            _build_insight(
                "entry_speed",
                "Don’t over-slow on entry",
                "Entry speed is lower with a similar or earlier brake point.",
                time_gain_s,
                confidence,
                evidence,
                comparison_label,
                common,
            )
        ]
    return []


def _rule_steering_smoothness(
    segment: Dict[str, Any],
    target: Dict[str, Any],
    reference: Dict[str, Any],
    quality: Dict[str, Any],
    time_gain_s: float,
    comparison_label: str,
    common: Dict[str, Optional[str]],
) -> List[Insight]:
    yaw_target = _get_float(target, "yaw_rms")
    yaw_ref = _get_float(reference, "yaw_rms")
    min_speed_target = _get_float(target, "min_speed_kmh")
    min_speed_ref = _get_float(reference, "min_speed_kmh")

    if yaw_target is None or yaw_ref is None or min_speed_target is None or min_speed_ref is None:
        return []

    yaw_ratio = yaw_target / yaw_ref if yaw_ref else None
    speed_delta = min_speed_target - min_speed_ref

    if yaw_ratio is not None and yaw_ratio >= 1.2 and speed_delta <= -2.0:
        confidence = _confidence_score(quality, imu_present=True)
        evidence = {"yaw_rms_ratio": yaw_ratio, "min_speed_delta_kmh": speed_delta}
        return [
            _build_insight(
                "steering_smoothness",
                "Smooth your steering here",
                "Yaw activity is higher with a lower minimum speed.",
                time_gain_s,
                confidence,
                evidence,
                comparison_label,
                common,
            )
        ]
    return []


def _build_insight(
    rule_id: str,
    title: str,
    detail: str,
    time_gain_s: float,
    confidence: float,
    evidence: Dict[str, Any],
    comparison_label: str,
    common: Dict[str, Optional[str]],
) -> Insight:
    return Insight(
        rule_id=rule_id,
        title=title,
        detail=detail,
        corner_id=common.get("corner_id"),
        segment_id=common.get("segment_id"),
        time_gain_s=round(time_gain_s, 4),
        confidence=round(confidence, 3),
        confidence_label=_confidence_label(confidence),
        evidence=evidence,
        comparison=comparison_label,
    )


def _segment_time_delta(target: Dict[str, Any], reference: Dict[str, Any]) -> Optional[float]:
    if "segment_time_delta_s" in target:
        return _get_float(target, "segment_time_delta_s")
    target_time = _get_float(target, "segment_time_s")
    ref_time = _get_float(reference, "segment_time_s")
    if target_time is None or ref_time is None:
        return None
    return target_time - ref_time


def _confidence_score(
    quality: Dict[str, Any],
    *,
    using_speed_proxy: bool = False,
    speed_noise_sigma_kmh: Optional[float] = None,
    apex_delta_m: Optional[float] = None,
    imu_present: Optional[bool] = None,
) -> float:
    if quality is None:
        quality = {}

    gps_accuracy = _get_float(quality, "gps_accuracy_m")
    satellites = _get_float(quality, "satellites")
    imu_present_flag = quality.get("imu_present")
    if imu_present is not None:
        imu_present_flag = imu_present

    imu_variance_low = quality.get("imu_variance_low")
    inline_acc_var = _get_float(quality, "inline_acc_var")

    confidence = 0.5

    if gps_accuracy is not None or satellites is not None:
        if gps_accuracy is not None and gps_accuracy <= 1.0:
            confidence += 0.2
        elif satellites is not None and satellites >= 10:
            confidence += 0.2

        if gps_accuracy is not None and gps_accuracy > 2.0:
            confidence -= 0.2
        if satellites is not None and satellites < 7:
            confidence -= 0.2

    if imu_present_flag:
        if imu_variance_low is True:
            confidence += 0.1
        elif inline_acc_var is not None and inline_acc_var <= 0.02:
            confidence += 0.1

    if speed_noise_sigma_kmh is not None and speed_noise_sigma_kmh < 0.5:
        confidence += 0.1

    if using_speed_proxy:
        confidence -= 0.1

    if apex_delta_m is not None and apex_delta_m > 8.0:
        confidence -= 0.1

    return float(max(0.1, min(0.9, confidence)))


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def _extract_quality(segment: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    quality = dict(segment.get("quality") or {})
    for key in ("gps_accuracy_m", "satellites", "imu_present", "imu_variance_low", "inline_acc_var"):
        if key not in quality and key in segment:
            quality[key] = segment.get(key)
        if key not in quality and key in target:
            quality[key] = target.get(key)
    return quality


def _get_float(source: Dict[str, Any], key: str) -> Optional[float]:
    if not source or key not in source:
        return None
    value = source.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_flag(target: Dict[str, Any], segment: Dict[str, Any], key: str) -> bool:
    for source in (target, segment):
        if key in source:
            return bool(source.get(key))
    return False


def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)
