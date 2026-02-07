from tools import eval_backend


def test_build_report_shape_and_deterministic_fields():
    entry_results = [
        {
            "id": "run-1",
            "path": "test_data/a.csv",
            "status": "pass",
            "latency_ms": 12.34567,
            "summary": {"segment_count": 2},
            "segments": {},
        },
        {
            "id": "run-2",
            "path": "test_data/b.csv",
            "status": "error",
            "latency_ms": 9.87654,
            "error": "RuntimeError: boom",
        },
    ]
    baseline = {"status": "fail", "mismatch_count": 2, "errors": ["run-1 mismatch", "run-2 mismatch"]}
    report = eval_backend._build_report(
        manifest="tests/fixtures/trend_eval_manifest.json",
        baseline="tests/fixtures/trend_eval_baseline.json",
        report_path="artifacts/eval_backend_report.json",
        entry_results=entry_results,
        latency_ms=[12.34567, 9.87654],
        baseline_comparison=baseline,
        hard_failures=1,
        evaluation_errors=["run-2: RuntimeError: boom"],
    )

    assert report["schema_version"] == "1"
    assert report["harness"] == "backend_eval"
    assert report["status"] == "fail"
    assert report["manifest"] == "tests/fixtures/trend_eval_manifest.json"
    assert report["baseline"] == "tests/fixtures/trend_eval_baseline.json"
    assert report["report_path"] == "artifacts/eval_backend_report.json"
    assert len(report["entries"]) == 2

    failures = report["failures"]
    assert failures["hard_failures"] == 1
    assert failures["entry_failures"] == 1
    assert failures["baseline_mismatches"] == 2
    assert failures["total_failures"] == 3

    latency = report["latency_summary"]
    assert latency["entry_count"] == 2
    assert latency["max_ms"] == 12.3457
    assert latency["p50_ms"] == 11.1111
    assert latency["p95_ms"] == 12.2222

    assert report["baseline_comparison"]["status"] == "fail"
    assert report["errors"][0].startswith("run-2:")


def test_resolve_exit_code():
    hard_fail_report = {
        "failures": {"hard_failures": 1},
        "baseline_comparison": {"status": "pass"},
    }
    assert eval_backend._resolve_exit_code(hard_fail_report) == 2

    mismatch_report = {
        "failures": {"hard_failures": 0},
        "baseline_comparison": {"status": "fail"},
    }
    assert eval_backend._resolve_exit_code(mismatch_report) == 1

    pass_report = {
        "failures": {"hard_failures": 0},
        "baseline_comparison": {"status": "pass"},
    }
    assert eval_backend._resolve_exit_code(pass_report) == 0
