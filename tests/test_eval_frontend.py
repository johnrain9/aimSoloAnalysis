from pathlib import Path

from tools import eval_frontend


def test_eval_frontend_report_schema():
    report = eval_frontend.build_report()

    assert report["harness"] == "frontend_eval"
    assert report["schema_version"] == "1.0"
    assert report["status"] in {"pass", "fail"}
    assert isinstance(report["runtime_ms"], float)
    assert report["summary"]["total_checks"] == len(report["checks"])
    assert report["summary"]["passed_checks"] + report["summary"]["failed_checks"] == len(report["checks"])
    assert "RQ-NFR-006" in report["requirements"]["artifact_requirement_ids"]

    for check in report["checks"]:
        assert check["check_id"]
        assert check["status"] in {"pass", "fail"}
        assert isinstance(check["duration_ms"], float)
        assert isinstance(check["requirement_ids"], list)
        assert isinstance(check["evidence"], dict)


def test_eval_frontend_core_checks_pass_against_repo_ui():
    report = eval_frontend.build_report()
    failed = [check for check in report["checks"] if check["status"] != "pass"]
    assert failed == []


def test_eval_frontend_did_vs_should_check_detects_missing_semantics(tmp_path: Path):
    index_path = tmp_path / "index.html"
    js_path = tmp_path / "app.js"

    index_path.write_text(
        '<section id="screen-import"></section>'
        '<section id="screen-summary"></section>'
        '<section id="screen-insights"></section>'
        '<section id="screen-compare"></section>'
        '<button data-route="import"></button>'
        '<button data-route="summary"></button>'
        '<button data-route="insights"></button>'
        '<button data-route="compare"></button>'
        '<input id="csv-file"/><input id="file-path"/><button id="analyze-now"></button>'
        '<div id="dropzone-note"></div><div id="insights-context"></div><div id="delta-list"></div>'
        '<div id="insight-summary"></div><svg id="track-map"></svg><div id="track-map-meta"></div>'
        '<svg id="compare-map"></svg>',
        encoding="utf-8",
    )
    js_path.write_text(
        'const routes = ["import", "summary", "insights", "compare"];'
        'function bindRouteButtons(){}'
        'function ensureDataForRoute(route){}'
        'function bindCompareSelectors(){}'
        'function bindInsightButtons(){}'
        'function renderTrackMap(){}'
        'function runImportAndLoad(){ }'
        'function renderSummary(){}'
        'function renderInsights(){}'
        'function renderCompare(){}'
        'function init(){setRoute(readRoute());}'
        'window.addEventListener("hashchange",()=>{});',
        encoding="utf-8",
    )

    report = eval_frontend.build_report(index_path=index_path, js_path=js_path)
    checks = {check["check_id"]: check for check in report["checks"]}
    assert checks["did_vs_should_map_semantics"]["status"] == "fail"


def test_eval_frontend_top1_check_passes_against_repo_ui():
    report = eval_frontend.build_report()
    checks = {check["check_id"]: check for check in report["checks"]}
    assert checks["top1_visual_priority_semantics"]["status"] == "pass"


def test_eval_frontend_top1_check_detects_missing_semantics():
    ok, _details, evidence = eval_frontend._check_top1_visual_priority_semantics(
        "<div class='insight-list'></div>",
        "function renderInsights(){}",
        ".insight{ }",
    )
    assert ok is False
    assert evidence["missing_js_tokens"] != []
