Reasoning mode: gpt-codex5.3 - Eval harness and scorecard gating are deterministic plumbing/reporting updates.

# Task Delegation Prompt - TASK-P0-14

## 1) Role and Boundaries
- Implement only eval-gate scope for did-vs-should quality checks.
- No unrelated refactors.

## 1.1 Branch and Workspace Assignment
- Assigned branch: `feature/task-p0-14-eval-gates`
- Assigned working directory: `C:\Users\Paul\ai\aimSoloAnalysis`

## 2) Task Context
- Objective: Gate did-vs-should coaching quality in eval scorecard with explicit pass/fail checks:
  - numeric delta present
  - causal rationale present
  - measurable success check present
  - unit/corner consistency
- Requirements: `RQ-P0-007`, `RQ-P0-008`, `RQ-P0-024`, `RQ-EVAL-008`
- Areas: `tools/eval_top1_scorecard.py`, `tools/eval_backend.py`, `tests/test_eval_top1_scorecard.py`, `tests/test_eval_backend.py`

## 3) Scope
- In scope:
  - Add quality-gate checks and reporting fields to eval artifacts.
  - Ensure scorecard surfaces gate failures clearly.
  - Add/update tests for gating behavior.
- Out of scope:
  - Insight generation logic changes (covered in prior tasks).
  - UI redesign.

## 4) Constraints
- Preserve existing eval outputs where possible; additive changes preferred.
- Keep report schema backward-compatible if feasible.

## 5) Implementation Requirements
- Required behavior:
  - Scorecard emits explicit check names and pass/fail status for did-vs-should quality.
  - Failures include concise reasons tied to missing semantic components.
  - Checks run as part of default no-arg evaluation chain if applicable.
- Error handling:
  - Missing artifacts should produce clear actionable failure messages.
- Performance:
  - No significant runtime regression in eval tests.

## 6) Verification Requirements
- Run:
  - `pytest tests/test_eval_top1_scorecard.py tests/test_eval_backend.py -v`

## 6.1 Git Discipline
- One focused commit.
- Message: `feat(eval): add did-vs-should coaching quality gates to scorecard`
- Body: `Refs: RQ-P0-007, RQ-P0-008, RQ-P0-024, RQ-EVAL-008`

## 8) Response Format
Use required handoff schema:

```text
[TASK-HANDOFF-START]
task_id: TASK-P0-14
branch: feature/task-p0-14-eval-gates
workdir: C:\Users\Paul\ai\aimSoloAnalysis
commit: <commit-hash>
status: <done|partial|blocked>
...
[TASK-HANDOFF-END]
```

## 10) Acceptance Criteria and Suggested Tests
- Acceptance criteria:
  - All required did-vs-should quality checks are present in scorecard output.
  - Check failures are explicit and diagnosable.
  - Eval tests cover pass and fail paths.
- Suggested tests:
  - `pytest tests/test_eval_top1_scorecard.py -v`
  - `pytest tests/test_eval_backend.py -v`
