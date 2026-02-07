# Tasks (Aim Solo Analysis)

Date: 2026-02-07
Status key: [done] [in-progress] [todo]

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
- [todo] Unified scorecard + release gating workflow combining backend/frontend checks
- [todo] Product-behavior assertion suite + golden scenario drift checks
- [todo] Human coach review workflow integrated into evaluation status

## Tonight Focus: Top-1 Recommendation Quality
- [todo] TASK-P0-03: Top-1 quality gates + gain root-cause trace (keep rec 2/3 behavior unchanged)
- [todo] TASK-EVAL-09: Batch top-1 trace runner over CSV corpus (`artifacts/top1_session_traces.jsonl`)
- [todo] TASK-EVAL-10: Aggregate top-1 scorecard with hard/soft metrics + drift support (`artifacts/eval_top1_quality_report.json`)
- [todo] TASK-EVAL-11: Deterministic coach review packet generator (`artifacts/top1_review_packet.md/.csv`)
