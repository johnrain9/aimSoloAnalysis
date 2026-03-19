# Project Bootstrap Snapshot

Generated: 2026-03-15T11:51:40-06:00
Purpose: Fast planner startup cache. Refresh with `python3 tools/update_bootstrap.py`.

## Repo State
- Root: `/home/cobra/aimSoloAnalysis`
- Branch: `master`
- HEAD: `cd0b3ca`
- Dirty: `True`

### Working Tree Changes
- ` M .gitignore`
- ` M AGENTS.md`
- ` M PLANNER_BOOTSTRAP.md`
- ` M PROJECT_BOOTSTRAP.md`
- ` M TASKS.md`
- ` M analytics/trackside/synthesis.py`
- ` M artifacts/frontend_eval_report.json`
- ` M artifacts/project_bootstrap.json`
- ` M skills/planner-orchestrator/SKILL.md`
- ` M tests/test_eval_top1_batch.py`
- ` M tests/test_eval_top1_scorecard.py`
- ` M tests/test_trackside_insight_contract.py`
- ` M tools/eval_frontend.py`
- ` M tools/eval_top1_batch.py`
- ` M tools/eval_top1_scorecard.py`
- `?? README.md`
- `?? docs/ui_v2_api_contract_v1.md`
- `?? docs/ui_v2_architecture_v1.md`
- `?? docs/wsl2_native_js_ui_design.md`
- `?? package.json`
- `?? tests/test_bootstrap_refresh.py`
- `?? tests/test_ui_v2_api_contract.py`
- `?? tools/repo_health_adapter.py`
- `?? tools/update_bootstrap.py`
- `?? ui-v2/`

## Recently Modified Files
- `.gitignore` (2026-03-09 09:40:00)
- `AGENTS.md` (2026-03-09 09:23:21)
- `PLANNER_BOOTSTRAP.md` (2026-03-09 09:23:21)
- `PROJECT_BOOTSTRAP.md` (2026-03-15 11:47:10)
- `TASKS.md` (2026-03-09 09:39:37)
- `analytics/trackside/synthesis.py` (2026-03-09 08:51:32)
- `artifacts/frontend_eval_report.json` (2026-03-15 11:51:40)
- `artifacts/project_bootstrap.json` (2026-03-15 11:47:10)
- `skills/planner-orchestrator/SKILL.md` (2026-03-09 09:23:21)
- `tests/test_eval_top1_batch.py` (2026-03-09 09:20:19)
- `tests/test_eval_top1_scorecard.py` (2026-03-09 09:21:02)
- `tests/test_trackside_insight_contract.py` (2026-03-09 09:22:43)
- `tools/eval_frontend.py` (2026-03-09 09:37:27)
- `tools/eval_top1_batch.py` (2026-03-09 09:17:29)
- `tools/eval_top1_scorecard.py` (2026-03-09 09:20:03)
- `README.md` (2026-03-15 11:51:17)
- `docs/ui_v2_api_contract_v1.md` (2026-03-09 09:31:40)
- `docs/ui_v2_architecture_v1.md` (2026-03-09 09:31:40)
- `docs/wsl2_native_js_ui_design.md` (2026-03-09 09:23:21)
- `package.json` (2026-03-09 09:31:40)
- `tests/test_bootstrap_refresh.py` (2026-03-09 09:17:13)
- `tests/test_ui_v2_api_contract.py` (2026-03-09 09:38:16)
- `tools/repo_health_adapter.py` (2026-03-15 11:43:40)
- `tools/update_bootstrap.py` (2026-03-09 09:16:48)
- `ui-v2/` (2026-03-15 11:44:29)

## Recent Commits
- `cd0b3ca` 2026-03-08 - merge: integrate feature/task-p0-12-evidence-plumbing into master
- `54804fb` 2026-03-08 - chore: commit all current workspace changes
- `ce867c1` 2026-02-07 - feat(trackside): harden did-vs-should evidence plumbing
- `b41edc2` 2026-02-07 - feat(trackside): enforce deterministic did-vs-should coaching copy
- `da69b0b` 2026-02-07 - feat(trackside): harden did-vs-should evidence plumbing
- `4cdf448` 2026-02-07 - feat(trackside): freeze did-vs-should payload contract
- `9cd4e34` 2026-02-07 - chore(planner): reconcile TASK-SCORECARD-03 status and refresh bootstrap
- `5b1c8f5` 2026-02-07 - test(eval): add end-to-end release gate workflow verification
- `568eade` 2026-02-07 - feat(eval): implement unified scorecard builder per TA v1.0
- `b1b2e69` 2026-02-07 - feat(eval): define unified scorecard contract TA v1.0
- `251fb92` 2026-02-06 - feat(ui): enforce visually dominant top1 insight
- `4d67af7` 2026-02-06 - feat(trackside): add recurrence narration and fatigue-aware weighting

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

## Open Task Items (`TASKS.md`)
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
