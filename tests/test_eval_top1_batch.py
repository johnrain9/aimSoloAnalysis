from tools import eval_top1_batch


def test_entry_from_insights_marks_top1_only_and_extracts_fields():
    rows = [
        {
            "rule_id": "line_inconsistency",
            "corner_id": "T3",
            "phase": "mid",
            "risk_tier": "Primary",
            "gate_decision": "allow",
            "gain_trace": {"time_gain_s": 0.12},
        },
        {
            "rule_id": "exit_speed",
            "corner_id": "T4",
            "phase": "exit",
            "risk_tier": "Experimental",
        },
    ]
    entry = eval_top1_batch._entry_from_insights(
        file_id="session/a.csv",
        file_path="test_data/session/a.csv",
        session_id=7,
        run_id=11,
        insights=rows,
    )

    assert entry["status"] == "pass"
    assert entry["top1_only"] is True
    assert entry["insight_count"] == 2
    assert entry["top1_rule_id"] == "line_inconsistency"
    assert entry["top1_corner_id"] == "T3"
    assert entry["top1_phase"] == "mid"
    assert entry["top1_risk_tier"] == "Primary"
    assert entry["top1_gate_decision"] == "allow"
    assert entry["top1_gain_trace"] == {"time_gain_s": 0.12}


def test_entry_from_insights_distinguishes_fail_and_not_ready():
    fail_entry = eval_top1_batch._entry_from_insights(
        file_id="session/fail.csv",
        file_path="test_data/session/fail.csv",
        session_id=8,
        run_id=12,
        insights=[
            {
                "rule_id": "entry_speed",
                "corner_id": "T1",
                "phase": "entry",
                "risk_tier": "Blocked",
            }
        ],
    )
    assert fail_entry["status"] == "fail"
    assert "blocked" in (fail_entry["detail"] or "").lower()

    not_ready_entry = eval_top1_batch._entry_from_insights(
        file_id="session/not_ready.csv",
        file_path="test_data/session/not_ready.csv",
        session_id=9,
        run_id=13,
        insights=[],
    )
    assert not_ready_entry["status"] == "not_ready"
    assert "not ready" in (not_ready_entry["detail"] or "").lower()


def test_build_report_has_hard_and_soft_sections():
    report = eval_top1_batch._build_report(
        root="test_data",
        report_path="artifacts/eval_top1_batch_report.json",
        rows=[
            {"status": "pass"},
            {"status": "fail"},
            {"status": "not_ready"},
            {"status": "error"},
        ],
        harness_errors=["harness_error: RuntimeError: boom"],
        hard_failures=1,
    )

    assert report["schema_version"] == "1"
    assert report["harness"] == "eval_top1_batch"
    assert report["status"] == "fail"
    assert report["top1_only"] is True
    assert report["hard_checks"]["harness_status"] == "fail"
    assert report["hard_checks"]["hard_failures"] == 1
    assert report["soft_indicators"]["pass_count"] == 1
    assert report["soft_indicators"]["fail_count"] == 1
    assert report["soft_indicators"]["not_ready_count"] == 1
    assert report["soft_indicators"]["error_count"] == 1
    assert report["errors"] == ["harness_error: RuntimeError: boom"]


def test_resolve_exit_code_harness_only():
    pass_report = {
        "hard_checks": {"hard_failures": 0},
    }
    fail_report = {
        "hard_checks": {"hard_failures": 2},
    }

    assert eval_top1_batch._resolve_exit_code(pass_report) == 0
    assert eval_top1_batch._resolve_exit_code(fail_report) == 2
