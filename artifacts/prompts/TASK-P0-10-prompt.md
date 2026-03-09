Reasoning mode: gpt-codex5.3high - Contract semantics and fallback behavior must be unambiguous across product behavior and downstream consumers.

# Task Delegation Prompt - TASK-P0-10

## 1) Role and Boundaries
- You are the implementation agent for this task.
- Do not redefine scope; execute exactly what is requested below.
- Do not make unrelated refactors or style-only edits.

## 1.1 Branch and Workspace Assignment
- Assigned branch: `feature/task-p0-10-contract-freeze`
- Assigned working directory: `C:\Users\Paul\ai\aimSoloAnalysis`

## 2) Task Context
- Project: `aimSoloAnalysis`
- Objective: Freeze top-insight did-vs-should payload contract (`did`, `should`, `because`, `success_check`) and null/fallback behavior.
- Why this matters: UI refactor depends on stable, explicit content semantics.
- Related requirement IDs: `RQ-P0-007`, `RQ-P0-008`, `RQ-P0-010`
- Related files/modules: `analytics/trackside/synthesis.py`, `analytics/trackside/pipeline.py`, `tests/test_trackside_insight_contract.py`, `docs/`

## 3) Scope
- In scope:
  - Define canonical payload shape for top-1 coaching insight.
  - Specify required vs optional fields and units.
  - Define deterministic missing-data fallback semantics.
- Out of scope:
  - UI redesign work.
  - Eval scorecard gating changes.

## 4) Constraints
- Preserve current behavior except where needed to satisfy contract freeze.
- Keep changes minimal and local.
- Maintain offline-first behavior.
- Do not remove tests; add/update tests as needed.

## 5) Implementation Requirements
- Required behavior:
  - Emit `did`, `should`, `because`, and `success_check` sections for applicable top insights.
  - Define and enforce required field presence and null semantics.
  - Ensure unit consistency in all numeric rider-facing fields.
- Error handling requirements:
  - If target/marker context is unavailable, emit explicit fallback fields/text without fabricated precision.
  - If evidence is partial, preserve deterministic output structure.
- Performance limits:
  - No meaningful runtime regression in existing trackside tests.

## 6) Verification Requirements
- Add or update tests for changed behavior.
- Run relevant tests locally.
- Report exact commands run and pass/fail summary.

## 6.1 Git Discipline
- One focused commit.
- Commit message: `feat(trackside): freeze did-vs-should payload contract`
- Commit body must include: `Refs: RQ-P0-007, RQ-P0-008, RQ-P0-010`

## 7) Deliverables
- Contract/spec updates and code wiring.
- Tests proving contract behavior and fallback semantics.
- Brief risk notes.

## 8) Response Format (Required)
Use exact structure:

```text
[TASK-HANDOFF-START]
task_id: TASK-P0-10
branch: feature/task-p0-10-contract-freeze
workdir: C:\Users\Paul\ai\aimSoloAnalysis
commit: <commit-hash>
status: <done|partial|blocked>

summary:
- <what changed and why>

files_changed:
- <path>: <one-line purpose>

tests:
- command: <exact command>
  result: <pass|fail>
  details: <short result summary>

requirements_coverage:
- requirement_id: <RQ-...>
  evidence: <file/function/test proving coverage>

open_items:
- <risk, deferred item, or blocker>

notes_for_planner:
- <anything needed for integration/cherry-pick order>
[TASK-HANDOFF-END]
```

## 9) Quality Gate
- [ ] In-scope requirements implemented.
- [ ] No known regressions introduced.
- [ ] Tests added/updated and run.
- [ ] Diff is focused and reviewable.
- [ ] Handoff format complete.
- [ ] One focused commit created.

## 10) Acceptance Criteria and Suggested Tests
- Acceptance criteria:
  - Top-insight contract fields and semantics are explicitly defined and implemented.
  - Missing-data handling is deterministic and test-covered.
  - Existing insight consumers remain compatible.
- Suggested test commands:
  - `pytest tests/test_trackside_insight_contract.py -v`
  - `pytest tests/test_trackside_observable_protocols.py -v`
