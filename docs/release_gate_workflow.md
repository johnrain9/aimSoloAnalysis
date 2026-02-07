# Release Gate Workflow

## Overview

The release gate workflow is an end-to-end automated verification pipeline that validates the full coaching recommendation system before deployment. It combines four independent evaluation sub-reports into a unified decision via TA v1.0 contract.

**Purpose**: Prevent silent failures in AI-driven iteration by systematically validating data integrity, API contracts, performance, and coaching recommendations.

**Related Requirements**: RQ-EVAL-007, RQ-NFR-005, RQ-NFR-006

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Release Gate Workflow                      │
└─────────────────────────────────────────────────────────────────┘

1. Sub-Report Generation (4 parallel harnesses)
   ├── Backend Eval Harness → eval_backend_report.json
   ├── Frontend Eval Harness → frontend_eval_report.json
   ├── Top-1 Quality Eval → top1_aggregated_report.json
   └── Human Review Packet → top1_review_packet.md

2. Unified Scorecard Builder
   └── tools/unified_scorecard.py
       ├── Load all 4 sub-reports
       ├── Extract statuses & metrics
       ├── Apply TA v1.0 gate logic
       └── Compute overall_status via rollup rules

3. Decision Logic (7 Hard Gates)
   ├── Gate-A: Data Integrity (backend status)
   ├── Gate-B: API/UI Contract (backend status)
   ├── Gate-C: Unit Consistency (backend status)
   ├── Gate-D: Test Suite (backend status)
   ├── Gate-E: P0 Behavior (top1 status)
   ├── Gate-F: Eval Harness (frontend AND backend)
   └── Gate-G: Quality Model (top1 AND human_review)

4. Rollup Precedence (Highest to Lowest)
   1. fail → overall = fail
   2. blocked → overall = blocked
   3. not_ready → overall = not_ready
   4. pass → overall = pass
```

## Three Golden Scenarios

### Scenario 1: All Pass (Release Ready)

**Condition**: All sub-reports pass, human review approved

**Commands**:
```bash
# 1. Run all evaluation harnesses
$env:PYTHONPATH='.'; python tools/eval_backend.py
$env:PYTHONPATH='.'; python tools/eval_frontend.py
$env:PYTHONPATH='.'; python tools/eval_top1_batch.py --input-corpus artifacts/top1_traces.jsonl
$env:PYTHONPATH='.'; python tools/eval_top1_scorecard.py --input-path artifacts/top1_aggregated_report.json

# 2. Manually approve human review (edit artifacts/top1_review_packet.md, set Status: **approved**)

# 3. Build unified scorecard
$env:PYTHONPATH='.'; python tools/unified_scorecard.py

# 4. Check result
cat artifacts/unified_scorecard.json | jq .overall_status
# Output: "pass"
```

**Expected Output**:
```json
{
  "scorecard_version": "1.0",
  "overall_status": "pass",
  "hard_gates": [
    {"gate_id": "Gate-A-DataIntegrity", "status": "pass"},
    {"gate_id": "Gate-B-APIUIContract", "status": "pass"},
    {"gate_id": "Gate-C-UnitConsistency", "status": "pass"},
    {"gate_id": "Gate-D-TestSuite", "status": "pass"},
    {"gate_id": "Gate-E-P0Behavior", "status": "pass"},
    {"gate_id": "Gate-F-EvalHarness", "status": "pass"},
    {"gate_id": "Gate-G-QualityModel", "status": "pass"}
  ]
}
```

**Next Steps**: Proceed with release/deployment.

---

### Scenario 2: Single Gate Failure (Release Blocked)

**Condition**: One or more sub-reports fail (e.g., baseline mismatch)

**Commands**:
```bash
# 1. Run all harnesses
$env:PYTHONPATH='.'; python tools/eval_backend.py
# ... (all harnesses)

# 2. Check backend report status
cat artifacts/eval_backend_report.json | jq .status
# Output: "fail"

# 3. Build unified scorecard (will include failure)
$env:PYTHONPATH='.'; python tools/unified_scorecard.py

# 4. Check result
cat artifacts/unified_scorecard.json | jq '.overall_status'
# Output: "fail"

# 5. Inspect failure details
cat artifacts/unified_scorecard.json | jq '.hard_gates[] | select(.status=="fail")'
# Output:
# {
#   "gate_id": "Gate-A-DataIntegrity",
#   "status": "fail",
#   "reason": "Data Integrity check failed (baseline comparison)"
# }
```

**Expected Outcome**:
- `overall_status` = "fail"
- One or more hard gates fail
- Rollup precedence ensures fail wins over pass/blocked/not_ready

**Next Steps**:
1. Investigate root cause in failing sub-report (check baseline_comparison, latency, unit consistency)
2. Fix underlying issue
3. Re-run harnesses
4. Rebuild scorecard

---

### Scenario 3: Human Review Blocked (Safety Gate)

**Condition**: Human review rejects recommendations (safety concern)

**Commands**:
```bash
# 1. Run all harnesses including human review
$env:PYTHONPATH='.'; python tools/eval_backend.py
$env:PYTHONPATH='.'; python tools/eval_frontend.py
$env:PYTHONPATH='.'; python tools/eval_top1_batch.py
$env:PYTHONPATH='.'; python tools/eval_top1_scorecard.py
$env:PYTHONPATH='.'; python tools/build_top1_review_packet.py

# 2. Human coach reviews and rejects (edits top1_review_packet.md)
# Set: Status: **rejected**
# Add rejection reason in packet

# 3. Build unified scorecard
$env:PYTHONPATH='.'; python tools/unified_scorecard.py

# 4. Check result
cat artifacts/unified_scorecard.json | jq '.overall_status'
# Output: "blocked"

# 5. Inspect Gate-G decision
cat artifacts/unified_scorecard.json | jq '.hard_gates[] | select(.gate_id=="Gate-G-QualityModel")'
# Output:
# {
#   "gate_id": "Gate-G-QualityModel",
#   "status": "blocked",
#   "reason": "Human review flagged unsafe recommendations",
#   "evidence": {"human_review_status": "rejected"}
# }
```

**Expected Outcome**:
- `overall_status` = "blocked"
- Gate-G status = "blocked" (human_review_status = "rejected")
- Release is prevented until human concerns are resolved

**Next Steps**:
1. Review rejection reason in human review packet
2. Address safety or quality concerns identified
3. Re-run top1 harness to recompute recommendations
4. Rebuild human review packet
5. Update human review status to "approved"
6. Rebuild scorecard

---

## Edge Cases

### Edge Case 1: Missing Sub-Report (Graceful Degradation)

**Condition**: One or more sub-reports not found

**Behavior**:
- Missing report → sub-report status = "not_ready"
- Gates depending on missing report degrade to "not_ready"
- Rollup precedence makes overall = "not_ready"

**Example**:
```bash
# If eval_backend_report.json is missing:
$env:PYTHONPATH='.'; python tools/unified_scorecard.py
# → Gates A-D: not_ready
# → overall_status: not_ready

cat artifacts/unified_scorecard.json | jq '.sub_reports.backend'
# {
#   "path": "artifacts/eval_backend_report.json",
#   "status": "not_ready",
#   "reason": "artifact not found"
# }
```

### Edge Case 2: Malformed JSON (Parse Error)

**Condition**: Sub-report contains invalid JSON

**Behavior**:
- Malformed JSON → sub-report status = "fail"
- Gate depending on malformed report fails
- Overall status = "fail"

**Example**:
```bash
# If eval_backend_report.json is corrupted:
$env:PYTHONPATH='.'; python tools/unified_scorecard.py
# → Gates A-D: fail
# → overall_status: fail

cat artifacts/unified_scorecard.json | jq '.sub_reports.backend'
# {
#   "path": "artifacts/eval_backend_report.json",
#   "status": "fail",
#   "reason": "JSON parse error: Expecting value"
# }
```

### Edge Case 3: Human Review Pending (Not Yet Reviewed)

**Condition**: Human review packet exists but status not set

**Behavior**:
- Missing status line → defaults to "pending_review"
- Gate-G status = "not_ready" (if top1 pass)
- Overall status = "not_ready" (cannot release until reviewed)

**Example**:
```bash
# If top1_review_packet.md has no Status: **status** line:
$env:PYTHONPATH='.'; python tools/unified_scorecard.py

cat artifacts/unified_scorecard.json | jq '.hard_gates[] | select(.gate_id=="Gate-G-QualityModel")'
# {
#   "gate_id": "Gate-G-QualityModel",
#   "status": "not_ready",
#   "reason": "Quality Model check not ready (human review: pending_review)"
# }
```

---

## Soft Metrics (Advisory, Non-Blocking)

The scorecard includes soft metrics that provide visibility into performance and quality trends without blocking release:

```json
{
  "soft_metrics": [
    {
      "metric_id": "backend-latency-p95",
      "value": 815.31,
      "threshold": 1000.0,
      "status": "ok"
    },
    {
      "metric_id": "frontend-runtime-ms",
      "value": 0.77,
      "threshold": 5.0,
      "status": "ok"
    },
    {
      "metric_id": "top1-pass-rate",
      "value": 0.96,
      "threshold": 0.95,
      "status": "ok"
    }
  ]
}
```

**Note**: Soft metrics warn but do not trigger release gate failure. Use for performance monitoring and trend analysis.

---

## Workflow Commands Reference

### Full End-to-End Release Check

```bash
# 1. Run all evaluation harnesses
$env:PYTHONPATH='.'; python tools/eval_backend.py
$env:PYTHONPATH='.'; python tools/eval_frontend.py
$env:PYTHONPATH='.'; python tools/eval_top1_batch.py
$env:PYTHONPATH='.'; python tools/eval_top1_scorecard.py
$env:PYTHONPATH='.'; python tools/build_top1_review_packet.py

# 2. (Optional) Human review: edit artifacts/top1_review_packet.md to set Status: **approved** or **rejected**

# 3. Build unified scorecard
$env:PYTHONPATH='.'; python tools/unified_scorecard.py

# 4. Inspect results
cat artifacts/unified_scorecard.json | jq .
```

### Scorecard Builder with Custom Paths

```bash
$env:PYTHONPATH='.'; python tools/unified_scorecard.py `
  --backend-report artifacts/eval_backend_report.json `
  --frontend-report artifacts/frontend_eval_report.json `
  --top1-report artifacts/top1_aggregated_report.json `
  --human-review-packet artifacts/top1_review_packet.md `
  --output artifacts/unified_scorecard.json
```

### Quick Status Check

```bash
# Just check overall_status
cat artifacts/unified_scorecard.json | jq '.overall_status'

# List all gate statuses
cat artifacts/unified_scorecard.json | jq '.hard_gates[] | {gate_id, status}'

# Find any failing gates
cat artifacts/unified_scorecard.json | jq '.hard_gates[] | select(.status=="fail")'
```

---

## Testing the Workflow

Run end-to-end integration tests:

```bash
# Run workflow tests
pytest tests/test_release_gate_workflow.py -v

# Run all scorecard tests (including unit tests)
pytest tests/test_unified_scorecard.py tests/test_release_gate_workflow.py -v

# Run specific golden scenario test
pytest tests/test_release_gate_workflow.py::TestReleaseGateWorkflowE2E::test_golden_scenario_all_pass -v
```

---

## TA v1.0 Schema Reference

### Scorecard Top-Level Structure

```json
{
  "scorecard_version": "1.0",
  "timestamp": "2026-02-07T12:00:00Z",
  "overall_status": "pass|fail|blocked|not_ready",
  "hard_gates": [...],
  "soft_metrics": [...],
  "sub_reports": {...}
}
```

### Hard Gate Structure

```json
{
  "gate_id": "Gate-A-DataIntegrity|Gate-B-APIUIContract|...",
  "status": "pass|fail|blocked|not_ready",
  "reason": "Human-readable explanation",
  "evidence": {
    "sub_report": "backend|frontend|top1|human_review",
    "check": "path.to.metric",
    "...": "Additional context"
  }
}
```

### Sub-Report Structure

```json
{
  "backend": {
    "path": "artifacts/eval_backend_report.json",
    "status": "pass|fail|not_ready",
    "key_metrics": {
      "entries": 21,
      "failures": 0,
      "latency_p95_ms": 815.31
    }
  }
}
```

---

## Troubleshooting

| Symptom | Root Cause | Solution |
|---------|-----------|----------|
| `overall_status` = "fail" | Backend harness failure or baseline mismatch | Check `eval_backend_report.json` for baseline_comparison.status |
| `overall_status` = "blocked" | Human review rejected recommendations | Check human review packet for rejection reason; address safety concern |
| `overall_status` = "not_ready" | Sub-report missing or human review pending | Run missing harness or complete human review |
| `overall_status` = "pass" but Gate-G = "not_ready" | Human review not yet completed | Have human coach complete review and set status in packet |
| Malformed JSON parse error | Corrupt sub-report file | Re-run corresponding harness to regenerate artifact |

---

## Related Documentation

- **TA v1.0 Contract**: Defines unified scorecard schema and gate logic
- **TASK-SCORECARD-02**: Implementation of unified scorecard builder
- **eval_backend.py**: Backend evaluation harness
- **eval_frontend.py**: Frontend evaluation harness
- **eval_top1_batch.py**: Top-1 trace harness
- **eval_top1_scorecard.py**: Top-1 aggregated scorecard
- **build_top1_review_packet.py**: Human review packet generator

---

## Release Gate Matrix

| All Harnesses | Human Review | overall_status | Can Release? |
|---------------|--------------|-----------------|-------------|
| pass | approved | **pass** | ✅ Yes |
| pass | rejected | **blocked** | ❌ No (Safety) |
| pass | pending | **not_ready** | ❌ No (Incomplete) |
| fail | approved | **fail** | ❌ No (Quality) |
| fail | rejected | **fail** | ❌ No (Quality) |
| not_ready | - | **not_ready** | ❌ No (Incomplete) |

---

## Historical Examples

See `docs/examples/` for golden scorecard outputs:
- `scorecard_example_pass.json` - All gates pass, ready to release
- `scorecard_example_fail.json` - Backend data integrity failure, release blocked
- `scorecard_example_blocked.json` - Human review rejection, safety gate blocking release
