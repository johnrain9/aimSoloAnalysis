"""Top-1 quality evaluation harness with machine-readable JSON artifact.

Documented command:
  $env:PYTHONPATH='.'; python tools/eval_top1_scorecard.py
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.top1_artifact_contract import (
    DEFAULT_TOP1_SCORECARD_PATH,
    DEFAULT_TOP1_TRACE_PATH,
    LEGACY_BATCH_REPORT_PATH,
    LEGACY_SCORECARD_INPUT_PATH,
)

DEFAULT_INPUT = DEFAULT_TOP1_TRACE_PATH.as_posix()
DEFAULT_REPORT = DEFAULT_TOP1_SCORECARD_PATH.as_posix()
ROUND_DIGITS = 4
MALFORMED_EXAMPLE_LIMIT = 20
TOP_EXAMPLE_LIMIT = 20
AUTO_SCORED_REQUIREMENTS = ["RQ-EVAL-007", "RQ-EVAL-008", "RQ-EVAL-010", "RQ-NFR-006"]
HUMAN_REVIEWED_REQUIREMENTS = ["RQ-EVAL-011", "RQ-EVAL-012", "RQ-NFR-007"]
COACHING_GATE_LABELS = {
    "did_vs_should_fields_present": "Did/should/because/success_check fields are present.",
    "did_vs_should_delta_present": "Did/detail copy includes a numeric did-vs-should delta.",
    "did_vs_should_rationale_present": "Because copy includes a causal rationale.",
    "did_vs_should_success_check_measurable": "Success check includes measurable criteria.",
    "did_vs_should_unit_consistency": "Rider-facing copy avoids metric/internal unit leakage.",
    "did_vs_should_corner_consistency": "Rider-facing copy uses a stable corner label.",
}
DELTA_PATTERN = re.compile(
    r"(\b\d+(?:\.\d+)?\s*(?:ft|mph|s)\b.*\b(reference|earlier|later|lower|wider)\b)|(\b\d+(?:\.\d+)?x reference\b)",
    re.IGNORECASE,
)
MEASURABLE_CHECK_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ft|mph|s|lap|laps)\b|\bnext\s+\d+\s+laps?\b",
    re.IGNORECASE,
)
METRIC_LEAK_PATTERN = re.compile(r"\bkm/h\b|\bm/s\b|_[a-z0-9]+m\b|\b\d+(?:\.\d+)?\s*m\b", re.IGNORECASE)


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, ROUND_DIGITS)
    if isinstance(value, list):
        return [_round(v) for v in value]
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    return value


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_snippet(line: str, limit: int = 160) -> str:
    text = line.strip().replace("\t", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _first_non_empty(record: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for key in keys:
        if key in record:
            value = record[key]
            if value is not None and value != "":
                return value
    return default


def _extract_top1_pass(record: Dict[str, Any]) -> Optional[bool]:
    value = _first_non_empty(
        record,
        ["top1_pass", "top1_ok", "pass", "is_pass", "passed", "top1_result"],
    )
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"pass", "passed", "ok", "true", "1"}:
            return True
        if normalized in {"fail", "failed", "false", "0"}:
            return False
    return None


def _extract_gain_s(record: Dict[str, Any]) -> Optional[float]:
    value = _first_non_empty(
        record,
        [
            "actual_gain_s",
            "gain_s",
            "expected_gain_s",
            "time_gain_s",
            "delta_s",
            "time_delta_s",
            "actual_gain_ms",
            "gain_ms",
            "expected_gain_ms",
            "time_gain_ms",
            "delta_ms",
        ],
    )
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    ms_keys = {
        "actual_gain_ms",
        "gain_ms",
        "expected_gain_ms",
        "time_gain_ms",
        "delta_ms",
    }
    for key in ms_keys:
        if key in record and record.get(key) is not None:
            return numeric / 1000.0
    return numeric


def _normalize_row(record: Dict[str, Any], line_number: int) -> Dict[str, Any]:
    trace_id = _first_non_empty(record, ["trace_id", "session_id", "run_id", "id"], default=f"line-{line_number}")
    case_id = _first_non_empty(record, ["case_id", "file_id", "scenario_id", "id"], default=str(trace_id))
    rule_id = _first_non_empty(record, ["rule_id", "rule", "top1_rule_id"], default="UNKNOWN")
    risk_tier = _first_non_empty(record, ["risk_tier", "risk", "tier"], default="UNKNOWN")
    recommendation_text = _first_non_empty(
        record,
        ["recommendation_text", "recommendation", "action", "title", "detail", "did"],
        default=f"Investigate rule {rule_id}.",
    )
    evidence_summary = _first_non_empty(
        record,
        ["evidence_summary", "evidence", "causal_reason", "because", "detail"],
        default="",
    )
    reason = _first_non_empty(
        record,
        ["failure_reason", "fail_reason", "reason", "top1_failure_reason"],
        default="",
    )
    did = _first_non_empty(record, ["did", "top1_did"], default="")
    should = _first_non_empty(record, ["should", "top1_should"], default="")
    because = _first_non_empty(record, ["because", "top1_because"], default="")
    success_check = _first_non_empty(record, ["success_check", "top1_success_check"], default="")
    detail = _first_non_empty(record, ["detail", "top1_detail", "recommendation_text"], default="")
    operational_action = _first_non_empty(
        record,
        ["operational_action", "top1_operational_action", "should"],
        default="",
    )
    causal_reason = _first_non_empty(record, ["causal_reason", "top1_causal_reason", "because"], default="")
    corner_id = _first_non_empty(record, ["corner_id", "top1_corner_id"], default="")
    corner_label = _first_non_empty(record, ["corner_label", "top1_corner_label", "corner_id"], default="")
    phase = _first_non_empty(record, ["phase", "top1_phase"], default="")
    top1_pass = _extract_top1_pass(record)
    if top1_pass is True:
        normalized_reason = ""
    else:
        normalized_reason = str(reason or "unknown_failure")

    return {
        "trace_id": str(trace_id),
        "case_id": str(case_id),
        "line_number": line_number,
        "top1_pass": top1_pass,
        "failure_reason": normalized_reason,
        "rule_id": str(rule_id),
        "risk_tier": str(risk_tier),
        "recommendation_text": str(recommendation_text),
        "evidence_summary": str(evidence_summary),
        "detail": str(detail),
        "did": str(did),
        "should": str(should),
        "because": str(because),
        "success_check": str(success_check),
        "operational_action": str(operational_action),
        "causal_reason": str(causal_reason),
        "corner_id": str(corner_id),
        "corner_label": str(corner_label),
        "phase": str(phase),
        "gain_s": _extract_gain_s(record),
    }


def _percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * pct
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[int(index)]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _sorted_distribution(counts: Dict[str, int], key_name: str) -> List[Dict[str, Any]]:
    items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{key_name: key, "count": value} for key, value in items]


def _outlier_gain_list(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows_with_gain = [row for row in rows if row.get("gain_s") is not None]
    gains = [float(row["gain_s"]) for row in rows_with_gain]
    if len(gains) < 4:
        return []

    q1 = _percentile(gains, 0.25)
    q3 = _percentile(gains, 0.75)
    median = _percentile(gains, 0.5)
    if q1 is None or q3 is None or median is None:
        return []

    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = []
    for row in rows_with_gain:
        gain = float(row["gain_s"])
        if gain < lower or gain > upper:
            side = "low" if gain < lower else "high"
            outliers.append(
                {
                    "trace_id": row["trace_id"],
                    "line_number": row["line_number"],
                    "gain_s": gain,
                    "outlier_side": side,
                    "distance_from_median_s": abs(gain - median),
                }
            )

    outliers.sort(
        key=lambda item: (
            -item["distance_from_median_s"],
            item["line_number"],
            item["trace_id"],
        )
    )
    return outliers[:TOP_EXAMPLE_LIMIT]


def _worst_examples(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    failed = [row for row in rows if row.get("top1_pass") is False]
    failed.sort(
        key=lambda row: (
            float("inf") if row.get("gain_s") is None else float(row["gain_s"]),
            row["line_number"],
            row["trace_id"],
        )
    )
    return [
        {
            "trace_id": row["trace_id"],
            "line_number": row["line_number"],
            "failure_reason": row["failure_reason"],
            "rule_id": row["rule_id"],
            "risk_tier": row["risk_tier"],
            "gain_s": row["gain_s"],
        }
        for row in failed[:TOP_EXAMPLE_LIMIT]
    ]


def _gate(name: str, ok: bool, details: str) -> Dict[str, Any]:
    return {"gate": name, "status": "pass" if ok else "fail", "details": details}


def _present_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _coaching_text_blob(row: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(row.get("detail") or ""),
            str(row.get("did") or ""),
            str(row.get("should") or ""),
            str(row.get("because") or ""),
            str(row.get("success_check") or ""),
            str(row.get("operational_action") or ""),
            str(row.get("causal_reason") or ""),
        ]
    ).strip()


def _delta_present(row: Dict[str, Any]) -> bool:
    text = " ".join([str(row.get("detail") or ""), str(row.get("did") or "")]).strip()
    return bool(text) and bool(DELTA_PATTERN.search(text))


def _rationale_present(row: Dict[str, Any]) -> bool:
    because = str(row.get("because") or "").strip()
    return bool(because) and "because" in because.lower()


def _success_check_measurable(row: Dict[str, Any]) -> bool:
    success_check = str(row.get("success_check") or "").strip()
    return bool(success_check) and bool(MEASURABLE_CHECK_PATTERN.search(success_check))


def _unit_consistent(row: Dict[str, Any]) -> bool:
    text = _coaching_text_blob(row)
    return bool(text) and not bool(METRIC_LEAK_PATTERN.search(text))


def _corner_consistent(row: Dict[str, Any]) -> bool:
    corner = str(row.get("corner_id") or row.get("corner_label") or "").strip()
    if not corner or ":" in corner:
        return False
    return corner in _coaching_text_blob(row)


def _evaluate_coaching_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    checks = {
        "did_vs_should_fields_present": all(
            _present_text(row.get(field)) for field in ("did", "should", "because", "success_check")
        ),
        "did_vs_should_delta_present": _delta_present(row),
        "did_vs_should_rationale_present": _rationale_present(row),
        "did_vs_should_success_check_measurable": _success_check_measurable(row),
        "did_vs_should_unit_consistency": _unit_consistent(row),
        "did_vs_should_corner_consistency": _corner_consistent(row),
    }
    failed_checks = [name for name, ok in checks.items() if not ok]
    return {
        "checks": checks,
        "failed_checks": failed_checks,
        "status": "pass" if not failed_checks else "fail",
    }


def _coaching_gate_details(name: str, failing_rows: List[Dict[str, Any]], total_rows: int) -> str:
    if total_rows == 0:
        return "No valid rows parsed."
    if not failing_rows:
        return COACHING_GATE_LABELS[name]
    examples = ", ".join(str(row.get("trace_id")) for row in failing_rows[:3])
    return f"{len(failing_rows)} of {total_rows} rows failed. Examples: {examples}."


def _coerce_record(record: Dict[str, Any]) -> Dict[str, Any]:
    coerced = dict(record)
    status = str(record.get("status") or "").strip().lower()

    if "top1_pass" not in coerced and status:
        if status == "pass":
            coerced["top1_pass"] = True
        elif status in {"fail", "failed", "error", "not_ready", "blocked"}:
            coerced["top1_pass"] = False

    if not coerced.get("failure_reason"):
        reason = _first_non_empty(record, ["detail", "error", "failure_reason"], default="")
        if reason:
            coerced["failure_reason"] = reason

    if not coerced.get("rule_id") and record.get("top1_rule_id") is not None:
        coerced["rule_id"] = record.get("top1_rule_id")
    if not coerced.get("corner_id") and record.get("top1_corner_id") is not None:
        coerced["corner_id"] = record.get("top1_corner_id")
    if not coerced.get("corner_label") and record.get("top1_corner_label") is not None:
        coerced["corner_label"] = record.get("top1_corner_label")
    if not coerced.get("phase") and record.get("top1_phase") is not None:
        coerced["phase"] = record.get("top1_phase")
    if not coerced.get("risk_tier") and record.get("top1_risk_tier") is not None:
        coerced["risk_tier"] = record.get("top1_risk_tier")
    for field in (
        "detail",
        "did",
        "should",
        "because",
        "success_check",
        "operational_action",
        "causal_reason",
    ):
        prefixed = f"top1_{field}"
        if not coerced.get(field) and record.get(prefixed) is not None:
            coerced[field] = record.get(prefixed)
    if not coerced.get("trace_id"):
        if record.get("file_id"):
            coerced["trace_id"] = record.get("file_id")
        elif record.get("session_id") is not None and record.get("run_id") is not None:
            coerced["trace_id"] = f"session-{record.get('session_id')}-run-{record.get('run_id')}"
    if not coerced.get("case_id"):
        coerced["case_id"] = _first_non_empty(record, ["file_id", "trace_id"], default="")

    gain_trace = record.get("top1_gain_trace")
    if coerced.get("expected_gain_s") is None and isinstance(gain_trace, dict):
        value = gain_trace.get("final_expected_gain_s")
        if value is None:
            value = gain_trace.get("expected_gain_s")
        if value is not None:
            coerced["expected_gain_s"] = value

    return coerced


def _parse_records(records: List[Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    malformed_examples: List[Dict[str, Any]] = []
    malformed_count = 0
    total_lines = 0
    for line_number, payload in enumerate(records, start=1):
        total_lines += 1
        try:
            if not isinstance(payload, dict):
                raise ValueError("trace row is not a JSON object")
            rows.append(_normalize_row(_coerce_record(payload), line_number))
        except Exception as exc:
            malformed_count += 1
            if len(malformed_examples) < MALFORMED_EXAMPLE_LIMIT:
                malformed_examples.append(
                    {
                        "line_number": line_number,
                        "error": f"{type(exc).__name__}: {exc}",
                        "snippet": _safe_snippet(json.dumps(payload, sort_keys=True, ensure_ascii=False)),
                    }
                )
    return {
        "total_lines": total_lines,
        "rows": rows,
        "malformed_count": malformed_count,
        "malformed_examples": malformed_examples,
    }


def _parse_jsonl(path: Path) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    malformed_examples: List[Dict[str, Any]] = []
    malformed_count = 0
    total_lines = 0

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            total_lines += 1
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("trace line is not a JSON object")
                rows.append(_normalize_row(_coerce_record(payload), line_number))
            except Exception as exc:
                malformed_count += 1
                if len(malformed_examples) < MALFORMED_EXAMPLE_LIMIT:
                    malformed_examples.append(
                        {
                            "line_number": line_number,
                            "error": f"{type(exc).__name__}: {exc}",
                            "snippet": _safe_snippet(line),
                        }
                    )

    return {
        "total_lines": total_lines,
        "rows": rows,
        "malformed_count": malformed_count,
        "malformed_examples": malformed_examples,
    }


def _parse_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: List[Any]
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for key in ("entries", "rows", "top1_cases", "traces", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                records = value
                break
        else:
            records = []
    else:
        records = []
    return _parse_records(records)


def _resolve_input_path(input_path: Path) -> Path:
    if input_path.exists():
        return input_path

    requested = input_path.as_posix()
    default_requested = requested == DEFAULT_INPUT
    if default_requested:
        fallback_candidates = [Path(LEGACY_SCORECARD_INPUT_PATH), Path(LEGACY_BATCH_REPORT_PATH)]
        for candidate in fallback_candidates:
            if candidate.exists():
                return candidate
    return input_path


def _build_top1_cases(rows: List[Dict[str, Any]], outlier_gain_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    outlier_ids = {str(row.get("trace_id")) for row in outlier_gain_list}
    cases: List[Dict[str, Any]] = []
    for row in rows:
        top1_pass = row.get("top1_pass")
        status = "pass" if top1_pass is True else "fail" if top1_pass is False else "unknown"
        failure_reason = row.get("failure_reason") or ""
        coaching_gate_reasons = list(row.get("coaching_gate_reasons") or [])
        cases.append(
            {
                "case_id": row.get("case_id") or row.get("trace_id"),
                "trace_id": row.get("trace_id"),
                "status": status,
                "top1_pass": top1_pass,
                "failure_reason": failure_reason,
                "gate_reasons": ([] if top1_pass is True else [failure_reason]) + coaching_gate_reasons,
                "rule_id": row.get("rule_id"),
                "risk_tier": row.get("risk_tier"),
                "expected_gain_s": row.get("gain_s"),
                "outlier_score": 1.0 if str(row.get("trace_id")) in outlier_ids else 0.0,
                "recommendation_text": row.get("recommendation_text"),
                "evidence_summary": row.get("evidence_summary"),
                "coaching_quality_status": row.get("coaching_quality_status", "unknown"),
                "coaching_gate_reasons": coaching_gate_reasons,
            }
        )
    return cases


def _requirement_modes(*, hard_status: str) -> List[Dict[str, str]]:
    modes: List[Dict[str, str]] = []
    for requirement in AUTO_SCORED_REQUIREMENTS:
        modes.append(
            {
                "requirement_id": requirement,
                "evaluation_mode": "auto_scored",
                "status": hard_status,
            }
        )
    for requirement in HUMAN_REVIEWED_REQUIREMENTS:
        modes.append(
            {
                "requirement_id": requirement,
                "evaluation_mode": "human_reviewed",
                "status": "pending_review",
            }
        )
    return modes


def build_report(*, input_path: Path, report_path: Path) -> Dict[str, Any]:
    errors: List[str] = []
    rows: List[Dict[str, Any]] = []
    malformed_count = 0
    malformed_examples: List[Dict[str, Any]] = []
    total_lines = 0

    resolved_input_path = _resolve_input_path(input_path)
    input_exists = resolved_input_path.exists()
    if input_exists and resolved_input_path.as_posix() != input_path.as_posix():
        errors.append(
            f"input_fallback: requested={input_path.as_posix()} resolved={resolved_input_path.as_posix()}"
        )
    if input_exists:
        try:
            if resolved_input_path.suffix.lower() == ".jsonl":
                parsed = _parse_jsonl(resolved_input_path)
            else:
                parsed = _parse_json(resolved_input_path)
            rows = parsed["rows"]
            malformed_count = parsed["malformed_count"]
            malformed_examples = parsed["malformed_examples"]
            total_lines = parsed["total_lines"]
        except Exception as exc:
            errors.append(f"input_parse_error: {type(exc).__name__}: {exc}")
            malformed_count = 1
            malformed_examples = [
                {
                    "line_number": 1,
                    "error": f"{type(exc).__name__}: {exc}",
                    "snippet": resolved_input_path.as_posix(),
                }
            ]
    else:
        errors.append(f"input_missing: {input_path.as_posix()}")

    pass_count = len([row for row in rows if row.get("top1_pass") is True])
    fail_count = len([row for row in rows if row.get("top1_pass") is False])
    unknown_count = len(rows) - pass_count - fail_count

    reason_counts: Dict[str, int] = {}
    rule_counts: Dict[str, int] = {}
    risk_counts: Dict[str, int] = {}
    rule_risk_counts: Dict[str, int] = {}

    for row in rows:
        rule = row["rule_id"]
        risk = row["risk_tier"]
        rule_counts[rule] = rule_counts.get(rule, 0) + 1
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        combo = f"{rule}::{risk}"
        rule_risk_counts[combo] = rule_risk_counts.get(combo, 0) + 1
        if row.get("top1_pass") is False:
            reason = row.get("failure_reason") or "unknown_failure"
            reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1
        coaching_quality = _evaluate_coaching_quality(row)
        row["coaching_quality_status"] = coaching_quality["status"]
        row["coaching_gate_reasons"] = coaching_quality["failed_checks"]
        row["coaching_quality_checks"] = coaching_quality["checks"]

    gates = [
        _gate(
            "input_artifact_present",
            input_exists,
            "Input artifact is present." if input_exists else "Input artifact is missing.",
        ),
        _gate(
            "top1_scope_label",
            True,
            "Report is explicitly scoped to top-1 quality.",
        ),
        _gate(
            "trace_lines_well_formed",
            malformed_count == 0,
            "No malformed trace lines detected." if malformed_count == 0 else f"Malformed trace lines: {malformed_count}.",
        ),
        _gate(
            "valid_rows_present",
            len(rows) > 0,
            "At least one valid row parsed." if rows else "No valid rows parsed.",
        ),
    ]
    for gate_name in COACHING_GATE_LABELS:
        failing_rows = [row for row in rows if not row.get("coaching_quality_checks", {}).get(gate_name, False)]
        gates.append(
            _gate(
                gate_name,
                len(rows) > 0 and not failing_rows,
                _coaching_gate_details(gate_name, failing_rows, len(rows)),
            )
        )

    failed_gates = [gate for gate in gates if gate["status"] == "fail"]
    hard_status = "pass" if not failed_gates else "fail"
    outlier_gain_list = _outlier_gain_list(rows)
    top1_cases = _build_top1_cases(rows, outlier_gain_list)
    coaching_fail_examples = [
        {
            "trace_id": row["trace_id"],
            "line_number": row["line_number"],
            "failed_checks": row.get("coaching_gate_reasons", []),
        }
        for row in rows
        if row.get("coaching_quality_status") == "fail"
    ][:TOP_EXAMPLE_LIMIT]
    coaching_fail_count = len([row for row in rows if row.get("coaching_quality_status") == "fail"])

    report = {
        "schema_version": "1",
        "harness": "top1_quality_eval",
        "scope": "top1",
        "status": hard_status,
        "input_path": resolved_input_path.as_posix(),
        "report_path": report_path.as_posix(),
        "summary": {
            "total_lines": total_lines,
            "valid_rows": len(rows),
            "malformed_lines": malformed_count,
        },
        "requirements": {
            "auto_scored": AUTO_SCORED_REQUIREMENTS,
            "human_reviewed": HUMAN_REVIEWED_REQUIREMENTS,
            "evaluation_modes": _requirement_modes(hard_status=hard_status),
        },
        "hard_gates": {
            "status": hard_status,
            "failed_count": len(failed_gates),
            "checks": gates,
        },
        "soft_indicators": {
            "quality_status": "pass" if fail_count == 0 and coaching_fail_count == 0 and len(rows) > 0 else "fail",
            "top1_counts": {
                "pass": pass_count,
                "fail": fail_count,
                "unknown": unknown_count,
            },
            "coaching_quality_summary": {
                "pass": len(rows) - coaching_fail_count,
                "fail": coaching_fail_count,
            },
            "failure_reason_distribution": _sorted_distribution(reason_counts, "reason"),
            "rule_distribution": _sorted_distribution(rule_counts, "rule_id"),
            "risk_tier_distribution": _sorted_distribution(risk_counts, "risk_tier"),
            "rule_risk_distribution": _sorted_distribution(rule_risk_counts, "rule_risk"),
            "coaching_quality_fail_examples": coaching_fail_examples,
            "outlier_gain_list": outlier_gain_list,
            "worst_20_examples": _worst_examples(rows),
        },
        "top1_cases": top1_cases,
        "malformed_examples": malformed_examples,
        "errors": errors,
    }
    return _round(report)


def _resolve_exit_code(report: Dict[str, Any]) -> int:
    if report.get("hard_gates", {}).get("status") == "fail":
        return 2
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate top-1 decision traces and emit JSON scorecard.")
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help="Input trace artifact path (JSONL canonical; legacy JSON report also supported).",
    )
    parser.add_argument("--report-path", default=DEFAULT_REPORT, help="Output JSON report path.")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    report_path = Path(args.report_path)

    report = build_report(input_path=input_path, report_path=report_path)
    _write_json(report_path, report)
    print(json.dumps({"status": report["status"], "report_path": report["report_path"]}, sort_keys=True))
    return _resolve_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
