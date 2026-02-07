# Planner Delegation Prompt Template

Use this template when delegating implementation work to another AI.

## 1) Role and Boundaries
- You are the implementation agent for this task.
- Do not redefine scope; execute exactly what is requested below.
- Do not make unrelated refactors or style-only edits.

## 2) Task Context
- Project: `aimSoloAnalysis`
- Objective: `{{objective}}`
- Why this matters: `{{business_or_user_value}}`
- Related requirement IDs: `{{requirement_ids}}`
- Related files/modules: `{{files_or_areas}}`

## 3) Scope
- In scope:
  - `{{in_scope_item_1}}`
  - `{{in_scope_item_2}}`
  - `{{in_scope_item_3}}`
- Out of scope:
  - `{{out_of_scope_item_1}}`
  - `{{out_of_scope_item_2}}`

## 4) Constraints
- Preserve existing behavior except where explicitly changed.
- Keep changes minimal and local.
- Follow existing architecture and naming conventions.
- Maintain offline-first behavior.
- Do not remove tests; add/update tests as needed.

## 5) Implementation Requirements
- Required behavior:
  - `{{behavior_1}}`
  - `{{behavior_2}}`
  - `{{behavior_3}}`
- Error handling requirements:
  - `{{error_requirement_1}}`
  - `{{error_requirement_2}}`
- Performance limits:
  - `{{perf_requirement_1}}`

## 6) Verification Requirements
- Add or update tests for all changed behavior.
- Run relevant tests locally.
- Report exact commands run and pass/fail summary.
- If any test cannot run, state why and what remains unverified.

## 7) Deliverables
- Code changes implementing scope.
- Tests proving behavior.
- Short changelog with file references.
- Risk notes and follow-ups.

## 8) Response Format (Required)
1. Summary: what changed and why.
2. Files changed: one-line purpose per file.
3. Tests: commands + results.
4. Requirement coverage: map each requirement ID to implementation evidence.
5. Risks/open items: blockers, tradeoffs, deferred work.

## 9) Quality Gate (Must Pass Before Hand-off)
- [ ] All in-scope requirements implemented.
- [ ] No known regressions introduced.
- [ ] Tests added/updated and run.
- [ ] Diff is focused and reviewable.
- [ ] Handoff response format fully completed.

## 10) Task Payload (Fill Before Sending)
- Objective: `{{objective}}`
- Requirements: `{{requirement_ids}}`
- Acceptance criteria:
  - `{{ac_1}}`
  - `{{ac_2}}`
  - `{{ac_3}}`
- Suggested test commands:
  - `{{test_cmd_1}}`
  - `{{test_cmd_2}}`

