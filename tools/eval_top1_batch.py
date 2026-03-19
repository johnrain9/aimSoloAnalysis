"""Batch top-1 evaluation harness for import -> insights flows.

Documented command:
  $env:PYTHONPATH='.'; python tools/eval_top1_batch.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.trackside.pipeline import generate_trackside_insights
from ingest.csv.parser import parse_csv
from ingest.csv.save import save_to_db
from tools.top1_artifact_contract import (
    DEFAULT_TOP1_TRACE_PATH,
    LEGACY_BATCH_REPORT_PATH,
)


REPORT_DEFAULT = LEGACY_BATCH_REPORT_PATH.as_posix()
TRACE_DEFAULT = DEFAULT_TOP1_TRACE_PATH.as_posix()
ROOT_DEFAULT = "test_data"

_TOP1_REQUIRED_FIELDS = ("rule_id", "corner_id", "phase", "risk_tier")
_BLOCKING_GATE_DECISIONS = {"blocked", "fail", "failed", "reject", "rejected", "deny", "denied"}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True))
            handle.write("\n")


def _normalize_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _discover_csv_files(root: Path) -> List[Path]:
    files = [path for path in root.rglob("*.csv") if path.is_file()]
    files.sort(key=lambda item: _normalize_path(item).lower())
    return files


def _extract_gate_decision(top1: Dict[str, Any]) -> Optional[str]:
    raw = top1.get("gate_decision")
    if raw is None:
        evidence = top1.get("evidence")
        if isinstance(evidence, dict):
            raw = evidence.get("gate_decision")
    if raw is None:
        return None
    return str(raw)


def _extract_gain_trace(top1: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    direct = top1.get("gain_trace")
    if isinstance(direct, dict):
        return direct
    evidence = top1.get("evidence")
    if isinstance(evidence, dict) and isinstance(evidence.get("gain_trace"), dict):
        return evidence.get("gain_trace")
    return None


def _classify_top1(top1: Dict[str, Any], gate_decision: Optional[str]) -> Tuple[str, Optional[str]]:
    missing = [name for name in _TOP1_REQUIRED_FIELDS if not top1.get(name)]
    if missing:
        return "fail", f"top1 missing required fields: {', '.join(missing)}"

    if str(top1.get("risk_tier")) == "Blocked":
        return "fail", "top1 risk tier blocked"

    if gate_decision:
        normalized = gate_decision.strip().lower()
        if normalized in _BLOCKING_GATE_DECISIONS:
            return "fail", f"top1 gate decision {normalized}"

    return "pass", None


def _entry_not_ready(
    *,
    file_id: str,
    file_path: str,
    session_id: Optional[int],
    run_id: Optional[int],
    reason: str,
) -> Dict[str, Any]:
    return {
        "file_id": file_id,
        "file_path": file_path,
        "session_id": session_id,
        "run_id": run_id,
        "status": "not_ready",
        "detail": reason,
        "error": None,
        "top1_only": True,
        "insight_count": 0,
        "top1_rule_id": None,
        "top1_corner_id": None,
        "top1_phase": None,
        "top1_risk_tier": None,
        "top1_gate_decision": None,
        "top1_gain_trace": None,
        "top1_detail": None,
        "top1_did": None,
        "top1_should": None,
        "top1_because": None,
        "top1_success_check": None,
        "top1_operational_action": None,
        "top1_causal_reason": None,
        "top1_corner_label": None,
    }


def _entry_error(
    *,
    file_id: str,
    file_path: str,
    session_id: Optional[int],
    run_id: Optional[int],
    error: str,
) -> Dict[str, Any]:
    return {
        "file_id": file_id,
        "file_path": file_path,
        "session_id": session_id,
        "run_id": run_id,
        "status": "error",
        "detail": None,
        "error": error,
        "top1_only": True,
        "insight_count": 0,
        "top1_rule_id": None,
        "top1_corner_id": None,
        "top1_phase": None,
        "top1_risk_tier": None,
        "top1_gate_decision": None,
        "top1_gain_trace": None,
        "top1_detail": None,
        "top1_did": None,
        "top1_should": None,
        "top1_because": None,
        "top1_success_check": None,
        "top1_operational_action": None,
        "top1_causal_reason": None,
        "top1_corner_label": None,
    }


def _entry_from_insights(
    *,
    file_id: str,
    file_path: str,
    session_id: int,
    run_id: int,
    insights: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not insights:
        return _entry_not_ready(
            file_id=file_id,
            file_path=file_path,
            session_id=session_id,
            run_id=run_id,
            reason="insights pipeline not ready",
        )

    top1 = dict(insights[0])
    gate_decision = _extract_gate_decision(top1)
    gain_trace = _extract_gain_trace(top1)
    status, detail = _classify_top1(top1, gate_decision)
    return {
        "file_id": file_id,
        "file_path": file_path,
        "session_id": session_id,
        "run_id": run_id,
        "status": status,
        "detail": detail,
        "error": None,
        "top1_only": True,
        "insight_count": len(insights),
        "top1_rule_id": top1.get("rule_id"),
        "top1_corner_id": top1.get("corner_id"),
        "top1_phase": top1.get("phase"),
        "top1_risk_tier": top1.get("risk_tier"),
        "top1_gate_decision": gate_decision,
        "top1_gain_trace": gain_trace,
        "top1_detail": top1.get("detail"),
        "top1_did": top1.get("did"),
        "top1_should": top1.get("should"),
        "top1_because": top1.get("because"),
        "top1_success_check": top1.get("success_check"),
        "top1_operational_action": top1.get("operational_action"),
        "top1_causal_reason": top1.get("causal_reason"),
        "top1_corner_label": top1.get("corner_label"),
    }


def _build_report(
    *,
    root: str,
    report_path: str,
    trace_path: str,
    rows: Sequence[Dict[str, Any]],
    harness_errors: Sequence[str],
    hard_failures: int,
) -> Dict[str, Any]:
    pass_count = sum(1 for row in rows if row.get("status") == "pass")
    fail_count = sum(1 for row in rows if row.get("status") == "fail")
    not_ready_count = sum(1 for row in rows if row.get("status") == "not_ready")
    error_count = sum(1 for row in rows if row.get("status") == "error")

    return {
        "schema_version": "1",
        "harness": "eval_top1_batch",
        "status": "pass" if hard_failures == 0 else "fail",
        "root": root,
        "report_path": report_path,
        "trace_path": trace_path,
        "top1_only": True,
        "hard_checks": {
            "harness_status": "pass" if hard_failures == 0 else "fail",
            "hard_failures": hard_failures,
        },
        "soft_indicators": {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "not_ready_count": not_ready_count,
            "error_count": error_count,
        },
        "entries": list(rows),
        "errors": list(harness_errors),
    }


def _resolve_exit_code(report: Dict[str, Any]) -> int:
    hard_failures = int(report.get("hard_checks", {}).get("hard_failures", 0))
    if hard_failures > 0:
        return 2
    return 0


def _extract_expected_gain_s(gain_trace: Any) -> Optional[float]:
    if not isinstance(gain_trace, dict):
        return None
    candidate = gain_trace.get("final_expected_gain_s")
    if candidate is None:
        candidate = gain_trace.get("expected_gain_s")
    try:
        if candidate is None:
            return None
        return float(candidate)
    except (TypeError, ValueError):
        return None


def _trace_id_for_entry(entry: Dict[str, Any]) -> str:
    session_id = entry.get("session_id")
    run_id = entry.get("run_id")
    file_id = entry.get("file_id")
    if session_id is not None and run_id is not None:
        return f"session-{session_id}-run-{run_id}"
    if file_id:
        return str(file_id)
    return "unknown-trace"


def _trace_row_from_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    status = str(entry.get("status") or "").lower()
    top1_pass = True if status == "pass" else False if status in {"fail", "not_ready", "error"} else None
    failure_reason = ""
    if top1_pass is not True:
        failure_reason = str(entry.get("detail") or entry.get("error") or status or "unknown_failure")

    gain_trace = entry.get("top1_gain_trace")
    return {
        "trace_id": _trace_id_for_entry(entry),
        "case_id": entry.get("file_id") or _trace_id_for_entry(entry),
        "file_id": entry.get("file_id"),
        "file_path": entry.get("file_path"),
        "session_id": entry.get("session_id"),
        "run_id": entry.get("run_id"),
        "status": status or "unknown",
        "top1_pass": top1_pass,
        "failure_reason": failure_reason,
        "rule_id": entry.get("top1_rule_id"),
        "corner_id": entry.get("top1_corner_id"),
        "phase": entry.get("top1_phase"),
        "risk_tier": entry.get("top1_risk_tier"),
        "gate_decision": entry.get("top1_gate_decision"),
        "gain_trace": gain_trace,
        "expected_gain_s": _extract_expected_gain_s(gain_trace),
        "recommendation_text": entry.get("top1_detail"),
        "evidence_summary": entry.get("top1_causal_reason"),
        "detail": entry.get("top1_detail"),
        "did": entry.get("top1_did"),
        "should": entry.get("top1_should"),
        "because": entry.get("top1_because"),
        "success_check": entry.get("top1_success_check"),
        "operational_action": entry.get("top1_operational_action"),
        "causal_reason": entry.get("top1_causal_reason"),
        "corner_label": entry.get("top1_corner_label"),
    }


def _build_trace_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_trace_row_from_entry(row) for row in rows]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run top-1 batch evaluation across CSV files and emit a JSON artifact."
    )
    parser.add_argument("--root", default=ROOT_DEFAULT, help="Directory to recursively scan for CSV files.")
    parser.add_argument(
        "--report-path",
        default=REPORT_DEFAULT,
        help="JSON summary output path (legacy-compatible).",
    )
    parser.add_argument(
        "--trace-path",
        default=TRACE_DEFAULT,
        help="JSONL trace output path for scorecard/review-packet default chain.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    report_path = Path(args.report_path)
    trace_path = Path(args.trace_path)
    rows: List[Dict[str, Any]] = []
    harness_errors: List[str] = []
    hard_failures = 0

    try:
        if not root.exists():
            raise FileNotFoundError(f"scan root does not exist: {_normalize_path(root)}")

        csv_files = _discover_csv_files(root)
        with tempfile.TemporaryDirectory(prefix="eval_top1_batch_") as temp_dir:
            db_path = os.path.join(temp_dir, "eval_top1_batch.db")
            for idx, csv_path in enumerate(csv_files, start=1):
                file_path = _normalize_path(csv_path)
                file_id = str(csv_path.relative_to(root).as_posix())

                try:
                    parsed = parse_csv(str(csv_path))
                    persisted = save_to_db(
                        parsed,
                        db_path,
                        source_file=str(csv_path),
                        run_index=idx,
                    )
                except Exception as exc:  # noqa: BLE001
                    rows.append(
                        _entry_error(
                            file_id=file_id,
                            file_path=file_path,
                            session_id=None,
                            run_id=None,
                            error=f"import_error: {type(exc).__name__}: {exc}",
                        )
                    )
                    continue

                try:
                    insights = generate_trackside_insights(db_path, int(persisted.session_id))
                except Exception as exc:  # noqa: BLE001
                    rows.append(
                        _entry_error(
                            file_id=file_id,
                            file_path=file_path,
                            session_id=int(persisted.session_id),
                            run_id=int(persisted.run_id),
                            error=f"insights_error: {type(exc).__name__}: {exc}",
                        )
                    )
                    continue

                rows.append(
                    _entry_from_insights(
                        file_id=file_id,
                        file_path=file_path,
                        session_id=int(persisted.session_id),
                        run_id=int(persisted.run_id),
                        insights=insights,
                    )
                )
    except Exception as exc:  # noqa: BLE001
        hard_failures += 1
        harness_errors.append(f"harness_error: {type(exc).__name__}: {exc}")

    report = _build_report(
        root=_normalize_path(root),
        report_path=_normalize_path(report_path),
        trace_path=_normalize_path(trace_path),
        rows=rows,
        harness_errors=harness_errors,
        hard_failures=hard_failures,
    )
    trace_rows = _build_trace_rows(rows)
    _write_json(report_path, report)
    _write_jsonl(trace_path, trace_rows)
    print(
        json.dumps(
            {"status": report["status"], "report_path": report["report_path"], "trace_path": report["trace_path"]},
            sort_keys=True,
        )
    )
    return _resolve_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
