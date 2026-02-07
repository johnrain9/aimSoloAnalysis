# Project Bootstrap Snapshot

Generated: 2026-02-06T21:36:11-07:00
Purpose: Fast planner startup cache. Refresh with `pwsh -File tools/update_bootstrap.ps1`.

## Repo State
- Root: `C:\Users\Paul\ai\aimSoloAnalysis`
- Branch: `master`
- HEAD: `54914bb`
- Dirty: `True`

### Working Tree Changes
- ` M PLANNER_BOOTSTRAP.md`
- ` M aimsolo.db`
- ` M api/__pycache__/app.cpython-310.pyc`
- ` M api/__pycache__/units.cpython-310.pyc`
- ` M storage/__pycache__/db.cpython-310.pyc`
- ` M tools/update_bootstrap.ps1`
- `?? tests/__pycache__/test_api_import.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_compare_endpoint.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_db_upsert_ids.cpython-310-pytest-9.0.2.pyc`

## Recently Modified Files
- `PLANNER_BOOTSTRAP.md` (2026-02-06 21:36:08)
- `aimsolo.db` (2026-02-06 20:06:04)
- `tools\update_bootstrap.ps1` (2026-02-06 21:36:03)
- `PROJECT_BOOTSTRAP.md` (2026-02-06 21:33:23)
- `artifacts\project_bootstrap.json` (2026-02-06 21:33:23)
- `AGENTS.md` (2026-02-06 21:31:20)
- `skills\planner-orchestrator\SKILL.md` (2026-02-06 21:30:13)
- `api\app.py` (2026-02-06 20:55:25)
- `tests\test_compare_endpoint.py` (2026-02-06 20:55:25)
- `tests\test_api_import.py` (2026-02-06 20:54:44)
- `storage\db.py` (2026-02-06 20:53:08)
- `tests\test_db_upsert_ids.py` (2026-02-06 20:53:08)
- `PLANNER_PROMPT_TEMPLATE.md` (2026-02-06 20:51:10)
- `.gitignore` (2026-02-06 20:46:53)
- `REQUIREMENTS_BASELINE.md` (2026-02-06 20:37:58)
- `IMPERIAL_CONVERSION_PLAN.md` (2026-02-05 11:02:33)
- `INSIGHT_COPY_TEMPLATES.md` (2026-02-05 11:04:47)
- `INSIGHT_LEAN_PROXY.md` (2026-02-05 10:59:24)
- `INSIGHT_LIGHT_BRAKE_THROTTLE.md` (2026-02-05 11:00:54)
- `INSIGHT_SYNTHESIS_ALGORITHM.md` (2026-02-05 10:54:21)
- `INSIGHT_SYNTHESIS_OUTLINE.md` (2026-02-05 10:42:58)
- `LINE_STDDEV_RESEARCH.md` (2026-02-05 16:02:33)
- `ML_DATA_COLLECTION_PLAN.md` (2026-02-05 12:06:53)
- `RULES_SIGNALS_SYNTHESIS_CHECKLIST.md` (2026-02-05 11:05:35)
- `TASKS.md` (2026-02-05 10:42:19)

## Recent Commits
- `54914bb` 2026-02-06 - chore(planner): refresh bootstrap snapshot
- `c4b8271` 2026-02-06 - chore(planner): add planner skill and bootstrap state cache
- `be3d5c9` 2026-02-06 - fix(api): honor explicit compare lap query params
- `995028b` 2026-02-06 - fix(api): keep import run-meta lookup on open connection
- `8a8ee59` 2026-02-06 - Fix SQLite upsert helpers to return correct IDs on conflicts
- `438ad5c` 2026-02-06 - chore(planner): add fixed handoff schema for scalable agent intake
- `765609b` 2026-02-06 - chore(planner): assign branch/workdir in delegation template and ignore worktrees
- `f006526` 2026-02-06 - chore(planner): enforce per-task git commit discipline in prompt template
- `9855aac` 2026-02-06 - Add planner prompt template and requirements baseline for P0
- `2800617` 2026-02-05 - Update trend evaluation and data
- `e0b54da` 2026-02-04 - Implement trackside pipeline, API wiring, and analytics docs
- `91d0944` 2026-02-04 - plan

## Requirement Gap Snapshot
### Likely Closed (verify in baseline update)
- `GAP-001`: Recent commit subjects indicate upsert conflict-ID fix landed.
- `GAP-002`: Recent commit subjects indicate /import connection-lifecycle bug fix landed.
- `GAP-003`: Recent commit subjects indicate /compare explicit lap query support landed.

### Active Gaps
- GAP-004 (Medium): Units contract inconsistency (imperial flags with metric map payloads).
- GAP-005 (Medium): Derived metrics writer exists but is not integrated into pipeline persistence path.
- GAP-006 (Low): Channel blob persistence remains stubbed.
- GAP-007 (High): No unified backend+frontend evaluation harness with a single scorecard and release gating.
- GAP-008 (Medium): No formal human-in-the-loop qualitative review loop for coaching quality.

## Open Task Items (TASKS.md)
- [in-progress] XRK R&D notes (PROGRESS_AIMSOLO_XRK.txt) - continue in parallel
- [todo] Store raw arrays (compressed blobs) for full channel fidelity
- [todo] Persist derived metrics for trackside queries (use metrics_writer.py)
- [todo] Add lean-angle proxy (from lateral accel + GPS radius) with quality gating
- [todo] Add synthesis layer to reconcile conflicting insights (phase inference + suppression + actionable templates)
- [todo] Add light brake/throttle detection (turn/lean dependent) to synthesis
- [todo] Convert insight outputs to imperial units (mph, ft) for UI/evidence
- [todo] Decode hGPS 56-byte record format
- [todo] Validate CRC16 trailer and timebase mapping
- [todo] Map hCHS fields to data types + sample rates
- [todo] Ingestion time benchmark

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

