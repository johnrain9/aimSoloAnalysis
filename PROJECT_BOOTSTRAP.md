# Project Bootstrap Snapshot

Generated: 2026-02-06T22:28:54-07:00
Purpose: Fast planner startup cache. Refresh with `pwsh -File tools/update_bootstrap.ps1`.

## Repo State
- Root: `C:\Users\Paul\ai\aimSoloAnalysis`
- Branch: `master`
- HEAD: `fcc061f`
- Dirty: `True`

### Working Tree Changes
- ` M REQUIREMENTS_BASELINE.md`
- ` M TASKS.md`
- ` M aimsolo.db`
- ` M analytics/trackside/__pycache__/pipeline.cpython-310.pyc`
- ` M analytics/trackside/__pycache__/rank.cpython-310.pyc`
- ` M analytics/trackside/__pycache__/synthesis.cpython-310.pyc`
- ` M api/__pycache__/app.cpython-310.pyc`
- ` M api/__pycache__/units.cpython-310.pyc`
- ` M ingest/csv/__pycache__/save.cpython-310.pyc`
- ` M storage/__pycache__/db.cpython-310.pyc`
- `?? .claude/`
- `?? analytics/__pycache__/metrics_writer.cpython-310.pyc`
- `?? artifacts/eval_backend_report.json`
- `?? artifacts/eval_top1_batch_report.json`
- `?? artifacts/eval_top1_quality_report.json`
- `?? artifacts/frontend_eval_report.json`
- `?? artifacts/top1_review_packet.csv`
- `?? artifacts/top1_review_packet.md`
- `?? artifacts/top1_review_packet_fixture.csv`
- `?? artifacts/top1_review_packet_fixture.md`
- `?? tests/__pycache__/test_api_import.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_compare_endpoint.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_db_upsert_ids.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_backend.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_frontend.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_top1_batch.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_top1_scorecard.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_metrics_persistence_ingestion.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_review_packet.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_trackside_insight_contract.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_units_contract.cpython-310-pytest-9.0.2.pyc`
- `?? tools/__pycache__/`

## Recently Modified Files
- `REQUIREMENTS_BASELINE.md` (2026-02-06 22:28:48)
- `TASKS.md` (2026-02-06 22:28:24)
- `aimsolo.db` (2026-02-06 21:50:39)
- `.claude\` (2026-02-06 22:10:48)
- `artifacts\eval_backend_report.json` (2026-02-06 21:53:00)
- `artifacts\eval_top1_batch_report.json` (2026-02-06 22:27:34)
- `artifacts\eval_top1_quality_report.json` (2026-02-06 22:27:37)
- `artifacts\frontend_eval_report.json` (2026-02-06 21:52:43)
- `artifacts\top1_review_packet.csv` (2026-02-06 22:27:42)
- `artifacts\top1_review_packet.md` (2026-02-06 22:27:42)
- `artifacts\top1_review_packet_fixture.csv` (2026-02-06 22:27:50)
- `artifacts\top1_review_packet_fixture.md` (2026-02-06 22:27:50)
- `docs\top1_review_packet_workflow.md` (2026-02-06 22:26:59)
- `tests\fixtures\top1_review_report.json` (2026-02-06 22:26:59)
- `tests\fixtures\top1_review_traces.jsonl` (2026-02-06 22:26:59)
- `tests\test_review_packet.py` (2026-02-06 22:26:59)
- `tools\build_top1_review_packet.py` (2026-02-06 22:26:59)
- `tests\test_eval_top1_scorecard.py` (2026-02-06 22:26:55)
- `tools\eval_top1_scorecard.py` (2026-02-06 22:26:55)
- `tests\test_eval_top1_batch.py` (2026-02-06 22:26:52)
- `tools\eval_top1_batch.py` (2026-02-06 22:26:52)
- `analytics\trackside\rank.py` (2026-02-06 22:26:49)
- `api\app.py` (2026-02-06 22:26:49)
- `tests\test_trackside_insight_contract.py` (2026-02-06 22:26:49)
- `PROJECT_BOOTSTRAP.md` (2026-02-06 22:23:22)

## Recent Commits
- `fcc061f` 2026-02-06 - feat(eval): add deterministic top1 coach review packet
- `2cb36f1` 2026-02-06 - feat(eval): add top1 decision trace scorecard
- `d1dd2e2` 2026-02-06 - feat(eval): add top-1 batch evaluation harness
- `ee27d45` 2026-02-06 - feat(trackside): add top-1 quality gate trace and decisions
- `b8e11bd` 2026-02-06 - chore(planner): refresh bootstrap after requirements update
- `11d436e` 2026-02-06 - chore(requirements): tighten p0 rider-facing behavior contract
- `f5dabf3` 2026-02-06 - chore(planner): add tonight top1 quality task pack
- `b6c0579` 2026-02-06 - chore(planner): refresh bootstrap after handoff integration
- `a1f4445` 2026-02-06 - chore(planner): ingest handoffs and refresh baseline
- `395d812` 2026-02-06 - feat(trackside): enforce p0 next-session insight contract
- `f1fa416` 2026-02-06 - feat(eval): add frontend flow harness and JSON report
- `2df0b3e` 2026-02-06 - feat(eval): add backend evaluation harness and JSON report

## Requirement Gap Snapshot
### Active Gaps
- GAP-006 (Low): Channel blob persistence remains stubbed.
- GAP-007 (High): Backend/frontend harnesses exist, but no unified scorecard + release-gating flow yet.
- GAP-008 (Medium): Human-review packet exists, but review outcomes are not yet integrated into unified release scorecard status.
- GAP-009 (Medium): Backend baseline governance unresolved for known drift case (`HPR_Full_09292024-21`).
- GAP-013 (High): Rider-facing coaching copy is not guaranteed to be unit-consistent across all templated strings.
- GAP-014 (High): Corner naming may still surface internal identifiers instead of rider-recognizable corner identity.
- GAP-015 (Medium): Success checks and experimental abort criteria are not yet consistently rider-observable and change-type-specific.
- GAP-016 (Medium): UI does not yet enforce visually dominant top-1 recommendation in a requirement-tested way.
- GAP-017 (Medium): Recurring multi-session issue narration is not reliably surfaced in coaching copy.
- GAP-018 (Medium): Fatigue-aware weighting for late-session laps is not implemented.
- GAP-019 (High): Default top-1 evaluation artifact paths are not aligned across batch, scorecard, and review packet tools.

## Open Task Items (TASKS.md)
- [in-progress] XRK R&D notes (PROGRESS_AIMSOLO_XRK.txt) - continue in parallel
- [todo] Store raw arrays (compressed blobs) for full channel fidelity
- [todo] Add lean-angle proxy (from lateral accel + GPS radius) with quality gating
- [todo] Add light brake/throttle detection (turn/lean dependent) to synthesis
- [todo] Decode hGPS 56-byte record format
- [todo] Validate CRC16 trailer and timebase mapping
- [todo] Map hCHS fields to data types + sample rates
- [todo] Ingestion time benchmark
- [todo] Unified scorecard + release gating workflow combining backend/frontend checks
- [todo] Product-behavior assertion suite + golden scenario drift checks
- [todo] Human coach review workflow integrated into evaluation status
- [todo] TASK-EVAL-12: Align top-1 artifact path contracts so default no-arg chain works end-to-end (batch -> scorecard -> review packet)
- [todo] TASK-P0-04: Unit-consistent rider-facing coaching copy (RQ-P0-007, RQ-P0-024)
- [todo] TASK-P0-05: Rider-recognizable corner identity and fallback phrasing (RQ-P0-006, RQ-P0-026)
- [todo] TASK-P0-06: Rider-observable success checks and change-type-specific experimental protocols (RQ-P0-017, RQ-P0-018, RQ-P0-029)
- [todo] TASK-P0-07: Make top-1 insight visually dominant in UI and evaluate explicitly (RQ-P0-025)
- [todo] TASK-P0-08: Session recurrence narration + late-session fatigue-aware weighting (RQ-P0-027, RQ-P0-028)

## Planner Entrypoints
- `PROJECT_BOOTSTRAP.md`
- `REQUIREMENTS_BASELINE.md`
- `TASKS.md`
- `PLANNER_PROMPT_TEMPLATE.md`
- `skills/planner-orchestrator/SKILL.md`

## Incremental Update Protocol
1. Refresh snapshot.
2. Read this file first.
3. Deep-read only files touched by new handoffs.
4. Re-run refresh after integration.

