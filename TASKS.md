# Tasks (Aim Solo Analysis)

Date: 2026-02-07
Status key: [done] [in-progress] [blocked] [todo]

## Planner Task Metadata (Required For New Tasks)
- `class`: `T|I|V`
- `depends_on`: list of task IDs, commit hashes, and/or `TA vX.Y`
- `ta_version_required`: required TA version for execution (`none` only when not applicable)
- `blocking_reason`: required when status is `[blocked]`
- Rule: `I` cannot start before required `T` is complete and TA is frozen.
- Rule: `V` depends on TA and/or completed implementation tasks.

## Docs & Planning
- [done] Architecture overview (ARCHITECTURE.md)
- [done] Overall plan (AIM_SOLO_PLAN.md)
- [done] CSV ingestion design (aim_csv_ingestion_design.md)
- [done] Trackside rules spec (TRACKSIDE_RULES.md)
- [done] UX spec (UX_SPEC.md)
- [done] Trackside build plan (BUILD_PLAN.md)
- [done] Segmentation defaults (SEGMENTATION_DEFAULTS.md)
- [done] Robust segmentation algorithm (robust-segmenting-algorithm.md)
- [done] Advanced insights R&D doc (virtual reference, ML, predictive insights)
- [in-progress] XRK R&D notes (PROGRESS_AIMSOLO_XRK.txt) - continue in parallel

## CSV Ingestion (MVP path)
- [done] Implement CSV parser under ingest/csv/
- [done] Create RunData container under domain/run_data.py
- [done] Map metadata -> session + track direction (CW/CCW)
- [done] Parse header + units -> channel registry
- [done] Load data rows -> time/distance aligned arrays
- [done] Lap detection from Beacon Markers; fallback via distance reset
- [done] Store minimal sample_points (time/dist/lat/lon/speed)
- [todo] Store raw arrays (compressed blobs) for full channel fidelity


## Storage
- [done] Storage schema (storage/schema.sql)
- [done] DB persistence helpers (sessions, runs, channels, samples)

## Analytics (Trackside)
- [done] Implement reference lap selection (fastest valid lap per track+direction)
- [done] Implement corner/segment auto-detection (GPS + optional IMU)
- [done] Implement insight rules (early braking, late throttle proxy, line inconsistency, corner speed loss, neutral throttle)
- [done] Confidence scoring + ranking (top 3-5 insights)
- [done] Derived metrics tables + analytics_version
- [done] Build segment metric extraction (entry/apex/exit speeds, brake point proxy, throttle proxy, line variance)
- [done] Compute per-lap segment metrics + deltas (wire deltas.py + segments.py + reference.py)
- [done] Persist derived metrics for trackside queries (use metrics_writer.py)
- [todo] Add lean-angle proxy (from lateral accel + GPS radius) with quality gating
- [done] Add synthesis layer to reconcile conflicting insights (phase inference + suppression + actionable templates)
- [todo] Add light brake/throttle detection (turn/lean dependent) to synthesis
- [done] Convert insight outputs to imperial units (mph, ft) for UI/evidence

## API (Local)
- [done] Minimal API skeleton (import, summary, insights, compare)
- [done] Return cached summaries for UI
- [done] Wire /import to CSV ingestion + DB persistence
- [done] Wire /summary, /insights, /compare to DB-backed analytics output

## UI (Trackside)
- [done] Basic route shell (import -> summary -> insights -> compare)
- [done] Track+direction selector in top bar
- [done] Insight cards with confidence + gain display
- [done] Lap compare placeholder (map + plots)
- [done] UI to API wiring with mock fallback

## XRK R&D (Parallel)
- [todo] Decode hGPS 56-byte record format
- [todo] Validate CRC16 trailer and timebase mapping
- [todo] Map hCHS fields to data types + sample rates

## Tests
- [done] CSV parser unit tests
- [done] Lap boundary inference tests
- [done] RunData validation tests
- [done] CSV ingestion tests
- [done] Insight rule sanity tests
- [todo] Ingestion time benchmark

## Evaluation Harness
- [done] Backend eval harness with baseline/latency/failure JSON report (`tools/eval_backend.py`)
- [done] Frontend eval harness with flow/semantics JSON report (`tools/eval_frontend.py`)
- [done] TASK-SCORECARD-01: Define unified scorecard contract TA v1.0 (FROZEN)
- [done] TASK-SCORECARD-02: Implement unified scorecard builder per TA v1.0
  - class: `I`
  - depends_on: `TA v1.0`, `TASK-EVAL-02`, `TASK-EVAL-03`, `TASK-EVAL-09`, `TASK-EVAL-10`, `TASK-EVAL-11`, `TASK-EVAL-12`
  - ta_version_required: `TA v1.0`
  - prompt: `artifacts/prompts/TASK-SCORECARD-02-prompt.md`
  - commit: `568eade`
- [done] TASK-SCORECARD-03: Add end-to-end release gate workflow test
  - class: `V`
  - depends_on: `TA v1.0`, `TASK-SCORECARD-02`
  - ta_version_required: `TA v1.0`
  - prompt: `artifacts/prompts/TASK-SCORECARD-03-prompt.md`
  - commit: `5b1c8f5`
- [todo] Product-behavior assertion suite + golden scenario drift checks
  - class: `V`
  - depends_on: `TA v1.0`, `TASK-P0-03`, `TASK-P0-04`, `TASK-P0-05`, `TASK-P0-06`, `TASK-P0-07`, `TASK-P0-08`
  - ta_version_required: `TA v1.0`

## Tonight Focus: Top-1 Recommendation Quality
- [done] TASK-P0-03: Top-1 quality gates + gain root-cause trace (keep rec 2/3 behavior unchanged)
- [done] TASK-EVAL-09: Batch top-1 trace runner over CSV corpus (`tools/eval_top1_batch.py`, canonical `artifacts/top1_traces.jsonl`)
- [done] TASK-EVAL-10: Aggregate top-1 scorecard with hard/soft metrics + drift support (`tools/eval_top1_scorecard.py`, canonical `artifacts/top1_aggregated_report.json`)
- [done] TASK-EVAL-11: Deterministic coach review packet generator (`tools/build_top1_review_packet.py`, `artifacts/top1_review_packet.md/.csv`)
- [done] TASK-EVAL-12: Align top-1 artifact path contracts so default no-arg chain works end-to-end (batch -> scorecard -> review packet)

## P0 Requirement Updates (Newly Added/Strengthened)
- [done] TASK-P0-04: Unit-consistent rider-facing coaching copy (RQ-P0-007, RQ-P0-024)
- [done] TASK-P0-05: Rider-recognizable corner identity and fallback phrasing (RQ-P0-006, RQ-P0-026)
- [done] TASK-P0-06: Rider-observable success checks and change-type-specific experimental protocols (RQ-P0-017, RQ-P0-018, RQ-P0-029)
- [done] TASK-P0-07: Make top-1 insight visually dominant in UI and evaluate explicitly (RQ-P0-025)
- [done] TASK-P0-08: Session recurrence narration + late-session fatigue-aware weighting (RQ-P0-027, RQ-P0-028)
- [todo] TASK-P0-09: Upgrade coaching copy from consistency-only cues to explicit did-vs-should turn-in delta with causal rationale and concrete marker guidance (RQ-P0-006, RQ-P0-007, RQ-P0-008, RQ-P0-009, RQ-P0-010)
  - class: `I`
  - depends_on: `TA v1.0`, `TASK-P0-04`, `TASK-P0-05`, `TASK-P0-03`
  - ta_version_required: `TA v1.0`
- [done] TASK-P0-10: Freeze top-insight did-vs-should payload contract (`did`, `should`, `because`, `success_check`) and null/fallback behavior (RQ-P0-007, RQ-P0-008, RQ-P0-010)
  - class: `T`
  - depends_on: `TA v1.0`, `TASK-P0-09`
  - ta_version_required: `TA v1.0`
  - prompt: `artifacts/prompts/TASK-P0-10-prompt.md`
  - acceptance: Contract doc/spec defines required vs optional fields, units, and missing-data semantics with examples.
  - test: `pytest tests/test_trackside_insight_contract.py -v`
- [done] TASK-P0-11: Implement deterministic coaching copy policy for did-vs-should delta + causal rationale + measurable validation wording (ban vague-only consistency cues) (RQ-P0-006, RQ-P0-007, RQ-P0-008, RQ-P0-017)
  - class: `I`
  - depends_on: `TA v1.0`, `TASK-P0-10`
  - ta_version_required: `TA v1.0`
  - prompt: `artifacts/prompts/TASK-P0-11-prompt.md`
  - acceptance: Synthesized top insight includes corner/phase specificity, numeric delta, causal "because", and next-session success check.
  - test: `pytest tests/test_trackside_insight_contract.py tests/test_trackside_observable_protocols.py -v`
- [done] TASK-P0-12: Ensure evidence plumbing always provides target/reference turn-in, rider average, and recent-lap turn-in history with graceful degradation (RQ-P0-007, RQ-P0-009, RQ-P0-010)
  - class: `I`
  - depends_on: `TA v1.0`, `TASK-P0-10`
  - ta_version_required: `TA v1.0`
  - prompt: `artifacts/prompts/TASK-P0-12-prompt.md`
  - acceptance: Pipeline emits complete evidence fields when available and deterministic fallback copy when partial data is missing.
  - test: `pytest tests/test_line_trends.py tests/test_trackside_insight_contract.py -v`
- [done] TASK-P0-13: Add golden behavior tests for did-vs-should coaching scenarios (off-target high variance, on-target high variance, missing marker mapping) (RQ-P0-007, RQ-P0-008, RQ-P0-011)
  - class: `V`
  - depends_on: `TA v1.0`, `TASK-P0-11`, `TASK-P0-12`
  - ta_version_required: `TA v1.0`
  - prompt: `artifacts/prompts/TASK-P0-13-prompt.md`
  - acceptance: Golden tests lock expected wording structure and evidence semantics for core scenario matrix.
  - test: `pytest tests/test_trackside_insight_contract.py tests/test_line_trends.py -v`
- [done] TASK-P0-14: Gate did-vs-should coaching quality in eval scorecard (presence of delta, rationale, measurable check, unit/corner consistency) (RQ-P0-007, RQ-P0-008, RQ-P0-024, RQ-EVAL-008)
  - class: `V`
  - depends_on: `TA v1.0`, `TASK-P0-13`, `TASK-SCORECARD-02`
  - ta_version_required: `TA v1.0`
  - prompt: `artifacts/prompts/TASK-P0-14-prompt.md`
  - acceptance: Eval harness/report emits explicit pass/fail checks for coaching content quality and surfaces failures in scorecard artifacts.
  - test: `pytest tests/test_eval_top1_scorecard.py tests/test_eval_backend.py -v`

## WSL2 Native Runtime + Modern JS UI
- [done] TASK-PLAT-01: Replace PowerShell bootstrap with native Python bootstrap refresh for WSL2/Linux planning flows (RQ-NFR-001, RQ-NFR-003, planner operability)
  - class: `I`
  - depends_on: `none`
  - ta_version_required: `none`
  - acceptance: `tools/update_bootstrap.py` becomes the canonical native refresh path, generates the same planner-critical snapshot outputs, and repo instructions can be followed from WSL2 without `pwsh`.
  - test: `PYTHONPATH=. python3 tools/update_bootstrap.py && pytest tests/test_*bootstrap* -v`
- [done] TASK-PLAT-02: Document and validate native WSL2 run/eval workflow for backend, frontend, and planner operations (RQ-NFR-001, RQ-NFR-003, RQ-NFR-005)
  - class: `V`
  - depends_on: `TASK-PLAT-01`
  - ta_version_required: `none`
  - acceptance: One documented native WSL2 workflow exists for backend startup, frontend startup, import/eval commands, and planner refresh, including browser access expectations from Windows.
  - test: `PYTHONPATH=. pytest tests/test_eval_backend.py tests/test_eval_frontend.py -v`
- [done] TASK-UI-10: Freeze rewritten-UI API and payload contract for import/summary/insights/compare/map, including not-ready/error states (RQ-API-001..005, RQ-UI-001..003, RQ-P0-007..010)
  - class: `T`
  - depends_on: `TA v1.0`, `TASK-P0-10`
  - ta_version_required: `TA v1.0`
  - acceptance: A versioned contract doc defines required fields, optional fields, error payloads, unit semantics, and examples for all rewritten P0 UI routes.
  - test: `PYTHONPATH=. pytest tests/test_api_import.py tests/test_compare_endpoint.py tests/test_trackside_insight_contract.py -v`
- [done] TASK-UI-11: Freeze modern JS trackside UI architecture and visual system for P0 flow (`ui-v2` shell, routes, state model, component model, design tokens) (RQ-P0-019..023, RQ-P0-025, RQ-UI-001..003)
  - class: `T`
  - depends_on: `TASK-UI-10`
  - ta_version_required: `TA v1.0`
  - acceptance: Design doc specifies stack, route model, shared components, visual hierarchy rules, selector/state behavior, and evaluation implications for the rewritten frontend.
  - test: `manual review of design doc + planner sign-off`
- [done] TASK-UI-12: Scaffold `ui-v2/` modern JS frontend shell and route skeleton for import/summary/insights/compare/corner (RQ-UI-001, RQ-P0-019..023)
  - class: `I`
  - depends_on: `TASK-PLAT-02`, `TASK-UI-11`
  - ta_version_required: `TA v1.0`
  - acceptance: New frontend app boots locally in WSL2, serves route shell for the P0 flow, and coexists with the current `ui/` prototype during migration.
  - test: `npm run build && pytest tests/test_eval_frontend.py -v`
- [done] TASK-UI-13: Implement rewritten Insights experience with top-1 dominance and structured did-vs-should rendering (RQ-P0-005..010, RQ-P0-019..025, RQ-P0-026)
  - class: `I`
  - depends_on: `TASK-P0-11`, `TASK-P0-12`, `TASK-UI-12`
  - ta_version_required: `TA v1.0`
  - acceptance: Insights screen renders explicit `did`, `should`, `because`, and `success_check` fields with visually dominant top-1 focus, confidence/risk semantics, and map-linked corner context.
  - test: `PYTHONPATH=. pytest tests/test_trackside_insight_contract.py tests/test_eval_frontend.py -v`
- [done] TASK-UI-14: Upgrade frontend evaluation harness for rewritten UI quality gates (top-1 dominance, did-vs-should presence, route stability, interaction clarity) (RQ-EVAL-004..012, RQ-P0-019..025)
  - class: `V`
  - depends_on: `TASK-P0-13`, `TASK-P0-14`, `TASK-UI-13`
  - ta_version_required: `TA v1.0`
  - acceptance: Frontend evaluation emits explicit pass/fail coverage for rewritten P0 UI quality rules, not just route smoke checks.
  - test: `PYTHONPATH=. python3 tools/eval_frontend.py && pytest tests/test_eval_frontend.py tests/test_eval_top1_scorecard.py -v`
