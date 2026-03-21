# aimSoloAnalysis Investigation

Date: 2026-03-20
Task: AIM-1

## Executive Summary

- Current branch: `feature/task-p0-12-evidence-plumbing`
- Working tree at investigation start: clean
- Latest commit: `2bb3718` (`docs: add repo AI guide`)
- Previous implementation commit: `da69b0b` (`feat(trackside): harden did-vs-should evidence plumbing`)
- Repo status: core CSV -> SQLite -> analytics -> FastAPI -> UI/eval flow is present and well-covered by targeted tests, but the local Python test environment is not reproducible from this checkout alone.

The biggest immediate gap is not product code discovery; it is environment reproducibility. There is no checked-in `pyproject.toml`, `requirements*.txt`, or repo-local virtualenv, so `pytest` could not be executed in this environment. That means current pass/fail and coverage numbers could not be re-verified from this checkout, even though the repository clearly contains a substantial automated test suite and recent implementation activity around the did-vs-should coaching track.

## Inputs Reviewed

- `AI_GUIDE.md`
- `PROJECT_BOOTSTRAP.md`
- `REQUIREMENTS_BASELINE.md`
- `TASKS.md`
- `artifacts/prompts/TASK-P0-10-prompt.md`
- `artifacts/prompts/TASK-P0-11-prompt.md`
- `artifacts/prompts/TASK-P0-12-prompt.md`
- `artifacts/prompts/TASK-P0-13-prompt.md`
- `artifacts/prompts/TASK-P0-14-prompt.md`
- `api/app.py`
- `analytics/trackside/pipeline.py`
- `ingest/csv/save.py`
- `PROGRESS_AIMSOLO_XRK.txt`
- recent commits `2bb3718`, `54804fb`, `da69b0b`

## What Works End-to-End

Based on code inspection, route wiring, and the existing test suite shape, the following flows appear implemented end-to-end:

- Offline CSV import into SQLite via `/import`, including metadata return and DB-backed persistence.
- Session summary generation via `/summary/{session_id}` with structured `not_ready` behavior.
- Ranked trackside coaching insights via `/insights/{session_id}`.
- Lap comparison via `/compare/{session_id}` with explicit lap selection support.
- Map/overlay payload generation via `/map/{session_id}`.
- Rider-facing unit normalization for insights, compare, and map payloads.
- Trackside synthesis/ranking features already landed for:
  - rider-recognizable corner naming
  - unit-consistent copy
  - rider-observable success checks / experimental protocols
  - top-1 visual dominance
  - recurrence narration / fatigue-aware weighting
- Evaluation/reporting flow already landed for:
  - backend eval harness
  - frontend eval harness
  - top-1 batch trace generation
  - top-1 scorecard aggregation
  - review packet generation
  - unified release scorecard
  - release-gate workflow tests

Strong evidence for the above is in:

- API route definitions in `api/app.py`
- trackside pipeline entrypoints in `analytics/trackside/pipeline.py`
- contract tests such as `tests/test_api_import.py`, `tests/test_compare_endpoint.py`, `tests/test_units_contract.py`, `tests/test_trackside_insight_contract.py`, `tests/test_eval_frontend.py`, `tests/test_unified_scorecard.py`, and `tests/test_release_gate_workflow.py`

## Test Execution and Coverage Status

### Environment findings

- No repo-local `.venv`, `venv`, `pyproject.toml`, `requirements.txt`, `pytest.ini`, or `setup.cfg` was present.
- `python3` resolved to Homebrew Python `3.14.3`; `/usr/bin/python3` resolved to Python `3.9.6`.
- `pytest` was not installed for either interpreter.
- Attempting to create a disposable venv in `/tmp` succeeded, but package installation failed because network/package index access is unavailable in this environment.

### Commands attempted

```bash
python3 --version
python3 -m pytest --version
/usr/bin/python3 --version
/usr/bin/python3 -m pytest --version
python3 -m venv /tmp/aimsolo-investigation-venv
/tmp/aimsolo-investigation-venv/bin/python -m pip install pytest pytest-cov fastapi pydantic httpx
```

### Results

- Executed pytest test files: `0`
- Passed tests: `0`
- Failed tests: `0`
- Blocked tests: all repo tests, due missing test dependencies / offline package install failure
- Coverage: unavailable; `pytest-cov` could not be installed and no prior checked-in coverage artifact was found

### Key coverage gaps

- No reproducible dependency manifest is checked in, so test execution itself is currently a coverage gap.
- No current measured line/branch coverage report is available from this checkout.
- `TASKS.md` still lists the ingestion time benchmark as `[todo]`.
- `TASKS.md` still lists the product-behavior assertion suite + golden drift checks as `[todo]`.
- Raw channel blob persistence remains stubbed in `ingest/csv/save.py`.
- XRK decode work remains R&D-only and is not wired into verified product flows.

## Backlog Audit: All `[todo]` Items

| Task | Relevance now | Dependencies / notes | Scope assessment | Recommended priority |
| --- | --- | --- | --- | --- |
| Store raw arrays (compressed blobs) for full channel fidelity | Still relevant | Depends on schema/persistence path already present; `storage/schema.sql` already has `data_blob`, but `ingest/csv/save.py` still uses `_persist_channel_blobs_stub()` | Medium implementation. Improves fidelity and future replay/XRK parity; not required to resume P0 coaching work immediately. | Medium |
| Add lean-angle proxy (from lateral accel + GPS radius) with quality gating | Likely already substantially implemented | `analytics/segment_metrics.py` already computes `lean_proxy_deg` and `lean_quality`; task appears stale in `TASKS.md` | Small reconciliation task first: verify acceptance, then mark done or narrow to any missing edge cases. | Medium |
| Add light brake/throttle detection (turn/lean dependent) to synthesis | Partially implemented / unclear closure | `analytics/trackside/synthesis.py` contains `light_brake` and `light_throttle` branches; need acceptance-level verification, not blind reimplementation | Small-to-medium verification/reconciliation task. Update backlog status before new code. | Medium |
| Decode hGPS 56-byte record format | Still relevant, but P1/R&D | Depends on XRK R&D notes in `PROGRESS_AIMSOLO_XRK.txt`; explicitly out of P0 scope in requirements baseline | Medium research task. Valuable for future ingest parity, not a current resume blocker. | Low |
| Validate CRC16 trailer and timebase mapping | Still relevant, but P1/R&D | Depends on hGPS decode and hCHS mapping work | Medium research/validation task. Not needed for current CSV/FastAPI stack. | Low |
| Map hCHS fields to data types + sample rates | Still relevant, but P1/R&D | Depends on XRK reverse-engineering chain | Medium research task. Same priority band as other XRK items. | Low |
| Ingestion time benchmark | Still relevant | Independent; requires runnable test/benchmark env first | Small verification/tooling task. Useful once environment reproducibility is fixed. | Medium |
| Product-behavior assertion suite + golden scenario drift checks | Still relevant and important | Depends on stable did-vs-should semantics; should follow P0-10/11/12/13 | Medium-to-large verification task. Important release protection, but sequencing matters. | High after did-vs-should contract work |
| TASK-P0-09: upgrade coaching copy to explicit did-vs-should turn-in delta with rationale and marker guidance | Still relevant, but backlog shape is stale | This reads like an umbrella implementation item. Current branch already contains `da69b0b` for evidence plumbing, and downstream tasks split contract/copy/tests/gates more cleanly. No prompt artifact for `TASK-P0-09` was found under `artifacts/prompts/`. | Recast as an umbrella/epic, or decompose its remaining acceptance into P0-10 and P0-11. Avoid executing it as a duplicate coding task. | High, but as backlog reconciliation |
| TASK-P0-10: freeze top-insight did-vs-should payload contract | Still relevant | Depends on P0-09 in `TASKS.md`, but practically can proceed after reconciling P0-09 as umbrella scope | Small theory/spec + targeted contract test task. Needed before more behavior changes. | Highest |
| TASK-P0-11: deterministic did-vs-should coaching copy policy | Still relevant | Depends on P0-10 | Medium implementation task in synthesis/copy logic. Core product-behavior step. | Highest |
| TASK-P0-12: evidence plumbing for target/reference/rider-average/recent history | Likely implemented on current branch, but backlog not reconciled | Strong evidence: branch name `feature/task-p0-12-evidence-plumbing`, commit `da69b0b`, matching file/test changes. Needs rerun of targeted tests in a reproducible env before marking done confidently. | Treat as verification + backlog/status reconciliation, not new implementation. | High, but likely near-close |
| TASK-P0-13: golden did-vs-should coaching scenarios | Still relevant | Depends on settled contract/copy/evidence behavior | Medium verification task. Important to lock the product semantics once P0-10/11/12 are resolved. | High |
| TASK-P0-14: eval scorecard gates for did-vs-should quality | Still relevant | Depends on P0-13 and existing scorecard stack | Medium verification/plumbing task. Should be the final guardrail after semantics are frozen. | High |

## Recommended Next 3-5 CENTRAL Tasks to Queue

1. `CENTRAL-AIM-ENV-01`: restore reproducible Python test environment for the repo.
   Scope: add a checked-in dependency manifest (`pyproject.toml` or `requirements-dev.txt`), document the supported interpreter, and make `PYTHONPATH=.` test execution reproducible from a clean checkout.
   Why first: every other backlog claim is weaker until pytest can be rerun locally.

2. `CENTRAL-AIM-P0-STATUS-01`: reconcile stale backlog items against current branch reality.
   Scope: verify whether lean proxy, light brake/light throttle synthesis, and especially `TASK-P0-12` are already complete; update `TASKS.md` and bootstrap docs accordingly; convert `TASK-P0-09` from ambiguous umbrella work into explicit remaining acceptance or mark it superseded by `TASK-P0-10/11/12`.
   Why second: the backlog is no longer a fully trustworthy source of truth.

3. `CENTRAL-AIM-P0-10`: freeze the did-vs-should payload contract.
   Scope: execute the existing prompt artifact for `TASK-P0-10`, define required/optional fields and null semantics, and lock them with `tests/test_trackside_insight_contract.py`.
   Why next: downstream copy, golden tests, and eval gates all need a stable contract.

4. `CENTRAL-AIM-P0-11`: implement deterministic did-vs-should copy policy.
   Scope: remove vague consistency-only top-1 wording, require numeric did-vs-should delta, causal rationale, and measurable success-check semantics.
   Why next: this is the main product-behavior improvement the backlog is aiming for.

5. `CENTRAL-AIM-P0-13-14`: lock and gate the behavior.
   Scope: first add the golden scenario suite from `TASK-P0-13`, then wire explicit scorecard gates from `TASK-P0-14`.
   Why next: once contract and copy semantics are stable, protect them with deterministic tests and release gates.

## Additional Notes

- The repo currently tracks only `22` checked-in Python test files under `tests/*.py`, not `24`.
- `PROJECT_BOOTSTRAP.md` is stale relative to the current clean branch state and newer commits.
- The checked-in branch already contains evidence that work resumed after the bootstrap snapshot; investigation consumers should trust live git history over the snapshot.
- The absence of `artifacts/prompts/TASK-P0-09-prompt.md` is worth fixing if `TASK-P0-09` is kept as an executable task.

## Conclusion

The codebase is not in a lost state. It has a coherent P0 product path, a meaningful test suite, and recent forward motion on did-vs-should coaching. The immediate operational problem is that the repo cannot currently re-establish its own test environment from source alone. After fixing that, the right sequence is to reconcile backlog drift, freeze the did-vs-should contract, finish the copy semantics, then protect them with golden tests and scorecard gates.
