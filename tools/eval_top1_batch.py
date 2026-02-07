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


REPORT_DEFAULT = "artifacts/eval_top1_batch_report.json"
ROOT_DEFAULT = "test_data"

_TOP1_REQUIRED_FIELDS = ("rule_id", "corner_id", "phase", "risk_tier")
_BLOCKING_GATE_DECISIONS = {"blocked", "fail", "failed", "reject", "rejected", "deny", "denied"}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


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
    }


def _build_report(
    *,
    root: str,
    report_path: str,
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run top-1 batch evaluation across CSV files and emit a JSON artifact."
    )
    parser.add_argument("--root", default=ROOT_DEFAULT, help="Directory to recursively scan for CSV files.")
    parser.add_argument("--report-path", default=REPORT_DEFAULT, help="JSON artifact output path.")
    args = parser.parse_args()

    root = Path(args.root)
    report_path = Path(args.report_path)
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
        rows=rows,
        harness_errors=harness_errors,
        hard_failures=hard_failures,
    )
    _write_json(report_path, report)
    print(json.dumps({"status": report["status"], "report_path": report["report_path"]}, sort_keys=True))
    return _resolve_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
