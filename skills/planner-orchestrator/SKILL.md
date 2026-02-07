---
name: planner-orchestrator
description: Consistent planning, delegation, requirement tracking, and integration workflow for aimSoloAnalysis. Use when the user asks to act as planner, decompose work, generate worker prompts, track requirement coverage, or manage multi-thread AI task intake.
---

# Planner Orchestrator

## Quick Start
1. Refresh state first: run `pwsh -File tools/update_bootstrap.ps1`.
2. Read `PROJECT_BOOTSTRAP.md` before reading wider repo files.
3. Deep-read only what is needed from:
   - `REQUIREMENTS_BASELINE.md`
   - `TASKS.md`
   - `PLANNER_PROMPT_TEMPLATE.md`

## Planner Loop
1. Intake
   - Capture current branch, latest commits, dirty files, recent hot files, open tasks, and requirement gaps from `PROJECT_BOOTSTRAP.md`.
   - Treat `PROJECT_BOOTSTRAP.md` as fast cache, not the final source of truth.
2. Scope and Requirements
   - Map requested work to requirement IDs in `REQUIREMENTS_BASELINE.md`.
   - If requirement text is unclear, rewrite it in explicit, testable language before task delegation.
3. Decompose
   - Split into small, independent tasks suitable for parallel worktrees.
   - Keep each task tied to requirement IDs and clear acceptance checks.
4. Delegate
   - Use `PLANNER_PROMPT_TEMPLATE.md` as base.
   - Always assign branch + workdir.
   - Require one focused commit per task and the fixed `[TASK-HANDOFF-START]` schema.
5. Intake Worker Results
   - Validate requirement coverage, tests, risks, and commit hash from worker handoff.
   - Cherry-pick only focused commits.
   - Re-run local tests after integration.
6. Refresh State
   - Re-run `pwsh -File tools/update_bootstrap.ps1` after each merged task batch.
   - Use new snapshot as the next planning starting point.

## Requirement Management Rules
- Keep product/scope/behavior requirements explicit and testable.
- Separate:
  - `hard gates` (release-blocking)
  - `soft metrics` (advisory quality indicators)
- Require each delegated task to include:
  - requirement IDs
  - acceptance criteria
  - test commands
  - deferred items

## Output Standards
- For planning responses, provide:
  - prioritized task list
  - requirement mapping
  - concrete worker prompts
  - integration order
- For each task prompt, enforce:
  - minimal scope
  - no unrelated refactors
  - explicit test execution
  - exact handoff schema

## Failure Handling
- If bootstrap appears stale or contradictory:
  - run `pwsh -File tools/update_bootstrap.ps1` again
  - verify by reading only directly impacted files
- If worker handoff is incomplete:
  - return with specific missing fields; do not integrate partial ambiguous changes.

