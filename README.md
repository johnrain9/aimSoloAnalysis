# aimSoloAnalysis

`aimSoloAnalysis` is a local, offline-first telemetry analysis repo for AiM Solo / RaceStudio session data. It ingests CSV exports, stores normalized session data in SQLite, computes trackside coaching insights, exposes those results through a small FastAPI app, and renders them in browser-based trackside UIs.

This README is intentionally AI-first: another agent should be able to read only this file and understand what the repo does, where the important code lives, how the main flows work, and which constraints matter before making changes.

## What This Repo Is For

The current product target is P0 trackside coaching:

- import a RaceStudio CSV export
- infer laps, track identity, and direction
- build a standardized `RunData` object
- persist core session/run/lap/sample data in SQLite
- compute segment metrics, compare a target lap against a reference lap, and synthesize top coaching recommendations
- expose summary/insight/compare/map payloads through a local API
- render those payloads in a lightweight local UI geared toward quick trackside comprehension

The guiding product requirements live in [REQUIREMENTS_BASELINE.md](/home/cobra/aimSoloAnalysis/REQUIREMENTS_BASELINE.md). The short version is:

- P0 optimizes for the next session, not long-form post-event reporting.
- Everything is local/offline-first.
- The main user-facing output is a short ranked briefing with at most 3 insights.
- Insights should be corner-specific, operational, risk-aware, and easy to scan quickly.

## Current Shape

This repo currently has four important runtime layers:

1. Ingestion: parse AiM RaceStudio CSV exports and convert them into aligned telemetry series.
2. Storage + analytics: persist sessions to SQLite and compute trackside metrics, signals, and synthesized coaching insights.
3. Local API: serve `/import`, `/summary/{session_id}`, `/insights/{session_id}`, `/compare/{session_id}`, and `/map/{session_id}`.
4. Frontend + evaluation: a legacy static UI in `ui/`, a newer `ui-v2/` shell, plus repo-local evaluation and health-report tooling.

The repo is not packaged as a library and does not currently ship a locked Python dependency manifest. Treat it as an application/workbench repo.

## Start Here If You Are An AI

Read these files first, in this order:

1. [README.md](/home/cobra/aimSoloAnalysis/README.md)
2. [PROJECT_BOOTSTRAP.md](/home/cobra/aimSoloAnalysis/PROJECT_BOOTSTRAP.md)
3. [REQUIREMENTS_BASELINE.md](/home/cobra/aimSoloAnalysis/REQUIREMENTS_BASELINE.md)
4. [TASKS.md](/home/cobra/aimSoloAnalysis/TASKS.md)
5. [ARCHITECTURE.md](/home/cobra/aimSoloAnalysis/ARCHITECTURE.md)

Planner-oriented docs and prompts:

- [PLANNER_PROMPT_TEMPLATE.md](/home/cobra/aimSoloAnalysis/PLANNER_PROMPT_TEMPLATE.md)
- [PLANNER_BOOTSTRAP.md](/home/cobra/aimSoloAnalysis/PLANNER_BOOTSTRAP.md)
- [AGENTS.md](/home/cobra/aimSoloAnalysis/AGENTS.md)
- [skills/planner-orchestrator/SKILL.md](/home/cobra/aimSoloAnalysis/skills/planner-orchestrator/SKILL.md)

Important repo convention:

- refresh repo bootstrap with `python3 tools/update_bootstrap.py` before broad exploration, and again after integrating a task batch

## Architecture

### End-to-End Flow

```text
RaceStudio CSV
  -> ingest/csv/parser.py
  -> ingest/csv/importer.py
  -> domain/run_data.py
  -> ingest/csv/save.py
  -> storage/schema.sql + storage/db.py + aimsolo.db
  -> analytics/*
  -> analytics/trackside/pipeline.py
  -> api/app.py
  -> ui-v2/ or ui/
  -> tools/eval_*.py / tools/repo_health_adapter.py
```

### Main Runtime Concepts

- `RunData`: the core in-memory analytics shape. All telemetry series must align to `time_s`. Defined in [domain/run_data.py](/home/cobra/aimSoloAnalysis/domain/run_data.py).
- Track identity: treated as `(track_name, direction)`, where direction is required and normalized to `CW`, `CCW`, or `UNKNOWN`.
- Reference lap selection: analytics compare a target lap against a selected reference lap for the same track/direction.
- Trackside insight contract: the P0 coaching payload emphasizes `did`, `should`, `because`, and `success_check`.
- Local persistence: imported data is stored in `aimsolo.db` at repo root.

### Analytics Pipeline

The trackside pipeline is centered in [analytics/trackside/pipeline.py](/home/cobra/aimSoloAnalysis/analytics/trackside/pipeline.py):

- load session/run/lap/sample data from SQLite
- rebuild `RunData`
- filter/select valid laps
- choose a reference lap and target lap
- segment the lap into corners/phases
- compute segment deltas and metrics
- generate rule signals
- synthesize coaching copy
- rank the final insight list

Supporting modules:

- [analytics/reference.py](/home/cobra/aimSoloAnalysis/analytics/reference.py): reference lap selection and validity filtering
- [analytics/segments.py](/home/cobra/aimSoloAnalysis/analytics/segments.py): lap segmentation and labeling
- [analytics/segment_metrics.py](/home/cobra/aimSoloAnalysis/analytics/segment_metrics.py): per-segment metrics
- [analytics/trackside/signals.py](/home/cobra/aimSoloAnalysis/analytics/trackside/signals.py): rule signal generation
- [analytics/trackside/synthesis.py](/home/cobra/aimSoloAnalysis/analytics/trackside/synthesis.py): coaching copy and evidence shaping
- [analytics/trackside/rank.py](/home/cobra/aimSoloAnalysis/analytics/trackside/rank.py): final top-N ranking
- [analytics/trackside/corner_identity.py](/home/cobra/aimSoloAnalysis/analytics/trackside/corner_identity.py): rider-facing corner naming

### API Layer

The FastAPI app lives in [api/app.py](/home/cobra/aimSoloAnalysis/api/app.py).

Important behaviors:

- `POST /import`
  - with `{"file_path": "/abs/path/to/file.csv"}` imports a local CSV into SQLite
  - with no `file_path` returns the newest stored session from the local DB
- `GET /summary/{session_id}`
  - returns summary cards and lap table data
- `GET /insights/{session_id}`
  - returns ranked coaching items plus a track map payload
- `GET /compare/{session_id}?reference_lap=<n>&target_lap=<n>`
  - returns lap comparison deltas
- `GET /map/{session_id}?lap_a=<n>&lap_b=<n>`
  - returns map overlays for a selected lap pair

Contract docs:

- [docs/ui_v2_api_contract_v1.md](/home/cobra/aimSoloAnalysis/docs/ui_v2_api_contract_v1.md)
- [tests/test_ui_v2_api_contract.py](/home/cobra/aimSoloAnalysis/tests/test_ui_v2_api_contract.py)

### Frontend Layer

There are two frontends:

- [ui/](/home/cobra/aimSoloAnalysis/ui): older static prototype
- [ui-v2/](/home/cobra/aimSoloAnalysis/ui-v2): current rewritten route shell and the default frontend build target

`ui-v2/` is intentionally lightweight:

- plain browser ES modules
- no framework dependency
- dev server in [ui-v2/scripts/dev.mjs](/home/cobra/aimSoloAnalysis/ui-v2/scripts/dev.mjs)
- build script in [ui-v2/scripts/build.mjs](/home/cobra/aimSoloAnalysis/ui-v2/scripts/build.mjs)
- app state and route logic in [ui-v2/src/main.js](/home/cobra/aimSoloAnalysis/ui-v2/src/main.js)

`ui-v2` route model:

- `import`
- `summary`
- `insights`
- `compare`
- `corner`

Architecture and UX intent:

- [docs/ui_v2_architecture_v1.md](/home/cobra/aimSoloAnalysis/docs/ui_v2_architecture_v1.md)
- [docs/wsl2_native_js_ui_design.md](/home/cobra/aimSoloAnalysis/docs/wsl2_native_js_ui_design.md)

### Evaluation + Release Gate Layer

The repo includes local machine-readable evaluation tooling:

- [tools/eval_backend.py](/home/cobra/aimSoloAnalysis/tools/eval_backend.py): backend baseline/latency/failure report
- [tools/eval_frontend.py](/home/cobra/aimSoloAnalysis/tools/eval_frontend.py): static wiring/semantics checks for `ui-v2`
- [tools/eval_top1_batch.py](/home/cobra/aimSoloAnalysis/tools/eval_top1_batch.py): top-1 trace generation
- [tools/eval_top1_scorecard.py](/home/cobra/aimSoloAnalysis/tools/eval_top1_scorecard.py): top-1 aggregated scoring
- [tools/build_top1_review_packet.py](/home/cobra/aimSoloAnalysis/tools/build_top1_review_packet.py): deterministic human-review packet
- [tools/unified_scorecard.py](/home/cobra/aimSoloAnalysis/tools/unified_scorecard.py): merges sub-reports into a release decision
- [tools/repo_health_adapter.py](/home/cobra/aimSoloAnalysis/tools/repo_health_adapter.py): repo-local health snapshot for repo-health/status systems

Workflow docs:

- [docs/release_gate_workflow.md](/home/cobra/aimSoloAnalysis/docs/release_gate_workflow.md)
- [docs/top1_review_packet_workflow.md](/home/cobra/aimSoloAnalysis/docs/top1_review_packet_workflow.md)
- [docs/TA_SCORECARD_v1.0.md](/home/cobra/aimSoloAnalysis/docs/TA_SCORECARD_v1.0.md)

## Repository Map

High-signal directories:

- [analytics/](/home/cobra/aimSoloAnalysis/analytics): metrics, deltas, segmentation, reference selection, and trackside coaching pipeline
- [api/](/home/cobra/aimSoloAnalysis/api): FastAPI app and unit conversion helpers
- [domain/](/home/cobra/aimSoloAnalysis/domain): shared domain models, especially `RunData`
- [ingest/](/home/cobra/aimSoloAnalysis/ingest): CSV parser, lap inference, and DB save path
- [storage/](/home/cobra/aimSoloAnalysis/storage): SQLite schema and persistence helpers
- [ui/](/home/cobra/aimSoloAnalysis/ui): legacy prototype UI
- [ui-v2/](/home/cobra/aimSoloAnalysis/ui-v2): current frontend shell and default build target
- [tools/](/home/cobra/aimSoloAnalysis/tools): evaluation, bootstrap, scorecard, and repo-health utilities
- [tests/](/home/cobra/aimSoloAnalysis/tests): unit/integration/contract coverage
- [test_data/](/home/cobra/aimSoloAnalysis/test_data): fixture CSV corpora used by analytics/eval flows
- [docs/](/home/cobra/aimSoloAnalysis/docs): frozen contracts, release-gate docs, and UI design notes
- [artifacts/](/home/cobra/aimSoloAnalysis/artifacts): generated bootstrap/eval/report outputs

Top-level planning and product docs:

- [REQUIREMENTS_BASELINE.md](/home/cobra/aimSoloAnalysis/REQUIREMENTS_BASELINE.md)
- [TASKS.md](/home/cobra/aimSoloAnalysis/TASKS.md)
- [ARCHITECTURE.md](/home/cobra/aimSoloAnalysis/ARCHITECTURE.md)
- [BUILD_PLAN.md](/home/cobra/aimSoloAnalysis/BUILD_PLAN.md)
- [TRACKSIDE_RULES.md](/home/cobra/aimSoloAnalysis/TRACKSIDE_RULES.md)
- [UX_SPEC.md](/home/cobra/aimSoloAnalysis/UX_SPEC.md)

## Data Model And Workflow Details

### Ingestion Workflow

1. Parse CSV metadata, header, units, and rows in [ingest/csv/parser.py](/home/cobra/aimSoloAnalysis/ingest/csv/parser.py).
2. Convert parsed rows into aligned `RunData` in [ingest/csv/importer.py](/home/cobra/aimSoloAnalysis/ingest/csv/importer.py).
3. Infer lap boundaries in [ingest/csv/laps.py](/home/cobra/aimSoloAnalysis/ingest/csv/laps.py).
4. Persist riders, bikes, tracks, sessions, runs, laps, channels, sample points, and derived metrics in [ingest/csv/save.py](/home/cobra/aimSoloAnalysis/ingest/csv/save.py).

Storage schema highlights from [storage/schema.sql](/home/cobra/aimSoloAnalysis/storage/schema.sql):

- `tracks`, `sessions`, `runs`, `laps`: session organization
- `channels`, `channel_series`: channel metadata and optional compressed raw arrays
- `sample_points`: normalized time/distance/GPS samples used by the P0 API/analytics flow
- `derived_metrics`: versioned computed metrics
- `insights`: stored insight records

### What Actually Drives The UI

The rewritten frontend mostly depends on API payload contracts, not direct DB access.

The important UI payload surfaces are:

- summary cards and lap table from `/summary`
- ranked insight items and map payload from `/insights`
- selected-lap comparison deltas from `/compare`
- explicit lap-pair geometry from `/map`

The UI is built around fast trackside comprehension:

- one dominant top-1 recommendation
- explicit did-vs-should structure
- quick compare flow
- route stability and deterministic fallback states

### Units

P0 UI payloads are normalized to imperial rider-facing units. Unit conversion helpers live in [api/units.py](/home/cobra/aimSoloAnalysis/api/units.py), and the frozen contract is tested in [tests/test_units_contract.py](/home/cobra/aimSoloAnalysis/tests/test_units_contract.py).

## Setup And Commands

The repo does not currently provide a single bootstrap installer. The practical local prerequisites are:

- Python 3
- Node.js + npm
- Python packages needed by the app/tests, including `fastapi`, `pydantic`, `uvicorn`, and `pytest`

### Bootstrap / Orientation

```bash
python3 tools/update_bootstrap.py
```

Writes:

- [PROJECT_BOOTSTRAP.md](/home/cobra/aimSoloAnalysis/PROJECT_BOOTSTRAP.md)
- [artifacts/project_bootstrap.json](/home/cobra/aimSoloAnalysis/artifacts/project_bootstrap.json)

### Run The API

```bash
PYTHONPATH=. python3 -m uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

Notes:

- API entrypoint: [api/app.py](/home/cobra/aimSoloAnalysis/api/app.py)
- local DB path defaults to `aimsolo.db` in the repo root
- CORS currently allows `http://127.0.0.1:5173` and `http://localhost:5173`
- `ui-v2`'s dev server defaults to port `4173`, so live browser API calls need either a CORS adjustment or a matching frontend port

### Run The Frontend

From repo root:

```bash
npm run dev -- --host 0.0.0.0 --port 4173
```

Build:

```bash
npm run build
```

Notes:

- root [package.json](/home/cobra/aimSoloAnalysis/package.json) delegates both commands to `ui-v2`
- built static assets land in [ui-v2/dist/](/home/cobra/aimSoloAnalysis/ui-v2/dist)
- `ui-v2/index.html` defaults its API base to `http://localhost:8000`

### Import A Session

Example API call once the backend is running:

```bash
curl -X POST http://localhost:8000/import \
  -H 'Content-Type: application/json' \
  -d '{"file_path":"/absolute/path/to/session.csv"}'
```

If you omit `file_path`, `/import` tries to return the most recent stored session from `aimsolo.db`.

### Run Tests

Full test suite:

```bash
PYTHONPATH=. python3 -m pytest -q
```

Useful focused suites:

```bash
PYTHONPATH=. python3 -m pytest tests/test_bootstrap_refresh.py -v
PYTHONPATH=. python3 -m pytest tests/test_eval_frontend.py tests/test_ui_v2_api_contract.py -v
PYTHONPATH=. python3 -m pytest tests/test_trackside_insight_contract.py tests/test_line_trends.py -v
```

### Run Evaluation Harnesses

```bash
PYTHONPATH=. python3 tools/eval_backend.py
PYTHONPATH=. python3 tools/eval_frontend.py
PYTHONPATH=. python3 tools/eval_top1_batch.py
PYTHONPATH=. python3 tools/eval_top1_scorecard.py
PYTHONPATH=. python3 tools/build_top1_review_packet.py
PYTHONPATH=. python3 tools/unified_scorecard.py
```

Important default artifacts:

- [artifacts/eval_backend_report.json](/home/cobra/aimSoloAnalysis/artifacts/eval_backend_report.json)
- [artifacts/frontend_eval_report.json](/home/cobra/aimSoloAnalysis/artifacts/frontend_eval_report.json)
- [artifacts/top1_traces.jsonl](/home/cobra/aimSoloAnalysis/artifacts/top1_traces.jsonl)
- [artifacts/top1_aggregated_report.json](/home/cobra/aimSoloAnalysis/artifacts/top1_aggregated_report.json)
- [artifacts/top1_review_packet.md](/home/cobra/aimSoloAnalysis/artifacts/top1_review_packet.md)
- [artifacts/unified_scorecard.json](/home/cobra/aimSoloAnalysis/artifacts/unified_scorecard.json)

### Repo Health Snapshot

```bash
python3 tools/repo_health_adapter.py snapshot --json
```

This is the repo-local adapter intended for repo-health/status aggregation tooling.

## Known Limitations

The requirements baseline and task list are explicit that this repo is still mid-build. High-signal limitations:

- Raw compressed channel persistence is still stubbed in the CSV save path, even though `channel_series` support exists in schema/helpers.
- The repo has no pinned Python dependency file (`requirements.txt`, `pyproject.toml`, lockfile), so environment setup is still manual.
- `ui/` and `ui-v2/` coexist; `ui-v2/` is the active path, but the migration is not fully complete.
- The frontend dev-server default (`4173`) does not currently match the API CORS allowlist (`5173`), so live browser development needs a small local adjustment.
- Frontend evaluation is currently static semantic inspection of `ui-v2` source files, not a browser-driven end-to-end harness.
- Full XRK decode parity is out of scope for P0 and remains unfinished.
- Several coaching-quality gaps remain active in [REQUIREMENTS_BASELINE.md](/home/cobra/aimSoloAnalysis/REQUIREMENTS_BASELINE.md), including release-gate governance, corner naming/wording quality, and some rider-facing behavior polish.
- The repo is offline/local-first and intentionally does not include cloud deployment infrastructure.

## How To Work Safely In This Repo

- Preserve the `(track_name, direction)` identity model.
- Keep `RunData` arrays aligned; `RunData.validate_lengths()` is a real invariant, not a suggestion.
- Prefer adding or updating tests in `tests/` when changing API contracts, insight wording contracts, or evaluation outputs.
- Treat evaluation artifact paths as contracts; several tools chain together by default paths in `artifacts/`.
- If you change planner-facing docs or merge task batches, refresh bootstrap with `python3 tools/update_bootstrap.py`.
- If you touch `ui-v2`, run `npm run build` and `PYTHONPATH=. python3 tools/eval_frontend.py`.
- If you change insight payload shape or wording policy, run the contract tests around `tests/test_trackside_insight_contract.py` and related eval scorecard tests.

## Next-Level Docs

Use these when the README is not enough:

- Product requirements: [REQUIREMENTS_BASELINE.md](/home/cobra/aimSoloAnalysis/REQUIREMENTS_BASELINE.md)
- Active work and known tasks: [TASKS.md](/home/cobra/aimSoloAnalysis/TASKS.md)
- Architecture background: [ARCHITECTURE.md](/home/cobra/aimSoloAnalysis/ARCHITECTURE.md)
- Trackside rule intent: [TRACKSIDE_RULES.md](/home/cobra/aimSoloAnalysis/TRACKSIDE_RULES.md)
- UI architecture: [docs/ui_v2_architecture_v1.md](/home/cobra/aimSoloAnalysis/docs/ui_v2_architecture_v1.md)
- API payload contract: [docs/ui_v2_api_contract_v1.md](/home/cobra/aimSoloAnalysis/docs/ui_v2_api_contract_v1.md)
- Release gating: [docs/release_gate_workflow.md](/home/cobra/aimSoloAnalysis/docs/release_gate_workflow.md)
- Human review workflow: [docs/top1_review_packet_workflow.md](/home/cobra/aimSoloAnalysis/docs/top1_review_packet_workflow.md)
