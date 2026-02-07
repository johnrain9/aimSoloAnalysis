# Aim Solo Analysis Requirements Baseline

Date: 2026-02-07
Purpose: Convert implicit project assumptions into explicit, trackable requirements for planning and delegation.

## 1) Product Goals
- P0: Deliver fast, actionable, offline trackside coaching from AiM session data.
- P1: Support richer, multi-session analysis for at-home review.
- P0 reliability: Ensure import -> summary -> insights -> compare works end-to-end without manual fixes.

## 2) Scope Definition
- P0 in scope:
  - CSV ingestion from RaceStudio exports.
  - Local SQLite persistence.
  - Trackside analytics pipeline (reference lap, segmentation, metrics, signals, synthesis, ranking).
  - Local API for UI (`/import`, `/summary`, `/insights`, `/compare`, `/map`).
  - UI flow for import, summary, insights, compare.
- P0 out of scope:
  - Full XRK decode parity.
  - Cloud deployment.
  - Real-time telemetry streaming.
- P1 planned scope (non-blocking for P0):
  - Explanatory lap-comparison mode: "tell me why this lap was faster than that lap."

## 3) P0 Product/Behavior Requirements

### 3.1 P0 Session Intent
- RQ-P0-001: P0 shall optimize outputs for the very next on-track session.
  - Acceptance: Primary output is a next-session briefing, not a long-form report.
- RQ-P0-002: Long-term trends may be used only when they directly improve next-session decisions.
  - Acceptance: Any trend-derived recommendation includes explicit "why now" linkage.

### 3.2 Club Sprint Context
- RQ-P0-003: Default coaching objective shall match club sprint priorities (fast lap and immediate racecraft), not endurance pacing.
  - Acceptance: Ranking logic does not assume long tire-management race strategy by default.
- RQ-P0-004: System shall support a "practice experiment" context where slower pace is acceptable while testing a deliberate change.
  - Acceptance: Recommendations can be marked as experiment-first rather than outright pace-maximizing.

### 3.3 Output Shape and Brevity
- RQ-P0-005: P0 briefing shall contain at most 3 insights, with at most 2 primary focus items.
  - Acceptance: API/UI enforce top-N limits and primary focus designation.
- RQ-P0-006: Each recommendation shall be corner- and phase-specific (`entry`, `mid`, `exit`).
  - Acceptance: Output includes corner/segment identifier and phase field or equivalent phrasing.

### 3.4 Operational and Causal Coaching Language
- RQ-P0-007: Recommendations shall be operational ("what/where/how much"), not only diagnostic labels.
  - Acceptance: Insight copy includes concrete action cue (distance/time/marker-based).
- RQ-P0-008: Recommendations shall include causal reasoning tied to evidence.
  - Acceptance: Insight text follows "do X because Y evidence indicates Z" structure.

### 3.5 Visual Evidence and "Did vs Should"
- RQ-P0-009: Evidence shall be glanceable under trackside time pressure.
  - Acceptance: Each insight includes a concise evidence summary line.
- RQ-P0-010: UI shall clearly display "what you did" vs "what you should do," including track-line deviation visualization when relevant.
  - Acceptance: Map/overlay view can highlight affected segment and target behavior context.

### 3.6 Uncertainty, Risk, and Safety Policy
- RQ-P0-011: System shall explicitly represent uncertainty rather than silently suppressing all uncertain ideas.
  - Acceptance: Output includes confidence and data-quality notes for each recommendation.
- RQ-P0-012: Recommendations shall be tiered as `Primary`, `Experimental`, or `Blocked`.
  - Acceptance: Every recommendation carries a risk tier with explanatory reason.
- RQ-P0-013: Borderline-risk/high-upside ideas may be emitted as `Experimental` with explicit safety framing.
  - Acceptance: Experimental recommendations include expected gain, explicit risk, and execution bounds.
- RQ-P0-014: Clearly unsafe recommendations shall be `Blocked` and not presented as actionable coaching instructions.
  - Acceptance: Red-line safety conditions produce non-actionable blocked output.
- RQ-P0-015: System shall avoid dangerous advice patterns in high-risk contexts (e.g., aggressive brake/throttle escalation at already high lean/instability).
  - Acceptance: Guardrails prevent unsafe escalation suggestions under flagged risk conditions.

### 3.7 Conflict Management and Closed Loop
- RQ-P0-016: System shall resolve/suppress conflicting recommendations in the same corner-phase to avoid contradictory rider instructions.
  - Acceptance: Final briefing has coherent, non-conflicting action set.
- RQ-P0-017: Each recommendation shall include a next-session success check (measurable validation target).
  - Acceptance: Output includes concrete verification metric for the next run.
- RQ-P0-018: Experimental recommendations shall include bounded test protocol.
  - Acceptance: Output includes one-variable test guidance, short trial window, and abort criteria.

### 3.8 Trackside UI Quality
- RQ-P0-019: P0 UI shall prioritize rapid understanding with strong information hierarchy.
  - Acceptance: Primary focus items, risk tier, confidence, and expected gain are visually dominant above secondary details.
- RQ-P0-020: Insights view shall support "fast briefing" comprehension.
  - Acceptance: Coach can identify top 1-2 actions, where they apply, and why within a quick scan (no drill-down required).
- RQ-P0-021: Visual semantics shall be consistent and unambiguous.
  - Acceptance: Confidence, risk tier, and recommendation status use consistent labels/colors/icons across screens.
- RQ-P0-022: "Did vs Should" graphics shall be clear at a glance.
  - Acceptance: Track overlays include legend/context and clearly distinguish rider path vs target path in affected segments.
- RQ-P0-023: UI interaction quality shall support trackside pace.
  - Acceptance: Common actions (screen switch, insight select, map highlight) feel immediate and do not require repeated retries.

## 4) Functional Requirements

### 4.1 Ingestion and Normalization
- RQ-ING-001: System shall parse RaceStudio CSV metadata, header, units, and data rows.
  - Acceptance: Parser returns structured metadata/header/units/rows for valid CSV.
- RQ-ING-002: System shall normalize track identity with explicit direction (`CW`, `CCW`, `UNKNOWN`).
  - Acceptance: Stored session has direction and track identity string.
- RQ-ING-003: System shall build aligned `RunData` series with validated lengths.
  - Acceptance: `RunData.validate_lengths()` passes on successful import.
- RQ-ING-004: System shall infer laps from beacon markers when available.
  - Acceptance: Lap boundaries created from marker transitions.
- RQ-ING-005: System shall fallback to distance reset or GPS crossing lap inference when beacons are missing.
  - Acceptance: Heuristic lap boundaries generated when conditions are met.

### 4.2 Storage and Data Integrity
- RQ-DB-001: System shall persist riders, bikes, tracks, sessions, runs, laps, channels, and sample points.
  - Acceptance: Successful import produces rows with valid foreign keys.
- RQ-DB-002: Upsert helpers shall return correct primary keys for both insert and conflict-update paths.
  - Acceptance: Returned IDs always correspond to existing row keys.
- RQ-DB-003: Session/run persistence shall be idempotent for stable source/session identity.
  - Acceptance: Re-import does not duplicate equivalent session/run unexpectedly.
- RQ-DB-004: System shall preserve referential integrity under repeated imports.
  - Acceptance: No foreign key failures on valid data.

### 4.3 Analytics Pipeline
- RQ-ANL-001: System shall select reference laps per track+direction with quality filters.
  - Acceptance: Reference selection excludes invalid laps where possible.
- RQ-ANL-002: System shall detect corner segments from GPS (and IMU when available).
  - Acceptance: Segmentation returns ordered segment set with start/apex/end.
- RQ-ANL-003: System shall compute segment metrics including entry/min/exit speeds and timing deltas.
  - Acceptance: Metrics payload contains required fields for rules.
- RQ-ANL-004: System shall produce rule signals and synthesized insights per segment.
  - Acceptance: Output includes rule ID, evidence, confidence, and action text.
- RQ-ANL-005: System shall rank top trackside insights by time gain and confidence with corner diversity.
  - Acceptance: Output constrained to configured min/max and diversity rules.
- RQ-ANL-006: System shall support trend-based line guidance with configurable filters.
  - Acceptance: Trend harness baseline check passes on fixture set.

### 4.4 API Contract
- RQ-API-001: `/import` shall return session identity and metadata after successful import.
  - Acceptance: Response contains `session_id`, `track_name`, `direction`, `analytics_version`.
- RQ-API-002: `/summary/{session_id}` shall return lap list and summary cards or structured `not_ready`.
  - Acceptance: Deterministic response shape for both ready and not-ready states.
- RQ-API-003: `/insights/{session_id}` shall return ranked insight items and evidence.
  - Acceptance: Insight payload includes confidence and comparison context.
- RQ-API-004: `/compare/{session_id}` shall support lap selection and return sector/segment deltas.
  - Acceptance: Query-selected lap comparison is honored by response.
- RQ-API-005: `/map/{session_id}` shall return map polylines for selected laps.
  - Acceptance: Payload includes requested lap pair geometry.

### 4.5 UI Requirements
- RQ-UI-001: UI shall support route flow import -> summary -> insights -> compare.
  - Acceptance: User can navigate and render each route with API-backed data.
- RQ-UI-002: UI shall show fallback and not-ready states without crashing.
  - Acceptance: Missing API data renders informative placeholders.
- RQ-UI-003: UI shall display confidence and gain for each insight.
  - Acceptance: Insight cards show confidence badge and gain.

### 4.6 Units and Evidence
- RQ-UNT-001: User-facing summary/insight values shall be consistent with declared units.
  - Acceptance: Payload and displayed evidence use coherent unit system.
- RQ-UNT-002: Evidence conversion shall correctly convert meter/kmh/mps fields where required.
  - Acceptance: Converted evidence fields match conversion constants.

### 4.7 Evaluation and Measurement
- RQ-EVAL-001: System shall provide a repeatable backend evaluation harness runnable with a documented command.
  - Acceptance: One command runs backend evaluation and emits a machine-readable report artifact.
- RQ-EVAL-002: Backend harness shall compare current behavior against versioned baseline fixtures.
  - Acceptance: Report includes pass/fail comparison against stored baseline outputs.
- RQ-EVAL-003: Backend harness shall measure key quality and performance indicators.
  - Acceptance: Report includes at least correctness/regression status, latency summary, and failure counts.
- RQ-EVAL-004: System shall provide a repeatable frontend evaluation harness for critical trackside flows.
  - Acceptance: One command runs scripted UI checks for import/summary/insights/compare behavior and timing.
- RQ-EVAL-005: Frontend harness shall verify visual/interaction outcomes for "Did vs Should" comprehension surfaces.
  - Acceptance: Report includes checks for map overlays/highlight behavior and critical UI state transitions.
- RQ-EVAL-006: System shall produce a unified scorecard combining backend and frontend evaluation results.
  - Acceptance: Combined report clearly indicates overall pass/fail and per-domain failures.
- RQ-EVAL-007: Evaluation harness shall support frequent automated execution for AI-driven iteration.
  - Acceptance: Documented workflow supports running harness on each substantial change with deterministic outputs.

### 4.8 Product Behavior Evaluation Model
- RQ-EVAL-008: Evaluation harness shall automatically score product behavior rules that are objectively testable.
  - Acceptance: Automated report verifies limits/structure/safety semantics including top-N limits, required coaching fields, risk tier presence, conflict suppression, and next-session success-check presence.
- RQ-EVAL-009: Evaluation harness shall maintain golden scenario fixtures for expected coaching patterns.
  - Acceptance: Report detects drift against baseline recommendation patterns for curated scenarios.
- RQ-EVAL-010: Evaluation output shall distinguish hard pass/fail checks from soft quality indicators.
  - Acceptance: Scorecard includes separate sections for strict gates (release blocking) and advisory metrics (non-blocking).
- RQ-EVAL-011: System shall include periodic human coach review for qualitative coaching quality not reliably machine-judged.
  - Acceptance: Documented review workflow captures reviewer verdicts on recommendation quality, usefulness, and risk framing.
- RQ-EVAL-012: Evaluation report shall declare which requirements are auto-scored versus human-reviewed.
  - Acceptance: Each behavior requirement in scope has a declared evaluation mode and latest status.

## 5) Non-Functional Requirements
- RQ-NFR-001: App shall run fully local/offline with no network dependency for core flows.
- RQ-NFR-002: Analytics outputs shall be deterministic for identical input data and version.
- RQ-NFR-003: Core tests shall pass in local dev environment with documented command.
- RQ-NFR-004: Failures shall be explicit and diagnosable (`not_ready`, structured errors).
- RQ-NFR-005: Evaluation commands shall be practical for frequent use in local development.
  - Acceptance: Backend and frontend harnesses complete within documented runtime budgets on target dev hardware.
- RQ-NFR-006: Evaluation artifacts shall be machine-consumable to support automated AI decision loops.
  - Acceptance: Reports are emitted in stable JSON (or equivalent) schemas with explicit status fields.
- RQ-NFR-007: Human-review process for qualitative coaching behavior shall have defined cadence and traceability.
  - Acceptance: Review logs include date, reviewer, scenario set, and disposition; cadence is documented.

## 6) Current Status Snapshot

### 6.1 Verified Working
- CSV parser/import/lap inference tests present and passing.
- Analytics signals/synthesis/ranking tests present and passing.
- Trend harness baseline currently matches fixtures.
- Existing trend harness provides partial backend measurement coverage (`tools/eval_trends.py`).

### 6.2 Active Gaps / Must-Fix
- GAP-005 (Medium): Derived metrics writer exists but is not integrated into pipeline persistence path.
  - Related requirements: RQ-ANL-003, RQ-ANL-006.
- GAP-006 (Low): Channel blob persistence remains stubbed.
  - Affects: raw channel fidelity and future replay features.
  - Related requirements: RQ-DB-001.
- GAP-007 (High): No unified backend+frontend evaluation harness with a single scorecard and release gating.
  - Affects: confidence in automated AI-driven iteration.
  - Related requirements: RQ-EVAL-001 through RQ-EVAL-007, RQ-NFR-005, RQ-NFR-006.
- GAP-008 (Medium): No formal human-in-the-loop qualitative review loop for coaching quality.
  - Affects: validation of nuanced coaching usefulness/safety framing beyond deterministic checks.
  - Related requirements: RQ-EVAL-011, RQ-EVAL-012, RQ-NFR-007.

### 6.3 Recently Closed Gaps (Merged on `master`)
- Closed GAP-001 (High): Upsert ID conflict-path correctness fixed.
  - Evidence: commit `8a8ee59`, tests `tests/test_db_upsert_ids.py`.
  - Related requirements: RQ-DB-002, RQ-DB-004.
- Closed GAP-002 (High): `/import` closed-connection metadata lookup fixed.
  - Evidence: commit `995028b`, regression test `tests/test_api_import.py`.
  - Related requirements: RQ-API-001.
- Closed GAP-003 (Medium): `/compare` explicit lap query params aligned with UI.
  - Evidence: commit `be3d5c9`, tests `tests/test_compare_endpoint.py`.
  - Related requirements: RQ-API-004, RQ-UI-001.
- Closed GAP-004 (Medium): Units contract normalized across `/insights`, `/compare`, `/map`.
  - Evidence: commit `a8ec07b`, tests `tests/test_units_contract.py`.
  - Related requirements: RQ-UNT-001, RQ-UNT-002.

## 7) Release Gates (P0)
- Gate A: No high severity data-integrity defects open (GAP-001/002 resolved).
- Gate B: API/UI compare contract aligned and tested.
- Gate C: Unit declarations consistent across API responses.
- Gate D: Test suite and trend harness pass in documented local command set.
- Gate E: P0 behavior outputs satisfy RQ-P0-005 through RQ-P0-023 (brevity, coherence, risk tiering, measurable next-session checks, and UI quality).
- Gate F: Unified evaluation harness is in place and passing (backend + frontend scorecard, baseline/regression checks, machine-readable artifacts).
- Gate G: Product-behavior evaluation model is active (auto-scored checks + golden scenarios + current human-review status).

## 8) Delegation Rules
- Every implementation task must cite requirement IDs and target one or more release gates.
- Every PR-sized task must include:
  - Requirement coverage mapping.
  - Tests added/updated and run output summary.
  - Explicit list of deferred items.

## 9) Suggested Task Breakdown
- TASK-ANL-01: Wire `metrics_writer` into persistence path (RQ-ANL-003/006).
- TASK-EVAL-01: Define evaluation schema + scorecard contract for automated decision loops (RQ-EVAL-006/007, RQ-NFR-006).
- TASK-EVAL-02: Expand backend harness to include latency/failure KPIs and baseline governance (RQ-EVAL-001/002/003).
- TASK-EVAL-03: Implement frontend harness for critical trackside flows and UI state validations (RQ-EVAL-004/005).
- TASK-EVAL-04: Add frequent-run workflow and release gating docs/commands (RQ-EVAL-007, RQ-NFR-005).
- TASK-EVAL-05: Implement product-behavior assertion suite + golden scenario drift checks (RQ-EVAL-008/009/010).
- TASK-EVAL-06: Implement coach-review workflow + status integration into scorecard (RQ-EVAL-011/012, RQ-NFR-007).

### 9.1 Completed Task Breakdown (Merged)
- TASK-DB-01: Fix upsert key return guarantees (RQ-DB-002/004).
- TASK-API-01: Fix `/import` connection lifecycle bug (RQ-API-001).
- TASK-API-02: Align `/compare` query contract with UI (RQ-API-004, RQ-UI-001).
- TASK-UNT-02: Normalize units contract for `/insights`, `/compare`, `/map` (RQ-UNT-001/002).

## 10) P1 Planned Requirements (Non-Blocking)

### 10.1 P1 Mode: Why Lap A Was Faster Than Lap B
- RQ-P1-001: System shall support a mode that explains why one lap was faster than another lap.
  - Acceptance: User can select Lap A and Lap B and receive ranked explanatory factors.
- RQ-P1-002: Explanation output shall attribute time difference by corner/phase with evidence.
  - Acceptance: Output includes per-corner or per-segment contribution and supporting metrics.
- RQ-P1-003: Explanation output shall separate causal drivers from correlated observations.
  - Acceptance: Output labels each factor as likely driver, possible contributor, or low-confidence correlate.
- RQ-P1-004: Explanation mode shall include concise coaching translation.
  - Acceptance: Each top explanatory factor includes "what to repeat" and/or "what to avoid next lap."
- RQ-P1-005: Explanation mode shall include confidence and uncertainty notes.
  - Acceptance: Report includes confidence level and data-quality caveats for each major claim.
- RQ-P1-006: P1 explanation mode shall not block P0 release.
  - Acceptance: P0 gates remain unchanged if P1 mode is incomplete.

### 10.2 Suggested P1 Task Stub
- TASK-P1-01: Design and implement "Why Faster" mode API/UI and explanation ranking logic (RQ-P1-001 through RQ-P1-005).
