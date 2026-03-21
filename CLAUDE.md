# CLAUDE.md — AiM Solo Analysis Project

## What This Project Is

Offline-first telemetry analysis system for AiM Solo 2 / RaceStudio session data. Ingests CSV exports, normalizes to `RunData`, persists to SQLite, computes segment-based analytics, and serves coaching insights through a local FastAPI backend + JavaScript frontend.

**Primary user**: Paul, riding a Yamaha R6 Race bike at tracks like High Plains Raceway (HPR) and Pueblo Motorsports Park in Colorado.

**P0 goal**: Fast trackside coaching — import → summary → insights → compare in <5 seconds, fully offline.

## Architecture (End-to-End Flow)

```
RaceStudio CSV → ingest/csv/parser.py → ingest/csv/importer.py → RunData
    → ingest/csv/save.py → aimsolo.db (SQLite)
    → api/app.py (FastAPI) → analytics/trackside/pipeline.py → insights
    → ui-v2/src/main.js (browser)
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `domain/run_data.py` | Core data container — aligned time/distance/channel arrays |
| `ingest/csv/` | Parse CSV, infer laps, build RunData, persist to SQLite |
| `storage/db.py` + `schema.sql` | SQLite schema, connection helpers, upsert logic |
| `analytics/segments.py` | GPS-based corner/segment detection (curvature analysis) |
| `analytics/reference.py` | Reference lap selection (fastest valid per track+direction) |
| `analytics/deltas.py` | Time/distance delta series between laps |
| `analytics/segment_metrics.py` | Per-segment metrics extraction |
| `analytics/trackside/` | Full coaching pipeline: signals → synthesis → rank |
| `api/app.py` | Endpoints: `/import`, `/summary`, `/insights`, `/compare`, `/map` |
| `api/units.py` | Imperial unit conversion (all rider-facing output is mph/ft/sec) |
| `ui-v2/` | Pure JS frontend, no framework, ES modules |

### Analytics Pipeline Detail

```
analytics/trackside/signals.py    → Deterministic rule hits (8 coaching rules)
analytics/trackside/synthesis.py  → Resolve conflicts, emit did/should/because insights
analytics/trackside/rank.py       → Score by time_gain × confidence, top 3 max
analytics/trackside/config.py     → TrendFilterConfig for tuning
analytics/trackside/corner_identity.py → Rider-facing corner labels
```

## Critical Invariants

1. **RunData alignment**: All arrays must have same length as `time_s`. Enforced by `RunData.validate_lengths()`.
2. **Track identity**: `(track_name, direction)` is the unique key. All comparisons require matching direction (CW/CCW).
3. **Top-N cap**: Maximum 3 insights per session, no more than 2 per corner.
4. **Unit consistency**: All rider-facing text uses imperial (mph, ft, sec). Internal is metric.
5. **Confidence range**: [0.1, 0.9], labeled High (≥0.75), Medium (0.5-0.74), Low (<0.5).
6. **Risk tiers**: Every insight is "Primary", "Experimental", or "Blocked".
7. **Reference lap**: Fastest valid lap per track+direction is the comparison baseline.

## Available Data Channels (AiM Solo 2 GPS-only)

From CSV exports (20 Hz sample rate):
- GPS Speed (km/h), GPS Heading (deg), GPS Latitude/Longitude
- GPS LatAcc (g), GPS LonAcc (g), GPS Slope, GPS Gyro
- GPS Altitude, GPS PosAccuracy, GPS SpdAccuracy, GPS Radius
- InlineAcc, LateralAcc, VerticalAcc (IMU accelerometers, g)
- RollRate, PitchRate, YawRate (IMU gyros, deg/s)
- GPS Nsat, Internal Battery, Distance on GPS Speed

## 8 Coaching Rules (TRACKSIDE_RULES.md)

1. **Early Braking** — brake point >8-15 m earlier than reference
2. **Late Throttle Pickup** — throttle pickup >10-20 m later than reference
3. **Neutral Throttle / Coasting** — |InlineAcc| < 0.03g for ≥1.0s
4. **Line Inconsistency** — cross-track error stddev vs reference
5. **Corner Speed Loss** — apex min speed >3 km/h lower than reference
6. **Over-Braking** — braking longer/harder than reference (same entry speed)
7. **Exit Speed Loss** — exit speed deficit vs reference
8. **Entry Speed Gain** — entry speed higher but worse segment time (carrying too much speed)

## How to Run

```bash
# API server
PYTHONPATH=. python3 -m uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

# Frontend dev server
npm run dev          # port 4173

# Tests
PYTHONPATH=. python3 -m pytest -q

# Evaluation harnesses (produce JSON reports in artifacts/)
PYTHONPATH=. python3 tools/eval_backend.py
PYTHONPATH=. python3 tools/eval_frontend.py
PYTHONPATH=. python3 tools/eval_top1_batch.py
PYTHONPATH=. python3 tools/eval_top1_scorecard.py
PYTHONPATH=. python3 tools/unified_scorecard.py

# Bootstrap refresh (updates PROJECT_BOOTSTRAP.md)
python3 tools/update_bootstrap.py
```

## Test Data

- `test_data/HPR_Full_09292024/` — High Plains Raceway sessions
- `test_data/Pueblo_09142024/` — Pueblo Motorsports Park sessions
- `test_data/*.csv` — Individual session files (R6 Race, rider Paul)

## Key Design Documents

| Doc | What it covers |
|-----|---------------|
| `REQUIREMENTS_BASELINE.md` | 28 P0 functional requirements |
| `TRACKSIDE_RULES.md` | Coaching rule definitions and thresholds |
| `ARCHITECTURE.md` | Architecture principles and layout |
| `UX_SPEC.md` | UI/UX design specification |
| `docs/ui_v2_api_contract_v1.md` | Frozen API payload schema |
| `docs/release_gate_workflow.md` | Release gating procedure |
| `AGENTS.md` | Planner orchestrator instructions |
| `TASKS.md` | Active task list with dependencies |

## Planning & Orchestration

- Before broad exploration, run `python3 tools/update_bootstrap.py` and read `PROJECT_BOOTSTRAP.md`.
- `REQUIREMENTS_BASELINE.md`, `TASKS.md`, and `PLANNER_PROMPT_TEMPLATE.md` are canonical planning docs.
- `skills/planner-orchestrator/SKILL.md` defines the planner skill interface.
- Evaluation artifacts land in `artifacts/` as JSON files.

## Database

- **Path**: `aimsolo.db` (repo root)
- **Schema**: `storage/schema.sql`
- Tables: tracks, sessions, runs, laps, channels, channel_series, sample_points, derived_metrics, insights

## Dependencies (no requirements.txt yet)

**Python** (3.10+): fastapi, pydantic, uvicorn, pytest, sqlite3 (stdlib)
**JavaScript**: No external deps. Pure ES modules, Node.js for build scripts.

## Known Gaps / In-Progress Work

- XRK binary decode: R&D ongoing, not P0 scope (`PROGRESS_AIMSOLO_XRK.txt`)
- Compressed channel blob persistence: stubbed, only sample_points persists
- Multi-session trend analysis: fatigue detection and recurrence narration in progress
- No pinned Python dependencies file
- Grip metrics research completed (`tools/research/grip_metrics.md`) — not yet implemented
- Frontend CORS: dev server on 4173 but CORS config may reference 5173

## Quick Reference: Where to Edit

| Task | File(s) |
|------|---------|
| Add coaching rule | `analytics/trackside/signals.py`, `TRACKSIDE_RULES.md` |
| Change segmentation | `analytics/segments.py`, `analytics/trackside/config.py` |
| Modify API contract | `api/app.py`, `docs/ui_v2_api_contract_v1.md`, `tests/test_ui_v2_api_contract.py` |
| Adjust insight ranking | `analytics/trackside/rank.py` |
| Change insight copy | `analytics/trackside/synthesis.py`, `tests/test_trackside_insight_contract.py` |
| Add DB schema | `storage/schema.sql`, `storage/db.py` |
| Frontend changes | `ui-v2/src/main.js`, `ui-v2/src/styles.css` |
| Unit conversion | `api/units.py`, `tests/test_units_contract.py` |
