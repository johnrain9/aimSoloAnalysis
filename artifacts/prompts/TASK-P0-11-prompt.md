Reasoning mode: gpt-codex5.3high - Coaching wording rules affect product behavior quality and must avoid vague guidance regressions.

# Task Delegation Prompt - TASK-P0-11

## 1) Role and Boundaries
- Execute only this task scope.
- No unrelated refactors.

## 1.1 Branch and Workspace Assignment
- Assigned branch: `feature/task-p0-11-copy-policy`
- Assigned working directory: `C:\Users\Paul\ai\aimSoloAnalysis`
- Use a clean branch/worktree for this task (no unrelated local changes).

## 1.2 Environment Preconditions
- Run tests with `PYTHONPATH=.` to ensure local package imports resolve.

## 2) Task Context
- Objective: Implement deterministic coaching copy policy for did-vs-should delta + causal rationale + measurable validation, and ban vague-only consistency cues.
- Requirements: `RQ-P0-006`, `RQ-P0-007`, `RQ-P0-008`, `RQ-P0-017`
- Areas: `analytics/trackside/synthesis.py`, `tests/test_trackside_insight_contract.py`, `tests/test_trackside_observable_protocols.py`

## 3) Scope
- In scope:
  - Enforce wording structure: corner/phase specificity, numeric did-vs-should delta, explicit causal rationale, measurable success check.
  - Prevent standalone "be consistent" phrasing as final recommendation text.
  - Preserve readability for rider-facing copy.
- Out of scope:
  - Schema redesign (handled by TASK-P0-10).
  - Eval scorecard gating (handled by TASK-P0-14).

## 4) Constraints
- Keep behavior changes local to synthesis/copy policy.
- Preserve existing risk-tier semantics.
- Keep unit consistency intact.

## 5) Implementation Requirements
- Required behavior:
  - Top insight must include what rider did, what should change, and why it matters.
  - Recommendations must remain corner-recognizable and operational.
  - Success check text must contain measurable target and lap/session window where applicable.
- Error handling:
  - If evidence is partial, degrade with explicit uncertainty language rather than vague generic advice.
- Performance:
  - No meaningful slowdown in targeted tests.

## 6) Verification Requirements
- Add/update tests covering positive and negative copy cases.
- Run:
  - `$env:PYTHONPATH='.'; pytest tests/test_trackside_insight_contract.py tests/test_trackside_observable_protocols.py -v`

## 6.1 Git Discipline
- One focused commit.
- Message: `feat(trackside): enforce deterministic did-vs-should coaching copy`
- Body: `Refs: RQ-P0-006, RQ-P0-007, RQ-P0-008, RQ-P0-017`

## 8) Response Format
Return with required handoff schema:

```text
[TASK-HANDOFF-START]
task_id: TASK-P0-11
branch: feature/task-p0-11-copy-policy
workdir: C:\Users\Paul\ai\aimSoloAnalysis
commit: <commit-hash>
status: <done|partial|blocked>
...
[TASK-HANDOFF-END]
```

## 10) Acceptance Criteria and Suggested Tests
- Acceptance criteria:
  - No top-1 output can pass with vague-only consistency coaching.
  - Copy includes numeric did-vs-should and explicit because-clause semantics.
  - Measurable next-session validation remains present.
- Suggested tests:
  - `$env:PYTHONPATH='.'; pytest tests/test_trackside_insight_contract.py -v`
  - `$env:PYTHONPATH='.'; pytest tests/test_trackside_observable_protocols.py -v`
