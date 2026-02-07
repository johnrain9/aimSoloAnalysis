# Task Prompt Pack (Wave 2)

Use one block per worker thread. Each prompt assumes the worker can read this repo.

## TASK-ANL-03
```text
You are the implementation agent for this task.

First read:
- AGENTS.md
- PLANNER_PROMPT_TEMPLATE.md

Then execute the template with this payload:
- task_id: TASK-ANL-03
- assigned_branch: task/anl-03-metrics-writer-integration
- assigned_workdir: C:\Users\Paul\ai\aimSoloAnalysis\.worktrees\task-anl-03
- objective: Persist derived analytics metrics into SQLite for trackside queries by wiring analytics.metrics_writer into the existing pipeline.
- business_or_user_value: Trackside API can query precomputed metrics reliably and quickly without recomputing.
- requirement_ids: RQ-ANL-003, RQ-ANL-006
- files_or_areas: analytics/metrics_writer.py, analytics/trackside/pipeline.py, ingest/csv/save.py, storage/schema.sql, tests/

In scope:
- Integrate metrics persistence in a deterministic path (import-time or analytics-time) with idempotent upsert behavior.
- Persist at least lap-level and segment-level metrics keyed by analytics_version.
- Add focused tests proving rows are written and updated correctly on re-run.

Out of scope:
- UI changes.
- Broad analytics algorithm refactors unrelated to persistence.

Required behavior:
- Metrics are actually written to `derived_metrics` during normal project flow.
- Re-running the same flow updates existing rows instead of duplicating logical metrics.
- Implementation preserves existing API contract behavior.

Error handling requirements:
- If persistence fails, fail explicitly with actionable error context.
- Do not silently skip writes for non-empty metrics payloads.

Performance limits:
- No material slowdown for existing tests/fixtures; avoid O(n^2) scans.

Suggested test commands:
- $env:PYTHONPATH='.'; pytest -q -k metrics
- $env:PYTHONPATH='.'; pytest -q

Return final output strictly in the required [TASK-HANDOFF-START]/[TASK-HANDOFF-END] schema from PLANNER_PROMPT_TEMPLATE.md.
```

## TASK-P0-02
```text
You are the implementation agent for this task.

First read:
- AGENTS.md
- PLANNER_PROMPT_TEMPLATE.md
- REQUIREMENTS_BASELINE.md (RQ-P0-005 through RQ-P0-018)

Then execute the template with this payload:
- task_id: TASK-P0-02
- assigned_branch: task/p0-02-risk-tier-synthesis
- assigned_workdir: C:\Users\Paul\ai\aimSoloAnalysis\.worktrees\task-p0-02
- objective: Enforce explicit next-session coaching contract in insight output (risk tier + causal operational language + bounded experiments + safety blocks).
- business_or_user_value: Rider gets fast, safe, actionable coaching in 20-30 minute trackside windows.
- requirement_ids: RQ-P0-005, RQ-P0-006, RQ-P0-007, RQ-P0-008, RQ-P0-011, RQ-P0-012, RQ-P0-013, RQ-P0-014, RQ-P0-015, RQ-P0-017, RQ-P0-018
- files_or_areas: analytics/trackside/synthesis.py, analytics/trackside/rank.py, api/app.py, tests/

In scope:
- Add explicit insight fields for risk tier (`Primary|Experimental|Blocked`) with reason.
- Ensure recommendation text is operational and causal (action + because/evidence linkage).
- Add bounded experiment protocol fields for experimental insights and blocked behavior for unsafe guidance.

Out of scope:
- Frontend visual redesign.
- New telemetry channels or XRK decoding.

Required behavior:
- Insights response enforces top-N limit and includes required coaching contract fields.
- High-risk but potentially valuable ideas are emitted as clearly marked `Experimental` with bounds.
- Unsafe suggestions are emitted as `Blocked` (not actionable coaching instructions).

Error handling requirements:
- Missing evidence/quality context must degrade to conservative tiering, not aggressive suggestions.
- Contract fields must be present even for fallback/not-ready-like edge cases where insights exist.

Performance limits:
- Preserve current endpoint responsiveness on fixture tests.

Suggested test commands:
- $env:PYTHONPATH='.'; pytest -q -k trackside
- $env:PYTHONPATH='.'; pytest -q

Return final output strictly in the required [TASK-HANDOFF-START]/[TASK-HANDOFF-END] schema from PLANNER_PROMPT_TEMPLATE.md.
```

## TASK-EVAL-07
```text
You are the implementation agent for this task.

First read:
- AGENTS.md
- PLANNER_PROMPT_TEMPLATE.md
- REQUIREMENTS_BASELINE.md (RQ-EVAL-006, RQ-EVAL-007, RQ-NFR-006)

Then execute the template with this payload:
- task_id: TASK-EVAL-07
- assigned_branch: task/eval-07-unified-scorecard
- assigned_workdir: C:\Users\Paul\ai\aimSoloAnalysis\.worktrees\task-eval-07
- objective: Add a unified evaluation scorecard artifact that combines backend/frontend evaluation results into one machine-readable pass/fail report.
- business_or_user_value: AI-driven iteration can gate changes with one deterministic report.
- requirement_ids: RQ-EVAL-006, RQ-EVAL-007, RQ-NFR-006
- files_or_areas: tools/, artifacts/, tests/

In scope:
- Create scorecard schema + generator command.
- Aggregate backend/frontend report inputs (or explicit missing-status placeholders) into one JSON artifact.
- Include hard-gate vs soft-metric sections and overall pass/fail.

Out of scope:
- Large refactors to existing eval tools.
- UI implementation work.

Required behavior:
- One command produces a stable JSON scorecard file with explicit status fields.
- Scorecard clearly identifies missing components vs failed checks.
- Command exits non-zero when any hard gate fails.

Error handling requirements:
- Malformed or missing input report files are surfaced as structured failures, not silent omissions.
- Output artifact is still emitted with failure detail.

Performance limits:
- Keep runtime practical for frequent local execution.

Suggested test commands:
- $env:PYTHONPATH='.'; pytest -q -k eval
- $env:PYTHONPATH='.'; pytest -q

Return final output strictly in the required [TASK-HANDOFF-START]/[TASK-HANDOFF-END] schema from PLANNER_PROMPT_TEMPLATE.md.
```

## TASK-EVAL-08
```text
You are the implementation agent for this task.

First read:
- AGENTS.md
- PLANNER_PROMPT_TEMPLATE.md
- REQUIREMENTS_BASELINE.md (RQ-EVAL-008, RQ-EVAL-009, RQ-EVAL-010, RQ-EVAL-012)

Then execute the template with this payload:
- task_id: TASK-EVAL-08
- assigned_branch: task/eval-08-behavior-assertions
- assigned_workdir: C:\Users\Paul\ai\aimSoloAnalysis\.worktrees\task-eval-08
- objective: Implement product-behavior evaluation checks and golden-scenario drift detection for coaching output quality.
- business_or_user_value: Prevent regressions in the actual coaching behavior contract, not just API mechanics.
- requirement_ids: RQ-EVAL-008, RQ-EVAL-009, RQ-EVAL-010, RQ-EVAL-012
- files_or_areas: tools/, tests/fixtures/, tests/

In scope:
- Add deterministic behavior assertions (top-N limits, required fields, risk tier presence, success-check presence, no contradictory outputs).
- Add golden scenario fixture format and drift check command.
- Emit report separating hard gates from soft quality indicators.

Out of scope:
- Frontend visual harness implementation.
- Human-review workflow process design (handled separately).

Required behavior:
- Command can run repeatedly and produce deterministic JSON output.
- Behavior checks fail loudly when contract violations are detected.
- Golden fixture drift is reported with precise scenario/field context.

Error handling requirements:
- Bad fixture shape must return explicit validation failure.
- Partial scenario failures must not hide other scenario results.

Performance limits:
- Keep fixture count and runtime practical for frequent local runs.

Suggested test commands:
- $env:PYTHONPATH='.'; pytest -q -k eval
- $env:PYTHONPATH='.'; pytest -q

Return final output strictly in the required [TASK-HANDOFF-START]/[TASK-HANDOFF-END] schema from PLANNER_PROMPT_TEMPLATE.md.
```
