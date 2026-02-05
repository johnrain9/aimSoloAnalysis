# Robust Segmenting Algorithm (GPS + Speed, Optional IMU)

This document defines a practical segmentation approach for track laps using GPS and speed (optional IMU).

## 1. Corner Start/End and Apex Detection

### Signals
- Primary: GPS position, speed `v`, heading `ψ` (from GPS course over ground).
- Optional: IMU yaw rate `r` (gyro), lateral accel `ay`.
- Derived: path curvature `κ` ≈ dψ/ds (heading change per distance), or `r / v` if IMU present.

### Preprocessing
1. Resample to uniform time (e.g., 10–20 Hz).
2. Smooth `ψ` and `v` with a low‑pass filter (e.g., Savitzky–Golay or Butterworth).
3. Compute `κ` by differentiating heading wrt distance:
   - `Δψ` unwrapped; `Δs` from GPS; `κ = Δψ / Δs`.
   - If IMU: `κ ≈ r / v` (clip `v` small).

### Corner candidate detection
- Use thresholds on curvature magnitude plus persistence:
  - `|κ| > κ_start` for at least `T_min` or distance `D_min` → corner entry candidate.
  - `|κ| < κ_end` for at least `T_min` → corner exit candidate.
- Hysteresis: `κ_start > κ_end` to avoid chatter.
- Merge adjacent corner segments if separated by short straights (`< D_merge`).

### Corner start/end refinement
- Start = first point where `|κ|` exceeds `κ_start` after a straight.
- End = last point where `|κ|` stays above `κ_end` before returning to straight.
- If speed is unreliable, add a secondary check:
  - Entry often coincides with braking: `dv/ds < -a_min` can help refine start.
  - Exit often coincides with acceleration: `dv/ds > a_min` can help refine end.
- If IMU: confirm turn direction via sign of `r` or `ay`.

### Apex detection
- Apex = peak curvature magnitude within the corner:
  - `apex = argmax |κ|` between start/end.
- If hairpin or double‑apex: use local maxima separation > `D_apex_gap`.
  - Keep primary apex (largest |κ|) and optionally tag secondary apexes.

### Recommended defaults (tune per track/receiver)
- `κ_start`: 0.015–0.030 1/m
- `κ_end`: 0.008–0.015 1/m
- `D_min`: 15–30 m
- `D_merge`: 10–20 m
- `T_min`: 0.4–0.8 s

## 2. Consistent Turn Labeling Across Laps (Per Track Direction)

### Goal
Stable IDs like “T1, T2, …” consistent across laps.

### Approach
1. Build a reference lap with stable corner list and track direction.
2. For each lap, match detected corners to reference corners by spatial proximity and order.
3. Use direction (CW/CCW) to enforce sign consistency.

### Track direction
- Compute lap direction from the sign of average curvature (or signed area of path).
- Store as `direction = CW | CCW`.

### Reference corner templates
Each reference corner has:
- `center point` (mean GPS of corner points or apex location).
- `entry/exit bearings`.
- `radius proxy` (mean |κ| or min radius).
- `turn sign` (left/right = sign of κ).

### Matching per lap
- For each detected corner, compute distance to reference corner center and compare order along lap distance.
- Use dynamic time warping or simpler nearest‑neighbor with order constraint:
  - Ensure consistent sequence with small allowed skips/merges.
- Reject matches if:
  - Distance > `D_match_max` (e.g., 30–60 m) or sign mismatch.
- Unmatched corners become “new” or “unknown” until manual review.

### Labeling rule
- If matched, label as `T{index}` from reference.
- Store `turn_id` stable across laps; store `lap_turn_id` for per‑lap detection instance.

## 3. Reference Lap Selection (Fastest Valid Lap Per Track+Direction, With Outlier Filtering)

### Steps
1. Group by `track_id + direction`.
2. Compute lap time and validity flags (off‑track, incomplete, GPS dropout).
3. Filter outliers:
   - Remove laps with missing data > `p%` (e.g., 2–5% of samples).
   - Remove laps with abnormal distance (`|dist - median| > k * MAD`, e.g., k=3).
   - Remove laps with large GPS jitter (median HDOP/pos error above threshold).
4. From remaining, pick the fastest lap as reference.
5. If fastest lap fails corner detection (e.g., missing turns), pick next fastest.

### Optional robustness
- If the fastest lap has unusual speed spikes or curvature anomalies, require:
  - Turn count within ±1 of median.
  - Average curvature profile correlation with median > 0.7.

## 4. Manual Overrides in the Data Model

Design the model to support authoritative edits without breaking automation.

### Entities
- `Lap`
  - `lap_id`, `track_id`, `direction`, `time`, `is_valid`, `source`, `quality_flags`
- `Turn` (reference, stable across laps)
  - `turn_id`, `track_id`, `direction`, `label`, `center`, `entry_bearing`, `exit_bearing`, `sign`
- `LapTurn` (per lap detection instance)
  - `lap_turn_id`, `lap_id`, `turn_id?`, `start_idx`, `apex_idx`, `end_idx`, `confidence`, `auto_version`
- `Override`
  - `override_id`, `target_type` (LapTurn/Turn), `target_id`, `field`, `old_value`, `new_value`, `author`, `timestamp`, `reason`

### Override rules
- If `Override` exists for a field, it supersedes auto output.
- Preserve auto output for auditability (`auto_version` + original fields).
- Allow:
  - Re‑labeling turns (`turn_id` assignment).
  - Adjusting `start/apex/end` indices.
  - Adding/removing corners.
  - Marking laps invalid.

### Conflict policy
- Auto‑recompute never overwrites manual fields unless explicitly cleared.
- Store `manual_lock` flag on `LapTurn` for fields that should remain fixed.
