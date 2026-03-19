from tools import eval_top1_batch


def test_entry_from_insights_marks_top1_only_and_extracts_fields():
    rows = [
        {
            "rule_id": "line_inconsistency",
            "corner_id": "T3",
            "corner_label": "T3",
            "phase": "mid",
            "risk_tier": "Primary",
            "gate_decision": "allow",
            "gain_trace": {"time_gain_s": 0.12},
            "detail": "At T3 (mid phase), line spread is about 2.6 ft wider than reference.",
            "did": "At T3 (mid phase), line spread is about 2.6 ft wider than reference.",
            "should": "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
            "because": "Because line variance is elevated (5.9 ft), timing and speed consistency drop through mid.",
            "success_check": "Rider check: repeat the same turn-in and apex marker for the next 3 laps.",
            "operational_action": "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
            "causal_reason": "Because line variance is elevated (5.9 ft), timing and speed consistency drop through mid.",
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
    assert entry["top1_did"].startswith("At T3")
    assert entry["top1_should"].startswith("T3:")
    assert entry["top1_because"].startswith("Because ")
    assert "next 3 laps" in entry["top1_success_check"]


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
        trace_path="artifacts/top1_traces.jsonl",
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
    assert report["trace_path"] == "artifacts/top1_traces.jsonl"
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


def test_trace_row_contract_for_scorecard_and_review_packet():
    entry = {
        "file_id": "session/a.csv",
        "file_path": "test_data/session/a.csv",
        "session_id": 7,
        "run_id": 11,
        "status": "fail",
        "detail": "missing metrics",
        "top1_rule_id": "line_inconsistency",
        "top1_corner_id": "T3",
        "top1_phase": "mid",
        "top1_risk_tier": "Experimental",
        "top1_gate_decision": "blocked",
        "top1_gain_trace": {"final_expected_gain_s": 0.12},
        "top1_detail": "At T3 (mid phase), line spread is about 2.6 ft wider than reference.",
        "top1_did": "At T3 (mid phase), line spread is about 2.6 ft wider than reference.",
        "top1_should": "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
        "top1_because": "Because line variance is elevated (5.9 ft), timing and speed consistency drop through mid.",
        "top1_success_check": "Rider check: repeat the same turn-in and apex marker for the next 3 laps.",
        "top1_operational_action": "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
        "top1_causal_reason": "Because line variance is elevated (5.9 ft), timing and speed consistency drop through mid.",
        "top1_corner_label": "T3",
    }

    trace = eval_top1_batch._trace_row_from_entry(entry)

    assert trace["trace_id"] == "session-7-run-11"
    assert trace["case_id"] == "session/a.csv"
    assert trace["top1_pass"] is False
    assert trace["failure_reason"] == "missing metrics"
    assert trace["rule_id"] == "line_inconsistency"
    assert trace["risk_tier"] == "Experimental"
    assert trace["gate_decision"] == "blocked"
    assert trace["expected_gain_s"] == 0.12
    assert trace["did"].startswith("At T3")
    assert trace["should"].startswith("T3:")
    assert trace["because"].startswith("Because ")
    assert trace["success_check"].startswith("Rider check:")
    assert trace["corner_label"] == "T3"
