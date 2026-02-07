# TA v1.0 - P0 Coaching Semantics (Frozen)

Frozen on: 2026-02-07  
Scope: P0 coaching-output contract semantics for RQ-P0-006, RQ-P0-007, RQ-P0-017, RQ-P0-018, RQ-P0-024, RQ-P0-025, RQ-P0-026, RQ-P0-027, RQ-P0-028, RQ-P0-029.

## 1) Definitions and invariants
- Output scope: `/insights/{session_id}` emits exactly top 3 ranked insight items when ready.
- `phase` is always one of `entry|mid|exit`.
- `risk_tier` is always one of `Primary|Experimental|Blocked`.
- Corner semantics: every insight is corner- and phase-specific, and `corner_id`/`corner_label` must be rider-recognizable (never raw internal segment IDs).
- Coaching language semantics: each insight must include operational action + causal reason + rider-observable success check; rider-facing text is unit-consistent in the rider unit system.
- Focus semantics: at most 2 items may carry `is_primary_focus=true`.
- Conflict semantics: final ranked set must not contain duplicate `(corner_id, phase)` instructions.
- Top-1 gate semantics: item index 0 includes `quality_gate` and `gain_trace`; gate failure downgrades tier to `Experimental` or `Blocked` and clears primary-focus flag.

## 2) Insight contract fields
Required on every insight item:
- `rule_id`, `title`, `detail`, `phase`
- `did`, `should`, `because` (top-insight did-vs-should semantic sections)
- `operational_action`, `causal_reason`
- `risk_tier`, `risk_reason`
- `data_quality_note`, `uncertainty_note`
- `success_check`
- `expected_gain_s`, `time_gain_s`, `gain`
- `confidence`, `confidence_label`
- `actions` (list), `options` (list)
- `corner_id`, `corner_label`, `comparison`
- `evidence` (object)
- `is_primary_focus` (bool)

Optional/conditional:
- `did_vs_should` object:
  - optional convenience mirror for UI consumers
  - when present, contains `did`, `should`, `because`, `success_check`
  - null/empty section values are not allowed; fallback text must be emitted instead
- `experimental_protocol`:
  - required when `risk_tier=Experimental`
  - otherwise nullable
  - when present, includes `behavior_class`, `expected_gain_s`, `risk`, `bounds`, `abort_criteria` (+ optional `note` for conservative fallback)
- `segment_id`: optional identifier for internal linkage only (not rider-facing)
- `quality_gate`, `gain_trace`: required only for ranked top-1 item

## 3) Recurrence and fatigue semantics
- Recurrence detection:
  - `recurrence_detected=true` when 2+ same-track sessions contribute usable trend samples.
  - `recurrence_priority_shift=true` when current-session apex bias is materially worse than the recurring stable line (bias >= 2.0 m and growth >= 1.0 m vs prior sessions).
  - When priority shift is true and `why_now` exists, coaching detail must append explicit recurrence + "Why now" narration.
- Fatigue detection/de-weighting:
  - Evaluated per session only when lap count >= 6.
  - Late-session fade trigger: late-lap median segment-time slowdown >= max(0.18 s, 1.5% of early median), with no large matching technique shift (apex shift <= 4.0 m and line-shape shift <= 0.35 m).
  - Flagged late laps are dropped from trend fitting and surfaced via fatigue evidence fields (`fatigue_likely`, session/lap counts, max fade).
  - Coaching detail must explicitly state fatigue de-weighting rationale when fatigue is flagged.

## 4) Fallback and failure semantics
- API readiness fallback: if insights cannot be produced, return structured `error=not_ready` payload with explicit `detail`.
- Corner-label fallback order:
  1) explicit rider-facing label,
  2) parsed turn token from internal ID (`...:T7` -> `T7`),
  3) deterministic human phrase (`left-hander/right-hander/corner near <m>`).
- Experimental protocol fallback: unknown change type uses `behavior_class=generic_safe` with conservative one-variable, 1-2 lap bounds and immediate-abort criteria.
- Did-vs-should section fallback: if target/marker context is unavailable or evidence is partial, emit deterministic explicit fallback text for `did|should|because|success_check` and avoid fabricated precision.
- Top-1 gate failure fallback: keep recommendation visible but downgrade risk semantics and attach explicit gate reasons in `quality_gate`.
