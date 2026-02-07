# Project Bootstrap Snapshot

Generated: 2026-02-06T21:49:36-07:00
Purpose: Fast planner startup cache. Refresh with `pwsh -File tools/update_bootstrap.ps1`.

## Repo State
- Root: `C:\Users\Paul\ai\aimSoloAnalysis`
- Branch: `master`
- HEAD: `395d812`
- Dirty: `True`

### Working Tree Changes
- ` M REQUIREMENTS_BASELINE.md`
- ` M TASKS.md`
- ` M analytics/trackside/__pycache__/pipeline.cpython-310.pyc`
- ` M analytics/trackside/__pycache__/rank.cpython-310.pyc`
- ` M analytics/trackside/__pycache__/synthesis.cpython-310.pyc`
- ` M api/__pycache__/app.cpython-310.pyc`
- ` M api/__pycache__/units.cpython-310.pyc`
- ` M ingest/csv/__pycache__/save.cpython-310.pyc`
- ` M storage/__pycache__/db.cpython-310.pyc`
- `?? analytics/__pycache__/metrics_writer.cpython-310.pyc`
- `?? artifacts/eval_backend_report.json`
- `?? artifacts/frontend_eval_report.json`
- `?? tests/__pycache__/test_api_import.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_compare_endpoint.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_db_upsert_ids.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_backend.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_eval_frontend.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_metrics_persistence_ingestion.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_trackside_insight_contract.cpython-310-pytest-9.0.2.pyc`
- `?? tests/__pycache__/test_units_contract.cpython-310-pytest-9.0.2.pyc`
- `?? tools/__pycache__/`

## Recently Modified Files
- `REQUIREMENTS_BASELINE.md` (2026-02-06 21:49:24)
- `TASKS.md` (2026-02-06 21:49:31)
- `artifacts\eval_backend_report.json` (2026-02-06 21:48:39)
- `artifacts\frontend_eval_report.json` (2026-02-06 21:48:09)
- `analytics\trackside\pipeline.py` (2026-02-06 21:48:03)
- `analytics\trackside\rank.py` (2026-02-06 21:48:03)
- `analytics\trackside\synthesis.py` (2026-02-06 21:48:03)
- `api\app.py` (2026-02-06 21:48:03)
- `tests\test_trackside_insight_contract.py` (2026-02-06 21:48:03)
- `tests\test_eval_frontend.py` (2026-02-06 21:47:59)
- `tools\eval_frontend.py` (2026-02-06 21:47:59)
- `tests\test_eval_backend.py` (2026-02-06 21:47:56)
- `tools\eval_backend.py` (2026-02-06 21:47:56)
- `ingest\csv\save.py` (2026-02-06 21:47:53)
- `tests\test_metrics_persistence_ingestion.py` (2026-02-06 21:47:53)
- `PROJECT_BOOTSTRAP.md` (2026-02-06 21:43:18)
- `TASK_PROMPTS_WAVE2.md` (2026-02-06 21:43:12)
- `artifacts\project_bootstrap.json` (2026-02-06 21:43:18)
- `api\units.py` (2026-02-06 21:37:36)
- `tests\test_units_contract.py` (2026-02-06 21:37:36)
- `PLANNER_BOOTSTRAP.md` (2026-02-06 21:36:08)
- `tools\update_bootstrap.ps1` (2026-02-06 21:36:03)
- `AGENTS.md` (2026-02-06 21:31:20)
- `skills\planner-orchestrator\SKILL.md` (2026-02-06 21:30:13)
- `tests\test_compare_endpoint.py` (2026-02-06 20:55:25)

## Recent Commits
- `395d812` 2026-02-06 - feat(trackside): enforce p0 next-session insight contract
- `f1fa416` 2026-02-06 - feat(eval): add frontend flow harness and JSON report
- `2df0b3e` 2026-02-06 - feat(eval): add backend evaluation harness and JSON report
- `6f62753` 2026-02-06 - feat(analytics): persist derived metrics in ingestion path
- `f650d9e` 2026-02-06 - chore(planner): add wave-2 prompt pack and refresh bootstrap
- `a7da7c0` 2026-02-06 - chore(planner): update baseline and tasks after units merge
- `a8ec07b` 2026-02-06 - fix(api): normalize units contract across insights/compare/map
- `0f37b66` 2026-02-06 - chore(planner): optimize bootstrap recency and document cost model
- `54914bb` 2026-02-06 - chore(planner): refresh bootstrap snapshot
- `c4b8271` 2026-02-06 - chore(planner): add planner skill and bootstrap state cache
- `be3d5c9` 2026-02-06 - fix(api): honor explicit compare lap query params
- `995028b` 2026-02-06 - fix(api): keep import run-meta lookup on open connection

## Requirement Gap Snapshot
### Active Gaps
- GAP-006 (Low): Channel blob persistence remains stubbed.
- GAP-007 (High): Backend/frontend harnesses exist, but no unified scorecard + release-gating flow yet.
- GAP-008 (Medium): No formal human-in-the-loop qualitative review loop for coaching quality.
- GAP-009 (Medium): Backend baseline governance unresolved for known drift case (`HPR_Full_09292024-21`).

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

