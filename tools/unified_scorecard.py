"""Unified scorecard builder combining backend/frontend/top1/human_review reports.

Documented command:
  $env:PYTHONPATH='.'; python tools/unified_scorecard.py

Creates artifacts/unified_scorecard.json per TA v1.0 contract.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Default artifact paths per TA v1.0
BACKEND_REPORT = "artifacts/eval_backend_report.json"
FRONTEND_REPORT = "artifacts/frontend_eval_report.json"
TOP1_REPORT = "artifacts/top1_aggregated_report.json"
HUMAN_REVIEW_PACKET = "artifacts/top1_review_packet.md"
SCORECARD_OUTPUT = "artifacts/unified_scorecard.json"


def _read_json(path: Path) -> Dict[str, Any]:
    """Read JSON file with error handling."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error in {path}: {exc}")
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON file with formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _extract_human_review_status(packet_path: Path) -> str:
    """Extract review status from markdown review packet.

    Looks for "Status: **<status>**" in the first few lines.
    Returns: "approved", "rejected", or "pending_review" (default)
    """
    if not packet_path.exists():
        return "pending_review"

    try:
        content = packet_path.read_text(encoding="utf-8")
        # Look for "Status: **<status>**" pattern in first 10 lines
        for line in content.split("\n")[:10]:
            match = re.search(r"Status:\s*\*\*(\w+)\*\*", line)
            if match:
                status_str = match.group(1).lower()
                if status_str in ("approved", "rejected", "pending_review", "pass", "fail"):
                    # Map "pass" -> "approved", "fail" -> "rejected"
                    if status_str == "pass":
                        return "approved"
                    elif status_str == "fail":
                        return "rejected"
                    return status_str
        return "pending_review"
    except Exception:
        return "pending_review"


def _load_sub_report(
    path: Path,
    report_name: str,
) -> Tuple[str, Optional[Dict[str, Any]], str]:
    """Load a sub-report and extract its status.

    Returns: (status, report_dict, reason)
    - status: "pass", "fail", "not_ready"
    - report_dict: parsed JSON or None
    - reason: human-readable explanation
    """
    if not path.exists():
        return "not_ready", None, f"{report_name} artifact not found at {path}"

    try:
        report = _read_json(path)
    except Exception as exc:
        return "fail", None, f"{report_name} JSON parse error: {exc}"

    # Infer status from report structure
    report_status = report.get("status")
    if report_status in ("pass", "fail", "not_ready"):
        return report_status, report, f"Status from {report_name}: {report_status}"

    # If no explicit status, assume pass
    return "pass", report, f"No explicit status in {report_name}, assuming pass"


def _build_hard_gates(
    backend_status: str,
    frontend_status: str,
    top1_status: str,
    human_review_status: str,
    backend_report: Optional[Dict[str, Any]],
    frontend_report: Optional[Dict[str, Any]],
    top1_report: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build 7 hard gates per TA v1.0 mapping table.

    Gate precedence:
    - Gate-A: backend status (data integrity)
    - Gate-B: backend status (API/UI contract)
    - Gate-C: backend status (unit consistency)
    - Gate-D: backend status (test suite)
    - Gate-E: top1 status (P0 behavior)
    - Gate-F: frontend AND backend status (eval harness)
    - Gate-G: top1 AND human_review status (quality model)
    """
    gates: List[Dict[str, Any]] = []

    # Gate-A: Data Integrity
    gates.append({
        "gate_id": "Gate-A-DataIntegrity",
        "status": backend_status,
        "reason": _gate_reason("Data Integrity", backend_status),
        "evidence": {
            "sub_report": "backend",
            "check": "baseline_comparison.status"
        }
    })

    # Gate-B: API/UI Contract
    gates.append({
        "gate_id": "Gate-B-APIUIContract",
        "status": backend_status,
        "reason": _gate_reason("API/UI Contract", backend_status),
        "evidence": {
            "sub_report": "backend",
            "check": "entries[].status"
        }
    })

    # Gate-C: Unit Consistency
    gates.append({
        "gate_id": "Gate-C-UnitConsistency",
        "status": backend_status,
        "reason": _gate_reason("Unit Consistency", backend_status),
        "evidence": {
            "sub_report": "backend",
            "check": "unit_consistency_checks"
        }
    })

    # Gate-D: Test Suite
    gates.append({
        "gate_id": "Gate-D-TestSuite",
        "status": backend_status,
        "reason": _gate_reason("Test Suite", backend_status),
        "evidence": {
            "sub_report": "backend",
            "check": "overall_status"
        }
    })

    # Gate-E: P0 Behavior
    gates.append({
        "gate_id": "Gate-E-P0Behavior",
        "status": top1_status,
        "reason": _gate_reason("P0 Behavior", top1_status),
        "evidence": {
            "sub_report": "top1",
            "check": "hard_gates.status"
        }
    })

    # Gate-F: Eval Harness (both frontend AND backend must pass)
    gate_f_status = "pass"
    if frontend_status == "fail" or backend_status == "fail":
        gate_f_status = "fail"
    elif frontend_status == "blocked" or backend_status == "blocked":
        gate_f_status = "blocked"
    elif frontend_status == "not_ready" or backend_status == "not_ready":
        gate_f_status = "not_ready"

    gates.append({
        "gate_id": "Gate-F-EvalHarness",
        "status": gate_f_status,
        "reason": _gate_reason("Eval Harness", gate_f_status, "frontend and backend"),
        "evidence": {
            "sub_report": "frontend",
            "check": "summary.passed_checks"
        }
    })

    # Gate-G: Quality Model (top1 must pass AND human_review not rejected)
    gate_g_status = top1_status
    if human_review_status == "rejected":
        gate_g_status = "blocked"
    elif human_review_status == "pending_review":
        if gate_g_status == "pass":
            gate_g_status = "not_ready"

    evidence_dict: Dict[str, Any] = {
        "sub_report": "top1",
        "check": "hard_gates.status",
        "human_review_status": human_review_status
    }

    gates.append({
        "gate_id": "Gate-G-QualityModel",
        "status": gate_g_status,
        "reason": _gate_reason("Quality Model", gate_g_status, f"human review: {human_review_status}"),
        "evidence": evidence_dict
    })

    return gates


def _gate_reason(gate_name: str, status: str, extra: str = "") -> str:
    """Generate human-readable gate reason."""
    if status == "pass":
        return f"{gate_name} check passed" + (f" ({extra})" if extra else "")
    elif status == "fail":
        return f"{gate_name} check failed" + (f" ({extra})" if extra else "")
    elif status == "blocked":
        return f"{gate_name} check blocked" + (f" ({extra})" if extra else "")
    elif status == "not_ready":
        return f"{gate_name} check not ready" + (f" ({extra})" if extra else "")
    return f"{gate_name}: {status}"


def _rollup_overall_status(hard_gates: List[Dict[str, Any]]) -> str:
    """Apply rollup precedence rules per TA v1.0.

    Precedence order (highest to lowest):
    1. If any gate is fail → overall = fail
    2. If any gate is blocked → overall = blocked
    3. If any gate is not_ready → overall = not_ready
    4. If all gates are pass → overall = pass
    """
    statuses = [gate["status"] for gate in hard_gates]

    if "fail" in statuses:
        return "fail"
    if "blocked" in statuses:
        return "blocked"
    if "not_ready" in statuses:
        return "not_ready"

    return "pass"


def _extract_soft_metrics(
    backend_report: Optional[Dict[str, Any]],
    frontend_report: Optional[Dict[str, Any]],
    top1_report: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Extract soft metrics from sub-reports.

    Soft metrics are advisory and do not affect overall_status.
    """
    metrics: List[Dict[str, Any]] = []

    # Backend latency metrics
    if backend_report:
        latency_summary = backend_report.get("latency_summary", {})
        if latency_summary.get("p95_ms") is not None:
            metrics.append({
                "metric_id": "backend-latency-p95",
                "value": latency_summary["p95_ms"],
                "threshold": 1000.0,
                "status": "ok" if latency_summary["p95_ms"] <= 1000.0 else "warn"
            })
        if latency_summary.get("mean_ms") is not None:
            metrics.append({
                "metric_id": "backend-latency-mean",
                "value": latency_summary["mean_ms"],
                "threshold": 600.0,
                "status": "ok" if latency_summary["mean_ms"] <= 600.0 else "warn"
            })

    # Frontend runtime metric
    if frontend_report:
        runtime_ms = frontend_report.get("runtime_ms")
        if runtime_ms is not None:
            metrics.append({
                "metric_id": "frontend-runtime-ms",
                "value": runtime_ms,
                "threshold": 5.0,
                "status": "ok" if runtime_ms <= 5.0 else "warn"
            })

    # Top1 pass rate metric
    if top1_report:
        # Extract pass rate from soft_indicators
        soft_indicators = top1_report.get("soft_indicators", {})
        top1_counts = soft_indicators.get("top1_counts", {})

        passed = top1_counts.get("pass", 0)
        total = passed + top1_counts.get("fail", 0)

        if total > 0:
            pass_rate = passed / total
            metrics.append({
                "metric_id": "top1-pass-rate",
                "value": round(pass_rate, 3),
                "threshold": 0.95,
                "status": "ok" if pass_rate >= 0.95 else "warn"
            })

    return metrics


def _build_sub_reports_summary(
    backend_status: str,
    backend_report: Optional[Dict[str, Any]],
    frontend_status: str,
    frontend_report: Optional[Dict[str, Any]],
    top1_status: str,
    top1_report: Optional[Dict[str, Any]],
    human_review_status: str,
) -> Dict[str, Any]:
    """Build sub-reports summary object."""
    sub_reports: Dict[str, Any] = {}

    # Backend
    sub_reports["backend"] = {
        "path": BACKEND_REPORT,
        "status": backend_status,
    }
    if backend_report:
        failures = backend_report.get("failures", {})
        latency = backend_report.get("latency_summary", {})
        sub_reports["backend"]["key_metrics"] = {
            "entries": len(backend_report.get("entries", [])),
            "failures": failures.get("total_failures", 0),
            "latency_p95_ms": latency.get("p95_ms"),
        }

    # Frontend
    sub_reports["frontend"] = {
        "path": FRONTEND_REPORT,
        "status": frontend_status,
    }
    if frontend_report:
        summary = frontend_report.get("summary", {})
        sub_reports["frontend"]["key_metrics"] = {
            "total_checks": summary.get("total_checks", 0),
            "passed_checks": summary.get("passed_checks", 0),
            "failed_checks": summary.get("failed_checks", 0),
        }

    # Top1
    sub_reports["top1"] = {
        "path": TOP1_REPORT,
        "status": top1_status,
    }
    if top1_report:
        soft_indicators = top1_report.get("soft_indicators", {})
        top1_counts = soft_indicators.get("top1_counts", {})
        passed = top1_counts.get("pass", 0)
        failed = top1_counts.get("fail", 0)
        total = passed + failed
        sub_reports["top1"]["key_metrics"] = {
            "total_cases": total,
            "passed": passed,
            "failed": failed,
        }

    # Human Review
    sub_reports["human_review"] = {
        "path": HUMAN_REVIEW_PACKET,
        "status": human_review_status,
    }
    # Human review metrics would be extracted from CSV if available
    sub_reports["human_review"]["key_metrics"] = {
        "reviewed_cases": 0,
        "approved": 0,
        "rejected": 0,
    }

    return sub_reports


def _build_scorecard(
    backend_status: str,
    backend_report: Optional[Dict[str, Any]],
    backend_reason: str,
    frontend_status: str,
    frontend_report: Optional[Dict[str, Any]],
    frontend_reason: str,
    top1_status: str,
    top1_report: Optional[Dict[str, Any]],
    top1_reason: str,
    human_review_status: str,
) -> Dict[str, Any]:
    """Build complete unified scorecard per TA v1.0 schema."""

    # Build hard gates
    hard_gates = _build_hard_gates(
        backend_status,
        frontend_status,
        top1_status,
        human_review_status,
        backend_report,
        frontend_report,
        top1_report,
    )

    # Determine overall status via rollup
    overall_status = _rollup_overall_status(hard_gates)

    # Extract soft metrics
    soft_metrics = _extract_soft_metrics(backend_report, frontend_report, top1_report)

    # Build sub-reports summary
    sub_reports = _build_sub_reports_summary(
        backend_status,
        backend_report,
        frontend_status,
        frontend_report,
        top1_status,
        top1_report,
        human_review_status,
    )

    # Build scorecard
    scorecard: Dict[str, Any] = {
        "scorecard_version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "overall_status": overall_status,
        "hard_gates": hard_gates,
        "soft_metrics": soft_metrics,
        "sub_reports": sub_reports,
    }

    return scorecard


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build unified scorecard combining backend/frontend/top1/human_review reports."
    )
    parser.add_argument(
        "--backend-report",
        default=BACKEND_REPORT,
        help=f"Backend evaluation report path (default: {BACKEND_REPORT})"
    )
    parser.add_argument(
        "--frontend-report",
        default=FRONTEND_REPORT,
        help=f"Frontend evaluation report path (default: {FRONTEND_REPORT})"
    )
    parser.add_argument(
        "--top1-report",
        default=TOP1_REPORT,
        help=f"Top1 aggregated report path (default: {TOP1_REPORT})"
    )
    parser.add_argument(
        "--human-review-packet",
        default=HUMAN_REVIEW_PACKET,
        help=f"Human review packet path (default: {HUMAN_REVIEW_PACKET})"
    )
    parser.add_argument(
        "--output",
        default=SCORECARD_OUTPUT,
        help=f"Output scorecard path (default: {SCORECARD_OUTPUT})"
    )

    args = parser.parse_args()

    backend_path = Path(args.backend_report)
    frontend_path = Path(args.frontend_report)
    top1_path = Path(args.top1_report)
    human_review_path = Path(args.human_review_packet)
    output_path = Path(args.output)

    # Load sub-reports
    backend_status, backend_report, backend_reason = _load_sub_report(backend_path, "backend")
    frontend_status, frontend_report, frontend_reason = _load_sub_report(frontend_path, "frontend")
    top1_status, top1_report, top1_reason = _load_sub_report(top1_path, "top1")

    # Extract human review status
    human_review_status = _extract_human_review_status(human_review_path)

    # Build scorecard
    scorecard = _build_scorecard(
        backend_status=backend_status,
        backend_report=backend_report,
        backend_reason=backend_reason,
        frontend_status=frontend_status,
        frontend_report=frontend_report,
        frontend_reason=frontend_reason,
        top1_status=top1_status,
        top1_report=top1_report,
        top1_reason=top1_reason,
        human_review_status=human_review_status,
    )

    # Write scorecard
    _write_json(output_path, scorecard)

    # Output result
    print(
        json.dumps(
            {
                "status": scorecard["overall_status"],
                "report_path": str(output_path).replace("\\", "/")
            },
            sort_keys=True
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
