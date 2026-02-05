# Insight Synthesis Algorithm (Deterministic)

This document defines a deterministic synthesis layer that infers phase, resolves conflicts, and emits one primary insight per segment using speed + GPS only.

## Decision Table
| Step | Condition (per segment) | Phase | Primary Insight | Suppress/Notes | Action Wording (lean-aware) |
|---|---|---|---|---|---|
| 1 | `line_stddev_m > 1.5` OR `line_stddev_delta_m >= 0.6` | Mid | Line inconsistency | Suppress `min_speed` unless `min_speed_delta_kmh <= -6` | ?Line is inconsistent; pick a repeatable line and fixed turn-in/apex markers. Speed comes after consistency.? |
| 2 | `entry_speed_delta_kmh <= -3` AND `brake_point_delta_m <= -10` | Entry | Early/slow entry | Suppress if `line_stddev` high or `apex_delta_m` large | If lean high: ?Entry is slow; focus on smoother release and line stability before pushing brake points.? Else: ?Entry is slow with early braking; move brake marker later or reduce initial brake to keep speed.? |
| 3 | `min_speed_delta_kmh <= -3` AND line stable (`line_stddev_m <= 1.5` AND `line_stddev_delta_m < 0.6`) | Mid | Min speed loss | Suppress if line unstable | If lean high: ?Maintain speed through the corner; focus on smooth release and holding line.? Else: ?Minimum speed is low; release brake slightly earlier or reduce mid-corner scrub once line is stable.? |
| 4 | `throttle_pickup_delta_m >= 12` OR `throttle_pickup_delta_s >= 0.12` | Exit | Late throttle | Suppress if line unstable or `apex_delta_m` large | If line unstable: ?Delay is likely line-related; stabilize line before earlier throttle.? Else: ?Pick up throttle earlier and smoothly after apex; verify exit speed improves.? |
| 5 | `exit_speed_delta_kmh <= -3` AND (`inline_acc_rise_delta_g` is None OR `<= -0.02`) | Exit | Exit speed loss | Suppress if line unstable | ?Exit speed is lower; prioritize earlier, smoother throttle pickup and reduce coasting.? |
| 6 | Neutral throttle present AND speed flat AND time loss | Symptom | Coasting | Only primary if no stronger phase signal | Entry: ?Avoid coasting; decide brake vs throttle earlier on entry.? Mid: ?Hold light maintenance throttle at apex; avoid neutral throttle.? Exit: ?Transition earlier to throttle; avoid long neutral zones.? |

## Phase Inference Logic (Explainable Scoring)
- Entry score: +2 if `entry_speed_delta_kmh <= -3`; +2 if `brake_point_delta_m <= -10`; +1 if time loss is before apex (if available).
- Mid score: +2 if `min_speed_delta_kmh <= -3`; +2 if line variance high; +1 if `apex_delta_m` large.
- Exit score: +2 if `exit_speed_delta_kmh <= -3`; +2 if throttle pickup later; +1 if `inline_acc_rise_delta_g <= -0.02`.
- Dominant phase = max score. If tie, precedence: Line inconsistency > Entry > Mid speed loss > Exit > Neutral throttle.

## Lean Gate
- If `lean_quality != good`, ignore lean gating.
- If `lean_proxy_deg >= 42`, suppress ?brake later / trail brake deeper? phrasing.
- If `30 <= lean_proxy_deg < 42`, allow entry brake advice only when line is stable.

## Conflict Resolver Rules
- If line inconsistency is true, it becomes primary unless min speed loss is extreme (`<= -6 km/h`) and line variance is only mildly elevated.
- Late throttle is treated as a symptom when `line_stddev` high or `apex_delta_m` large.
- Entry braking advice is suppressed when line instability or apex shift suggests line/root-cause over braking.
- Neutral throttle is never primary if any of Steps 1?5 triggers.

## Pseudo-Logic (Deterministic)
```text
for segment in segments:
  metrics = extract()
  phase_scores = score_entry_mid_exit(metrics)

  line_issue = line_stddev_high or line_stddev_delta_high
  min_speed_loss = min_speed_delta <= -3
  min_speed_extreme = min_speed_delta <= -6
  late_throttle = pickup_delta_m >= 12 or pickup_delta_s >= 0.12
  entry_slow = entry_speed_delta <= -3 and brake_point_delta <= -10
  exit_loss = exit_speed_delta <= -3 and (accel_rise_delta <= -0.02 or accel_rise_delta is None)
  neutral = neutral_throttle_long and speed_flat and time_loss

  if line_issue:
    primary = "line_inconsistency"
    if min_speed_extreme and line_issue is mild:
      primary = "min_speed_loss"
    suppress throttle/entry/exit advice
  else if entry_slow and (lean_gate_allows_entry_advice):
    primary = "entry_slow"
  else if min_speed_loss:
    primary = "min_speed_loss"
  else if late_throttle or exit_loss:
    primary = "late_throttle" if late_throttle else "exit_loss"
  else if neutral:
    primary = "neutral_throttle"
  else:
    primary = None

  output one insight with lean-aware wording and evidence
```

## Example Output
Segment has line variance + min speed loss + late throttle (line unstable dominates).

Input metrics:
- `line_stddev_m = 2.1` (high)
- `line_stddev_delta_m = 0.8` (high vs ref)
- `min_speed_delta_kmh = -4.0`
- `throttle_pickup_delta_m = 15`
- `apex_delta_m = 6` (moderate)
- `lean_proxy_deg = 35`, `lean_quality = good`

Primary insight (one only):
- Title: ?Use a tighter, repeatable line?
- Detail: ?Line variance is higher than reference. Late throttle looks line-related; stabilize the line before pushing minimum speed or earlier throttle.?
- Evidence: `line_stddev_m=2.1`, `line_stddev_delta_m=0.8`, `min_speed_delta_kmh=-4.0`, `throttle_pickup_delta_m=15`
