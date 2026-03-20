# AI Guide

## What This Repo Does

This repo builds a local, offline AiM Solo analysis stack for track-day and sprint-session coaching. The core flow is:

1. Import RaceStudio CSV exports.
2. Persist sessions, runs, laps, channels, and derived metrics into SQLite.
3. Generate trackside coaching insights, compare laps, and map overlays.
4. Expose that data through a local FastAPI app for the lightweight UI.
5. Evaluate output quality with backend/frontend/top-1 scorecard tooling.

The product goal is fast, actionable "next session" guidance, not long-form reporting.

## Main Directories / Modules

- `ingest/csv/`: CSV parsing, unit normalization, lap inference, and DB save path for imports.
- `domain/`: Shared typed containers, especially [`domain/run_data.py`](/Users/paul/projects/aimSoloAnalysis/domain/run_data.py).
- `storage/`: SQLite schema and persistence helpers. Start with [`storage/schema.sql`](/Users/paul/projects/aimSoloAnalysis/storage/schema.sql) and [`storage/db.py`](/Users/paul/projects/aimSoloAnalysis/storage/db.py).
- `analytics/`: Core lap/reference/segment/delta/metric computation.
- `analytics/trackside/`: Trackside-specific insight pipeline, ranking, rider-facing corner naming, signals, and synthesis. This is the main behavior layer.
- `api/`: Local FastAPI app and unit-conversion helpers. Primary entrypoint is [`api/app.py`](/Users/paul/projects/aimSoloAnalysis/api/app.py).
- `ui/`: Static frontend for import -> summary -> insights -> compare. Main behavior lives in [`ui/app.js`](/Users/paul/projects/aimSoloAnalysis/ui/app.js).
- `tools/`: Evaluation harnesses, scorecard builders, bootstrap refresh script, and release-gate utilities.
- `tests/`: Unit, contract, integration, and workflow tests.
- `docs/`: Evaluation and workflow docs, plus scorecard examples.
- `artifacts/`: Generated reports/prompts/scorecards. Useful for outputs, not usually for source edits.
- `test_data/`: Real fixture sessions for ingestion and analysis tests.
- `skills/`: Planner support; only relevant when the task is planning/orchestration-heavy.

## Where Common Changes Usually Live

- Import or CSV parsing issues: `ingest/csv/`, `domain/run_data.py`, `tests/test_csv_*`, `tests/test_laps.py`.
- DB schema or persistence bugs: `storage/schema.sql`, `storage/db.py`, `tests/test_db_upsert_ids.py`, `tests/test_metrics_persistence_ingestion.py`.
- Reference lap, segmentation, metrics, or line-trend behavior: `analytics/`, `analytics/trackside/pipeline.py`, matching analytics tests.
- Rider-facing coaching copy, evidence, ranking, or corner naming: `analytics/trackside/synthesis.py`, `analytics/trackside/rank.py`, `analytics/trackside/corner_identity.py`, and the `test_trackside_*` tests.
- API response shape or unit-conversion fixes: `api/app.py`, `api/units.py`, `tests/test_api_import.py`, `tests/test_compare_endpoint.py`, `tests/test_units_contract.py`.
- Frontend rendering or route behavior: `ui/app.js`, `ui/index.html`, `ui/styles.css`, plus `tests/test_eval_frontend.py`.
- Release-gate or evaluation output changes: `tools/eval_*.py`, `tools/unified_scorecard.py`, `tools/build_top1_review_packet.py`, and the corresponding eval/workflow tests.
- Planning state updates: `PROJECT_BOOTSTRAP.md`, `REQUIREMENTS_BASELINE.md`, `TASKS.md`. Treat these as canonical planning docs.

## Key Commands / Tests

These are the commands most likely to matter for normal work:

```bash
PYTHONPATH=. uvicorn api.app:app --reload
pytest -v
pytest tests/test_trackside_insight_contract.py tests/test_line_trends.py -v
pytest tests/test_eval_backend.py tests/test_eval_frontend.py tests/test_unified_scorecard.py -v
PYTHONPATH=. python tools/eval_backend.py
PYTHONPATH=. python tools/eval_frontend.py
PYTHONPATH=. python tools/eval_top1_batch.py
PYTHONPATH=. python tools/eval_top1_scorecard.py
PYTHONPATH=. python tools/build_top1_review_packet.py
PYTHONPATH=. python tools/unified_scorecard.py
```

Planning/bootstrap refresh is expected via:

```bash
pwsh -File tools/update_bootstrap.ps1
```

Note: this repo expects PowerShell for bootstrap refresh. In environments without `pwsh`, read the checked-in [`PROJECT_BOOTSTRAP.md`](/Users/paul/projects/aimSoloAnalysis/PROJECT_BOOTSTRAP.md) directly and do not assume it is fresh.

## Common Traps

- Ignore stale bootstrap state. `PROJECT_BOOTSTRAP.md` is useful, but it is a snapshot, not live truth.
- Keep unit handling consistent. Rider-facing text is expected to stay coherent with the imperial conversion contract, not just raw numeric fields.
- Do not break the API/UI contract casually. `/import`, `/summary`, `/insights`, `/compare`, and `/map` are wired directly into the frontend and eval harnesses.
- Trackside output is requirement-heavy. Changes in synthesis/ranking often need contract tests and scorecard/eval updates, not just local logic changes.
- The repo may contain generated `__pycache__` noise and artifact churn. Do not treat those as meaningful source changes.
- SQLite upsert behavior matters. ID-return semantics are covered by tests and are easy to regress if you alter persistence code.
- This codebase mixes product logic and evaluation gating. A behavior change may require updating both runtime code and the release-gate tools/docs.
- Some workflow docs use PowerShell examples. Translate them carefully if you run on a non-Windows shell.

## Where Not To Look Unless Necessary

- `__pycache__/` anywhere: generated noise.
- `.idea/`: editor-local state.
- `artifacts/`: generated outputs and prompts; inspect when debugging eval/report artifacts, otherwise avoid.
- `docs/examples/`: example scorecards, not implementation.
- `test_data/`: large fixtures; use only when debugging ingestion/analysis behavior against real sessions.
- `skills/`: planner tooling, not product runtime.
- `.git/`: never relevant for feature work beyond normal git commands.

## Changelog

- 2026-03-20T03:13:04Z: Created initial `AI_GUIDE.md` with repo purpose, module map, common edit locations, key commands, common traps, low-value directories, and timestamped changelog section.
