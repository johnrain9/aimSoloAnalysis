# Truth Artifact: Unified Scorecard Contract v1.0

**Status**: Draft for Planner Review
**Created**: 2026-02-07
**Requirements**: RQ-EVAL-006, RQ-EVAL-007, RQ-EVAL-010, RQ-NFR-006

## Purpose

Define the unified scorecard contract that combines backend quality, top-1 quality, frontend rendering, and human review status into one release-gating artifact enabling automated AI-driven iteration with clear go/no-go decisions.

## Schema Definition

### Top-Level Fields

```json
{
  "scorecard_version": "1.0",           // string, schema version
  "timestamp": "2026-02-07T12:00:00Z",  // ISO8601 timestamp
  "overall_status": "pass",              // enum: pass|fail|blocked|not_ready
  "hard_gates": [...],                   // array of gate objects
  "soft_metrics": [...],                 // array of metric objects
  "sub_reports": {...}                   // object with backend/frontend/top1/human_review keys
}
```

### Gate Object Schema (Hard Gates)

```json
{
  "gate_id": "Gate-A-DataIntegrity",    // string, unique gate identifier
  "status": "pass",                      // enum: pass|fail|blocked|not_ready
  "reason": "No high severity defects", // string, human-readable explanation
  "evidence": {...}                      // object, references sub-report or specific check
}
```

**Required Fields**: gate_id, status, reason
**Optional Fields**: evidence

### Metric Object Schema (Soft Metrics)

```json
{
  "metric_id": "backend-latency-p95",   // string, unique metric identifier
  "value": 815.31,                       // number|string, measured value
  "threshold": 1000.0,                   // number, optional threshold for ok/warn/advisory
  "status": "ok"                         // enum: ok|warn|advisory
}
```

**Required Fields**: metric_id, value, status
**Optional Fields**: threshold

### Sub-Reports Object Schema

```json
{
  "backend": {
    "path": "artifacts/eval_backend_report.json",  // string, artifact path
    "status": "fail",                               // enum: pass|fail|not_ready
    "key_metrics": {...}                            // optional summary object
  },
  "frontend": {
    "path": "artifacts/frontend_eval_report.json",
    "status": "pass",
    "key_metrics": {...}
  },
  "top1": {
    "path": "artifacts/top1_aggregated_report.json",
    "status": "pass",
    "key_metrics": {...}
  },
  "human_review": {
    "path": "artifacts/top1_review_packet.md",
    "status": "pending_review",                     // enum: approved|pending_review|rejected
    "key_metrics": {...}
  }
}
```

## Rollup Decision Rules

**Precedence Order** (highest to lowest):
1. If any hard gate is **fail** → overall_status = **fail**
2. If any hard gate is **blocked** → overall_status = **blocked**
3. If any hard gate is **not_ready** → overall_status = **not_ready**
4. If all hard gates are **pass** → overall_status = **pass**

**Soft Metrics**: Do not affect overall_status, advisory only.

## Release Gates A-G Mapping

| Gate ID | Gate Name | Description | Evidence Source |
|---------|-----------|-------------|-----------------|
| Gate-A-DataIntegrity | Data Integrity | No high severity data-integrity defects open | sub_reports.backend.status = pass |
| Gate-B-APIUIContract | API/UI Contract | API/UI compare contract aligned and tested | sub_reports.backend.status = pass |
| Gate-C-UnitConsistency | Unit Consistency | Unit declarations consistent across API responses | sub_reports.backend.status = pass |
| Gate-D-TestSuite | Test Suite Pass | Test suite and trend harness pass in documented local command set | sub_reports.backend.status = pass |
| Gate-E-P0Behavior | P0 Behavior | P0 behavior outputs satisfy RQ-P0-005 through RQ-P0-029 | sub_reports.top1.status = pass |
| Gate-F-EvalHarness | Eval Harness | Unified evaluation harness is in place and passing | sub_reports.frontend.status = pass AND sub_reports.backend.status = pass |
| Gate-G-QualityModel | Quality Model | Product-behavior evaluation model is active | sub_reports.top1.status = pass AND sub_reports.human_review.status != rejected |

## Artifact Path Conventions

### Input Artifacts
- Backend report: `artifacts/eval_backend_report.json`
- Frontend report: `artifacts/frontend_eval_report.json`
- Top-1 report: `artifacts/top1_aggregated_report.json`
- Review packet: `artifacts/top1_review_packet.md`

### Output Artifact
- Unified scorecard: `artifacts/unified_scorecard.json`

## Failure States and Fallback Behavior

### Missing Sub-Report
- If any sub-report artifact is missing → corresponding gate status = **not_ready**
- Overall status follows rollup precedence rules

### Malformed Sub-Report
- If sub-report JSON is malformed → gate status = **fail**, reason includes parse error
- Overall status = **fail**

### Human Review States
- `pending_review` → Gate-G status = **not_ready** (non-blocking for automated iteration)
- `approved` → Gate-G status = **pass**
- `rejected` → Gate-G status = **fail**

## Golden Examples

See `docs/examples/`:
- `scorecard_example_pass.json` – All gates pass, ready for release
- `scorecard_example_fail.json` – Single hard gate fails (Gate-A), blocks release
- `scorecard_example_blocked.json` – Gate blocked due to external dependency

## Version History

- **v1.0** (2026-02-07): Initial contract definition for planner freeze approval
