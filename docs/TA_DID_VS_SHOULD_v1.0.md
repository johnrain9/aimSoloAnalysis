# Truth Artifact: Did-vs-Should Top-Insight Payload Contract v1.0

**Status**: Frozen for implementation handoff  
**Created**: 2026-03-20  
**Task**: TASK-P0-10 / CENTRAL-OPS-92  
**Requirements**: RQ-P0-007, RQ-P0-008, RQ-P0-010 (supports RQ-P0-009, RQ-P0-017)

## 1) Objective

Freeze a single, deterministic payload contract for the top insight's did-vs-should coaching semantics so downstream work (copy policy, evidence plumbing, golden tests, and scorecard gating) can implement against stable fields.

## 2) Scope

### In Scope
- Canonical payload shape for top insight did-vs-should semantics.
- Required vs optional fields.
- Null/fallback behavior when evidence is partial or missing.
- Backward-compatibility policy for current consumers.

### Out of Scope
- UI redesign.
- Scorecard gate implementation details.
- Rewriting all insight text templates.

## 3) Current State Snapshot

Current `/insights` output already includes:
- `operational_action`
- `causal_reason`
- `success_check`
- `evidence` with line/turn-in fields and fallback status in some scenarios.

Gap for downstream work: no explicit frozen `did`, `should`, `because` contract that all consumers can depend on.

## 4) Options Considered

### Option A: Keep current fields only (`operational_action`, `causal_reason`, `success_check`)
- Pros: zero migration effort.
- Cons: "did vs should" semantics remain implicit; harder to test and gate deterministically; contract ambiguity persists.

### Option B: Add explicit top-level fields (`did`, `should`, `because`, `success_check`) while retaining existing fields (Recommended)
- Pros: clear semantics for product behavior and eval gates, low migration risk, additive rollout.
- Cons: temporary duplication between old/new wording fields.

### Option C: Replace existing fields with nested object only (`did_vs_should: {did, should, because, success_check}`)
- Pros: clean schema for long-term.
- Cons: immediate breaking change for API/UI/tests; too risky before golden/gating tasks land.

## 5) Decision

Adopt **Option B** for v1.0: **additive freeze**.

- Canonical semantics are frozen on top-level fields:
  - `did`
  - `should`
  - `because`
  - `success_check`
- Existing fields remain for compatibility during transition.
- Downstream tasks must treat the four fields above as source of truth for did-vs-should behavior checks.

## 6) Frozen Contract (v1.0)

### 6.1 Applicability
- Required for `items[0]` (top insight / primary focus) when `/insights` is in ready state.
- Recommended for additional ranked insights when available, but not a v1.0 hard requirement.

### 6.2 Field Definitions

```json
{
  "did": "string",
  "should": "string",
  "because": "string",
  "success_check": "string",
  "did_vs_should_status": "resolved|partial|insufficient_data",
  "did_vs_should_source": {
    "rule_id": "string|null",
    "evidence_keys": ["string", "..."]
  }
}
```

### 6.3 Required vs Optional
- Required fields:
  - `did` (non-empty string)
  - `should` (non-empty string)
  - `because` (non-empty string)
  - `success_check` (non-empty string)
  - `did_vs_should_status` (enum)
- Optional field:
  - `did_vs_should_source` (object; if present, `evidence_keys` may be empty list)

### 6.4 Content Semantics
- `did`: observed rider behavior in the target lap/session context (what happened).
- `should`: explicit next action cue (what to do next).
- `because`: causal evidence linkage in rider-facing language.
- `success_check`: measurable next-session validation cue.

### 6.5 Unit and Language Policy
- Rider-facing numeric language must follow active rider unit system consistently.
- No fabricated precision when source evidence is missing.
- Avoid internal-only identifiers in rider text (use rider-recognizable corner labeling).

## 7) Deterministic Fallback/Null Behavior

### 7.1 Status Values
- `resolved`: enough evidence to express specific did/should/because with concrete marker or delta.
- `partial`: recommendation is still actionable but one or more specific evidence anchors are unavailable.
- `insufficient_data`: evidence quality/availability does not support precise coaching claim.

### 7.2 Fallback Rules
- Structure never disappears: all required fields remain present even in degraded cases.
- If marker/turn-in context is missing:
  - `did` uses available observed behavior without fake marker distance.
  - `should` uses bounded qualitative cue with real known context.
  - `because` explicitly states evidence limitation.
  - `did_vs_should_status` = `partial` or `insufficient_data`.
- `success_check` remains measurable and rider-observable; if telemetry precision is unavailable, fallback to on-track observable cue with explicit wording.

### 7.3 Disallowed Behaviors
- Missing required fields.
- Empty-string placeholders.
- Invented numeric values not supported by evidence.
- Contradictory did/should statements for same corner-phase top insight.

## 8) Compatibility and Migration Policy

- v1.0 is additive and non-breaking.
- Existing consumers may continue reading legacy fields during transition.
- New implementations and gates must prefer frozen fields.
- Legacy-field deprecation decision is deferred to a later TA revision after TASK-P0-14 is stable.

## 9) Acceptance Checklist (Peer Review)

- Objective is clear and contract-focused.
- Scope is bounded to contract freeze, not implementation redesign.
- Trade-offs and selected option are explicit.
- Required fields and fallback semantics are deterministic.
- Follow-on implementation tasks are defined.

## 10) Downstream Task Stubs (Derived from this freeze)

1. TASK-P0-11 (Implementation)
- Implement deterministic copy policy populating `did`/`should`/`because`/`success_check` for top insight.
- Preserve compatibility fields while deriving from frozen semantics.

2. TASK-P0-12 (Implementation)
- Guarantee evidence plumbing for turn-in target/reference/rider-average/history.
- Ensure fallback status mapping drives `did_vs_should_status` deterministically.

3. TASK-P0-13 (Verification)
- Add golden tests for resolved/partial/insufficient-data scenarios.
- Lock wording structure and field presence for top insight contract.

4. TASK-P0-14 (Verification/Gating)
- Add scorecard checks for did-vs-should required fields, status semantics, and measurable success checks.

## 11) Open Questions

1. Should v1.0 require did-vs-should fields for all ranked insights or only top-1? (Current decision: hard requirement top-1 only.)
2. Should `did_vs_should_source` become required for auditability in v1.1?
3. Should `insufficient_data` top-1 insights be auto-demoted in ranking, or remain rank-eligible with explicit risk/status framing?
4. When should legacy fields (`operational_action`, `causal_reason`) be formally deprecated?

## 12) Implementation Notes for Next Task Owners

- Treat this file as the frozen contract authority for TASK-P0-11 through TASK-P0-14.
- If implementation reveals a contract flaw, open TA revision proposal rather than silently changing field semantics.
