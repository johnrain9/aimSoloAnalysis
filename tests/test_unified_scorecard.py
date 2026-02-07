"""Tests for unified scorecard builder per TA v1.0 contract."""

import json
from pathlib import Path
from unittest import mock

import pytest

from tools import unified_scorecard as sb


class TestLoadSubReport:
    """Test sub-report loading with error handling."""

    def test_load_existing_json_report(self, tmp_path):
        """Test loading a valid JSON report."""
        report_file = tmp_path / "test_report.json"
        report_data = {"status": "pass", "data": "test"}
        report_file.write_text(json.dumps(report_data), encoding="utf-8")

        status, report, reason = sb._load_sub_report(report_file, "test")

        assert status == "pass"
        assert report == report_data
        assert "test" in reason

    def test_load_missing_report(self, tmp_path):
        """Test handling of missing report file."""
        report_file = tmp_path / "missing.json"

        status, report, reason = sb._load_sub_report(report_file, "backend")

        assert status == "not_ready"
        assert report is None
        assert "not found" in reason.lower()

    def test_load_malformed_json(self, tmp_path):
        """Test handling of malformed JSON."""
        report_file = tmp_path / "bad.json"
        report_file.write_text("{invalid json", encoding="utf-8")

        status, report, reason = sb._load_sub_report(report_file, "backend")

        assert status == "fail"
        assert report is None
        assert "parse error" in reason.lower()

    def test_explicit_status_from_report(self, tmp_path):
        """Test that explicit status in report is preserved."""
        report_file = tmp_path / "test.json"
        report_file.write_text(json.dumps({"status": "fail"}), encoding="utf-8")

        status, report, reason = sb._load_sub_report(report_file, "test")

        assert status == "fail"

    def test_assume_pass_when_no_status(self, tmp_path):
        """Test that pass is assumed when no status field."""
        report_file = tmp_path / "test.json"
        report_file.write_text(json.dumps({"data": "test"}), encoding="utf-8")

        status, report, reason = sb._load_sub_report(report_file, "test")

        assert status == "pass"
        assert "assuming pass" in reason.lower()


class TestHumanReviewStatusExtraction:
    """Test extraction of human review status from markdown."""

    def test_extract_approved_status(self, tmp_path):
        """Test extracting approved status."""
        packet_file = tmp_path / "packet.md"
        packet_file.write_text("# Review\n\nStatus: **approved**\n\nOther content", encoding="utf-8")

        status = sb._extract_human_review_status(packet_file)

        assert status == "approved"

    def test_extract_rejected_status(self, tmp_path):
        """Test extracting rejected status."""
        packet_file = tmp_path / "packet.md"
        packet_file.write_text("# Review\n\nStatus: **rejected**\n\n", encoding="utf-8")

        status = sb._extract_human_review_status(packet_file)

        assert status == "rejected"

    def test_extract_pending_status(self, tmp_path):
        """Test extracting pending_review status."""
        packet_file = tmp_path / "packet.md"
        packet_file.write_text("# Review\n\nStatus: **pending_review**\n\n", encoding="utf-8")

        status = sb._extract_human_review_status(packet_file)

        assert status == "pending_review"

    def test_map_pass_to_approved(self, tmp_path):
        """Test that pass maps to approved."""
        packet_file = tmp_path / "packet.md"
        packet_file.write_text("Status: **pass**\n", encoding="utf-8")

        status = sb._extract_human_review_status(packet_file)

        assert status == "approved"

    def test_map_fail_to_rejected(self, tmp_path):
        """Test that fail maps to rejected."""
        packet_file = tmp_path / "packet.md"
        packet_file.write_text("Status: **fail**\n", encoding="utf-8")

        status = sb._extract_human_review_status(packet_file)

        assert status == "rejected"

    def test_missing_packet_returns_pending(self, tmp_path):
        """Test that missing packet defaults to pending_review."""
        packet_file = tmp_path / "missing.md"

        status = sb._extract_human_review_status(packet_file)

        assert status == "pending_review"

    def test_no_status_pattern_returns_pending(self, tmp_path):
        """Test that missing status pattern defaults to pending_review."""
        packet_file = tmp_path / "packet.md"
        packet_file.write_text("# Review\n\nNo status here\n", encoding="utf-8")

        status = sb._extract_human_review_status(packet_file)

        assert status == "pending_review"


class TestHardGates:
    """Test hard gate construction per TA v1.0 mapping."""

    def test_gate_a_reflects_backend_status(self):
        """Gate-A reflects backend data integrity status."""
        gates = sb._build_hard_gates(
            backend_status="fail",
            frontend_status="pass",
            top1_status="pass",
            human_review_status="pending_review",
            backend_report=None,
            frontend_report=None,
            top1_report=None,
        )
        gate_a = next(g for g in gates if g["gate_id"] == "Gate-A-DataIntegrity")
        assert gate_a["status"] == "fail"

    def test_gate_e_reflects_top1_status(self):
        """Gate-E reflects top1 P0 behavior status."""
        gates = sb._build_hard_gates(
            backend_status="pass",
            frontend_status="pass",
            top1_status="fail",
            human_review_status="pending_review",
            backend_report=None,
            frontend_report=None,
            top1_report=None,
        )
        gate_e = next(g for g in gates if g["gate_id"] == "Gate-E-P0Behavior")
        assert gate_e["status"] == "fail"

    def test_gate_f_combines_frontend_and_backend(self):
        """Gate-F fails if either frontend or backend fails."""
        # Backend fail, frontend pass
        gates = sb._build_hard_gates(
            backend_status="fail",
            frontend_status="pass",
            top1_status="pass",
            human_review_status="pending_review",
            backend_report=None,
            frontend_report=None,
            top1_report=None,
        )
        gate_f = next(g for g in gates if g["gate_id"] == "Gate-F-EvalHarness")
        assert gate_f["status"] == "fail"

        # Frontend fail, backend pass
        gates = sb._build_hard_gates(
            backend_status="pass",
            frontend_status="fail",
            top1_status="pass",
            human_review_status="pending_review",
            backend_report=None,
            frontend_report=None,
            top1_report=None,
        )
        gate_f = next(g for g in gates if g["gate_id"] == "Gate-F-EvalHarness")
        assert gate_f["status"] == "fail"

        # Both pass
        gates = sb._build_hard_gates(
            backend_status="pass",
            frontend_status="pass",
            top1_status="pass",
            human_review_status="pending_review",
            backend_report=None,
            frontend_report=None,
            top1_report=None,
        )
        gate_f = next(g for g in gates if g["gate_id"] == "Gate-F-EvalHarness")
        assert gate_f["status"] == "pass"

    def test_gate_g_blocked_when_human_review_rejected(self):
        """Gate-G is blocked if human review is rejected."""
        gates = sb._build_hard_gates(
            backend_status="pass",
            frontend_status="pass",
            top1_status="pass",
            human_review_status="rejected",
            backend_report=None,
            frontend_report=None,
            top1_report=None,
        )
        gate_g = next(g for g in gates if g["gate_id"] == "Gate-G-QualityModel")
        assert gate_g["status"] == "blocked"

    def test_gate_g_not_ready_when_human_review_pending(self):
        """Gate-G is not_ready if human review is pending_review."""
        gates = sb._build_hard_gates(
            backend_status="pass",
            frontend_status="pass",
            top1_status="pass",
            human_review_status="pending_review",
            backend_report=None,
            frontend_report=None,
            top1_report=None,
        )
        gate_g = next(g for g in gates if g["gate_id"] == "Gate-G-QualityModel")
        assert gate_g["status"] == "not_ready"

    def test_gate_g_pass_when_human_review_approved(self):
        """Gate-G is pass if human review is approved."""
        gates = sb._build_hard_gates(
            backend_status="pass",
            frontend_status="pass",
            top1_status="pass",
            human_review_status="approved",
            backend_report=None,
            frontend_report=None,
            top1_report=None,
        )
        gate_g = next(g for g in gates if g["gate_id"] == "Gate-G-QualityModel")
        assert gate_g["status"] == "pass"

    def test_all_seven_gates_present(self):
        """Verify all 7 gates are created."""
        gates = sb._build_hard_gates(
            backend_status="pass",
            frontend_status="pass",
            top1_status="pass",
            human_review_status="approved",
            backend_report=None,
            frontend_report=None,
            top1_report=None,
        )

        gate_ids = [g["gate_id"] for g in gates]
        expected_ids = [
            "Gate-A-DataIntegrity",
            "Gate-B-APIUIContract",
            "Gate-C-UnitConsistency",
            "Gate-D-TestSuite",
            "Gate-E-P0Behavior",
            "Gate-F-EvalHarness",
            "Gate-G-QualityModel",
        ]
        assert gate_ids == expected_ids


class TestRollupLogic:
    """Test overall status rollup per TA v1.0 precedence rules."""

    def test_fail_precedence(self):
        """If any gate fails, overall is fail."""
        gates = [
            {"gate_id": "A", "status": "pass"},
            {"gate_id": "B", "status": "fail"},
            {"gate_id": "C", "status": "not_ready"},
        ]
        overall = sb._rollup_overall_status(gates)
        assert overall == "fail"

    def test_blocked_precedence_over_not_ready(self):
        """If any gate blocked (and none fail), overall is blocked."""
        gates = [
            {"gate_id": "A", "status": "pass"},
            {"gate_id": "B", "status": "blocked"},
            {"gate_id": "C", "status": "not_ready"},
        ]
        overall = sb._rollup_overall_status(gates)
        assert overall == "blocked"

    def test_not_ready_when_no_fail_or_blocked(self):
        """If any gate not_ready (and none fail/blocked), overall is not_ready."""
        gates = [
            {"gate_id": "A", "status": "pass"},
            {"gate_id": "B", "status": "not_ready"},
        ]
        overall = sb._rollup_overall_status(gates)
        assert overall == "not_ready"

    def test_pass_when_all_pass(self):
        """If all gates pass, overall is pass."""
        gates = [
            {"gate_id": "A", "status": "pass"},
            {"gate_id": "B", "status": "pass"},
        ]
        overall = sb._rollup_overall_status(gates)
        assert overall == "pass"


class TestSoftMetrics:
    """Test soft metric extraction."""

    def test_extract_backend_latency_metrics(self):
        """Extract backend latency p95 and mean."""
        backend_report = {
            "latency_summary": {
                "p95_ms": 815.31,
                "mean_ms": 516.57,
            }
        }

        metrics = sb._extract_soft_metrics(backend_report, None, None)

        p95_metric = next(m for m in metrics if m["metric_id"] == "backend-latency-p95")
        assert p95_metric["value"] == 815.31
        assert p95_metric["threshold"] == 1000.0
        assert p95_metric["status"] == "ok"

        mean_metric = next(m for m in metrics if m["metric_id"] == "backend-latency-mean")
        assert mean_metric["value"] == 516.57
        assert mean_metric["status"] == "ok"

    def test_latency_warn_status_when_exceeds_threshold(self):
        """Latency metric is warn when exceeds threshold."""
        backend_report = {
            "latency_summary": {
                "p95_ms": 1500.0,
                "mean_ms": 700.0,
            }
        }

        metrics = sb._extract_soft_metrics(backend_report, None, None)

        p95_metric = next(m for m in metrics if m["metric_id"] == "backend-latency-p95")
        assert p95_metric["status"] == "warn"

        mean_metric = next(m for m in metrics if m["metric_id"] == "backend-latency-mean")
        assert mean_metric["status"] == "warn"

    def test_extract_frontend_runtime_metric(self):
        """Extract frontend runtime metric."""
        frontend_report = {
            "runtime_ms": 0.767,
        }

        metrics = sb._extract_soft_metrics(None, frontend_report, None)

        runtime_metric = next(m for m in metrics if m["metric_id"] == "frontend-runtime-ms")
        assert runtime_metric["value"] == 0.767
        assert runtime_metric["threshold"] == 5.0
        assert runtime_metric["status"] == "ok"

    def test_extract_top1_pass_rate_metric(self):
        """Extract top1 pass rate from soft_indicators."""
        top1_report = {
            "soft_indicators": {
                "top1_counts": {
                    "pass": 28,
                    "fail": 0,
                }
            }
        }

        metrics = sb._extract_soft_metrics(None, None, top1_report)

        pass_rate_metric = next(m for m in metrics if m["metric_id"] == "top1-pass-rate")
        assert pass_rate_metric["value"] == 1.0
        assert pass_rate_metric["threshold"] == 0.95
        assert pass_rate_metric["status"] == "ok"

    def test_pass_rate_warn_when_below_threshold(self):
        """Pass rate metric is warn when below 95%."""
        top1_report = {
            "soft_indicators": {
                "top1_counts": {
                    "pass": 90,
                    "fail": 10,
                }
            }
        }

        metrics = sb._extract_soft_metrics(None, None, top1_report)

        pass_rate_metric = next(m for m in metrics if m["metric_id"] == "top1-pass-rate")
        assert pass_rate_metric["value"] == 0.9
        assert pass_rate_metric["status"] == "warn"


class TestScorecardSchema:
    """Test unified scorecard schema compliance."""

    def test_scorecard_has_required_fields(self):
        """Verify all required top-level fields."""
        scorecard = sb._build_scorecard(
            backend_status="pass",
            backend_report=None,
            backend_reason="test",
            frontend_status="pass",
            frontend_report=None,
            frontend_reason="test",
            top1_status="pass",
            top1_report=None,
            top1_reason="test",
            human_review_status="approved",
        )

        assert "scorecard_version" in scorecard
        assert scorecard["scorecard_version"] == "1.0"
        assert "timestamp" in scorecard
        assert "overall_status" in scorecard
        assert "hard_gates" in scorecard
        assert "soft_metrics" in scorecard
        assert "sub_reports" in scorecard

    def test_gate_has_required_fields(self):
        """Verify gate objects have required fields."""
        scorecard = sb._build_scorecard(
            backend_status="pass",
            backend_report=None,
            backend_reason="test",
            frontend_status="pass",
            frontend_report=None,
            frontend_reason="test",
            top1_status="pass",
            top1_report=None,
            top1_reason="test",
            human_review_status="approved",
        )

        for gate in scorecard["hard_gates"]:
            assert "gate_id" in gate
            assert "status" in gate
            assert "reason" in gate
            # evidence is optional but should be present
            assert "evidence" in gate

    def test_metric_has_required_fields(self):
        """Verify metric objects have required fields."""
        backend_report = {
            "latency_summary": {
                "p95_ms": 815.31,
            }
        }
        scorecard = sb._build_scorecard(
            backend_status="pass",
            backend_report=backend_report,
            backend_reason="test",
            frontend_status="pass",
            frontend_report=None,
            frontend_reason="test",
            top1_status="pass",
            top1_report=None,
            top1_reason="test",
            human_review_status="approved",
        )

        for metric in scorecard["soft_metrics"]:
            assert "metric_id" in metric
            assert "value" in metric
            assert "status" in metric

    def test_sub_reports_has_all_four_reports(self):
        """Verify sub_reports contains all 4 sub-reports."""
        scorecard = sb._build_scorecard(
            backend_status="pass",
            backend_report={},
            backend_reason="test",
            frontend_status="pass",
            frontend_report={},
            frontend_reason="test",
            top1_status="pass",
            top1_report={},
            top1_reason="test",
            human_review_status="approved",
        )

        sub_reports = scorecard["sub_reports"]
        assert "backend" in sub_reports
        assert "frontend" in sub_reports
        assert "top1" in sub_reports
        assert "human_review" in sub_reports

    def test_sub_report_has_path_and_status(self):
        """Verify each sub-report has path and status."""
        scorecard = sb._build_scorecard(
            backend_status="pass",
            backend_report={},
            backend_reason="test",
            frontend_status="pass",
            frontend_report={},
            frontend_reason="test",
            top1_status="pass",
            top1_report={},
            top1_reason="test",
            human_review_status="approved",
        )

        for sub_report in scorecard["sub_reports"].values():
            assert "path" in sub_report
            assert "status" in sub_report


class TestIntegrationWithGoldenExamples:
    """Integration tests using provided golden examples."""

    def test_pass_example_output_matches_schema(self):
        """Test that golden pass example matches TA v1.0 schema."""
        # Load the golden example
        example_path = Path("docs/examples/scorecard_example_pass.json")
        if not example_path.exists():
            pytest.skip("Golden example not found")

        golden = json.loads(example_path.read_text(encoding="utf-8"))

        # Verify schema
        assert golden["scorecard_version"] == "1.0"
        assert golden["overall_status"] == "pass"
        assert len(golden["hard_gates"]) == 7
        assert all(g["status"] in ("pass", "fail", "blocked", "not_ready") for g in golden["hard_gates"])

    def test_fail_example_output_matches_schema(self):
        """Test that golden fail example matches TA v1.0 schema."""
        example_path = Path("docs/examples/scorecard_example_fail.json")
        if not example_path.exists():
            pytest.skip("Golden example not found")

        golden = json.loads(example_path.read_text(encoding="utf-8"))

        # Verify schema
        assert golden["scorecard_version"] == "1.0"
        assert golden["overall_status"] == "fail"
        assert len(golden["hard_gates"]) == 7

    def test_blocked_example_output_matches_schema(self):
        """Test that golden blocked example matches TA v1.0 schema."""
        example_path = Path("docs/examples/scorecard_example_blocked.json")
        if not example_path.exists():
            pytest.skip("Golden example not found")

        golden = json.loads(example_path.read_text(encoding="utf-8"))

        # Verify schema
        assert golden["scorecard_version"] == "1.0"
        assert golden["overall_status"] == "blocked"
        assert len(golden["hard_gates"]) == 7


class TestErrorHandling:
    """Test error handling per TA v1.0 failure states."""

    def test_missing_backend_report_sets_gates_to_not_ready(self, tmp_path):
        """Missing backend report sets A-D gates to not_ready."""
        # Create temp directory with missing backend report
        frontend_path = tmp_path / "frontend.json"
        frontend_path.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

        top1_path = tmp_path / "top1.json"
        top1_path.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

        packet_path = tmp_path / "packet.md"
        packet_path.write_text("Status: **approved**", encoding="utf-8")

        # Load with missing backend
        backend_status, _, _ = sb._load_sub_report(tmp_path / "missing.json", "backend")

        assert backend_status == "not_ready"

    def test_malformed_json_report_sets_gate_to_fail(self, tmp_path):
        """Malformed JSON report sets gate to fail."""
        bad_report = tmp_path / "bad.json"
        bad_report.write_text("not valid json", encoding="utf-8")

        status, _, reason = sb._load_sub_report(bad_report, "backend")

        assert status == "fail"
        assert "parse error" in reason.lower()

    def test_overall_status_fail_when_any_gate_fails(self):
        """Overall status is fail when any gate fails."""
        scorecard = sb._build_scorecard(
            backend_status="fail",  # This will fail gates A-D
            backend_report=None,
            backend_reason="test",
            frontend_status="pass",
            frontend_report=None,
            frontend_reason="test",
            top1_status="pass",
            top1_report=None,
            top1_reason="test",
            human_review_status="approved",
        )

        assert scorecard["overall_status"] == "fail"


class TestTimestamp:
    """Test timestamp generation."""

    def test_timestamp_is_iso8601_utc(self):
        """Scorecard timestamp is ISO8601 UTC format."""
        scorecard = sb._build_scorecard(
            backend_status="pass",
            backend_report=None,
            backend_reason="test",
            frontend_status="pass",
            frontend_report=None,
            frontend_reason="test",
            top1_status="pass",
            top1_report=None,
            top1_reason="test",
            human_review_status="approved",
        )

        timestamp = scorecard["timestamp"]
        # Should match ISO8601 format with Z suffix (UTC)
        assert timestamp.endswith("Z")
        assert "T" in timestamp
        # Should be parseable
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert dt is not None
