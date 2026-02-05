# ML Data Collection Plan (Staged)

## Stage 1 — Baseline (now)
Goal: enough data to rank insights per track.
- Target: 50–150 clean laps per track+direction.
- Logs: per-segment metrics + segment deltas + lap validity flags + GPS quality + lean proxy.
- Filter: remove in/out laps and bad GPS.

## Stage 2 — Cross-rider robustness
Goal: stable insight ranking across riders on same track.
- Target: 200–500 clean laps per track+direction.
- Add: rider metadata (experience level), bike type.

## Stage 3 — Cross-track generalization
Goal: patterns that transfer across tracks.
- Target: 500–2,000+ clean laps across 5–10 tracks.
- Add: corner type labeling (slow/medium/fast, radius proxy, elevation change if available).

## Stage 4 — Personalization
Goal: rider-specific tuning.
- Target: 20–50 clean laps per rider per track.
- Approach: small personal adjustment layer on top of global model.

## Must-have logging (now)
- Segment metrics: entry/apex/exit/min speed, line variance, brake/neutral/throttle proxies.
- Segment deltas vs reference.
- Lap validity flags + in/out lap detection.
- GPS quality: PosAccuracy, SpdAccuracy, sample density.
- Lean proxy + quality flags.

## Quality gates
Discard laps with:
- GPS PosAccuracy above threshold for > X% of lap.
- Missing speed samples.
- Extreme segment delta outliers.

## Requirement
- Exclude in-laps and out-laps from training and insight comparison.

---

## Existing in/out lap filtering (current code)
See `analytics/reference.py`:
- `filter_valid_laps()` uses `_apply_out_in_filter()` based on:
  - short_distance (distance < median * min_distance_ratio)
  - short_duration (duration < median * min_duration_ratio)
  - slow_avg_speed (avg speed < median * 0.8)
  - slow_entry_exit (low_speed_ratio + entry/exit speed ratio < 0.6)
These are already used to exclude in/out laps from reference selection and API lap lists.
