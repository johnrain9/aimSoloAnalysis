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
            "risk_tier": "Primary",
            "actual_gain_s": 0.42,
        },
        {
            "trace_id": "t-fail-1",
            "top1_pass": False,
            "failure_reason": "missing_success_check",
            "rule_id": "RULE_B",
            "risk_tier": "Experimental",
            "actual_gain_s": -0.22,
        },
        {
            "trace_id": "t-fail-2",
            "top1_pass": False,
            "failure_reason": "missing_success_check",
            "rule_id": "RULE_B",
            "risk_tier": "Experimental",
            "actual_gain_s": -0.41,
        },
        {
            "trace_id": "t-fail-3",
            "top1_pass": False,
            "failure_reason": "unsafe_recommendation",
            "rule_id": "RULE_C",
            "risk_tier": "Blocked",
            "actual_gain_s": -1.1,
        },
    ]
    input_path.write_text("\n".join(json.dumps(item) for item in lines) + "\n", encoding="utf-8")

    report = eval_top1_scorecard.build_report(input_path=input_path, report_path=report_path)

    assert report["schema_version"] == "1"
    assert report["harness"] == "top1_quality_eval"
    assert report["scope"] == "top1"
    assert report["status"] == "pass"

    assert report["summary"] == {
        "total_lines": 4,
        "valid_rows": 4,
        "malformed_lines": 0,
    }

    assert report["hard_gates"]["status"] == "pass"
    assert report["hard_gates"]["failed_count"] == 0

    counts = report["soft_indicators"]["top1_counts"]
    assert counts == {"pass": 1, "fail": 3, "unknown": 0}

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
