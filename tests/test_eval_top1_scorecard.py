import json
from pathlib import Path

from tools import eval_top1_scorecard


def test_build_report_top1_schema_and_deterministic_fields(tmp_path: Path):
    input_path = tmp_path / "top1.jsonl"
    report_path = tmp_path / "report.json"

    lines = [
        {
            "trace_id": "t-pass-1",
            "top1_pass": True,
            "rule_id": "RULE_A",
            "corner_id": "T1",
            "corner_label": "T1",
            "phase": "mid",
            "risk_tier": "Primary",
            "actual_gain_s": 0.42,
            "detail": "At T1 (mid phase), line spread is about 2.0 ft wider than reference.",
            "did": "At T1 (mid phase), line spread is about 2.0 ft wider than reference.",
            "should": "T1: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
            "because": "Because line variance is elevated (5.9 ft), timing and speed consistency drop through mid.",
            "success_check": "Rider check: repeat the same turn-in and apex marker for the next 3 laps. Telemetry confirmation (optional): keep line variance delta <= +1.0 ft.",
        },
        {
            "trace_id": "t-fail-1",
            "top1_pass": False,
            "failure_reason": "missing_success_check",
            "rule_id": "RULE_B",
            "corner_id": "T2",
            "corner_label": "T2",
            "phase": "entry",
            "risk_tier": "Experimental",
            "actual_gain_s": -0.22,
            "detail": "At T2 (entry phase), entry speed is 3.0 mph lower than reference.",
            "did": "At T2 (entry phase), entry speed is 3.0 mph lower than reference.",
            "should": "At T2, carry speed to apex with one clean brake release and no extra scrub.",
            "because": "Because entry speed is down by 3.0 mph, this segment starts slower than reference.",
            "success_check": "Rider check: for the next 2 laps, carry speed to apex with one clean brake release and no extra scrub. Telemetry confirmation (optional): improve entry speed delta by >= +1.2 mph without increasing line spread.",
        },
        {
            "trace_id": "t-fail-2",
            "top1_pass": False,
            "failure_reason": "missing_success_check",
            "rule_id": "RULE_B",
            "corner_id": "T3",
            "corner_label": "T3",
            "phase": "exit",
            "risk_tier": "Experimental",
            "actual_gain_s": -0.41,
            "detail": "At T3 (exit phase), throttle pickup starts about 18.0 ft later than reference.",
            "did": "At T3 (exit phase), throttle pickup starts about 18.0 ft later than reference.",
            "should": "At T3, begin drive sooner after apex for the next 2 laps without widening exit.",
            "because": "Because throttle pickup is delayed by 18.0 ft, exit drive starts late.",
            "success_check": "Rider check: begin drive sooner after apex for the next 2 laps without widening exit. Telemetry confirmation (optional): cut pickup delay by >= 20 ft and improve exit speed delta by >= +1.2 mph.",
        },
        {
            "trace_id": "t-fail-3",
            "top1_pass": False,
            "failure_reason": "unsafe_recommendation",
            "rule_id": "RULE_C",
            "corner_id": "T4",
            "corner_label": "T4",
            "phase": "mid",
            "risk_tier": "Blocked",
            "actual_gain_s": -1.1,
            "detail": "At T4 (mid phase), steering activity is about 1.20x reference.",
            "did": "At T4 (mid phase), steering activity is about 1.20x reference.",
            "should": "At T4, make one clean steering input and hold it through apex for 2-3 laps.",
            "because": "Because steering activity is 1.20x reference, mid-corner scrub is likely increasing.",
            "success_check": "Rider check: make one clean steering input and hold it through apex for 2-3 laps. Telemetry confirmation (optional): bring yaw ratio to <= 1.10 while improving apex minimum speed delta by >= +0.6 mph.",
        },
    ]
    input_path.write_text("\n".join(json.dumps(item) for item in lines) + "\n", encoding="utf-8")

    report = eval_top1_scorecard.build_report(input_path=input_path, report_path=report_path)

    assert report["schema_version"] == "1"
    assert report["harness"] == "top1_quality_eval"
    assert report["scope"] == "top1"
    assert report["status"] == "pass"
    assert report["requirements"]["auto_scored"] == [
        "RQ-EVAL-007",
        "RQ-EVAL-008",
        "RQ-EVAL-010",
        "RQ-NFR-006",
    ]

    assert report["summary"] == {
        "total_lines": 4,
        "valid_rows": 4,
        "malformed_lines": 0,
    }

    assert report["hard_gates"]["status"] == "pass"
    assert report["hard_gates"]["failed_count"] == 0
    gate_names = [item["gate"] for item in report["hard_gates"]["checks"]]
    assert "did_vs_should_fields_present" in gate_names
    assert "did_vs_should_success_check_measurable" in gate_names

    counts = report["soft_indicators"]["top1_counts"]
    assert counts == {"pass": 1, "fail": 3, "unknown": 0}
    assert report["soft_indicators"]["coaching_quality_summary"] == {"pass": 4, "fail": 0}

    reasons = report["soft_indicators"]["failure_reason_distribution"]
    assert reasons == [
        {"reason": "missing_success_check", "count": 2},
        {"reason": "unsafe_recommendation", "count": 1},
    ]

    rule_dist = report["soft_indicators"]["rule_distribution"]
    assert rule_dist == [
        {"rule_id": "RULE_B", "count": 2},
        {"rule_id": "RULE_A", "count": 1},
        {"rule_id": "RULE_C", "count": 1},
    ]

    risk_dist = report["soft_indicators"]["risk_tier_distribution"]
    assert risk_dist == [
        {"risk_tier": "Experimental", "count": 2},
        {"risk_tier": "Blocked", "count": 1},
        {"risk_tier": "Primary", "count": 1},
    ]

    worst = report["soft_indicators"]["worst_20_examples"]
    assert worst[0]["trace_id"] == "t-fail-3"
    assert worst[0]["gain_s"] == -1.1
    assert worst[1]["trace_id"] == "t-fail-2"
    assert worst[2]["trace_id"] == "t-fail-1"

    assert isinstance(report["soft_indicators"]["outlier_gain_list"], list)
    assert len(report["top1_cases"]) == 4
    assert report["top1_cases"][0]["case_id"] == "t-pass-1"
    assert report["top1_cases"][0]["coaching_quality_status"] == "pass"


def test_missing_input_emits_structured_failure_report(tmp_path: Path):
    missing_input = tmp_path / "missing.jsonl"
    report_path = tmp_path / "report.json"

    report = eval_top1_scorecard.build_report(input_path=missing_input, report_path=report_path)

    assert report["status"] == "fail"
    assert report["hard_gates"]["status"] == "fail"
    assert report["hard_gates"]["failed_count"] >= 1
    assert report["summary"]["valid_rows"] == 0
    assert report["errors"]
    assert report["errors"][0].startswith("input_missing:")
    assert eval_top1_scorecard._resolve_exit_code(report) == 2


def test_partial_parse_failures_reported_without_hiding_valid_rows(tmp_path: Path):
    input_path = tmp_path / "top1.jsonl"
    report_path = tmp_path / "report.json"

    input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "trace_id": "good-1",
                        "top1_pass": True,
                        "rule_id": "R1",
                        "risk_tier": "Primary",
                        "actual_gain_s": 0.2,
                    }
                ),
                "{bad json",
                json.dumps(
                    {
                        "trace_id": "good-2",
                        "top1_pass": False,
                        "failure_reason": "risk_missing",
                        "rule_id": "R2",
                        "risk_tier": "Experimental",
                        "actual_gain_s": -0.3,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = eval_top1_scorecard.build_report(input_path=input_path, report_path=report_path)

    assert report["summary"]["total_lines"] == 3
    assert report["summary"]["valid_rows"] == 2
    assert report["summary"]["malformed_lines"] == 1
    assert len(report["malformed_examples"]) == 1
    assert report["malformed_examples"][0]["line_number"] == 2

    assert report["soft_indicators"]["top1_counts"] == {"pass": 1, "fail": 1, "unknown": 0}
    assert report["soft_indicators"]["failure_reason_distribution"] == [
        {"reason": "risk_missing", "count": 1}
    ]
    assert report["hard_gates"]["status"] == "fail"


def test_scorecard_accepts_legacy_batch_json_report_shape(tmp_path: Path):
    input_path = tmp_path / "legacy_batch_report.json"
    report_path = tmp_path / "scorecard.json"

    input_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "file_id": "a.csv",
                        "session_id": 1,
                        "run_id": 2,
                        "status": "pass",
                        "top1_rule_id": "RULE_A",
                        "top1_corner_id": "T1",
                        "top1_corner_label": "T1",
                        "top1_phase": "mid",
                        "top1_risk_tier": "Primary",
                        "top1_gain_trace": {"final_expected_gain_s": 0.22},
                        "top1_detail": "At T1 (mid phase), line spread is about 2.0 ft wider than reference.",
                        "top1_did": "At T1 (mid phase), line spread is about 2.0 ft wider than reference.",
                        "top1_should": "T1: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
                        "top1_because": "Because line variance is elevated (5.9 ft), timing and speed consistency drop through mid.",
                        "top1_success_check": "Rider check: repeat the same turn-in and apex marker for the next 3 laps. Telemetry confirmation (optional): keep line variance delta <= +1.0 ft.",
                    },
                    {
                        "file_id": "b.csv",
                        "session_id": 3,
                        "run_id": 4,
                        "status": "fail",
                        "detail": "gate blocked",
                        "top1_rule_id": "RULE_B",
                        "top1_corner_id": "T2",
                        "top1_corner_label": "T2",
                        "top1_phase": "entry",
                        "top1_risk_tier": "Blocked",
                        "top1_gain_trace": {"final_expected_gain_s": -0.04},
                        "top1_did": "At T2 (entry phase), entry speed is 3.0 mph lower than reference.",
                        "top1_should": "At T2, carry speed to apex with one clean brake release and no extra scrub.",
                        "top1_because": "Because entry speed is down by 3.0 mph, this segment starts slower than reference.",
                        "top1_success_check": "Rider check: for the next 2 laps, carry speed to apex with one clean brake release and no extra scrub. Telemetry confirmation (optional): improve entry speed delta by >= +1.2 mph without increasing line spread.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = eval_top1_scorecard.build_report(input_path=input_path, report_path=report_path)

    assert report["status"] == "pass"
    assert report["summary"]["valid_rows"] == 2
    assert report["soft_indicators"]["top1_counts"] == {"pass": 1, "fail": 1, "unknown": 0}
    assert report["top1_cases"][1]["failure_reason"] == "gate blocked"
    assert report["top1_cases"][1]["coaching_quality_status"] == "pass"


def test_scorecard_fails_explicit_coaching_quality_gates(tmp_path: Path):
    input_path = tmp_path / "top1.jsonl"
    report_path = tmp_path / "report.json"

    lines = [
        {
            "trace_id": "t-bad-1",
            "top1_pass": True,
            "rule_id": "RULE_A",
            "corner_id": "HPR Full:CW:T7",
            "risk_tier": "Primary",
            "detail": "Current telemetry shows a controllable issue.",
            "did": "Current telemetry shows a controllable issue.",
            "should": "Be consistent.",
            "because": "Evidence is partial.",
            "success_check": "Try it next time.",
        }
    ]
    input_path.write_text("\n".join(json.dumps(item) for item in lines) + "\n", encoding="utf-8")

    report = eval_top1_scorecard.build_report(input_path=input_path, report_path=report_path)

    assert report["status"] == "fail"
    failed_gates = {item["gate"] for item in report["hard_gates"]["checks"] if item["status"] == "fail"}
    assert failed_gates == {
        "did_vs_should_delta_present",
        "did_vs_should_rationale_present",
        "did_vs_should_success_check_measurable",
        "did_vs_should_corner_consistency",
    }
    assert report["soft_indicators"]["coaching_quality_summary"] == {"pass": 0, "fail": 1}
    assert report["soft_indicators"]["coaching_quality_fail_examples"][0]["trace_id"] == "t-bad-1"
