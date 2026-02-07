"""Ranking logic for trackside insights."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

_TOP1_MIN_CONFIDENCE = 0.45
_TOP1_BLOCK_CONFIDENCE = 0.30
_TOP1_MIN_EXPECTED_GAIN_S = 0.02
_TOP1_MIN_TIME_GAIN_S = 0.01

_TOP1_EVIDENCE_REQUIREMENTS: Dict[str, tuple[tuple[str, ...], ...]] = {
    "line_inconsistency": (("line_stddev_m", "line_stddev_delta_m"),),
    "early_braking": (("brake_point_delta_m", "entry_speed_delta_kmh"),),
    "entry_speed": (("entry_speed_delta_kmh", "brake_point_delta_m"),),
    "corner_speed_loss": (("min_speed_delta_kmh",),),
    "late_throttle_pickup": (("pickup_delta_m", "pickup_delta_s"),),
    "exit_speed": (("exit_speed_delta_kmh",),),
    "neutral_throttle": (("neutral_throttle_s", "neutral_throttle_dist_m", "neutral_speed_delta_kmh"),),
    "steering_smoothness": (("yaw_rms_ratio", "min_speed_delta_kmh"),),
}


def insight_score(time_gain_s: float, confidence: float) -> float:
    """Score by time gain * confidence with severity bonus."""
    severity_bonus = 0.2 if time_gain_s >= 0.15 else 0.0
    return time_gain_s * confidence * (1.0 + severity_bonus)


def rank_insights(
    insights: Iterable[Dict[str, Any]],
    *,
    min_count: int = 3,
    max_count: int = 3,
    min_confidence: float = 0.5,
    max_per_corner: int = 2,
    max_primary_focus: int = 2,
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
    seen_corner_phase: set[tuple[str, str]] = set()

    def can_take(item: Dict[str, Any]) -> bool:
        corner_id = _corner_key(item)
        phase = _phase_key(item)
        if corner_id is not None and phase is not None:
            if (corner_id, phase) in seen_corner_phase:
                return False
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
        phase = _phase_key(item)
        if corner_id is not None:
            per_corner[corner_id] = per_corner.get(corner_id, 0) + 1
        if corner_id is not None and phase is not None:
            seen_corner_phase.add((corner_id, phase))

    if len(selected) < min_count and candidates is not items:
        remaining = [item for item in items if item not in selected]
        for item in remaining:
            if len(selected) >= max_count:
                break
            if not can_take(item):
                continue
            selected.append(item)
            corner_id = _corner_key(item)
            phase = _phase_key(item)
            if corner_id is not None:
                per_corner[corner_id] = per_corner.get(corner_id, 0) + 1
            if corner_id is not None and phase is not None:
                seen_corner_phase.add((corner_id, phase))

    primary_assigned = 0
    for item in selected:
        tier = str(item.get("risk_tier") or "Primary")
        if tier == "Primary" and primary_assigned < max_primary_focus:
            item["is_primary_focus"] = True
            primary_assigned += 1
        else:
            item["is_primary_focus"] = False

    _apply_top1_quality_gate(selected)
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


def _phase_key(item: Dict[str, Any]) -> Optional[str]:
    phase = item.get("phase")
    if phase is None:
        return None
    return str(phase)


def _apply_top1_quality_gate(selected: List[Dict[str, Any]]) -> None:
    if not selected:
        return
    top = selected[0]
    tier_before = str(top.get("risk_tier") or "Primary")
    expected_gain_input = _get_expected_gain(top)
    decision = _build_top1_gate_decision(top, tier_before=tier_before)
    top["quality_gate"] = decision

    final_expected = _compute_top1_expected_gain(top, decision)
    top["expected_gain_s"] = final_expected
    top["gain_trace"] = _build_gain_trace(top, final_expected, expected_gain_input)

    if decision["decision"] != "fail":
        return

    tier_after = "Blocked" if decision["severity"] == "hard" else "Experimental"
    if tier_before == "Blocked":
        tier_after = "Blocked"
    top["risk_tier"] = tier_after
    decision["tier_after"] = tier_after

    reason_text = "; ".join(reason["message"] for reason in decision["reasons"])
    existing_reason = str(top.get("risk_reason") or "").strip()
    gate_reason = f"Top-1 quality gate failed: {reason_text}" if reason_text else "Top-1 quality gate failed."
    top["risk_reason"] = f"{existing_reason} {gate_reason}".strip() if existing_reason else gate_reason
    if tier_after != "Primary":
        top["is_primary_focus"] = False


def _build_top1_gate_decision(item: Dict[str, Any], *, tier_before: str) -> Dict[str, Any]:
    confidence = _get_confidence(item)
    time_gain_s = _get_time_gain(item)
    expected_gain = _get_expected_gain(item)
    success_check = str(item.get("success_check") or "").strip()
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}

    checks: List[Dict[str, Any]] = []
    reasons: List[Dict[str, str]] = []

    confidence_ok = confidence >= _TOP1_MIN_CONFIDENCE
    checks.append(
        {
            "id": "confidence_minimum",
            "pass": confidence_ok,
            "value": round(confidence, 3),
            "threshold": _TOP1_MIN_CONFIDENCE,
        }
    )
    if not confidence_ok:
        reasons.append(
            {
                "code": "low_confidence",
                "message": f"confidence {confidence:.3f} below minimum {_TOP1_MIN_CONFIDENCE:.2f}",
            }
        )

    time_gain_ok = time_gain_s >= _TOP1_MIN_TIME_GAIN_S
    checks.append(
        {
            "id": "time_gain_minimum",
            "pass": time_gain_ok,
            "value": round(time_gain_s, 4),
            "threshold": _TOP1_MIN_TIME_GAIN_S,
        }
    )
    if not time_gain_ok:
        reasons.append(
            {
                "code": "insufficient_time_gain",
                "message": f"time_gain_s {time_gain_s:.4f} below minimum {_TOP1_MIN_TIME_GAIN_S:.2f}",
            }
        )

    expected_gain_ok = expected_gain is not None and expected_gain >= _TOP1_MIN_EXPECTED_GAIN_S
    checks.append(
        {
            "id": "expected_gain_minimum",
            "pass": expected_gain_ok,
            "value": None if expected_gain is None else round(expected_gain, 4),
            "threshold": _TOP1_MIN_EXPECTED_GAIN_S,
        }
    )
    if not expected_gain_ok:
        if expected_gain is None:
            reasons.append(
                {
                    "code": "missing_expected_gain",
                    "message": "expected_gain_s is missing",
                }
            )
        else:
            reasons.append(
                {
                    "code": "insufficient_expected_gain",
                    "message": f"expected_gain_s {expected_gain:.4f} below minimum {_TOP1_MIN_EXPECTED_GAIN_S:.2f}",
                }
            )

    required_keys = _required_evidence_keys(str(item.get("rule_id") or ""))
    missing_keys = ["/".join(group) for group in required_keys if not _has_any_evidence_value(evidence, group)]
    evidence_ok = not missing_keys
    checks.append(
        {
            "id": "required_evidence_present",
            "pass": evidence_ok,
            "required_keys": missing_keys if missing_keys else ["/".join(group) for group in required_keys],
        }
    )
    if not evidence_ok:
        reasons.append(
            {
                "code": "missing_required_evidence",
                "message": f"missing required evidence fields: {', '.join(missing_keys)}",
            }
        )

    success_check_ok = bool(success_check)
    checks.append(
        {
            "id": "success_check_present",
            "pass": success_check_ok,
        }
    )
    if not success_check_ok:
        reasons.append(
            {
                "code": "missing_success_check",
                "message": "success_check is missing",
            }
        )

    hard_fail = (
        confidence < _TOP1_BLOCK_CONFIDENCE
        or any(reason["code"] in {"missing_required_evidence", "missing_expected_gain"} for reason in reasons)
    )
    decision = "fail" if reasons else "pass"
    severity = "hard" if decision == "fail" and hard_fail else ("soft" if decision == "fail" else "none")

    return {
        "scope": "top_1",
        "decision": decision,
        "severity": severity,
        "checks": checks,
        "reasons": reasons,
        "tier_before": tier_before,
        "tier_after": tier_before,
    }


def _compute_top1_expected_gain(item: Dict[str, Any], decision: Dict[str, Any]) -> float:
    confidence = _get_confidence(item)
    time_gain_s = max(0.0, _get_time_gain(item))
    weighted_gain = time_gain_s * max(0.0, confidence)
    expected_gain = _get_expected_gain(item)

    if expected_gain is None:
        base = weighted_gain
    elif decision["decision"] == "fail":
        base = min(expected_gain, weighted_gain)
    else:
        base = expected_gain

    final = max(_TOP1_MIN_TIME_GAIN_S, base)
    return round(final, 4)


def _build_gain_trace(
    item: Dict[str, Any],
    final_expected_gain_s: float,
    expected_gain_input_s: Optional[float],
) -> Dict[str, Any]:
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    time_gain_s = max(0.0, _get_time_gain(item))
    confidence = max(0.0, _get_confidence(item))
    weighted_gain = round(time_gain_s * confidence, 4)

    return {
        "raw_inputs": {
            "rule_id": item.get("rule_id"),
            "corner_id": item.get("corner_id"),
            "segment_id": item.get("segment_id"),
            "phase": item.get("phase"),
            "time_gain_s": round(time_gain_s, 4),
            "confidence": round(confidence, 3),
            "expected_gain_input_s": expected_gain_input_s,
            "evidence": deepcopy(evidence),
        },
        "transformations": [
            {
                "step": "normalize_time_gain",
                "output_time_gain_s": round(time_gain_s, 4),
            },
            {
                "step": "apply_confidence_weight",
                "input_time_gain_s": round(time_gain_s, 4),
                "input_confidence": round(confidence, 3),
                "output_weighted_gain_s": weighted_gain,
            },
            {
                "step": "finalize_expected_gain",
                "output_expected_gain_s": final_expected_gain_s,
            },
        ],
        "confidence_weighting": {
            "confidence": round(confidence, 3),
            "weighted_gain_s": weighted_gain,
        },
        "final_expected_gain_s": final_expected_gain_s,
    }


def _get_expected_gain(item: Dict[str, Any]) -> Optional[float]:
    value = item.get("expected_gain_s")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _required_evidence_keys(rule_id: str) -> tuple[tuple[str, ...], ...]:
    required = _TOP1_EVIDENCE_REQUIREMENTS.get(rule_id)
    if required:
        return required
    return (("segment_time_delta_s", "time_gain_s"),)


def _has_any_evidence_value(evidence: Dict[str, Any], keys: tuple[str, ...]) -> bool:
    for key in keys:
        if key in evidence and evidence.get(key) is not None:
            return True
    return False
