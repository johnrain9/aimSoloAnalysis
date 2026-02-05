# Line Stddev Research Notes

## Current Computation
- `line_stddev_m` is produced in `analytics/segment_metrics.py`.
- If a line-error channel exists (`Cross Track Error`, `Line Deviation`, `xte`, etc.), `line_stddev_m` is the standard deviation of that channel over the segment.
- If no line-error channel exists, `_line_stddev_from_latlon` is used:
  - GPS lat/lon points in the segment are projected to local XY.
  - The chord is defined as the straight line between the first and last point.
  - For each point, compute perpendicular distance to the chord.
  - `line_stddev_m` is the standard deviation of those distances.

## Why Large Values Happen (Even With Consistent Lines)
- The fallback metric measures curvature against the chord, not consistency.
- In a curved segment, distance-to-chord grows with arc curvature, even if the rider is consistent.
- Result: "line stddev" can exceed 20 ft without actual line inconsistency.

## Current Filter Usage
- `line_stddev_m` is filtered in `analytics/trackside/pipeline.py`:
  - Samples are dropped when `line_stddev_m > TREND_FILTERS.line_stddev_cap_m`.
  - In eval data, drop reasons are dominated by `line_stddev` (99%+).

## Option B (Reference-Aware Line Consistency)
- Use a reference lap path to compute cross-track error (CTE) per point.
- For a target lap point, find nearest reference point by distance along the lap (or nearest polyline).
- Compute CTE to the reference polyline.
- Subtract mean offset per lap/segment so an alternate but consistent line does not look inconsistent.
- `line_stddev_m = stddev(cte - mean(cte))`.

## Reference Lap Choice (Option B)
- Recommended: use the session reference lap selected by `select_reference_laps` (fastest valid lap per track+direction).
- This keeps consistency evaluation within a session and avoids cross-session drift.
- Alternate: a global reference across related sessions (more comparable, more variance).

## Takeaways
- The current fallback metric is biased by curvature and over-reports variance.
- If we want consistent "line variance" semantics, we should move to a reference-aware CTE metric (Option B) or a detrended self-path metric (Option A).
