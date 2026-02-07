"""Frontend evaluation harness for critical trackside UI flows.

Runs static wiring/semantics checks against ui/index.html and ui/app.js and
emits a machine-readable JSON report artifact.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HTML = ROOT / "ui" / "index.html"
DEFAULT_JS = ROOT / "ui" / "app.js"
DEFAULT_CSS = ROOT / "ui" / "styles.css"
DEFAULT_REPORT = ROOT / "artifacts" / "frontend_eval_report.json"

REQ_FLOW = ["RQ-EVAL-004", "RQ-EVAL-007"]
REQ_MAP = ["RQ-EVAL-005", "RQ-EVAL-007"]
REQ_TOP1 = ["RQ-P0-025", "RQ-P0-019", "RQ-P0-020", "RQ-EVAL-005", "RQ-EVAL-007"]
REQ_JSON = ["RQ-NFR-006", "RQ-EVAL-007"]


@dataclass
class CheckResult:
    check_id: str
    requirement_ids: list[str]
    status: str
    duration_ms: float
    details: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "requirement_ids": self.requirement_ids,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 3),
            "details": self.details,
            "evidence": self.evidence,
        }


def _extract_routes(js_text: str) -> list[str]:
    match = re.search(r"const\s+routes\s*=\s*\[([^\]]+)\]\s*;", js_text)
    if not match:
        return []
    entries = re.findall(r'"([^"]+)"|\'([^\']+)\'', match.group(1))
    routes = []
    for a, b in entries:
        value = a or b
        if value:
            routes.append(value)
    return routes


def _check_flow_wiring(index_text: str, js_text: str, _css_text: str) -> tuple[bool, str, dict[str, Any]]:
    required_routes = ["import", "summary", "insights", "compare"]
    routes = _extract_routes(js_text)
    route_set = set(routes)
    missing_routes = [r for r in required_routes if r not in route_set]

    missing_screens = [
        r for r in required_routes if f'id="screen-{r}"' not in index_text
    ]
    missing_route_buttons = [
        r for r in required_routes if f'data-route="{r}"' not in index_text
    ]

    has_bind_route = "function bindRouteButtons()" in js_text
    has_ensure_data = "function ensureDataForRoute(route)" in js_text
    has_init_route = "setRoute(readRoute())" in js_text
    has_hash_route = 'window.addEventListener("hashchange"' in js_text

    ok = (
        not missing_routes
        and not missing_screens
        and not missing_route_buttons
        and has_bind_route
        and has_ensure_data
        and has_init_route
        and has_hash_route
    )
    if ok:
        details = "Import->summary->insights->compare route wiring is present."
    else:
        details = "Missing required route wiring elements."
    evidence = {
        "routes_declared": routes,
        "missing_routes": missing_routes,
        "missing_screens": missing_screens,
        "missing_route_buttons": missing_route_buttons,
        "has_bind_route_buttons": has_bind_route,
        "has_ensure_data_for_route": has_ensure_data,
        "has_init_route_read": has_init_route,
        "has_hashchange_handler": has_hash_route,
    }
    return ok, details, evidence


def _check_ui_state_expectations(
    index_text: str, js_text: str, _css_text: str
) -> tuple[bool, str, dict[str, Any]]:
    required_ids = [
        "analyze-now",
        "csv-file",
        "file-path",
        "dropzone-note",
        "screen-summary",
        "screen-insights",
        "screen-compare",
        "insights-context",
        "delta-list",
        "insight-summary",
        "track-map",
        "track-map-meta",
        "compare-map",
    ]
    missing_ids = [item for item in required_ids if f'id="{item}"' not in index_text]

    required_js_tokens = [
        'runImportAndLoad({ force: true, routeAfter: "summary" })',
        "renderSummary(appState.summary)",
        "renderInsights(appState.insights)",
        "renderCompare(appState.compare)",
        "bindCompareSelectors()",
        "bindInsightButtons()",
        "renderTrackMap(appState.selectedSegmentId)",
    ]
    missing_js_tokens = [item for item in required_js_tokens if item not in js_text]

    ok = not missing_ids and not missing_js_tokens
    details = (
        "Critical UI state wiring and key route state expectations are present."
        if ok
        else "Missing required UI state wiring/state expectation elements."
    )
    evidence = {
        "missing_dom_ids": missing_ids,
        "missing_js_tokens": missing_js_tokens,
    }
    return ok, details, evidence


def _check_did_vs_should_map_semantics(
    index_text: str, js_text: str, _css_text: str
) -> tuple[bool, str, dict[str, Any]]:
    legend_tokens = [
        'id="track-map-legend"',
        "Reference",
        "Target",
        '<span class="dot a"></span> Lap A',
        '<span class="dot b"></span> Lap B',
    ]
    missing_legend = [item for item in legend_tokens if item not in index_text]

    map_tokens = [
        'class="track-target"',
        'class="track-reference"',
        'class="track-highlight"',
        'class="track-highlight ref"',
        'class="track-apex"',
        "Highlight:",
        "vs",
    ]
    missing_map_tokens = [item for item in map_tokens if item not in js_text]

    ok = not missing_legend and not missing_map_tokens
    details = (
        "Did-vs-should map semantics are wired (reference/target/highlight/legend)."
        if ok
        else "Missing did-vs-should map semantic elements."
    )
    evidence = {
        "missing_legend_tokens": missing_legend,
        "missing_map_tokens": missing_map_tokens,
    }
    return ok, details, evidence


def _check_top1_visual_priority_semantics(
    index_text: str, js_text: str, css_text: str
) -> tuple[bool, str, dict[str, Any]]:
    dom_tokens = [
        'id="top1-briefing"',
        'class="insight-list"',
    ]
    missing_dom_tokens = [token for token in dom_tokens if token not in index_text]

    js_tokens = [
        "function resolveTopInsightIndex(items)",
        "function renderTop1Briefing(item, source)",
        'article.className = isTop1 ? "card insight insight-top1" : "card insight insight-secondary";',
        'article.dataset.visualPriority = isTop1 ? "top1" : "secondary";',
        "const topIndex = resolveTopInsightIndex(deduped);",
    ]
    missing_js_tokens = [token for token in js_tokens if token not in js_text]

    css_tokens = [
        ".top1-briefing",
        ".insight.insight-top1",
        ".insight-list .insight.insight-secondary",
        ".briefing-action",
        ".insight-priority-line",
    ]
    missing_css_tokens = [token for token in css_tokens if token not in css_text]

    ok = not missing_dom_tokens and not missing_js_tokens and not missing_css_tokens
    details = (
        "Top-1 visual priority semantics are explicit (dominant card + fast briefing panel + fallback)."
        if ok
        else "Missing explicit top-1 visual priority semantics."
    )
    evidence = {
        "missing_dom_tokens": missing_dom_tokens,
        "missing_js_tokens": missing_js_tokens,
        "missing_css_tokens": missing_css_tokens,
    }
    return ok, details, evidence


def _run_check(
    check_id: str,
    requirement_ids: list[str],
    fn: Callable[[str, str, str], tuple[bool, str, dict[str, Any]]],
    *,
    index_text: str,
    js_text: str,
    css_text: str,
) -> CheckResult:
    start = time.perf_counter()
    ok, details, evidence = fn(index_text, js_text, css_text)
    duration_ms = (time.perf_counter() - start) * 1000.0
    return CheckResult(
        check_id=check_id,
        requirement_ids=requirement_ids,
        status="pass" if ok else "fail",
        duration_ms=duration_ms,
        details=details,
        evidence=evidence,
    )


def build_report(
    *, index_path: Path = DEFAULT_HTML, js_path: Path = DEFAULT_JS, css_path: Path = DEFAULT_CSS
) -> dict[str, Any]:
    started = time.perf_counter()
    index_text = index_path.read_text(encoding="utf-8")
    js_text = js_path.read_text(encoding="utf-8")
    css_text = css_path.read_text(encoding="utf-8")

    checks = [
        _run_check(
            "flow_wiring",
            REQ_FLOW,
            _check_flow_wiring,
            index_text=index_text,
            js_text=js_text,
            css_text=css_text,
        ),
        _run_check(
            "ui_state_expectations",
            REQ_FLOW,
            _check_ui_state_expectations,
            index_text=index_text,
            js_text=js_text,
            css_text=css_text,
        ),
        _run_check(
            "did_vs_should_map_semantics",
            REQ_MAP,
            _check_did_vs_should_map_semantics,
            index_text=index_text,
            js_text=js_text,
            css_text=css_text,
        ),
        _run_check(
            "top1_visual_priority_semantics",
            REQ_TOP1,
            _check_top1_visual_priority_semantics,
            index_text=index_text,
            js_text=js_text,
            css_text=css_text,
        ),
    ]

    passed = len([c for c in checks if c.status == "pass"])
    failed = len(checks) - passed
    status = "pass" if failed == 0 else "fail"
    runtime_ms = (time.perf_counter() - started) * 1000.0

    return {
        "harness": "frontend_eval",
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "runtime_ms": round(runtime_ms, 3),
        "summary": {
            "total_checks": len(checks),
            "passed_checks": passed,
            "failed_checks": failed,
        },
        "checks": [c.to_dict() for c in checks],
        "requirements": {
            "covered": sorted({req for check in checks for req in check.requirement_ids}),
            "artifact_requirement_ids": REQ_JSON,
        },
    }


def write_report(report: dict[str, Any], report_path: Path) -> Path:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run frontend evaluation harness and emit JSON artifact.")
    parser.add_argument("--index", default=str(DEFAULT_HTML))
    parser.add_argument("--appjs", default=str(DEFAULT_JS))
    parser.add_argument("--css", default=str(DEFAULT_CSS))
    parser.add_argument("--out", default=str(DEFAULT_REPORT))
    args = parser.parse_args(argv)

    report = build_report(index_path=Path(args.index), js_path=Path(args.appjs), css_path=Path(args.css))
    report_path = write_report(report, Path(args.out))
    print(f"frontend_eval status={report['status']} checks={report['summary']['total_checks']}")
    print(f"report={report_path.as_posix()}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
