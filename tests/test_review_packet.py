import csv
import json
from pathlib import Path

from tools import build_top1_review_packet as packet
from tools import eval_top1_scorecard


def test_review_packet_deterministic_sampling_and_required_columns(tmp_path: Path):
    report = Path("tests/fixtures/top1_review_report.json")
    traces = Path("tests/fixtures/top1_review_traces.jsonl")
    out_md_1 = tmp_path / "packet1.md"
    out_csv_1 = tmp_path / "packet1.csv"
    out_md_2 = tmp_path / "packet2.md"
    out_csv_2 = tmp_path / "packet2.csv"

    result1 = packet.build_review_packet(
        report_path=report,
        traces_path=traces,
        output_md=out_md_1,
        output_csv=out_csv_1,
        sample_size=5,
        seed=123,
    )
    result2 = packet.build_review_packet(
        report_path=report,
        traces_path=traces,
        output_md=out_md_2,
        output_csv=out_csv_2,
        sample_size=5,
        seed=123,
    )

    assert result1["status"] == "pass"
    assert result2["status"] == "pass"

    rows1 = list(csv.DictReader(out_csv_1.open("r", encoding="utf-8")))
    rows2 = list(csv.DictReader(out_csv_2.open("r", encoding="utf-8")))
    assert [row["case_id"] for row in rows1] == [row["case_id"] for row in rows2]

    for column in (
        "recommendation_text",
        "evidence_summary",
        "gate_reasons",
        "risk_tier",
        "reviewer_verdict",
        "reviewer_notes",
    ):
        assert column in rows1[0]


def test_review_packet_bias_includes_failures_outliers_and_some_passes(tmp_path: Path):
    report = Path("tests/fixtures/top1_review_report.json")
    traces = Path("tests/fixtures/top1_review_traces.jsonl")
    out_md = tmp_path / "packet.md"
    out_csv = tmp_path / "packet.csv"

    result = packet.build_review_packet(
        report_path=report,
        traces_path=traces,
        output_md=out_md,
        output_csv=out_csv,
        sample_size=5,
        seed=7,
    )

    assert result["status"] == "pass"
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))

    fail_count = len([row for row in rows if row["source_status"] == "fail"])
    pass_count = len([row for row in rows if row["source_status"] == "pass"])
    outlier_count = len([row for row in rows if float(row["outlier_score"]) >= 0.5])

    assert fail_count >= 1
    assert outlier_count >= 1
    assert pass_count >= 1

    md_text = out_md.read_text(encoding="utf-8")
    assert "RQ-EVAL-011" in md_text
    assert "RQ-EVAL-012" in md_text
    assert "RQ-NFR-007" in md_text


def test_review_packet_missing_inputs_writes_minimal_failure_artifacts(tmp_path: Path):
    out_md = tmp_path / "packet.md"
    out_csv = tmp_path / "packet.csv"

    result = packet.build_review_packet(
        report_path=tmp_path / "missing_report.json",
        traces_path=tmp_path / "missing_traces.jsonl",
        output_md=out_md,
        output_csv=out_csv,
        sample_size=3,
        seed=11,
    )

    assert result["status"] == "fail"
    assert out_md.exists()
    assert out_csv.exists()

    md_text = out_md.read_text(encoding="utf-8")
    assert "Generation Errors" in md_text
    assert "Missing aggregated report" in md_text

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["case_id"] == "ERROR"
    assert "blocked_missing_inputs" == rows[0]["disposition"]


def test_default_chain_scorecard_to_review_packet_interoperability(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    trace_path = artifacts / "top1_traces.jsonl"
    rows = [
        {
            "trace_id": "t-pass",
            "case_id": "t-pass",
            "top1_pass": True,
            "rule_id": "RULE_A",
            "risk_tier": "Primary",
            "expected_gain_s": 0.3,
            "recommendation_text": "Keep turn-in point",
            "evidence_summary": "Stable confidence-weighted gain",
        },
        {
            "trace_id": "t-fail",
            "case_id": "t-fail",
            "top1_pass": False,
            "failure_reason": "missing_success_check",
            "rule_id": "RULE_B",
            "risk_tier": "Blocked",
            "expected_gain_s": -0.1,
            "recommendation_text": "Do not apply until verified",
            "evidence_summary": "Missing success check",
        },
    ]
    trace_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    score_exit = eval_top1_scorecard.main([])
    assert score_exit == 0

    review_exit = packet.main([])
    assert review_exit == 0

    out_md = artifacts / "top1_review_packet.md"
    out_csv = artifacts / "top1_review_packet.csv"
    assert out_md.exists()
    assert out_csv.exists()

    packet_rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert {row["case_id"] for row in packet_rows} == {"t-pass", "t-fail"}
