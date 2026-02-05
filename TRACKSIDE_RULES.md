# Trackside Insight Rules (GPS + IMU Only)

## Scope
- Designed for quick, actionable coaching at trackside
- No throttle/brake/RPM channels required
- Uses GPS speed/position and IMU (InlineAcc, LateralAcc, YawRate) when available

## Core Ideas
- Work on distance-aligned data for comparisons
- Compare against a reference lap (fastest clean lap)
- Only surface top 3-5 actionable items per session
- Include confidence based on GPS/IMU quality

## Required Inputs
- GPS position + speed
- InlineAcc (longitudinal accel) and LateralAcc (optional but preferred)
- Lap boundaries
- Corner/segment definitions (auto + manual override)

## Derived Proxies
- Brake zone: sustained negative InlineAcc with decreasing speed
- Throttle pickup: transition from near-zero/negative InlineAcc to sustained positive InlineAcc
- Neutral throttle: InlineAcc near zero with steady speed in a segment
- Line consistency: cross-track error vs reference lap

## Rule Set
### 1) Early Braking
- Definition: brake point occurs earlier than reference by > 8-15 m, and segment time is worse
- Detection:
  - Find first significant negative InlineAcc in approach segment
  - Compare distance to reference lap brake point
- Confidence boosts:
  - GPS accuracy <= 1.0 m
  - InlineAcc signal is smooth (low variance)

### 2) Late Throttle Pickup
- Definition: throttle pickup (InlineAcc rise) occurs later than reference by > 10-20 m
- Detection:
  - Identify first sustained positive InlineAcc after apex
  - Compare distance to reference
- Note: if InlineAcc missing, use speed slope increase

### 3) Neutral Throttle / Coasting
- Definition: InlineAcc near zero for long portion of a segment while speed is flat or slowly falling
- Thresholds:
  - |InlineAcc| < 0.03 g for >= 1.0 s (or >= 15 m)
  - Speed change < 1.0 km/h over the window

### 4) Line Inconsistency
- Definition: higher lateral position variance than reference (same segment)
- Metric: stddev of cross-track error
- Thresholds:
  - Good: <= 0.8 m
  - Moderate: 0.8-1.5 m
  - Poor: > 1.5 m

### 5) Corner Speed Loss
- Definition: min speed at apex is lower vs reference by > 3 km/h
- Detection:
  - Determine apex as min speed in corner segment
  - Compare min speed to reference

## Rules Table (Coach Language, GPS + IMU Only)
| Rule (coach language) | Input signals | Computation steps | Thresholds | Confidence scoring |
| --- | --- | --- | --- | --- |
| Brake later into the corner | GPS speed, InlineAcc, GPS position, lap distance | 1) Brake point = first sustained InlineAcc < -0.08 g for >= 0.25 s on approach. 2) Compare brake point distance vs reference. 3) Check segment time delta. | Brake point earlier by >= 10 m and segment time worse by >= 0.08 s. | Start Medium. +1 if GPS accuracy <= 1.0 m and InlineAcc variance low. -1 if IMU missing. |
| Get back to power sooner | InlineAcc, GPS speed, lap distance | 1) Throttle pickup = first sustained InlineAcc > +0.05 g for >= 0.25 s after apex. 2) Compare pickup distance vs reference. | Pickup later by >= 12 m or later by >= 0.12 s. | Start Medium. +1 if InlineAcc present and smooth. -1 if using speed slope proxy only. |
| Stop coasting here | InlineAcc, GPS speed | 1) Find windows where |InlineAcc| < 0.03 g for >= 1.0 s (or >= 15 m). 2) Speed change < 1.0 km/h in window. | Window length >= 1.0 s and segment time worse by >= 0.05 s. | Start Medium. +1 if GPS speed noise low (sigma < 0.5 km/h). -1 if GPS accuracy > 2 m. |
| Carry more minimum speed | GPS speed, lap distance, GPS position | 1) Apex = min speed inside corner. 2) Compare min speed to reference. 3) Verify apex location within tolerance. | Min speed lower by >= 3.0 km/h. | Start Medium. +1 if apex location within +/- 5 m of reference. -1 if apex drifts > 8 m. |
| Use a tighter, repeatable line | GPS position, lap distance | 1) Compute cross-track error vs reference line. 2) Std dev in segment. | Std dev > 1.5 m or increase by >= 0.6 m vs reference. | Start Medium. +1 if GPS accuracy <= 1.0 m. -1 if satellites < 7 or accuracy > 2 m. |
| Improve exit speed | GPS speed, InlineAcc, lap distance | 1) Speed at 30 m after apex. 2) Compare to reference. 3) Check InlineAcc rise after apex. | Exit speed lower by >= 3.0 km/h and InlineAcc rise weaker. | Start Medium. +1 if InlineAcc present. -1 if only speed proxy. |
| Don’t over-slow on entry | GPS speed, InlineAcc | 1) Entry speed 25 m before apex. 2) Compare to reference. 3) Ensure brake point not later than reference. | Entry speed lower by >= 3.0 km/h and brake point same or earlier. | Start Medium. +1 if brake point detected cleanly. -1 if GPS accuracy > 2 m. |
| Smooth your steering here | YawRate, LatAcc (if present), GPS position | 1) YawRate RMS or peak/mean in segment. 2) Compare vs reference. 3) If higher with lower min speed, flag. | YawRate RMS > reference by >= 20% and min speed lower by >= 2.0 km/h. | Start Medium. +1 if YawRate present and stable. -1 if IMU missing. |

## Confidence Scoring
- High: GPS accuracy <= 1.0 m and >= 10 satellites
- Medium: GPS accuracy <= 2.0 m or 7-9 satellites
- Low: worse than above, or IMU missing/noisy

### Confidence Scoring (Numeric)
- Base confidence = 0.5
- +0.2 if GPS accuracy <= 1.0 m or satellites >= 10
- +0.1 if IMU present and variance low in the segment
- -0.2 if GPS accuracy > 2.0 m or satellites < 7
- -0.1 if using speed proxy instead of IMU
- Clamp to [0.1, 0.9]
- Label: High >= 0.75, Medium 0.5-0.74, Low < 0.5

## Output Format (UI)
- Title: short action
- Metric: distance/time delta
- Evidence: small sparkline or min speed delta
- Confidence: high/medium/low

## Notes
- If GPS accuracy fields are missing, default to Medium confidence
- Always verify lap boundaries before generating insights
## False Positive Warnings
- GPS drift can move apex or brake points by 5-10 m, especially under tree cover.
- Lap boundary errors can shift distance alignment and create fake entry/exit deltas.
- IMU noise or missing samples can make brake/pickup detection unstable.
- Low satellite count (< 7) inflates cross-track error and can falsely flag line inconsistency.
- Short segments or very slow corners produce unreliable time gain estimates.

## Decision Defaults (Recommended)
- Default comparison: best lap vs last lap for trackside coaching.
- Auto-fallback: best lap vs median of last 3 valid laps when last lap confidence < 0.5 or GPS accuracy > 2.0 m.
- Only surface insights with confidence >= 0.5 unless fewer than 3 insights qualify.
- Rank insights by time gain * confidence, add a small severity bonus for >= 0.15 s.
- Cap at 2 insights per corner in the top 3-5.
- Always state the comparison and confidence in the coach line.

## Ranking Function (Top 3-5)
Inputs: per-insight time gain estimate (seconds) and confidence [0.1..0.9].
Score:
- InsightScore = TimeGainEstimate * Confidence * (1 + SeverityBonus)
- SeverityBonus = 0.2 if TimeGainEstimate >= 0.15 s else 0
Selection:
- Filter out confidence < 0.5 unless fewer than 3 remain.
- Sort by InsightScore desc.
- Enforce diversity: no more than 2 insights from the same corner.

## Best vs Last vs Median (Guidance)
- If last lap confidence >= 0.5 and GPS accuracy <= 2.0 m: compare best vs last.
- Otherwise compare best vs median(last 3 valid laps).
- Output must explicitly state which comparison was used.
