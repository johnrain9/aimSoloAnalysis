Reasoning mode: gpt-codex5.3high - Golden behavior locks product wording semantics and scenario interpretation.

# Task Delegation Prompt - TASK-P0-13

## 1) Role and Boundaries
- Implement verification-focused scope only.
- No unrelated refactors.

## 1.1 Branch and Workspace Assignment
- Assigned branch: `feature/task-p0-13-golden-tests`
- Assigned working directory: `C:\Users\Paul\ai\aimSoloAnalysis`

## 2) Task Context
- Objective: Add golden behavior tests for did-vs-should coaching scenarios:
  - off-target high variance
  - on-target high variance
  - missing marker mapping
- Requirements: `RQ-P0-007`, `RQ-P0-008`, `RQ-P0-011`
- Areas: `tests/test_trackside_insight_contract.py`, `tests/test_line_trends.py`, optional golden fixtures under `tests/fixtures/`

## 3) Scope
- In scope:
  - Introduce deterministic scenario fixtures/inputs.
  - Assert wording structure and evidence semantics for each scenario.
  - Verify uncertainty/fallback language where appropriate.
- Out of scope:
  - Major algorithmic rewrites.
  - UI or scorecard changes.

## 4) Constraints
- Keep tests readable and deterministic.
- Avoid brittle assertions tied to incidental phrasing; assert required semantic components.

## 5) Implementation Requirements
- Required behavior:
  - Off-target high variance case includes explicit target delta and rationale.
  - On-target high variance case emphasizes stability strategy without losing specificity.
  - Missing marker case uses explicit fallback without fabricated marker detail.
- Error handling:
  - Golden tests should fail loudly on missing required sections.

## 6) Verification Requirements
- Run:
  - `pytest tests/test_trackside_insight_contract.py tests/test_line_trends.py -v`

## 6.1 Git Discipline
- One focused commit.
- Message: `test(trackside): add golden did-vs-should coaching scenarios`
- Body: `Refs: RQ-P0-007, RQ-P0-008, RQ-P0-011`

## 8) Response Format
Use required handoff schema:

```text
[TASK-HANDOFF-START]
task_id: TASK-P0-13
branch: feature/task-p0-13-golden-tests
workdir: C:\Users\Paul\ai\aimSoloAnalysis
commit: <commit-hash>
status: <done|partial|blocked>
...
[TASK-HANDOFF-END]
```

## 10) Acceptance Criteria and Suggested Tests
- Acceptance criteria:
  - Golden scenario matrix is implemented and deterministic.
  - Required semantic components are test-enforced for each case.
  - Fallback/uncertainty behavior is test-covered.
- Suggested tests:
  - `pytest tests/test_trackside_insight_contract.py -v`
  - `pytest tests/test_line_trends.py -v`
