"""Build deterministic human-review packet artifacts for top-1 recommendation quality.

Documented command:
  $env:PYTHONPATH='.'; python tools/build_top1_review_packet.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "artifacts" / "top1_aggregated_report.json"
DEFAULT_TRACES = ROOT / "artifacts" / "top1_traces.jsonl"
DEFAULT_MD = ROOT / "artifacts" / "top1_review_packet.md"
DEFAULT_CSV = ROOT / "artifacts" / "top1_review_packet.csv"
DEFAULT_SAMPLE_SIZE = 25
DEFAULT_SEED = 11

REQ_HUMAN = ["RQ-EVAL-011", "RQ-NFR-007"]
REQ_DECLARATION = ["RQ-EVAL-012"]

CSV_COLUMNS = [
    "case_id",
    "recommendation_text",
    "evidence_summary",
    "gate_reasons",
    "risk_tier",
    "reviewer_verdict",
    "reviewer_notes",
    "source_status",
    "outlier_score",
    "trace_id",
    "review_date",
    "reviewer",
    "scenario_set",
    "disposition",
]


@dataclass(frozen=True)
class ReviewCase:
    case_id: str
    recommendation_text: str
    evidence_summary: str
    gate_reasons: str
    risk_tier: str
    source_status: str
    outlier_score: float
    trace_id: str
    confidence: Optional[float]

    def to_csv_row(self, *, review_date: str, scenario_set: str) -> Dict[str, str]:
        return {
            "case_id": self.case_id,
            "recommendation_text": self.recommendation_text,
            "evidence_summary": self.evidence_summary,
            "gate_reasons": self.gate_reasons,
            "risk_tier": self.risk_tier,
            "reviewer_verdict": "",
            "reviewer_notes": "",
            "source_status": self.source_status,
            "outlier_score": f"{self.outlier_score:.3f}",
            "trace_id": self.trace_id,
            "review_date": review_date,
            "reviewer": "",
            "scenario_set": scenario_set,
            "disposition": "pending",
        }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {idx}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"Invalid JSONL at line {idx}: expected object")
        items.append(row)
    return items


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "; ".join(_stringify(v) for v in value if _stringify(v))
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _stringify(value).strip()
        if text:
            return text
    return ""


def _to_float(value: Any, *, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_case_list(report_payload: Any) -> List[Dict[str, Any]]:
    if isinstance(report_payload, list):
        return [row for row in report_payload if isinstance(row, dict)]
    if not isinstance(report_payload, dict):
        return []

    for key in (
        "top1_cases",
        "cases",
        "items",
        "entries",
        "recommendations",
        "results",
        "rows",
    ):
        rows = report_payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _extract_auto_scored_requirements(report_payload: Any) -> List[str]:
    if not isinstance(report_payload, dict):
        return []

    candidates: List[str] = []
    req_obj = report_payload.get("requirements")
    if isinstance(req_obj, dict):
        for key in ("auto_scored", "covered", "hard_gates", "soft_metrics"):
            values = req_obj.get(key)
            if isinstance(values, list):
                for value in values:
                    text = _stringify(value).strip()
                    if text.startswith("RQ-"):
                        candidates.append(text)

    seen = set()
    unique: List[str] = []
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _build_trace_index(trace_payload: Any) -> Dict[str, Dict[str, Any]]:
    rows = _as_list(trace_payload)
    index: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _first_non_empty(row.get("case_id"), row.get("id"), row.get("scenario_id"))
        if key:
            index[key] = row
    return index


def _normalize_case(raw: Dict[str, Any], *, fallback_id: str, trace: Optional[Dict[str, Any]]) -> ReviewCase:
    case_id = _first_non_empty(raw.get("case_id"), raw.get("id"), raw.get("scenario_id"), fallback_id)

    recommendation_text = _first_non_empty(
        raw.get("recommendation_text"),
        raw.get("recommendation"),
        raw.get("top1_recommendation"),
        raw.get("action"),
        raw.get("title"),
        trace.get("recommendation_text") if trace else None,
    )
    if not recommendation_text:
        recommendation_text = "(missing recommendation text in source report)"

    evidence_summary = _first_non_empty(
        raw.get("evidence_summary"),
        raw.get("evidence"),
        raw.get("summary"),
        raw.get("why"),
        trace.get("evidence_summary") if trace else None,
        trace.get("evidence") if trace else None,
    )

    gate_reasons = _first_non_empty(
        raw.get("gate_reasons"),
        raw.get("fail_reasons"),
        raw.get("reasons"),
        raw.get("errors"),
        trace.get("gate_reasons") if trace else None,
    )

    risk_tier = _first_non_empty(
        raw.get("risk_tier"),
        raw.get("tier"),
        raw.get("recommendation_tier"),
        trace.get("risk_tier") if trace else None,
    )
    if not risk_tier:
        risk_tier = "Unknown"

    status_text = _first_non_empty(raw.get("status"), raw.get("result"), trace.get("status") if trace else None)
    status_norm = status_text.lower()
    has_gate_reasons = bool(gate_reasons)
    source_status = "pass"
    if status_norm in {"fail", "failed", "error", "blocked"}:
        source_status = "fail"
    elif has_gate_reasons:
        source_status = "fail"

    outlier_score = _to_float(
        raw.get("outlier_score")
        if raw.get("outlier_score") is not None
        else raw.get("anomaly_score")
        if raw.get("anomaly_score") is not None
        else raw.get("deviation_score"),
        default=0.0,
    )

    confidence = None
    if raw.get("confidence") is not None:
        confidence = _to_float(raw.get("confidence"), default=0.0)

    trace_id = _first_non_empty(
        raw.get("trace_id"),
        trace.get("trace_id") if trace else None,
        trace.get("id") if trace else None,
        case_id,
    )

    return ReviewCase(
        case_id=case_id,
        recommendation_text=recommendation_text,
        evidence_summary=evidence_summary,
        gate_reasons=gate_reasons,
        risk_tier=risk_tier,
        source_status=source_status,
        outlier_score=outlier_score,
        trace_id=trace_id,
        confidence=confidence,
    )


def _seed_rank(seed: int, case_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{case_id}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _severity(case: ReviewCase) -> float:
    fail_boost = 100.0 if case.source_status == "fail" else 0.0
    outlier_boost = case.outlier_score * 10.0
    low_confidence = 0.0
    if case.confidence is not None:
        low_confidence = max(0.0, 1.0 - case.confidence)
    gate_boost = 5.0 if case.gate_reasons else 0.0
    return fail_boost + outlier_boost + low_confidence + gate_boost


def _sort_cases(cases: Iterable[ReviewCase], *, seed: int) -> List[ReviewCase]:
    return sorted(cases, key=lambda case: (-_severity(case), _seed_rank(seed, case.case_id), case.case_id))


def _pick(cases: List[ReviewCase], *, count: int) -> List[ReviewCase]:
    if count <= 0:
        return []
    return cases[:count]


def _sample_cases(cases: List[ReviewCase], *, sample_size: int, seed: int) -> List[ReviewCase]:
    if sample_size <= 0 or not cases:
        return []

    unique: Dict[str, ReviewCase] = {case.case_id: case for case in cases}
    pool = list(unique.values())

    failures = _sort_cases([case for case in pool if case.source_status == "fail"], seed=seed)
    passes = _sort_cases([case for case in pool if case.source_status == "pass"], seed=seed)
    outliers = _sort_cases(
        [case for case in pool if case.source_status != "fail" and case.outlier_score >= 0.5],
        seed=seed,
    )

    pass_quota = min(len(passes), max(1 if passes else 0, sample_size // 5))
    fail_quota = min(len(failures), max(1 if failures else 0, int(sample_size * 0.6)))
    outlier_quota = min(len(outliers), max(1 if outliers else 0, int(sample_size * 0.2)))

    selected: List[ReviewCase] = []
    seen: set[str] = set()

    def add_many(rows: List[ReviewCase]) -> None:
        for row in rows:
            if row.case_id in seen:
                continue
            if len(selected) >= sample_size:
                return
            seen.add(row.case_id)
            selected.append(row)

    add_many(_pick(failures, count=fail_quota))
    add_many(_pick(outliers, count=outlier_quota))
    add_many(_pick(passes, count=pass_quota))

    ranked_all = _sort_cases(pool, seed=seed)
    add_many(ranked_all)

    return selected[:sample_size]


def _write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _render_markdown(
    *,
    status: str,
    generated_at: str,
    runtime_ms: float,
    report_path: Path,
    traces_path: Path,
    output_csv: Path,
    sample_size: int,
    seed: int,
    selected: List[ReviewCase],
    errors: List[str],
    auto_scored_requirements: List[str],
) -> str:
    scenario_set = "top1-sample-" + generated_at[:10]
    requirement_lines = [
        "| Requirement ID | Evaluation Mode | Current Status | Evidence |",
        "| --- | --- | --- | --- |",
        "| RQ-EVAL-011 | Human-reviewed | pending_review | Packet rows + reviewer verdict/notes fields |",
        "| RQ-NFR-007 | Human-reviewed (cadenced) | pending_review | Review log fields: date/reviewer/scenario_set/disposition |",
        "| RQ-EVAL-012 | Auto-scored + declared in packet | declared | Requirement evaluation-mode declaration in this artifact |",
    ]

    auto_line = ", ".join(auto_scored_requirements) if auto_scored_requirements else "(not declared by source report)"

    lines: List[str] = []
    lines.append("# Top-1 Recommendation Review Packet")
    lines.append("")
    lines.append(f"Status: **{status}**")
    lines.append(f"Generated at (UTC): `{generated_at}`")
    lines.append(f"Runtime (ms): `{runtime_ms:.3f}`")
    lines.append(f"Scenario set: `{scenario_set}`")
    lines.append(f"Source aggregated report: `{report_path.as_posix()}`")
    lines.append(f"Source traces: `{traces_path.as_posix()}`")
    lines.append(f"Output CSV: `{output_csv.as_posix()}`")
    lines.append(f"Determinism: seed=`{seed}`, sample_size=`{sample_size}`")
    lines.append("")
    lines.append("## Requirement Evaluation Modes")
    lines.extend(requirement_lines)
    lines.append("")
    lines.append("Auto-scored requirements declared by source report:")
    lines.append(f"- {auto_line}")
    lines.append("")
    lines.append("## Review Cadence and Traceability")
    lines.append("- Cadence: run packet generation at least once per evaluation cycle (e.g., per release candidate or weekly review).")
    lines.append("- Required review log fields: `date`, `reviewer`, `scenario_set`, `disposition`, plus per-case verdict/notes.")
    lines.append("")

    if errors:
        lines.append("## Generation Errors")
        for item in errors:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("## Sample Summary")
    fail_count = len([row for row in selected if row.source_status == "fail"])
    pass_count = len([row for row in selected if row.source_status == "pass"])
    outlier_count = len([row for row in selected if row.outlier_score >= 0.5])
    lines.append(f"- selected_cases: {len(selected)}")
    lines.append(f"- failures_included: {fail_count}")
    lines.append(f"- outliers_included: {outlier_count}")
    lines.append(f"- passes_included: {pass_count}")
    lines.append("")

    lines.append("## Review Rows (Top 10)")
    lines.append("| case_id | source_status | risk_tier | gate_reasons | recommendation_text |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in selected[:10]:
        rec = row.recommendation_text.replace("|", " ").strip()
        reasons = row.gate_reasons.replace("|", " ").strip()
        lines.append(f"| {row.case_id} | {row.source_status} | {row.risk_tier} | {reasons} | {rec} |")

    if not selected:
        lines.append("| (none) | n/a | n/a | n/a | n/a |")

    return "\n".join(lines) + "\n"


def build_review_packet(
    *,
    report_path: Path,
    traces_path: Path,
    output_md: Path,
    output_csv: Path,
    sample_size: int,
    seed: int,
) -> Dict[str, Any]:
    started = time.perf_counter()
    generated_at = datetime.now(timezone.utc).isoformat()

    errors: List[str] = []
    report_payload: Any = None
    trace_payload: List[Dict[str, Any]] = []

    if report_path.exists():
        try:
            report_payload = _read_json(report_path)
        except Exception as exc:
            errors.append(
                f"Failed reading aggregated report `{report_path.as_posix()}`: {type(exc).__name__}: {exc}"
            )
    else:
        errors.append(
            f"Missing aggregated report `{report_path.as_posix()}`. Run the top-1 evaluation aggregation first or pass --report <path>."
        )

    if traces_path.exists():
        try:
            if traces_path.suffix.lower() == ".jsonl":
                trace_payload = _read_jsonl(traces_path)
            else:
                loaded = _read_json(traces_path)
                trace_payload = _as_list(loaded)
        except Exception as exc:
            errors.append(f"Failed reading traces `{traces_path.as_posix()}`: {type(exc).__name__}: {exc}")
    else:
        errors.append(
            f"Missing traces `{traces_path.as_posix()}`. Provide --traces <path> for richer evidence summaries."
        )

    trace_index = _build_trace_index(trace_payload)
    raw_cases = _extract_case_list(report_payload)
    normalized: List[ReviewCase] = []
    for idx, case in enumerate(raw_cases, start=1):
        case_id = _first_non_empty(case.get("case_id"), case.get("id"), case.get("scenario_id"), f"case-{idx}")
        normalized.append(_normalize_case(case, fallback_id=f"case-{idx}", trace=trace_index.get(case_id)))

    if report_payload is not None and not normalized:
        errors.append(
            "Aggregated report was loaded but no case list was found. Expected one of: "
            "top1_cases/cases/items/entries/recommendations/results."
        )

    selected = _sample_cases(normalized, sample_size=sample_size, seed=seed)
    auto_scored_requirements = _extract_auto_scored_requirements(report_payload)
    if not auto_scored_requirements:
        auto_scored_requirements = ["RQ-EVAL-004", "RQ-EVAL-005", "RQ-EVAL-007", "RQ-NFR-006"]

    scenario_set = "top1-sample-" + generated_at[:10]
    csv_rows = [row.to_csv_row(review_date=generated_at[:10], scenario_set=scenario_set) for row in selected]

    if errors and not csv_rows:
        csv_rows = [
            {
                "case_id": "ERROR",
                "recommendation_text": "Review packet generation failed before sampling.",
                "evidence_summary": "See markdown Generation Errors section.",
                "gate_reasons": "; ".join(errors),
                "risk_tier": "Blocked",
                "reviewer_verdict": "",
                "reviewer_notes": "",
                "source_status": "fail",
                "outlier_score": "0.000",
                "trace_id": "ERROR",
                "review_date": generated_at[:10],
                "reviewer": "",
                "scenario_set": scenario_set,
                "disposition": "blocked_missing_inputs",
            }
        ]

    _write_csv(output_csv, csv_rows)

    status = "pass"
    if errors and selected:
        status = "partial"
    elif errors:
        status = "fail"

    md_text = _render_markdown(
        status=status,
        generated_at=generated_at,
        runtime_ms=(time.perf_counter() - started) * 1000.0,
        report_path=report_path,
        traces_path=traces_path,
        output_csv=output_csv,
        sample_size=sample_size,
        seed=seed,
        selected=selected,
        errors=errors,
        auto_scored_requirements=auto_scored_requirements,
    )
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(md_text, encoding="utf-8")

    return {
        "status": status,
        "sample_size": sample_size,
        "selected_count": len(selected),
        "error_count": len(errors),
        "errors": errors,
        "report": report_path.as_posix(),
        "traces": traces_path.as_posix(),
        "output_md": output_md.as_posix(),
        "output_csv": output_csv.as_posix(),
        "seed": seed,
        "runtime_ms": round((time.perf_counter() - started) * 1000.0, 3),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic top-1 human review packet artifacts.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Path to aggregated top-1 report JSON.")
    parser.add_argument("--traces", default=str(DEFAULT_TRACES), help="Path to trace JSON/JSONL.")
    parser.add_argument("--out-md", default=str(DEFAULT_MD), help="Output markdown packet path.")
    parser.add_argument("--out-csv", default=str(DEFAULT_CSV), help="Output CSV packet path.")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    sample_size = max(1, int(args.sample_size))
    result = build_review_packet(
        report_path=Path(args.report),
        traces_path=Path(args.traces),
        output_md=Path(args.out_md),
        output_csv=Path(args.out_csv),
        sample_size=sample_size,
        seed=int(args.seed),
    )
    print(json.dumps({"status": result["status"], "output_md": result["output_md"], "output_csv": result["output_csv"]}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
