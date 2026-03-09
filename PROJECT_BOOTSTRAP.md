# Project Bootstrap Snapshot

Generated: 2026-02-07T15:00:53-07:00
Purpose: Fast planner startup cache. Refresh with `pwsh -File tools/update_bootstrap.ps1`.

## Repo State
- Root: `C:\Users\Paul\ai\aimSoloAnalysis`
- Branch: `feature/task-p0-12-evidence-plumbing`
- HEAD: `9cd4e34`
- Dirty: `True`

### Working Tree Changes
- ` M PROJECT_BOOTSTRAP.md`
- ` M TASKS.md`
- ` M analytics/trackside/__pycache__/pipeline.cpython-310.pyc`
- ` M analytics/trackside/__pycache__/rank.cpython-310.pyc`
- ` M analytics/trackside/__pycache__/synthesis.cpython-310.pyc`
- ` M analytics/trackside/pipeline.py`
- ` M analytics/trackside/synthesis.py`
- ` M api/__pycache__/app.cpython-310.pyc`
- ` M api/__pycache__/units.cpython-310.pyc`
- ` M artifacts/project_bootstrap.json`
- ` M ingest/csv/__pycache__/save.cpython-310.pyc`
- ` M skills/planner-orchestrator/SKILL.md`
- ` M storage/__pycache__/db.cpython-310.pyc`
- ` M tests/__pycache__/test_line_trends.cpython-310-pytest-9.0.2.pyc`
- ` M tests/test_line_trends.py`
- ` M tests/test_trackside_insight_contract.py`
- `?? .idea/`
- `?? analytics/__pycache__/metrics_writer.cpython-310.pyc`
- `?? analytics/trackside/__pycache__/corner_identity.cpython-310.pyc`
- `?? artifacts/frontend_eval_report.json`
- `?? artifacts/prompts/`
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
- `PROJECT_BOOTSTRAP.md` (2026-02-07 14:58:50)
- `TASKS.md` (2026-02-07 14:22:33)
- `analytics\trackside\pipeline.py` (2026-02-07 14:59:47)
- `analytics\trackside\synthesis.py` (2026-02-07 15:00:01)
- `artifacts\project_bootstrap.json` (2026-02-07 14:58:50)
- `skills\planner-orchestrator\SKILL.md` (2026-02-07 14:58:02)
- `tests\test_line_trends.py` (2026-02-07 15:00:45)
- `tests\test_trackside_insight_contract.py` (2026-02-07 15:00:36)
- `.idea\` (2026-02-07 14:57:57)
- `artifacts\frontend_eval_report.json` (2026-02-07 13:51:45)
- `artifacts\prompts\` (2026-02-07 14:22:17)
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

## Recent Commits
- `9cd4e34` 2026-02-07 - chore(planner): reconcile TASK-SCORECARD-03 status and refresh bootstrap
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
- [todo] TASK-P0-09: Upgrade coaching copy from consistency-only cues to explicit did-vs-should turn-in delta with causal rationale and concrete marker guidance (RQ-P0-006, RQ-P0-007, RQ-P0-008, RQ-P0-009, RQ-P0-010)
- [todo] TASK-P0-10: Freeze top-insight did-vs-should payload contract (`did`, `should`, `because`, `success_check`) and null/fallback behavior (RQ-P0-007, RQ-P0-008, RQ-P0-010)
- [todo] TASK-P0-11: Implement deterministic coaching copy policy for did-vs-should delta + causal rationale + measurable validation wording (ban vague-only consistency cues) (RQ-P0-006, RQ-P0-007, RQ-P0-008, RQ-P0-017)
- [todo] TASK-P0-12: Ensure evidence plumbing always provides target/reference turn-in, rider average, and recent-lap turn-in history with graceful degradation (RQ-P0-007, RQ-P0-009, RQ-P0-010)
- [todo] TASK-P0-13: Add golden behavior tests for did-vs-should coaching scenarios (off-target high variance, on-target high variance, missing marker mapping) (RQ-P0-007, RQ-P0-008, RQ-P0-011)
- [todo] TASK-P0-14: Gate did-vs-should coaching quality in eval scorecard (presence of delta, rationale, measurable check, unit/corner consistency) (RQ-P0-007, RQ-P0-008, RQ-P0-024, RQ-EVAL-008)

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

