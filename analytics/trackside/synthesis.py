"""Deterministic synthesis of trackside insights from signals + metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

_M_TO_FT = 3.28084
_KMH_TO_MPH = 0.621371


@dataclass(frozen=True)
class Insight:
    rule_id: str
    title: str
    detail: str
    actions: List[str]
    options: List[str]
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
            "actions": list(self.actions),
            "options": list(self.options),
            "corner_id": self.corner_id,
            "segment_id": self.segment_id,
            "time_gain_s": self.time_gain_s,
            "confidence": self.confidence,
            "confidence_label": self.confidence_label,
            "evidence": self.evidence,
            "comparison": self.comparison,
        }


def synthesize_insights(
    segments: Iterable[Dict[str, Any]],
    signals: Iterable[Dict[str, Any]],
    comparison_label: str,
) -> List[Dict[str, Any]]:
    """Resolve conflicts and emit at most one primary insight per segment."""

    signals_by_segment: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for signal in signals:
        seg_id = _as_str(signal.get("segment_id") or signal.get("corner_id"))
        if not seg_id:
            continue
        signals_by_segment.setdefault(seg_id, {})[signal.get("signal_id")] = signal

    insights: List[Insight] = []

    for segment in segments:
        target = segment.get("target", {}) or {}
        reference = segment.get("reference", {}) or {}
        segment_id = _as_str(segment.get("segment_id") or segment.get("corner_id"))
        if not segment_id:
            continue

        signal_map = signals_by_segment.get(segment_id, {})

        quality = _extract_quality(segment, target)
        time_delta_s = _segment_time_delta(target, reference)
        time_gain_s = max(0.0, time_delta_s or 0.0)

        metrics = _extract_metrics(target, reference)
        trend = segment.get("trend") or {}

        line_issue = "line_inconsistency" in signal_map
        early_braking = "early_braking" in signal_map
        entry_speed = "entry_speed" in signal_map
        min_speed_loss = "corner_speed_loss" in signal_map
        late_throttle = "late_throttle_pickup" in signal_map
        exit_loss = "exit_speed" in signal_map
        neutral = "neutral_throttle" in signal_map
        steering = "steering_smoothness" in signal_map

        line_stddev_m = metrics.get("line_stddev_m")
        line_stddev_delta_m = metrics.get("line_stddev_delta_m")
        min_speed_delta_kmh = metrics.get("min_speed_delta_kmh")
        apex_delta_m = metrics.get("apex_delta_m")
        pickup_delta_m = metrics.get("pickup_delta_m")
        pickup_delta_s = metrics.get("pickup_delta_s")
        exit_speed_delta_kmh = metrics.get("exit_speed_delta_kmh")
        accel_rise_delta_g = metrics.get("inline_acc_rise_delta_g")

        min_speed_extreme = min_speed_delta_kmh is not None and min_speed_delta_kmh <= -6.0
        apex_shift_large = apex_delta_m is not None and apex_delta_m >= 8.0
        line_issue_mild = (
            line_stddev_m is not None
            and line_stddev_m <= 1.8
            and (line_stddev_delta_m is None or line_stddev_delta_m < 0.9)
        )

        lean_proxy_deg = _get_float(target, "lean_proxy_deg")
        lean_quality = target.get("lean_quality") or quality.get("lean_quality")
        lean_gate = _lean_gate(lean_proxy_deg, lean_quality)
        lean_high = lean_gate == "high"

        phase = _infer_phase(metrics, line_issue=line_issue, late_throttle=late_throttle)
        entry_speed_low = metrics.get("entry_speed_delta_kmh") is not None and metrics.get(
            "entry_speed_delta_kmh"
        ) <= -3.0

        primary_id: Optional[str] = None
        primary_signal: Optional[Dict[str, Any]] = None
        title = ""
        detail = ""
        actions: List[str] = []
        options: List[str] = []
        evidence: Dict[str, Any] = {}

        if line_issue:
            if min_speed_extreme and line_issue_mild and min_speed_loss:
                primary_id = "corner_speed_loss"
                primary_signal = signal_map.get(primary_id)
            else:
                primary_id = "line_inconsistency"
                primary_signal = signal_map.get(primary_id)
            title, detail, actions = _template_copy(
                primary_id,
                lean_high=lean_high,
                line_variance_high=True,
                entry_speed_low=entry_speed_low,
                apex_delta_large=apex_shift_large,
                phase=phase,
            )
            evidence = _merge_evidence(
                primary_signal,
                line_stddev_m=line_stddev_m,
                line_stddev_delta_m=line_stddev_delta_m,
                min_speed_delta_kmh=min_speed_delta_kmh,
                pickup_delta_m=pickup_delta_m,
                pickup_delta_s=pickup_delta_s,
            )
            detail, actions, options, trend_evidence = _apply_line_trend_copy(
                detail,
                actions,
                trend,
                target_apex_m=_get_float(target, "apex_dist_m"),
            )
            if trend_evidence:
                evidence.update(trend_evidence)
        elif early_braking or entry_speed:
            if early_braking:
                primary_id = "early_braking"
            else:
                primary_id = "entry_speed"
            primary_signal = signal_map.get(primary_id)
            title, detail, actions = _template_copy(
                primary_id,
                lean_high=lean_high,
                line_variance_high=line_issue,
                entry_speed_low=entry_speed_low,
                apex_delta_large=apex_shift_large,
                phase=phase,
            )
            evidence = _merge_evidence(primary_signal, **metrics)
        elif min_speed_loss:
            primary_id = "corner_speed_loss"
            primary_signal = signal_map.get(primary_id)
            title, detail, actions = _template_copy(
                primary_id,
                lean_high=lean_high,
                line_variance_high=line_issue,
                entry_speed_low=entry_speed_low,
                apex_delta_large=apex_shift_large,
                phase=phase,
            )
            evidence = _merge_evidence(primary_signal, **metrics)
        elif late_throttle or exit_loss:
            primary_id = "late_throttle_pickup" if late_throttle else "exit_speed"
            primary_signal = signal_map.get(primary_id)
            title, detail, actions = _template_copy(
                primary_id,
                lean_high=lean_high,
                line_variance_high=line_issue,
                entry_speed_low=entry_speed_low,
                apex_delta_large=apex_shift_large,
                phase=phase,
            )
            evidence = _merge_evidence(primary_signal, **metrics)
        elif neutral:
            primary_id = "neutral_throttle"
            primary_signal = signal_map.get(primary_id)
            title, detail, actions = _template_copy(
                primary_id,
                lean_high=lean_high,
                line_variance_high=line_issue,
                entry_speed_low=entry_speed_low,
                apex_delta_large=apex_shift_large,
                phase=phase,
            )
            evidence = _merge_evidence(primary_signal, **metrics)
        elif steering:
            primary_id = "steering_smoothness"
            primary_signal = signal_map.get(primary_id)
            title, detail, actions = _template_copy(
                primary_id,
                lean_high=lean_high,
                line_variance_high=line_issue,
                entry_speed_low=entry_speed_low,
                apex_delta_large=apex_shift_large,
                phase=phase,
            )
            evidence = _merge_evidence(primary_signal, **metrics)
        else:
            continue

        confidence = _confidence_from(primary_signal, quality)
        confidence_label = _confidence_label(confidence)

        insights.append(
            Insight(
                rule_id=primary_id,
                title=title,
                detail=detail,
                actions=actions,
                options=options,
                corner_id=_as_str(segment.get("corner_id")),
                segment_id=_as_str(segment.get("segment_id")),
                time_gain_s=round(_time_gain(primary_signal, time_gain_s), 4),
                confidence=round(confidence, 3),
                confidence_label=confidence_label,
                evidence=evidence,
                comparison=comparison_label,
            )
        )

    return [item.to_dict() for item in insights]


def _template_copy(
    rule_id: str,
    *,
    lean_high: bool,
    line_variance_high: bool,
    entry_speed_low: bool,
    apex_delta_large: bool,
    phase: str,
) -> Tuple[str, str, List[str]]:
    template_id = _normalize_template_id(rule_id)
    title, detail, actions = _base_template(template_id, phase)
    variant_detail = _variant_detail(
        template_id,
        lean_high=lean_high,
        line_variance_high=line_variance_high,
        entry_speed_low=entry_speed_low,
        apex_delta_large=apex_delta_large,
        phase=phase,
    )
    if variant_detail:
        detail = variant_detail
    return title, detail, actions


def _apply_line_trend_copy(
    detail: str,
    actions: List[str],
    trend: Dict[str, Any],
    *,
    target_apex_m: Optional[float],
) -> Tuple[str, List[str], List[str], Dict[str, Any]]:
    if not trend:
        return detail, actions, [], {}
    apex_std = _get_float(trend, "apex_stddev_m")
    rec = trend.get("recommendation") or {}
    rec_apex = _get_float(rec, "apex_mean_m")
    trend_laps = _get_float(trend, "trend_laps")
    session_count = _get_float(trend, "session_count")
    trend_strength = str(trend.get("trend_strength") or "").lower()
    options = _format_line_options(trend)

    evidence: Dict[str, Any] = {}
    if apex_std is not None:
        evidence["apex_stddev_m"] = apex_std
    if rec_apex is not None:
        evidence["apex_recommend_m"] = rec_apex
    if trend_laps is not None:
        evidence["trend_laps"] = trend_laps
    if session_count is not None:
        evidence["trend_session_count"] = session_count
    if trend_strength:
        evidence["trend_strength"] = trend_strength

    delta_ft = None
    if target_apex_m is not None and rec_apex is not None:
        delta_m = target_apex_m - rec_apex
        evidence["apex_bias_m"] = delta_m
        delta_ft = abs(delta_m) * _M_TO_FT
        direction = "later" if delta_m > 0 else "earlier"
        if delta_ft >= 8.0:
            actions = [
                f"Target the stable apex about {delta_ft:.0f} ft {direction} than this lap.",
                "Hold that apex for 3 laps and compare line variance.",
                "If exit drive is the priority, try the alternate line below and compare exit speed.",
            ]

    if apex_std is not None:
        std_ft = apex_std * _M_TO_FT
        if std_ft >= 10.0:
            if trend_strength in {"light", "emerging"}:
                detail = (
                    f"Apex shows an emerging pattern, varying by about {std_ft:.0f} ft lap-to-lap. "
                    "Lock in a repeatable apex from your fastest stable laps."
                )
            else:
                detail = (
                    f"Apex tends to vary by about {std_ft:.0f} ft lap-to-lap. "
                    "Lock in a repeatable apex from your fastest stable laps."
                )

    return detail, actions, options, evidence


def _format_line_options(trend: Dict[str, Any]) -> List[str]:
    clusters = trend.get("clusters")
    if not isinstance(clusters, list) or len(clusters) < 2:
        return []
    scored = sorted(clusters, key=_cluster_option_score, reverse=True)
    top = scored[:2]
    options: List[str] = []
    for idx, cluster in enumerate(top, start=1):
        apex_m = _get_float(cluster, "apex_mean_m")
        exit_kmh = _get_float(cluster, "exit_speed_median_kmh")
        line_std = _get_float(cluster, "line_stddev_median_m")
        parts: List[str] = []
        if apex_m is not None:
            parts.append(f"apex ~{apex_m * _M_TO_FT:.0f} ft")
        if exit_kmh is not None:
            parts.append(f"exit {exit_kmh * _KMH_TO_MPH:.1f} mph")
        if line_std is not None:
            parts.append(f"variance {line_std * _M_TO_FT:.0f} ft")
        label = "Option A (default)" if idx == 1 else "Option B"
        options.append(f"{label}: " + ", ".join(parts))
    return options


def _cluster_option_score(cluster: Dict[str, Any]) -> float:
    time = _get_float(cluster, "segment_time_median_s")
    apex_std = _get_float(cluster, "apex_stddev_m")
    line_std = _get_float(cluster, "line_stddev_median_m")
    score = 0.0
    if time is not None:
        score += -time
    if apex_std is not None:
        score += 1.0 / (1.0 + apex_std)
    if line_std is not None:
        score += 1.0 / (1.0 + line_std)
    return score


def _normalize_template_id(rule_id: str) -> str:
    if rule_id in {"early_braking", "entry_speed"}:
        return "entry_speed"
    return rule_id


def _base_template(template_id: str, phase: str) -> Tuple[str, str, List[str]]:
    if template_id == "entry_speed":
        return (
            "Keep Entry Speed Up",
            "Entry speed is down and the speed trace shows an early slow-down before the apex. "
            "Focus on keeping entry speed without upsetting the line.",
            [
                "Shift your brake marker about 10-15 ft later or reduce initial brake to keep entry speed.",
                "Trail off smoothly to the apex to avoid a second slow-down.",
                "Recheck entry speed delta next lap to confirm improvement.",
            ],
        )
    if template_id == "line_inconsistency":
        return (
            "Make the Line Repeatable",
            "Your path varies more than the reference, which makes speed and throttle timing inconsistent. "
            "Fixing line consistency is the safest first gain.",
            [
                "Pick one turn-in point and hit it every lap (use a fixed trackside marker).",
                "Aim for a single apex marker and avoid mid-corner corrections.",
                "Re-run the segment and compare line variance.",
            ],
        )
    if template_id == "corner_speed_loss":
        return (
            "Hold More Mid-Corner Speed",
            "Minimum speed at the apex is lower than the reference with a stable line. "
            "Focus on reducing scrub mid-corner.",
            [
                "Release brake a touch earlier to keep speed through the apex.",
                "Hold a steady line and avoid extra steering input at peak lean.",
                "Compare min-speed delta after each change.",
            ],
        )
    if template_id == "late_throttle_pickup":
        return (
            "Start Drive Sooner",
            "The speed trace suggests throttle pickup is later than the reference after the apex. "
            "Earlier drive should improve exit speed if the line is stable.",
            [
                "Begin a gentle roll-on closer to the apex (about 10-15 ft earlier).",
                "Increase throttle smoothly while keeping the bike on the same line.",
                "Check exit speed delta to confirm.",
            ],
        )
    if template_id == "exit_speed":
        return (
            "Improve Exit Drive",
            "Exit speed and acceleration after the apex are down compared to reference. "
            "The line looks stable, so earlier drive is the likely gain.",
            [
                "Start roll-on at or just after apex and add throttle progressively.",
                "Keep the bike tracking to the same exit point to avoid hesitation.",
                "Compare exit speed delta after each adjustment.",
            ],
        )
    if template_id == "neutral_throttle":
        return (
            "Reduce Coasting",
            "The speed trace shows a long neutral zone with flat speed. Decide earlier between braking and drive.",
            [
                "If before apex: choose a clearer brake-to-release plan so you are not coasting.",
                "At apex: hold a light maintenance throttle instead of neutral.",
                "After apex: transition to a smooth roll-on earlier.",
            ],
        )
    if template_id == "steering_smoothness":
        return (
            "Smooth Steering Through Apex",
            "Yaw activity is higher while minimum speed is lower, suggesting extra steering input mid-corner. "
            "Smoother steering should help carry speed.",
            [
                "Reduce mid-corner corrections by fixing a single apex marker.",
                "Make one clean steering input and hold it longer.",
                "Recheck yaw and min-speed deltas.",
            ],
        )
    if template_id == "light_brake":
        return (
            "Shorten the Light-Brake Zone",
            "The decel zone is long and shallow before the apex, which costs entry speed. "
            "Tighten the braking phase without upsetting the line.",
            [
                "Use a slightly firmer initial brake, then release earlier to hit apex speed.",
                "Shorten the brake zone by 10-15 ft while keeping the same turn-in.",
                "Recheck decel duration and entry speed delta.",
            ],
        )
    if template_id == "light_throttle":
        return (
            "Increase Roll-On After Apex",
            "The speed trace shows a long neutral or soft-drive zone after the apex. "
            "Earlier, smoother roll-on should improve exit speed.",
            [
                "Start a gentle roll-on 10-15 ft earlier.",
                "Keep throttle increase smooth while holding the same exit line.",
                "Recheck exit speed delta and neutral-zone duration.",
            ],
        )

    return ("Insight", "Focus on a repeatable line and smooth inputs.", [])


def _variant_detail(
    template_id: str,
    *,
    lean_high: bool,
    line_variance_high: bool,
    entry_speed_low: bool,
    apex_delta_large: bool,
    phase: str,
) -> Optional[str]:
    if template_id == "entry_speed":
        if line_variance_high:
            return "Line is inconsistent; stabilize turn-in and apex marks before adjusting braking."
        if apex_delta_large:
            return "Apex location moved; fix line first, then revisit entry speed."
        if lean_high:
            return "Entry is slow at high lean; prioritize smooth release and line stability before moving the brake marker."
        return None
    if template_id == "line_inconsistency":
        if apex_delta_large:
            return "Apex shifted; lock in apex marker before chasing speed."
        if lean_high:
            return "Hold a stable lean angle; avoid mid-corner steering changes."
        return None
    if template_id == "corner_speed_loss":
        if line_variance_high:
            return "Line is inconsistent; stabilize the line before pushing mid-corner speed."
        if apex_delta_large:
            return "Apex moved; fix line before pushing mid-corner speed."
        if lean_high:
            return "At high lean, prioritize a smooth release and holding line over speed gains."
        if entry_speed_low:
            return "Entry speed may be the root; fix entry first if it is down."
        return None
    if template_id == "late_throttle_pickup":
        if line_variance_high:
            return "Delay is likely line-related; stabilize line before earlier pickup."
        if apex_delta_large:
            return "Apex moved; fix apex location before changing pickup timing."
        if lean_high:
            return "At high lean, focus on a smooth, earlier roll-on rather than a big pickup."
        return None
    if template_id == "exit_speed":
        if line_variance_high:
            return "Line is inconsistent; stabilize line before pushing exit drive."
        if apex_delta_large:
            return "Apex moved; correct apex location before pushing exit drive."
        if lean_high:
            return "Use a smooth, progressive roll-on at high lean."
        return None
    if template_id == "neutral_throttle":
        if line_variance_high:
            return "Neutral zone may be from line corrections; stabilize line first."
        if entry_speed_low and phase == "entry":
            return "Entry is slow; decide earlier between braking and drive instead of coasting."
        if apex_delta_large:
            return "Apex moved; stabilize the apex before changing throttle timing."
        if lean_high:
            return "Keep inputs smooth; avoid abrupt changes."
        return None
    if template_id == "steering_smoothness":
        if line_variance_high:
            return "Line is inconsistent; prioritize line consistency before fine-tuning steering."
        if apex_delta_large:
            return "Apex moved; fix apex point before fine-tuning steering."
        if lean_high:
            return "Hold steady lean; avoid additional steering at peak lean."
        return None
    if template_id == "light_brake":
        if line_variance_high:
            return "Line is inconsistent; stabilize line before tightening the brake zone."
        if apex_delta_large:
            return "Apex moved; fix line first before adjusting braking."
        if lean_high:
            return "At high lean, avoid brake-later advice; focus on a smooth release and stability."
        if not entry_speed_low:
            return "Entry speed looks normal; prioritize line stability before changing braking."
        return None
    if template_id == "light_throttle":
        if line_variance_high:
            return "Neutral zone may be line-related; stabilize line before earlier roll-on."
        if apex_delta_large:
            return "Apex moved; fix apex location before changing throttle timing."
        if lean_high:
            return "Use a gradual roll-on to stay stable at lean."
        return None
    return None


def _infer_phase(
    metrics: Dict[str, Optional[float]],
    *,
    line_issue: bool,
    late_throttle: bool,
) -> str:
    entry_score = 0
    mid_score = 0
    exit_score = 0

    entry_speed_delta = metrics.get("entry_speed_delta_kmh")
    brake_point_delta = metrics.get("brake_point_delta_m")
    min_speed_delta = metrics.get("min_speed_delta_kmh")
    apex_delta = metrics.get("apex_delta_m")
    exit_speed_delta = metrics.get("exit_speed_delta_kmh")
    accel_rise_delta = metrics.get("inline_acc_rise_delta_g")

    if entry_speed_delta is not None and entry_speed_delta <= -3.0:
        entry_score += 2
    if brake_point_delta is not None and brake_point_delta <= -10.0:
        entry_score += 2

    if min_speed_delta is not None and min_speed_delta <= -3.0:
        mid_score += 2
    if line_issue:
        mid_score += 2
    if apex_delta is not None and apex_delta >= 8.0:
        mid_score += 1

    if exit_speed_delta is not None and exit_speed_delta <= -3.0:
        exit_score += 2
    if late_throttle:
        exit_score += 2
    if accel_rise_delta is not None and accel_rise_delta <= -0.02:
        exit_score += 1

    scores = {"entry": entry_score, "mid": mid_score, "exit": exit_score}
    best = max(scores.values())
    if best == 0:
        return "mid"

    tied = [phase for phase, score in scores.items() if score == best]
    if len(tied) == 1:
        return tied[0]

    if line_issue and "mid" in tied:
        return "mid"
    if "entry" in tied:
        return "entry"
    if "mid" in tied:
        return "mid"
    return "exit"


def _lean_gate(lean_proxy_deg: Optional[float], lean_quality: object) -> str:
    if lean_proxy_deg is None:
        return "unknown"
    if not _lean_quality_good(lean_quality):
        return "unknown"
    if lean_proxy_deg >= 42.0:
        return "high"
    if lean_proxy_deg >= 30.0:
        return "mid"
    return "low"


def _lean_quality_good(value: object) -> bool:
    if value is None:
        return False
    if value is True:
        return True
    text = str(value).strip().lower()
    return text in {"good", "ok", "true", "1"}


def _merge_evidence(signal: Optional[Dict[str, Any]], **extras: Optional[float]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    if signal and signal.get("evidence"):
        merged.update(signal["evidence"])
    for key, value in extras.items():
        if value is None:
            continue
        merged[key] = value
    return merged


def _time_gain(signal: Optional[Dict[str, Any]], fallback: float) -> float:
    if signal and signal.get("time_gain_s") is not None:
        try:
            return float(signal["time_gain_s"])
        except (TypeError, ValueError):
            pass
    return fallback


def _confidence_from(signal: Optional[Dict[str, Any]], quality: Dict[str, Any]) -> float:
    if signal and signal.get("confidence") is not None:
        try:
            return float(signal["confidence"])
        except (TypeError, ValueError):
            pass
    return _confidence_score(quality)


def _confidence_score(quality: Dict[str, Any]) -> float:
    if quality is None:
        quality = {}
    gps_accuracy = _get_float(quality, "gps_accuracy_m")
    satellites = _get_float(quality, "satellites")
    confidence = 0.5
    if gps_accuracy is not None and gps_accuracy <= 1.0:
        confidence += 0.2
    elif satellites is not None and satellites >= 10:
        confidence += 0.2
    if gps_accuracy is not None and gps_accuracy > 2.0:
        confidence -= 0.2
    if satellites is not None and satellites < 7:
        confidence -= 0.2
    return float(max(0.1, min(0.9, confidence)))


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def _extract_metrics(target: Dict[str, Any], reference: Dict[str, Any]) -> Dict[str, Optional[float]]:
    metrics: Dict[str, Optional[float]] = {}
    metrics["entry_speed_delta_kmh"] = _coalesce(
        _get_float(target, "entry_speed_delta_kmh"),
        _delta_metric(target, reference, "entry_speed_kmh"),
    )
    metrics["min_speed_delta_kmh"] = _coalesce(
        _get_float(target, "min_speed_delta_kmh"),
        _delta_metric(target, reference, "min_speed_kmh"),
    )
    metrics["exit_speed_delta_kmh"] = _coalesce(
        _get_float(target, "exit_speed_delta_kmh"),
        _delta_metric(target, reference, "exit_speed_30m_kmh"),
    )
    metrics["brake_point_delta_m"] = _delta_metric(target, reference, "brake_point_dist_m")
    metrics["line_stddev_m"] = _get_float(target, "line_stddev_m")
    metrics["line_stddev_delta_m"] = _delta_metric(target, reference, "line_stddev_m")
    metrics["apex_delta_m"] = _abs_delta_metric(target, reference, "apex_dist_m")
    metrics["apex_dist_m"] = _get_float(target, "apex_dist_m")
    metrics["pickup_delta_m"] = _delta_metric(target, reference, "throttle_pickup_dist_m")
    metrics["pickup_delta_s"] = _delta_metric(target, reference, "throttle_pickup_time_s")
    metrics["inline_acc_rise_delta_g"] = _delta_metric(target, reference, "inline_acc_rise_g")
    metrics["neutral_throttle_s"] = _get_float(target, "neutral_throttle_s")
    metrics["neutral_throttle_dist_m"] = _get_float(target, "neutral_throttle_dist_m")
    metrics["neutral_speed_delta_kmh"] = _get_float(target, "neutral_speed_delta_kmh")
    metrics["decel_avg_g"] = _get_float(target, "decel_avg_g")
    metrics["decel_time_s"] = _get_float(target, "decel_time_s")
    metrics["decel_dist_m"] = _get_float(target, "decel_dist_m")
    metrics["decel_g_per_10m"] = _get_float(target, "decel_g_per_10m")
    metrics["lean_proxy_deg"] = _get_float(target, "lean_proxy_deg")
    metrics["yaw_rms_ratio"] = _ratio_metric(target, reference, "yaw_rms")
    metrics["segment_time_delta_s"] = _segment_time_delta(target, reference)
    return metrics


def _segment_time_delta(target: Dict[str, Any], reference: Dict[str, Any]) -> Optional[float]:
    if "segment_time_delta_s" in target:
        return _get_float(target, "segment_time_delta_s")
    target_time = _get_float(target, "segment_time_s")
    ref_time = _get_float(reference, "segment_time_s")
    if target_time is None or ref_time is None:
        return None
    return target_time - ref_time


def _extract_quality(segment: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    quality = dict(segment.get("quality") or {})
    for key in ("gps_accuracy_m", "satellites", "imu_present", "imu_variance_low", "inline_acc_var", "lean_quality"):
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


def _delta_metric(target: Dict[str, Any], reference: Dict[str, Any], key: str) -> Optional[float]:
    a = _get_float(target, key)
    b = _get_float(reference, key)
    if a is None or b is None:
        return None
    return a - b


def _abs_delta_metric(target: Dict[str, Any], reference: Dict[str, Any], key: str) -> Optional[float]:
    a = _get_float(target, key)
    b = _get_float(reference, key)
    if a is None or b is None:
        return None
    return abs(a - b)


def _ratio_metric(target: Dict[str, Any], reference: Dict[str, Any], key: str) -> Optional[float]:
    a = _get_float(target, key)
    b = _get_float(reference, key)
    if a is None or b is None or b == 0:
        return None
    return a / b


def _coalesce(*values: Optional[float]) -> Optional[float]:
    for value in values:
        if value is not None:
            return value
    return None


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)
