"""Top-1 quality evaluation harness with machine-readable JSON artifact.

Documented command:
  $env:PYTHONPATH='.'; python tools/eval_top1_scorecard.py
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_INPUT = "artifacts/top1_session_traces.jsonl"
DEFAULT_REPORT = "artifacts/eval_top1_quality_report.json"
ROUND_DIGITS = 4
MALFORMED_EXAMPLE_LIMIT = 20
TOP_EXAMPLE_LIMIT = 20


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
    rule_id = _first_non_empty(record, ["rule_id", "rule", "top1_rule_id"], default="UNKNOWN")
    risk_tier = _first_non_empty(record, ["risk_tier", "risk", "tier"], default="UNKNOWN")
    reason = _first_non_empty(
        record,
        ["failure_reason", "fail_reason", "reason", "top1_failure_reason"],
        default="",
    )
    top1_pass = _extract_top1_pass(record)
    if top1_pass is True:
        normalized_reason = ""
    else:
        normalized_reason = str(reason or "unknown_failure")

    return {
        "trace_id": str(trace_id),
        "line_number": line_number,
        "top1_pass": top1_pass,
        "failure_reason": normalized_reason,
        "rule_id": str(rule_id),
        "risk_tier": str(risk_tier),
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
                rows.append(_normalize_row(payload, line_number))
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


def build_report(*, input_path: Path, report_path: Path) -> Dict[str, Any]:
    errors: List[str] = []
    rows: List[Dict[str, Any]] = []
    malformed_count = 0
    malformed_examples: List[Dict[str, Any]] = []
    total_lines = 0

    input_exists = input_path.exists()
    if input_exists:
        parsed = _parse_jsonl(input_path)
        rows = parsed["rows"]
        malformed_count = parsed["malformed_count"]
        malformed_examples = parsed["malformed_examples"]
        total_lines = parsed["total_lines"]
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

    failed_gates = [gate for gate in gates if gate["status"] == "fail"]
    hard_status = "pass" if not failed_gates else "fail"

    report = {
        "schema_version": "1",
        "harness": "top1_quality_eval",
        "scope": "top1",
        "status": hard_status,
        "input_path": input_path.as_posix(),
        "report_path": report_path.as_posix(),
        "summary": {
            "total_lines": total_lines,
            "valid_rows": len(rows),
            "malformed_lines": malformed_count,
        },
        "hard_gates": {
            "status": hard_status,
            "failed_count": len(failed_gates),
            "checks": gates,
        },
        "soft_indicators": {
            "quality_status": "pass" if fail_count == 0 and len(rows) > 0 else "fail",
            "top1_counts": {
                "pass": pass_count,
                "fail": fail_count,
                "unknown": unknown_count,
            },
            "failure_reason_distribution": _sorted_distribution(reason_counts, "reason"),
            "rule_distribution": _sorted_distribution(rule_counts, "rule_id"),
            "risk_tier_distribution": _sorted_distribution(risk_counts, "risk_tier"),
            "rule_risk_distribution": _sorted_distribution(rule_risk_counts, "rule_risk"),
            "outlier_gain_list": _outlier_gain_list(rows),
            "worst_20_examples": _worst_examples(rows),
        },
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
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Input JSONL trace artifact path.")
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
