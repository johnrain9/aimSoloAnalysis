---
name: task-planner
description: Generic planning and delegation workflow for breaking requests into executable tasks, tracking requirements, and integrating worker outputs with minimal risk.
---

# Task Planner

## When To Use
Use this skill when you need to:
- decompose a request into concrete tasks
- assign work across branches/worktrees or teammates/agents
- map tasks to requirements/acceptance criteria
- integrate results in a controlled order

## Quick Start
1. Refresh project context using the repo's existing status/bootstrap scripts if available.
2. Read only the minimum planning docs needed (for example: requirements, backlog, planner template, open tasks).
3. Confirm assumptions about constraints (deadlines, risk tolerance, test gates, environment).

## Planner Loop
1. Intake
- Capture current branch, dirty files, recent commits, open tasks, and obvious risks.
- Treat snapshots/bootstrap docs as cache; verify critical details in source files when needed.

2. Scope and Requirements
- Translate the request into explicit, testable requirements.
- Map each requirement to an ID if IDs exist; otherwise create temporary IDs.
- Mark each requirement as either:
  - hard gate (must pass for merge/release)
  - soft metric (quality signal, non-blocking)

3. Decompose
- Split into small, independent tasks with clear boundaries.
- For each task define:
  - goal
  - in-scope files/components
  - out-of-scope items
  - acceptance criteria
  - validation/tests

4. Delegate
- Assign one branch/workdir per task when possible.
- Require minimal scope and no unrelated refactors.
- Include a reasoning mode recommendation for each task:
  - high reasoning for ambiguous behavior, policy/risk tradeoffs, or non-obvious root cause
  - medium reasoning for straightforward plumbing, deterministic wiring, and routine edits
- Require one focused commit per task.
- Require a fixed handoff block for consistency:

```text
[TASK-HANDOFF-START]
Task: <id>
Summary: <what changed>
Files: <paths>
Tests: <commands + results>
Risks/Follow-ups: <items or none>
Commit: <hash>
[TASK-HANDOFF-END]
```

5. Intake Worker Results
- Validate that changes satisfy stated requirements and acceptance criteria.
- Verify tests were run and results are believable.
- Reject or return incomplete handoffs instead of integrating ambiguous work.

6. Integrate
- Integrate focused commits in dependency order.
- Re-run required local tests after each batch.
- Re-check requirement coverage after integration.

7. Refresh State
- Update planning artifacts/status snapshot after each merged batch.
- Use the refreshed state as the next planning baseline.

## Output Standard
For planning output, include:
- prioritized task list
- requirement mapping (task -> requirement IDs)
- delegation prompts/messages
- integration order
- explicit test/validation commands

## Failure Handling
- If planning docs are stale/contradictory: refresh status, then verify directly in affected files.
- If worktrees/branches cannot be created: use fallback workspace and call out the exception.
- If tests cannot run locally: document exactly what was blocked and what remains to verify.
