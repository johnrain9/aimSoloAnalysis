"""Backend evaluation harness with machine-readable JSON artifact.

Documented command:
  $env:PYTHONPATH='.'; python tools/eval_backend.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage import db as db_mod
from tools import eval_trends as trend_eval


MANIFEST_DEFAULT = trend_eval.MANIFEST_DEFAULT
BASELINE_DEFAULT = trend_eval.BASELINE_DEFAULT
REPORT_DEFAULT = "artifacts/eval_backend_report.json"
ROUND_DIGITS = trend_eval.ROUND_DIGITS


def _round(value: Any) -> Any:
    return trend_eval._round(value)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _percentile(values: List[float], pct: float) -> Optional[float]:
    return trend_eval._percentile(values, pct)


def _summarize_latency(latency_ms: List[float]) -> Dict[str, Any]:
    if not latency_ms:
        return {
            "entry_count": 0,
            "total_ms": 0.0,
            "mean_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
    total = sum(latency_ms)
    return {
        "entry_count": len(latency_ms),
        "total_ms": total,
        "mean_ms": total / len(latency_ms),
        "p50_ms": _percentile(latency_ms, 0.5),
        "p95_ms": _percentile(latency_ms, 0.95),
        "max_ms": max(latency_ms),
    }


def _compare_with_baseline(
    entries: List[Dict[str, Any]],
    baseline_path: Path,
    *,
    update_baseline: bool,
    manifest: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    payload = {
        "manifest": manifest,
        "config": asdict(trend_eval.TREND_FILTERS),
        "entries": entries,
    }
    payload = _round(payload)
    if update_baseline or not baseline_path.exists():
        _write_json(baseline_path, payload)
        return {"status": "updated", "mismatch_count": 0, "errors": []}, payload

    baseline = _round(_read_json(baseline_path))
    errors: List[str] = []
    baseline_entries = {entry["id"]: entry for entry in baseline.get("entries", [])}
    for entry in payload["entries"]:
        baseline_entry = baseline_entries.get(entry["id"])
        if baseline_entry is None:
            errors.append(f"{entry['id']}: missing from baseline.")
            continue
        errors.extend(trend_eval._compare_entries(entry, baseline_entry))

    status = "pass" if not errors else "fail"
    return {"status": status, "mismatch_count": len(errors), "errors": errors}, payload


def _resolve_exit_code(report: Dict[str, Any]) -> int:
    failures = report.get("failures", {})
    hard_failures = int(failures.get("hard_failures", 0))
    baseline_status = str(report.get("baseline_comparison", {}).get("status", ""))
    if hard_failures > 0:
        return 2
    if baseline_status == "fail":
        return 1
    return 0


def _build_report(
    *,
    manifest: str,
    baseline: str,
    report_path: str,
    entry_results: List[Dict[str, Any]],
    latency_ms: List[float],
    baseline_comparison: Dict[str, Any],
    hard_failures: int,
    evaluation_errors: List[str],
) -> Dict[str, Any]:
    report = {
        "schema_version": "1",
        "harness": "backend_eval",
        "status": "pass",
        "manifest": manifest,
        "baseline": baseline,
        "report_path": report_path,
        "entries": entry_results,
        "baseline_comparison": baseline_comparison,
        "latency_summary": _summarize_latency(latency_ms),
        "failures": {
            "hard_failures": hard_failures,
            "entry_failures": len([e for e in entry_results if e.get("status") == "error"]),
            "baseline_mismatches": int(baseline_comparison.get("mismatch_count", 0)),
            "total_failures": hard_failures + int(baseline_comparison.get("mismatch_count", 0)),
        },
        "errors": evaluation_errors + list(baseline_comparison.get("errors", [])),
    }
    if report["failures"]["hard_failures"] > 0 or report["baseline_comparison"]["status"] == "fail":
        report["status"] = "fail"
    return _round(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backend evaluation and emit JSON artifact.")
    parser.add_argument("--manifest", default=MANIFEST_DEFAULT)
    parser.add_argument("--baseline", default=BASELINE_DEFAULT)
    parser.add_argument("--report-path", default=REPORT_DEFAULT)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    baseline_path = Path(args.baseline)
    report_path = Path(args.report_path)

    hard_failures = 0
    evaluation_errors: List[str] = []
    entry_results: List[Dict[str, Any]] = []
    latency_ms: List[float] = []
    baseline_comparison: Dict[str, Any] = {"status": "fail", "mismatch_count": 0, "errors": []}

    try:
        entries = trend_eval._load_manifest(manifest_path)
    except Exception as exc:
        hard_failures += 1
        evaluation_errors.append(f"manifest_error: {exc}")
        report = _build_report(
            manifest=str(manifest_path).replace("\\", "/"),
            baseline=str(baseline_path).replace("\\", "/"),
            report_path=str(report_path).replace("\\", "/"),
            entry_results=entry_results,
            latency_ms=latency_ms,
            baseline_comparison=baseline_comparison,
            hard_failures=hard_failures,
            evaluation_errors=evaluation_errors,
        )
        _write_json(report_path, report)
        print(json.dumps({"status": report["status"], "report_path": report["report_path"]}, sort_keys=True))
        return _resolve_exit_code(report)

    db_path = ""
    session_map: Dict[str, Dict[str, int]] = {}
    temp_dir: Optional[tempfile.TemporaryDirectory] = None
    try:
        db_path, session_map, temp_dir = trend_eval._build_db(entries)
        conn = db_mod.connect(db_path)
        try:
            with conn:
                for entry in entries:
                    start = time.perf_counter()
                    eval_status = "pass"
                    error = None
                    payload: Dict[str, Any] = {
                        "id": entry["id"],
                        "path": entry["path"],
                        "status": "error",
                    }
                    try:
                        ids = session_map[entry["id"]]
                        payload = trend_eval._evaluate_entry(
                            conn,
                            entry,
                            ids["session_id"],
                            ids["run_id"],
                        )
                        eval_status = "pass"
                    except Exception as exc:
                        hard_failures += 1
                        eval_status = "error"
                        error = f"{type(exc).__name__}: {exc}"
                        evaluation_errors.append(f"{entry['id']}: {error}")
                    elapsed_ms = (time.perf_counter() - start) * 1000.0
                    latency_ms.append(elapsed_ms)
                    payload["status"] = eval_status
                    payload["latency_ms"] = elapsed_ms
                    if error is not None:
                        payload["error"] = error
                    entry_results.append(payload)
        finally:
            conn.close()

        comparable_entries = [entry for entry in entry_results if entry.get("status") == "pass"]
        baseline_comparison, _ = _compare_with_baseline(
            comparable_entries,
            baseline_path,
            update_baseline=args.update_baseline,
            manifest=str(manifest_path).replace("\\", "/"),
        )
    except Exception as exc:
        hard_failures += 1
        evaluation_errors.append(f"harness_error: {type(exc).__name__}: {exc}")
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    report = _build_report(
        manifest=str(manifest_path).replace("\\", "/"),
        baseline=str(baseline_path).replace("\\", "/"),
        report_path=str(report_path).replace("\\", "/"),
        entry_results=entry_results,
        latency_ms=latency_ms,
        baseline_comparison=baseline_comparison,
        hard_failures=hard_failures,
        evaluation_errors=evaluation_errors,
    )
    _write_json(report_path, report)
    print(json.dumps({"status": report["status"], "report_path": report["report_path"]}, sort_keys=True))
    return _resolve_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
