# Task Prompt Pack (Tonight: Top-1 Recommendation Quality)

Use one block per worker thread. Each prompt assumes the worker can read this repo.

## Integration Order
1. TASK-P0-03
2. TASK-EVAL-09
3. TASK-EVAL-10
4. TASK-EVAL-11

TASK-EVAL-10 depends on TASK-EVAL-09 output artifact shape.
TASK-EVAL-11 depends on TASK-EVAL-10 report fields.

## TASK-P0-03
Reasoning mode: `gpt-codex5.3high` - recommendation safety/quality judgment and gain-causality reasoning are central.

```text
You are the implementation agent for this task.

First read:
- AGENTS.md
- PLANNER_PROMPT_TEMPLATE.md
- REQUIREMENTS_BASELINE.md (RQ-P0-007/008/011/012/013/014/015/017, RQ-EVAL-008)

Then execute the template with this payload:
- task_id: TASK-P0-03
- assigned_branch: task/p0-03-top1-quality-gates
- assigned_workdir: C:\Users\Paul\ai\aimSoloAnalysis\.worktrees\task-p0-03
- objective: Improve top-1 recommendation quality with explicit quality-gate decisions and root-cause gain trace, while leaving recs 2/3 behavior unchanged.
- business_or_user_value: We can quickly trust or debug the first recommendation before optimizing recommendation diversity.
- requirement_ids: RQ-P0-007, RQ-P0-008, RQ-P0-011, RQ-P0-012, RQ-P0-013, RQ-P0-014, RQ-P0-015, RQ-P0-017, RQ-EVAL-008
- files_or_areas: analytics/trackside/synthesis.py, analytics/trackside/rank.py, analytics/trackside/pipeline.py, api/app.py, tests/

In scope:
- Evaluate quality gates for only the top-ranked recommendation (index 0 after ranking).
- Add explicit top-1 gate decision fields (pass/fail + reasons) to insight payload for debugging.
- Add gain root-cause trace fields for top-1 (raw inputs, transformations, confidence weighting, final expected_gain_s).
- If top-1 fails quality gates, enforce conservative handling (e.g., downgrade to Experimental/Blocked with clear reason) without deleting other ranked items.

Out of scope:
- Reordering or suppressing recommendations 2 and 3 as a product behavior change.
- Frontend redesign work.

Required behavior:
- Existing top-N output shape remains compatible.
- Top-1 always has machine-readable gate decision and gain trace when items exist.
- Gate failure reasons are deterministic and actionable.

Error handling requirements:
- Missing/partial metrics must produce explicit gate-fail reasons, not crashes.
- Unsafe contexts must not produce aggressive top-1 primary guidance.

Performance limits:
- Keep overhead low enough that existing test runtimes remain practical.

Suggested test commands:
- $env:PYTHONPATH='.'; pytest -q -k "trackside or insight"
- $env:PYTHONPATH='.'; pytest -q

Return final output strictly in the required [TASK-HANDOFF-START]/[TASK-HANDOFF-END] schema from PLANNER_PROMPT_TEMPLATE.md.
```

## TASK-EVAL-09
Reasoning mode: `gpt-codex5.3` - this is harness plumbing and deterministic artifact/report wiring.

```text
You are the implementation agent for this task.

First read:
- AGENTS.md
- PLANNER_PROMPT_TEMPLATE.md
- REQUIREMENTS_BASELINE.md (RQ-EVAL-007, RQ-EVAL-008, RQ-EVAL-010, RQ-NFR-006)

Then execute the template with this payload:
- task_id: TASK-EVAL-09
- assigned_branch: task/eval-09-top1-batch-report
- assigned_workdir: C:\Users\Paul\ai\aimSoloAnalysis\.worktrees\task-eval-09
- objective: Add a batch runner that executes import->insights across many CSVs and emits per-session top-1 traces for debugging recommendation quality.
- business_or_user_value: We can validate top-1 behavior at scale on hundreds of laps and quickly locate bad recommendations.
- requirement_ids: RQ-EVAL-007, RQ-EVAL-008, RQ-EVAL-010, RQ-NFR-006
- files_or_areas: tools/, tests/, artifacts/

In scope:
- Add CLI tool to recursively scan CSVs and run top-1 extraction.
- Emit deterministic JSONL trace artifact (one row per session/file), default path `artifacts/top1_session_traces.jsonl`.
- Include key fields needed for debugging: file/session ids, top1 rule/corner/phase, risk tier, gate decision (if present), gain trace (if present), and error/not_ready status.

Out of scope:
- Changing core recommendation synthesis/ranking logic.
- Unified backend+frontend scorecard implementation.

Required behavior:
- Command runs in one shot and always emits an artifact, even on partial failures.
- Trace rows distinguish pass/fail/not_ready/error clearly.
- Top-1 focus is explicit; recs 2/3 are not scored.

Error handling requirements:
- Unreadable CSVs or import failures are recorded as structured trace rows, not silent drops.
- Tool exits non-zero only for hard harness-level failures, not for normal per-file quality failures.

Performance limits:
- Practical for frequent local runs over large CSV sets.

Suggested test commands:
- $env:PYTHONPATH='.'; pytest -q -k eval_top1
- $env:PYTHONPATH='.'; python tools/eval_top1_batch.py

Return final output strictly in the required [TASK-HANDOFF-START]/[TASK-HANDOFF-END] schema from PLANNER_PROMPT_TEMPLATE.md.
```

## TASK-EVAL-10
Reasoning mode: `gpt-codex5.3` - this is deterministic aggregation/schema and hard-vs-soft scorecard logic.

```text
You are the implementation agent for this task.

First read:
- AGENTS.md
- PLANNER_PROMPT_TEMPLATE.md
- REQUIREMENTS_BASELINE.md (RQ-EVAL-008, RQ-EVAL-009, RQ-EVAL-010, RQ-NFR-006)

Then execute the template with this payload:
- task_id: TASK-EVAL-10
- assigned_branch: task/eval-10-decision-trace-schema
- assigned_workdir: C:\Users\Paul\ai\aimSoloAnalysis\.worktrees\task-eval-10
- objective: Aggregate top-1 session traces into a deterministic quality score report with hard gates, soft metrics, and drift comparison support.
- business_or_user_value: We can see why top-1 quality fails and track improvement over time with one machine-readable report.
- requirement_ids: RQ-EVAL-008, RQ-EVAL-009, RQ-EVAL-010, RQ-NFR-006
- files_or_areas: tools/, tests/, artifacts/

In scope:
- Add CLI that reads `artifacts/top1_session_traces.jsonl` and writes `artifacts/eval_top1_quality_report.json`.
- Report must include: top1 pass/fail counts, failure reason distribution, rule/risk distribution, outlier gain list, and worst-20 examples.
- Separate hard-gate failures from soft indicators.
- Support optional baseline compare for drift reporting (explicit mismatch list/count).

Out of scope:
- Frontend harness changes.
- Human review workflow implementation.

Required behavior:
- Deterministic schema and field ordering for automation.
- Missing input artifact yields structured failure report (still emitted).
- Report is top-1 scoped and clearly labeled as such.

Error handling requirements:
- Malformed trace lines are counted/reported with context, not ignored.
- Partial parse failures do not hide valid rows.

Performance limits:
- Keep runtime practical for frequent local use.

Suggested test commands:
- $env:PYTHONPATH='.'; pytest -q -k eval_top1
- $env:PYTHONPATH='.'; python tools/eval_top1_scorecard.py

Return final output strictly in the required [TASK-HANDOFF-START]/[TASK-HANDOFF-END] schema from PLANNER_PROMPT_TEMPLATE.md.
```

## TASK-EVAL-11
Reasoning mode: `gpt-codex5.3` - this is deterministic review-packet generation and workflow/doc wiring.

```text
You are the implementation agent for this task.

First read:
- AGENTS.md
- PLANNER_PROMPT_TEMPLATE.md
- REQUIREMENTS_BASELINE.md (RQ-EVAL-011, RQ-EVAL-012, RQ-NFR-007)

Then execute the template with this payload:
- task_id: TASK-EVAL-11
- assigned_branch: task/eval-11-coach-review-packet
- assigned_workdir: C:\Users\Paul\ai\aimSoloAnalysis\.worktrees\task-eval-11
- objective: Generate a deterministic human-review packet for top-1 recommendation quality review from the aggregated report/traces.
- business_or_user_value: Fast 20-30 sample coach review loop can tune thresholds/templates with evidence.
- requirement_ids: RQ-EVAL-011, RQ-EVAL-012, RQ-NFR-007
- files_or_areas: tools/, artifacts/, docs/, tests/

In scope:
- Add CLI that samples cases from top-1 report/traces and emits:
  - `artifacts/top1_review_packet.md`
  - `artifacts/top1_review_packet.csv`
- Include required review columns: recommendation text, evidence summary, gate reasons, risk tier, reviewer verdict, reviewer notes.
- Deterministic sampling with seed and configurable sample size (default 25).

Out of scope:
- Building UI for review capture.
- Modifying analytics output logic.

Required behavior:
- Packet explicitly marks which requirements are human-reviewed vs auto-scored.
- Produces useful review set biased toward failures/outliers while including some passing examples.
- Works offline and is repeatable.

Error handling requirements:
- Missing inputs produce clear actionable errors.
- Tool still writes a minimal artifact with failure context when possible.

Performance limits:
- Single-command run in practical local runtime.

Suggested test commands:
- $env:PYTHONPATH='.'; pytest -q -k review_packet
- $env:PYTHONPATH='.'; python tools/build_top1_review_packet.py

Return final output strictly in the required [TASK-HANDOFF-START]/[TASK-HANDOFF-END] schema from PLANNER_PROMPT_TEMPLATE.md.
```
