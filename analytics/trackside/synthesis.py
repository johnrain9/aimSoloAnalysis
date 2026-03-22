"""Deterministic synthesis of trackside insights from signals + metrics."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from analytics.trackside.corner_identity import rider_corner_label

_M_TO_FT = 3.28084
_KMH_TO_MPH = 0.621371


def _to_ft(value_m: float) -> float:
    return value_m * _M_TO_FT


def _to_mph(value_kmh: float) -> float:
    return value_kmh * _KMH_TO_MPH


@dataclass(frozen=True)
class Insight:
    rule_id: str
    title: str
    detail: str
    phase: str
    operational_action: str
    causal_reason: str
    risk_tier: str
    risk_reason: str
    data_quality_note: str
    uncertainty_note: str
    success_check: str
    did: str
    should: str
    because: str
    did_vs_should_status: str
    did_vs_should_source: Dict[str, Any]
    expected_gain_s: float
    experimental_protocol: Optional[Dict[str, Any]]
    actions: List[str]
    options: List[str]
    corner_id: Optional[str]
    corner_label: Optional[str]
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
            "phase": self.phase,
            "operational_action": self.operational_action,
            "causal_reason": self.causal_reason,
            "risk_tier": self.risk_tier,
            "risk_reason": self.risk_reason,
            "data_quality_note": self.data_quality_note,
            "uncertainty_note": self.uncertainty_note,
            "success_check": self.success_check,
            "did": self.did,
            "should": self.should,
            "because": self.because,
            "did_vs_should_status": self.did_vs_should_status,
            "did_vs_should_source": dict(self.did_vs_should_source),
            "expected_gain_s": self.expected_gain_s,
            "experimental_protocol": self.experimental_protocol,
            "actions": list(self.actions),
            "options": list(self.options),
            "corner_id": self.corner_id,
            "corner_label": self.corner_label,
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
                turn_in_target_dist_m=metrics.get("turn_in_target_dist_m"),
                turn_in_reference_dist_m=metrics.get("turn_in_reference_dist_m"),
            )
            detail, actions, options, trend_evidence = _apply_line_trend_copy(
                detail,
                actions,
                trend,
                target_apex_m=_get_float(target, "apex_dist_m"),
            )
            if trend_evidence:
                evidence.update(trend_evidence)
            evidence = _line_evidence_defaults(evidence)
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

        corner_label = rider_corner_label(
            segment.get("corner_label") or segment.get("corner_id"),
            fallback_internal_id=segment_id,
            apex_m=metrics.get("apex_dist_m"),
        )

        confidence = _confidence_from(primary_signal, quality)
        confidence_label = _confidence_label(confidence)
        applied_gain_s = round(_time_gain(primary_signal, time_gain_s), 4)
        operational_action = _operational_action(
            actions,
            primary_id,
            phase,
            corner_label=corner_label,
            evidence=evidence,
        )
        causal_reason = _causal_reason(primary_id, evidence, phase)
        data_quality_note = _data_quality_note(quality)
        uncertainty_note = _uncertainty_note(confidence, quality, evidence)
        risk_tier, risk_reason = _risk_tier(
            primary_id,
            phase=phase,
            confidence=confidence,
            quality=quality,
            lean_high=lean_high,
            line_issue=line_issue,
        )
        behavior_class = _behavior_class(primary_id)
        success_check = _success_check(
            primary_id,
            behavior_class=behavior_class,
            phase=phase,
            metrics=metrics,
            evidence=evidence,
        )
        did_vs_should = _did_vs_should_copy(
            rule_id=primary_id,
            phase=phase,
            corner_label=corner_label,
            operational_action=operational_action,
            evidence=evidence,
        )
        expected_gain_s = applied_gain_s if applied_gain_s > 0 else 0.01
        experimental_protocol = None
        if risk_tier == "Experimental":
            experimental_protocol = _experimental_protocol(
                expected_gain_s=expected_gain_s,
                primary_id=primary_id,
                behavior_class=behavior_class,
                phase=phase,
                evidence=evidence,
            )

        insights.append(
            Insight(
                rule_id=primary_id,
                title=title,
                detail=detail,
                phase=phase,
                operational_action=operational_action,
                causal_reason=causal_reason,
                risk_tier=risk_tier,
                risk_reason=risk_reason,
                data_quality_note=data_quality_note,
                uncertainty_note=uncertainty_note,
                success_check=success_check,
                did=did_vs_should["did"],
                should=did_vs_should["should"],
                because=did_vs_should["because"],
                did_vs_should_status=did_vs_should["did_vs_should_status"],
                did_vs_should_source=did_vs_should["did_vs_should_source"],
                expected_gain_s=expected_gain_s,
                experimental_protocol=experimental_protocol,
                actions=actions,
                options=options,
                corner_id=corner_label,
                corner_label=corner_label,
                segment_id=_as_str(segment.get("segment_id")),
                time_gain_s=applied_gain_s,
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
    recurrence_detected = _as_bool(trend.get("recurrence_detected"))
    recurrence_session_count = _get_float(trend, "recurrence_session_count")
    recurrence_priority_shift = _as_bool(trend.get("recurrence_priority_shift"))
    why_now = str(trend.get("why_now") or "").strip()
    fatigue_likely = _as_bool(trend.get("fatigue_likely"))
    fatigue_session_count = _get_float(trend, "fatigue_session_count")
    fatigue_late_laps = _get_float(trend, "fatigue_late_laps")
    fatigue_max_fade_s = _get_float(trend, "fatigue_max_fade_s")
    recent_turn_in = trend.get("recent_turn_in_dist_m")
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
    if recurrence_detected and recurrence_session_count is not None:
        evidence["recurrence_session_count"] = recurrence_session_count
    if recurrence_priority_shift:
        evidence["recurrence_priority_shift"] = True
    if why_now:
        evidence["why_now"] = why_now
    if fatigue_likely:
        evidence["fatigue_likely"] = True
    if fatigue_session_count is not None:
        evidence["fatigue_session_count"] = fatigue_session_count
    if fatigue_late_laps is not None:
        evidence["fatigue_late_laps"] = fatigue_late_laps
    if fatigue_max_fade_s is not None:
        evidence["fatigue_max_fade_s"] = fatigue_max_fade_s
    if isinstance(recent_turn_in, list):
        recent_turn_in_vals: List[float] = []
        for value in recent_turn_in:
            try:
                recent_turn_in_vals.append(float(value))
            except (TypeError, ValueError):
                continue
        evidence["recent_turn_in_dist_m"] = recent_turn_in_vals[-4:]

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

    if recurrence_priority_shift and why_now:
        session_text = ""
        if recurrence_session_count is not None:
            session_text = f" across {int(recurrence_session_count)} same-track sessions"
        detail = f"{detail} Recurrence detected{session_text}. Why now: {why_now}"
        if actions:
            actions = list(actions)
            actions[0] = f"{actions[0]} Prioritize this corner first next session."

    if fatigue_likely:
        fade_text = ""
        if fatigue_max_fade_s is not None:
            fade_text = f" (~{fatigue_max_fade_s:.2f}s late fade)"
        detail = (
            f"{detail} Late-session pace fade looked fatigue-driven{fade_text}, "
            "so late laps were de-weighted to avoid false technique regression."
        )
        if not any("fresh laps" in action.lower() for action in actions):
            actions = list(actions)
            actions.append(
                "Validate on fresh laps next session before making larger technique corrections."
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


def _merge_evidence(signal: Optional[Dict[str, Any]], **extras: Any) -> Dict[str, Any]:
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
    metrics["turn_in_reference_dist_m"] = _get_float(reference, "start_dist_m")
    metrics["turn_in_target_dist_m"] = _coalesce(
        metrics["turn_in_reference_dist_m"],
        _get_float(target, "start_dist_m"),
    )
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


def _operational_action(
    actions: List[str],
    rule_id: str,
    phase: str,
    *,
    corner_label: Optional[str],
    evidence: Dict[str, Any],
) -> str:
    def _line_action(base: str) -> str:
        history_text = _turn_in_history_text(evidence.get("recent_turn_in_dist_m"))
        if history_text:
            return f"{base} Recent turn-in points were {history_text}."
        return base

    if rule_id == "line_inconsistency":
        turn_in_dist_m = _get_float(evidence, "turn_in_target_dist_m")
        if turn_in_dist_m is not None and corner_label:
            return _line_action(
                f"{corner_label}: initiate turn-in at about {_to_ft(turn_in_dist_m):.0f} ft lap distance "
                "each lap, then hold one apex marker."
            )
        if corner_label:
            return _line_action(
                f"{corner_label}: initiate turn-in at the same lap distance each lap and hold one apex marker."
            )
    if actions:
        return actions[0]
    return f"Use one repeatable {phase} marker in this corner and keep inputs smooth."


def _turn_in_history_text(raw_values: Any) -> str:
    if not isinstance(raw_values, list):
        return ""
    values_ft: List[str] = []
    for value in raw_values[-4:]:
        try:
            values_ft.append(f"{_to_ft(float(value)):.0f} ft")
        except (TypeError, ValueError):
            continue
    if len(values_ft) < 2:
        return ""
    return ", ".join(values_ft)


def _line_evidence_defaults(evidence: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(evidence)
    history = normalized.get("recent_turn_in_dist_m")
    if not isinstance(history, list):
        history = []
    normalized["recent_turn_in_dist_m"] = history

    if _get_float(normalized, "turn_in_target_dist_m") is None:
        normalized["turn_in_target_dist_m"] = None
    if _get_float(normalized, "turn_in_reference_dist_m") is None:
        normalized["turn_in_reference_dist_m"] = None

    turn_in_avg = _turn_in_average(history)
    normalized["turn_in_rider_avg_dist_m"] = turn_in_avg

    if _get_float(normalized, "turn_in_target_dist_m") is not None:
        normalized["turn_in_fallback_status"] = "resolved"
    elif turn_in_avg is not None:
        normalized["turn_in_fallback_status"] = "rider_average_only"
    else:
        normalized["turn_in_fallback_status"] = "missing"
    return normalized


def _turn_in_average(values: List[Any]) -> Optional[float]:
    numeric: List[float] = []
    for value in values:
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            continue
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def _did_vs_should_copy(
    *,
    rule_id: str,
    phase: str,
    corner_label: Optional[str],
    operational_action: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    status = _did_vs_should_status(rule_id, evidence)
    did = _did_clause(rule_id, phase, corner_label, evidence)
    should = _should_clause(
        rule_id=rule_id,
        phase=phase,
        corner_label=corner_label,
        operational_action=operational_action,
        evidence=evidence,
        status=status,
    )
    because = _because_clause(rule_id, evidence, phase=phase, status=status)
    return {
        "did": did,
        "should": should,
        "because": because,
        "did_vs_should_status": status,
        "did_vs_should_source": {
            "rule_id": rule_id,
            "evidence_keys": _did_vs_should_evidence_keys(rule_id, evidence),
        },
    }


def _did_vs_should_status(rule_id: str, evidence: Dict[str, Any]) -> str:
    required = _did_vs_should_evidence_keys(rule_id, evidence, present_only=False)
    present = _did_vs_should_evidence_keys(rule_id, evidence)
    if required and set(required).issubset(set(present)):
        return "resolved"
    if present:
        return "partial"
    return "insufficient_data"


def _did_clause(rule_id: str, phase: str, corner_label: Optional[str], evidence: Dict[str, Any]) -> str:
    prefix = f"{corner_label}: " if corner_label else ""
    delta = _did_delta_phrase(rule_id, evidence)
    if delta:
        return f"{prefix}{phase} phase: {delta}"
    return (
        f"{prefix}{phase} phase: observed behavior is off reference, but the available telemetry "
        "does not support a precise numeric delta."
    )


def _did_delta_phrase(rule_id: str, evidence: Dict[str, Any]) -> str:
    line_std_delta = _get_float(evidence, "line_stddev_delta_m")
    line_std = _get_float(evidence, "line_stddev_m")
    entry_delta = _get_float(evidence, "entry_speed_delta_kmh")
    brake_delta = _get_float(evidence, "brake_point_delta_m")
    min_delta = _get_float(evidence, "min_speed_delta_kmh")
    pickup_delta = _get_float(evidence, "pickup_delta_m")
    exit_delta = _get_float(evidence, "exit_speed_delta_kmh")
    neutral_s = _get_float(evidence, "neutral_throttle_s")
    neutral_dist = _get_float(evidence, "neutral_throttle_dist_m")
    yaw_ratio = _get_float(evidence, "yaw_rms_ratio")

    if rule_id == "line_inconsistency":
        if line_std_delta is not None:
            return f"line spread is about +{_to_ft(abs(line_std_delta)):.1f} ft versus reference."
        if line_std is not None:
            return f"line spread is running around {_to_ft(line_std):.1f} ft lap to lap."
    if rule_id in {"entry_speed", "early_braking"}:
        if entry_delta is not None:
            return f"entry speed is down by {abs(_to_mph(entry_delta)):.1f} mph."
        if brake_delta is not None:
            return f"braking starts about {abs(_to_ft(brake_delta)):.1f} ft earlier than reference."
    if rule_id == "corner_speed_loss" and min_delta is not None:
        return f"apex minimum speed is down by {abs(_to_mph(min_delta)):.1f} mph."
    if rule_id in {"late_throttle_pickup", "exit_speed"}:
        if pickup_delta is not None:
            return f"throttle pickup is about {abs(_to_ft(pickup_delta)):.1f} ft late."
        if exit_delta is not None:
            return f"exit speed is down by {abs(_to_mph(exit_delta)):.1f} mph."
    if rule_id == "neutral_throttle":
        if neutral_s is not None:
            return f"neutral throttle persists for about {neutral_s:.2f} s through transition."
        if neutral_dist is not None:
            return f"neutral throttle spans about {_to_ft(neutral_dist):.1f} ft."
    if rule_id == "steering_smoothness" and yaw_ratio is not None:
        return f"steering activity is {yaw_ratio:.2f}x the reference trace."
    return ""


def _should_clause(
    *,
    rule_id: str,
    phase: str,
    corner_label: Optional[str],
    operational_action: str,
    evidence: Dict[str, Any],
    status: str,
) -> str:
    action = _strip_corner_prefix(operational_action, corner_label)
    prefix = f"{corner_label}: " if corner_label else ""
    should = f"{prefix}{phase} phase: {action}"
    if status != "resolved":
        should = (
            f"{should} If marker precision is limited, keep one repeatable reference for the next 2-3 laps"
            f" and compare the same metric trend. Measurable target: {_measurable_target(rule_id, evidence)}"
        )
    if _is_vague_only_consistency_cue(should):
        should = f"{should} Measurable target: {_measurable_target(rule_id, evidence)}"
    return should


def _strip_corner_prefix(action: str, corner_label: Optional[str]) -> str:
    text = str(action or "").strip()
    if not text:
        return "Use one repeatable marker and keep inputs smooth."
    if corner_label and text.startswith(f"{corner_label}:"):
        return text[len(corner_label) + 1 :].strip()
    return text


def _is_vague_only_consistency_cue(text: str) -> bool:
    lowered = text.lower()
    has_vague = any(token in lowered for token in ("consistent", "consistency", "stabilize", "smooth"))
    has_number = bool(re.search(r"\d", lowered))
    return has_vague and not has_number


def _measurable_target(rule_id: str, evidence: Dict[str, Any]) -> str:
    if rule_id == "line_inconsistency":
        return "hold line variance delta at or below +1.0 ft."
    if rule_id in {"entry_speed", "early_braking"}:
        return "recover at least +1.2 mph entry speed delta."
    if rule_id == "corner_speed_loss":
        return "recover at least +1.2 mph apex minimum speed delta."
    if rule_id in {"late_throttle_pickup", "exit_speed"}:
        return "recover at least +1.2 mph exit speed delta."
    if rule_id == "neutral_throttle":
        return "reduce neutral throttle below 0.8 s."
    if rule_id == "steering_smoothness":
        return "bring yaw ratio to <= 1.10."
    return "confirm a repeatable improvement over the next 2 laps."


def _because_clause(rule_id: str, evidence: Dict[str, Any], *, phase: str, status: str) -> str:
    because = _causal_reason(rule_id, evidence, phase)
    if not because.lower().startswith("because"):
        because = f"Because {because[0].lower() + because[1:]}" if because else "Because telemetry indicates this."
    if status == "partial":
        return f"{because} Evidence is partial, so marker precision is bounded to available channels."
    if status == "insufficient_data":
        return (
            f"{because} Evidence is insufficient for a precise marker delta, so use conservative, "
            "repeatable references next session."
        )
    return because


def _did_vs_should_evidence_keys(
    rule_id: str, evidence: Dict[str, Any], *, present_only: bool = True
) -> List[str]:
    mapping = {
        "line_inconsistency": ("line_stddev_delta_m", "turn_in_target_dist_m"),
        "entry_speed": ("entry_speed_delta_kmh", "brake_point_delta_m"),
        "early_braking": ("entry_speed_delta_kmh", "brake_point_delta_m"),
        "corner_speed_loss": ("min_speed_delta_kmh",),
        "late_throttle_pickup": ("pickup_delta_m", "exit_speed_delta_kmh"),
        "exit_speed": ("pickup_delta_m", "exit_speed_delta_kmh"),
        "neutral_throttle": ("neutral_throttle_s", "neutral_throttle_dist_m"),
        "steering_smoothness": ("yaw_rms_ratio", "min_speed_delta_kmh"),
    }
    keys = mapping.get(rule_id, ())
    if not present_only:
        return list(keys)
    present: List[str] = []
    for key in keys:
        if _get_float(evidence, key) is not None:
            present.append(key)
    return present


def _causal_reason(rule_id: str, evidence: Dict[str, Any], phase: str) -> str:
    if rule_id == "line_inconsistency":
        line_std = _get_float(evidence, "line_stddev_m")
        if line_std is not None:
            return (
                f"Because line variance is elevated ({_to_ft(line_std):.1f} ft), "
                f"timing and speed consistency drop through {phase}."
            )
    if rule_id in {"early_braking", "entry_speed"}:
        entry_delta = _get_float(evidence, "entry_speed_delta_kmh")
        brake_delta = _get_float(evidence, "brake_point_delta_m")
        if entry_delta is not None:
            return (
                f"Because entry speed is down by {abs(_to_mph(entry_delta)):.1f} mph, "
                "this segment starts slower than reference."
            )
        if brake_delta is not None:
            return (
                f"Because braking starts {abs(_to_ft(brake_delta)):.1f} ft earlier, "
                "speed is shed too soon before apex."
            )
    if rule_id == "corner_speed_loss":
        min_delta = _get_float(evidence, "min_speed_delta_kmh")
        if min_delta is not None:
            return (
                f"Because apex minimum speed is lower by {abs(_to_mph(min_delta)):.1f} mph, "
                "mid-corner time is being lost."
            )
    if rule_id in {"late_throttle_pickup", "exit_speed"}:
        pickup_delta = _get_float(evidence, "pickup_delta_m")
        exit_delta = _get_float(evidence, "exit_speed_delta_kmh")
        if pickup_delta is not None:
            return (
                f"Because throttle pickup is delayed by {abs(_to_ft(pickup_delta)):.1f} ft, "
                "exit drive starts late."
            )
        if exit_delta is not None:
            return (
                f"Because exit speed is down by {abs(_to_mph(exit_delta)):.1f} mph, "
                "acceleration phase is underperforming."
            )
    if rule_id == "neutral_throttle":
        neutral_s = _get_float(evidence, "neutral_throttle_s")
        if neutral_s is not None:
            return f"Because neutral throttle lasts {neutral_s:.2f} s, the bike coasts instead of braking or driving."
    if rule_id == "steering_smoothness":
        yaw_ratio = _get_float(evidence, "yaw_rms_ratio")
        if yaw_ratio is not None:
            return f"Because steering activity is {yaw_ratio:.2f}x reference, mid-corner scrub is likely increasing."
    return "Because segment evidence shows this is the dominant controllable source of lost time."


def _risk_tier(
    rule_id: str,
    *,
    phase: str,
    confidence: float,
    quality: Dict[str, Any],
    lean_high: bool,
    line_issue: bool,
) -> Tuple[str, str]:
    gps_accuracy = _get_float(quality, "gps_accuracy_m")
    satellites = _get_float(quality, "satellites")
    low_quality = (gps_accuracy is not None and gps_accuracy > 2.0) or (
        satellites is not None and satellites < 7
    )
    if lean_high and rule_id in {"entry_speed", "early_braking", "late_throttle_pickup", "exit_speed"}:
        return (
            "Blocked",
            f"High-lean {phase} context; avoid aggressive brake/throttle timing changes until stability improves.",
        )
    if confidence < 0.55 or low_quality or (line_issue and rule_id in {"late_throttle_pickup", "exit_speed"}):
        return (
            "Experimental",
            "Plausible gain with uncertainty; run as a bounded test before adopting as primary focus.",
        )
    return ("Primary", "Evidence quality and context support this as a main next-session focus.")


def _data_quality_note(quality: Dict[str, Any]) -> str:
    gps_accuracy = _get_float(quality, "gps_accuracy_m")
    satellites = _get_float(quality, "satellites")
    notes: List[str] = []
    if gps_accuracy is None:
        notes.append("gps accuracy unknown")
    elif gps_accuracy <= 1.0:
        notes.append(f"gps accuracy good ({_to_ft(gps_accuracy):.1f} ft)")
    elif gps_accuracy <= 2.0:
        notes.append(f"gps accuracy fair ({_to_ft(gps_accuracy):.1f} ft)")
    else:
        notes.append(f"gps accuracy weak ({_to_ft(gps_accuracy):.1f} ft)")
    if satellites is None:
        notes.append("satellite count unavailable")
    elif satellites >= 10:
        notes.append(f"{satellites:.0f} satellites")
    elif satellites >= 7:
        notes.append(f"{satellites:.0f} satellites (borderline)")
    else:
        notes.append(f"{satellites:.0f} satellites (low)")
    return "; ".join(notes)


def _uncertainty_note(confidence: float, quality: Dict[str, Any], evidence: Dict[str, Any]) -> str:
    confidence_label = _confidence_label(confidence)
    gaps: List[str] = []
    if quality.get("imu_present") is False:
        gaps.append("no IMU channels")
    if _get_float(evidence, "segment_time_delta_s") is None:
        gaps.append("segment time delta missing")
    if _get_float(quality, "gps_accuracy_m") is None:
        gaps.append("gps accuracy missing")
    if not gaps:
        return f"{confidence_label.capitalize()} confidence from current telemetry quality."
    return f"{confidence_label.capitalize()} confidence; uncertainty from " + ", ".join(gaps) + "."


def _success_check(
    rule_id: str,
    *,
    behavior_class: str,
    phase: str,
    metrics: Dict[str, Optional[float]],
    evidence: Dict[str, Any],
) -> str:
    if rule_id == "line_inconsistency":
        return (
            "Rider check: repeat the same turn-in and apex marker for the next 3 laps with no"
            " mid-corner correction. Telemetry confirmation (optional): keep line variance delta"
            " <= +1.0 ft."
        )
    if rule_id in {"entry_speed", "early_braking"}:
        return (
            "Rider check: for the next 2 laps, carry speed to apex with one clean brake release and"
            " no extra scrub. Telemetry confirmation (optional): improve entry speed delta by"
            " >= +1.2 mph without increasing line spread."
        )
    if rule_id == "corner_speed_loss":
        return (
            "Rider check: hold a single arc through apex for 2-3 laps and feel less steering scrub"
            " at max lean. Telemetry confirmation (optional): improve apex minimum speed delta by"
            " >= +1.2 mph while keeping apex location within 13 ft."
        )
    if rule_id in {"late_throttle_pickup", "exit_speed"}:
        return (
            "Rider check: begin drive sooner after apex for the next 2 laps without widening exit."
            " Telemetry confirmation (optional): cut pickup delay by >= 20 ft (or 0.06 s) and"
            " improve exit speed delta by >= +1.2 mph."
        )
    if rule_id == "neutral_throttle":
        return (
            "Rider check: replace post-apex coasting with one smooth roll-on within 2 laps while"
            " keeping the same line. Telemetry confirmation (optional): reduce neutral throttle"
            " below 0.8 s (or 39 ft)."
        )
    if rule_id == "steering_smoothness":
        return (
            "Rider check: make one clean steering input and hold it through apex for 2-3 laps."
            " Telemetry confirmation (optional): bring yaw ratio to <= 1.10 while improving apex"
            " minimum speed delta by >= +0.6 mph."
        )
    if behavior_class == "braking":
        return (
            "Rider check: run two laps with one braking marker change only and keep the same turn-in"
            " line. Telemetry confirmation (optional): entry speed and brake timing trend in the"
            " target direction."
        )
    if behavior_class == "throttle":
        return (
            "Rider check: run two laps with one earlier, smoother drive input while holding exit"
            " line. Telemetry confirmation (optional): throttle pickup/exit-speed metrics improve"
            " without extra line spread."
        )
    if behavior_class == "line_trajectory":
        return (
            "Rider check: lock one turn-in and apex marker for 3 laps with minimal correction."
            " Telemetry confirmation (optional): line repeatability and segment speed trend improve."
        )
    return (
        f"Rider check: run 2 controlled laps and feel a clear {phase} improvement with stable bike"
        " behavior. Telemetry confirmation (optional): trend metrics in this segment improve."
    )


def _experimental_protocol(
    *,
    expected_gain_s: float,
    primary_id: str,
    behavior_class: str,
    phase: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    protocol_class = behavior_class
    if protocol_class not in {"braking", "throttle", "line_trajectory"}:
        protocol_class = "generic_safe"

    protocol = {
        "behavior_class": protocol_class,
        "expected_gain_s": round(expected_gain_s, 3),
        "risk": "",
        "bounds": "",
        "abort_criteria": "",
    }

    if protocol_class == "braking":
        protocol["risk"] = "Over-braking can destabilize turn-in and increase front-end load abruptly."
        protocol["bounds"] = (
            "Change braking timing only; run 2 laps; adjust one marker step (~5-10 ft) while"
            " keeping release shape and line constant."
        )
        protocol["abort_criteria"] = (
            "Abort the test if the bike chatters, runs wide at turn-in, or needs a second brake"
            " stab to make apex."
        )
        return protocol

    if protocol_class == "throttle":
        protocol["risk"] = "Early or abrupt drive can force line widening or rear instability."
        protocol["bounds"] = (
            "Change throttle timing/rate only; run 2 laps; begin drive one small step earlier (~5-10 ft)"
            " with smooth roll-on."
        )
        protocol["abort_criteria"] = (
            "Abort the test if rear slip spikes, exit line opens, or you must roll out to catch the"
            " bike."
        )
        return protocol

    if protocol_class == "line_trajectory":
        protocol["risk"] = "Forcing line changes can reduce confidence and create mid-corner corrections."
        protocol["bounds"] = (
            "Change line marker choice only; run 3 laps; lock one turn-in/apex marker and keep brake"
            " and throttle timing unchanged."
        )
        protocol["abort_criteria"] = (
            "Abort the test if repeated mid-corner corrections appear, curb misses increase, or the"
            " bike feels unsettled."
        )
        return protocol

    protocol["risk"] = "Unknown change type; treat as elevated risk until classified."
    protocol["bounds"] = (
        "Conservative fallback: change one input only; run 1-2 laps max; keep all other references"
        " fixed and prioritize stability."
    )
    protocol["abort_criteria"] = (
        "Abort immediately on any instability, missed reference point, or confidence drop."
    )
    protocol["note"] = (
        f"Unknown behavior class for rule '{primary_id}'. Applied conservative generic protocol."
    )
    return protocol


def _behavior_class(rule_id: str) -> str:
    if rule_id in {"entry_speed", "early_braking", "light_brake"}:
        return "braking"
    if rule_id in {"late_throttle_pickup", "exit_speed", "light_throttle", "neutral_throttle"}:
        return "throttle"
    if rule_id in {"line_inconsistency", "corner_speed_loss", "steering_smoothness"}:
        return "line_trajectory"
    return "generic_safe"


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
