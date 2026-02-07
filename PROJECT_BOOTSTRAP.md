# Project Bootstrap Snapshot

Generated: 2026-02-07T13:50:24-07:00
Purpose: Fast planner startup cache. Refresh with `pwsh -File tools/update_bootstrap.ps1`.

## Repo State
- Root: `C:\Users\Paul\ai\aimSoloAnalysis`
- Branch: `feature/scorecard-e2e-test`
- HEAD: `5b1c8f5`
- Dirty: `True`

### Working Tree Changes
- ` M PROJECT_BOOTSTRAP.md`
- ` M TASKS.md`
- ` M analytics/trackside/__pycache__/pipeline.cpython-310.pyc`
- ` M analytics/trackside/__pycache__/rank.cpython-310.pyc`
- ` M analytics/trackside/__pycache__/synthesis.cpython-310.pyc`
- ` M api/__pycache__/app.cpython-310.pyc`
- ` M api/__pycache__/units.cpython-310.pyc`
- ` M artifacts/project_bootstrap.json`
- ` M ingest/csv/__pycache__/save.cpython-310.pyc`
- ` M storage/__pycache__/db.cpython-310.pyc`
- ` M tests/__pycache__/test_line_trends.cpython-310-pytest-9.0.2.pyc`
- `?? analytics/__pycache__/metrics_writer.cpython-310.pyc`
- `?? analytics/trackside/__pycache__/corner_identity.cpython-310.pyc`
- `?? artifacts/unified_scorecard.json`
- `?? tests/__pycache__/test_api_import.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_compare_endpoint.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_db_upsert_ids.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_backend.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_frontend.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_top1_batch.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_top1_scorecard.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_metrics_persistence_ingestion.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_release_gate_workflow.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_review_packet.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_trackside_corner_identity.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_trackside_insight_contract.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_trackside_observable_protocols.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_unified_scorecard.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_units_contract.cpython-310-pytest-9.0.2.pyc`
- `?? tools/__pycache__/`

## Recently Modified Files
- `PROJECT_BOOTSTRAP.md` (2026-02-07 13:49:29)
- `TASKS.md` (2026-02-07 13:50:20)
- `artifacts\project_bootstrap.json` (2026-02-07 13:49:29)
- `artifacts\unified_scorecard.json` (2026-02-07 13:42:24)
- `docs\release_gate_workflow.md` (2026-02-07 13:46:58)
- `tests\test_release_gate_workflow.py` (2026-02-07 13:47:21)
- `tests\test_unified_scorecard.py` (2026-02-07 13:42:12)
- `tools\unified_scorecard.py` (2026-02-07 13:42:12)
- `docs\TA_SCORECARD_v1.0.md` (2026-02-07 13:42:08)
- `docs\examples\scorecard_example_blocked.json` (2026-02-07 13:09:46)
- `docs\examples\scorecard_example_fail.json` (2026-02-07 13:09:29)
- `docs\examples\scorecard_example_pass.json` (2026-02-07 13:09:13)
- `tests\test_eval_frontend.py` (2026-02-06 23:43:44)
- `tools\eval_frontend.py` (2026-02-06 23:43:44)
- `ui\app.js` (2026-02-06 23:43:44)
- `ui\index.html` (2026-02-06 23:43:44)
- `ui\styles.css` (2026-02-06 23:43:44)
- `analytics\trackside\pipeline.py` (2026-02-06 23:43:40)
- `analytics\trackside\synthesis.py` (2026-02-06 23:43:40)
- `tests\test_line_trends.py` (2026-02-06 23:43:40)
- `tests\test_trackside_observable_protocols.py` (2026-02-06 23:42:49)
- `analytics\trackside\corner_identity.py` (2026-02-06 23:42:20)
- `api\app.py` (2026-02-06 23:42:42)
- `tests\test_trackside_corner_identity.py` (2026-02-06 23:42:20)
- `tests\test_trackside_insight_contract.py` (2026-02-06 23:42:20)

## Recent Commits
- `5b1c8f5` 2026-02-07 - test(eval): add end-to-end release gate workflow verification
- `568eade` 2026-02-07 - feat(eval): implement unified scorecard builder per TA v1.0
- `b1b2e69` 2026-02-07 - feat(eval): define unified scorecard contract TA v1.0
- `251fb92` 2026-02-06 - feat(ui): enforce visually dominant top1 insight
- `4d67af7` 2026-02-06 - feat(trackside): add recurrence narration and fatigue-aware weighting
- `4953eaf` 2026-02-06 - feat(trackside): add rider-observable success checks and typed protocols
- `30a2fd9` 2026-02-06 - feat(trackside): add rider-recognizable corner identity labels
- `7254690` 2026-02-06 - fix(trackside): enforce unit-consistent rider-facing coaching copy
- `2b7b289` 2026-02-06 - chore(planner): mark task-eval-12 complete and refresh bootstrap
- `2a4eb84` 2026-02-06 - fix(eval): align top1 artifact contracts for default chain
- `6affae2` 2026-02-06 - chore(planner): add reasoning-mode guidance to prompts and skill
- `4185a60` 2026-02-06 - chore(planner): integrate top1 handoffs and update requirement gaps

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

## Open Task Items (TASKS.md)
- [in-progress] XRK R&D notes (PROGRESS_AIMSOLO_XRK.txt) - continue in parallel
- [todo] Store raw arrays (compressed blobs) for full channel fidelity
- [todo] Add lean-angle proxy (from lateral accel + GPS radius) with quality gating
- [todo] Add light brake/throttle detection (turn/lean dependent) to synthesis
- [todo] Decode hGPS 56-byte record format
- [todo] Validate CRC16 trailer and timebase mapping
- [todo] Map hCHS fields to data types + sample rates
- [todo] Ingestion time benchmark
- [todo] Product-behavior assertion suite + golden scenario drift checks

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

