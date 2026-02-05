# Insight Synthesis Outline (Speed-Only)

## Goal
Reduce conflicting coaching advice by inferring a dominant root cause per segment and emitting a single, coherent recommendation, even with speed + GPS only.

## 1) Phase Model (Entry / Mid / Exit)
- Entry metrics: entry speed delta, brake point delta, early decel length (from speed slope)
- Mid metrics: min speed delta, apex distance delta, line variance
- Exit metrics: exit speed delta, accel rise timing (from speed slope)
- For each metric, define: phase, strength (primary vs secondary), and likely cause.

## 2) Root-Cause Inference
Compute phase confidence scores and pick one dominant hypothesis.
- Entry-issue if entry speed low + brake point early + time loss before apex.
- Mid-issue if min speed low + apex shift + line variance high.
- Exit-issue if exit speed low + delayed acceleration rise + time loss after apex.

## 3) Conflict Resolver (Mutual Exclusion & Precedence)
- If line variance high: suppress “carry more minimum speed” unless min speed delta is extreme.
- If entry speed low: suppress “brake later” if apex is late or line variance high.
- If neutral throttle present:
  - entry zone -> likely braking/line indecision
  - apex zone -> likely line/roll-on timing
  - suppress “earlier throttle” unless exit acceleration is clearly delayed

## 4) Conditional Advice Templates
Replace blunt rules with conditioned templates:
- “If entry speed is low and line variance is stable, consider braking later.”
- “If line variance is high, prioritize line consistency before pushing minimum speed.”
- “If exit speed is low and line stable, focus on earlier throttle pickup.”

## 5) Evidence Bundling
Include “why it won” + “what was suppressed” for transparency:
- Example: “Primary issue: mid-corner line variance (20.3 m). Suppressed: min-speed advice (likely secondary).”

## 6) Analogous Issue Handling
Late throttle may be a symptom of line instability or low corner speed.
- If line variance high or apex delta large, treat late throttle as symptom and suppress throttle advice.
- Only recommend earlier throttle when line variance is low and apex is stable.

## 7) Data Availability Guardrails
No lean angle or brake pressure => avoid aggressive prescriptions.
- If mid-corner speed already high + line stable, prefer smoother brake release over “brake later.”
- If speed low + line unstable, prioritize line stability.

## 8) Confidence Calibration
Lower confidence when:
- GPS accuracy poor
- time deltas extreme (e.g., in/out laps)
- phase metrics disagree

## 9) Insight Consolidation
If multiple issues map to same phase, emit ONE combined insight with 2–3 actions.

## 10) Output Design Intent
Per segment: 1 primary insight max, optional secondary only if non-conflicting.
Session-level: cap repeated advice for the same segment to avoid noise.

---

## Deterministic vs Model-Based (Hybrid Plan)

### Why deterministic first
- Encodes policy/safety (avoid contradictions, be conservative without lean/brake data).
- Easier to explain and verify; lower risk for trackside use.
- Data volume likely insufficient for robust causal learning early on.

### Where a model can help later
- Rank and weight non-conflicting insights.
- Learn metric interactions and latent “corner behavior patterns.”
- Predict likely root cause when rules disagree due to noise.

### Hybrid approach
1) Deterministic synthesis picks phase + suppresses conflicts.
2) Lightweight model adjusts confidence or ranks within allowed insights.
3) Model remains advisory until data volume + validation improve.

## Sketch: Lightweight Model (Advisory)

### Inputs (per segment)
- Deltas: entry/apex/exit/min speed, segment time delta.
- Line metrics: line variance, apex delta.
- Timing metrics: brake point delta, throttle pickup delta, neutral throttle duration.
- Quality: GPS accuracy, sample density, lap validity flags.

### Outputs
- Phase score (entry/mid/exit probability)
- Root-cause label (e.g., early braking, line instability, late throttle)
- Confidence scalar for ranking

### Model type
- Start with calibrated linear/logistic model or gradient-boosted trees.
- Train on “expert-labeled” or consensus data once available.

### Guardrails
- Hard constraints still enforced by deterministic layer.
- Model cannot emit advice outside allowed set.
- If model conflicts with hard constraints, deterministic wins.

---

## Lean-Aware Actionable Decision Table (Draft)

### Inputs (per segment)
- entry_speed_delta, brake_point_delta
- min_speed_delta, apex_delta, line_stddev
- exit_speed_delta, accel_rise_delta
- neutral_throttle duration + speed_flat
- lean_proxy_deg + lean_quality

### Lean gate
- If lean_quality != good -> ignore lean in suppression.
- If lean_proxy >= 42° -> suppress “brake later / trail brake deeper” phrasing.
- If lean_proxy 30–42° -> allow only if entry speed low AND line variance low.

### Decision table (primary insight + actionable wording)

1) Entry-phase issue
- Condition: entry_speed_delta <= -3 mph AND brake_point_delta <= -10 ft (or early)
- Action:
  - If lean high: “Entry is slow; focus on smoother release and line stability before pushing brake points.”
  - Else: “Entry is slow with early braking; move brake marker ~10–15 ft later or reduce initial brake to keep speed.”

2) Mid-corner line issue
- Condition: line_stddev high OR line_stddev_delta high
- Action:
  - “Line is inconsistent; pick a repeatable line and fixed turn-in/apex markers. Speed gains come after consistency.”
  - Suppress “carry more speed” unless min_speed_delta <= -6 mph.

3) Mid-corner speed loss (line stable)
- Condition: min_speed_delta <= -3 mph AND line_stddev low
- Action:
  - If lean high: “Maintain speed through the corner; focus on smooth release and holding line.”
  - Else: “Minimum speed is low; release brake slightly earlier or reduce mid-corner scrub once line is stable.”

4) Late throttle (exit)
- Condition: throttle_pickup later by >= 12 ft or >=0.12s
- Action:
  - If line_stddev high OR apex_delta large: “Delay is likely line-related; stabilize line before earlier throttle.”
  - Else: “Pick up throttle earlier and more smoothly after apex; verify exit speed improves.”

5) Exit speed loss
- Condition: exit_speed_delta <= -3 mph AND accel_rise_delta <= threshold
- Action:
  - “Exit speed is lower; prioritize earlier, smoother throttle pickup and reduce coasting.”

6) Neutral throttle (coasting)
- Condition: neutral_throttle >= 1.0s or 15 ft AND speed flat AND time loss
- Action:
  - If entry issue present: “Avoid coasting; decide brake vs throttle earlier on entry.”
  - If mid-corner issue present: “Hold light maintenance throttle at apex; avoid neutral throttle.”
  - If exit issue present: “Transition earlier to throttle; avoid long neutral zones.”

### Priority rules
- Only one primary insight per segment.
- Order of precedence:
  1) Line inconsistency
  2) Entry speed / brake point
  3) Mid-corner speed loss (if line stable)
  4) Exit speed / late throttle
  5) Neutral throttle (as symptom unless dominant)

### Imperial conversions
- Speed: mph
- Distance: ft
- Keep internal calculations in metric; convert only for output/threshold display.

---

## Light Brake / Light Throttle Detection (Synthesis Notes)

### Light braking (speed-only proxy)
- Detect long, low-magnitude decel on entry:
  - Early brake onset (relative to reference) + low decel magnitude (from speed slope).
  - Long decel duration but shallow speed drop per unit distance.
- Action guidance:
  - If lean proxy high in mid-corner: avoid “brake later/harder.” Prefer “brake a bit earlier but firmer, then smoother release before peak lean.”
  - If lean proxy low: suggest shortening brake zone with slightly higher decel to free time for earlier throttle.

### Light throttle (speed-only proxy)
- Detect extended neutral/maintenance throttle + slow accel rise after apex.
- If line stable and lean decreasing: recommend earlier, smoother roll-on.
- If line unstable or apex shifted: treat as symptom; prioritize line stability before throttle timing.

### Integration with synthesis
- Treat “light brake” as entry-phase issue; “light throttle” as exit-phase issue.
- Apply the same conflict resolver (line inconsistency suppresses speed/throttle advice).
