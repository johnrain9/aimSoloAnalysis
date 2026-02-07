"""Canonical artifact contract for the top-1 evaluation default CLI chain."""

from __future__ import annotations

from pathlib import Path

ARTIFACTS_DIR = Path("artifacts")

# Canonical default chain: batch traces -> scorecard report -> review packet.
DEFAULT_TOP1_TRACE_PATH = ARTIFACTS_DIR / "top1_traces.jsonl"
DEFAULT_TOP1_SCORECARD_PATH = ARTIFACTS_DIR / "top1_aggregated_report.json"

# Legacy paths kept for practical backward compatibility.
LEGACY_BATCH_REPORT_PATH = ARTIFACTS_DIR / "eval_top1_batch_report.json"
LEGACY_SCORECARD_INPUT_PATH = ARTIFACTS_DIR / "top1_session_traces.jsonl"
LEGACY_SCORECARD_REPORT_PATH = ARTIFACTS_DIR / "eval_top1_quality_report.json"
