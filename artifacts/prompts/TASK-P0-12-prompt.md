Reasoning mode: gpt-codex5.3 - This is evidence plumbing and deterministic fallback wiring.

# Task Delegation Prompt - TASK-P0-12

## 1) Role and Boundaries
- Execute only this implementation scope.
- No unrelated refactors.

## 1.1 Branch and Workspace Assignment
- Assigned branch: `feature/task-p0-12-evidence-plumbing`
- Assigned working directory: `C:\Users\Paul\ai\aimSoloAnalysis`
- Use a clean branch/worktree for this task (no unrelated local changes).

## 1.2 Environment Preconditions
- Run tests with `PYTHONPATH=.` to ensure local package imports resolve.

## 2) Task Context
- Objective: Ensure evidence plumbing always provides target/reference turn-in, rider average, and recent-lap turn-in history with graceful degradation.
- Requirements: `RQ-P0-007`, `RQ-P0-009`, `RQ-P0-010`
- Areas: `analytics/trackside/pipeline.py`, `analytics/trackside/synthesis.py`, `tests/test_line_trends.py`, `tests/test_trackside_insight_contract.py`

## 3) Scope
- In scope:
  - Add/verify upstream fields needed for did-vs-should evidence.
  - Preserve deterministic field presence and fallback behavior.
  - Keep units/ranges coherent and rider-facing.
- Out of scope:
  - New UI behaviors.
  - New scoring policy.

## 4) Constraints
- Keep changes minimal and local.
- Do not fabricate missing precision.
- Preserve compatibility with existing insight consumers.

## 5) Implementation Requirements
- Required behavior:
  - Provide target turn-in value (when derivable), rider average turn-in, and recent turn-in samples in evidence payloads.
  - When data is missing, provide explicit fallback values/text and maintain stable structure.
  - Keep corner identity and phase context attached.
- Error handling:
  - Missing marker mapping or sparse lap samples must not crash synthesis.
- Performance:
  - Maintain current test runtime expectations for targeted suites.

## 6) Verification Requirements
- Add/update tests for complete and partial evidence conditions.
- Run:
  - `$env:PYTHONPATH='.'; pytest tests/test_line_trends.py tests/test_trackside_insight_contract.py -v`

## 6.1 Git Discipline
- One focused commit.
- Message: `feat(trackside): harden did-vs-should evidence plumbing`
- Body: `Refs: RQ-P0-007, RQ-P0-009, RQ-P0-010`

## 8) Response Format
Use required handoff schema:

```text
[TASK-HANDOFF-START]
task_id: TASK-P0-12
branch: feature/task-p0-12-evidence-plumbing
workdir: C:\Users\Paul\ai\aimSoloAnalysis
commit: <commit-hash>
status: <done|partial|blocked>
...
[TASK-HANDOFF-END]
```

## 10) Acceptance Criteria and Suggested Tests
- Acceptance criteria:
  - Evidence fields are consistently present and typed as expected.
  - Graceful degradation works for missing marker/target/sample scenarios.
  - Tests explicitly cover both complete and partial contexts.
- Suggested tests:
  - `$env:PYTHONPATH='.'; pytest tests/test_line_trends.py -v`
  - `$env:PYTHONPATH='.'; pytest tests/test_trackside_insight_contract.py -v`
