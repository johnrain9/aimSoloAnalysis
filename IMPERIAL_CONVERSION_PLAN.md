# Imperial Units Conversion Plan (mph, feet)

Goal: convert all user-facing outputs to imperial while keeping internal calculations metric.

## Core Principle
- Internal analytics and storage remain metric (m, m/s, km/h).
- Convert at the API response boundary to imperial.
- UI only formats labels and does not re-convert if API already returns imperial.

## Conversion Formulas
- `m -> ft`: `ft = m * 3.28084`
- `km/h -> mph`: `mph = kmh * 0.621371`
- `m/s -> mph`: `mph = mps * 2.23694`
- `s -> s`: no change
- `g`: no change
- `deg`: no change

## Where to Convert
1) API layer (recommended)
- Add a unit-conversion step in API responses for endpoints used by `ui/app.js`:
  - `/summary/{session_id}`
  - `/insights/{session_id}`
  - `/compare/{session_id}`
  - `/map/{session_id}` (if distances are displayed or compared with UI using units)
- Include a top-level flag: `units: "imperial"` in each response.

2) UI layer (only formatting)
- UI should only display units based on response units.
- Update evidence labels in `formatEvidence()` to use `ft` and `mph`.

## Field Inventory + Conversions

### Insights (from `analytics/trackside/rules.py` / `generate_insights`)
Evidence fields (convert in API response):
- `brake_point_delta_m` -> ft
- `pickup_delta_m` -> ft
- `neutral_throttle_dist_m` -> ft
- `line_stddev_m` -> ft
- `line_stddev_delta_m` -> ft
- `apex_delta_m` -> ft
- `entry_speed_delta_kmh` -> mph
- `min_speed_delta_kmh` -> mph
- `exit_speed_delta_kmh` -> mph
- `neutral_speed_delta_kmh` -> mph
- `segment_time_delta_s` -> seconds (no change)
- `inline_acc_rise_delta_g` -> g (no change)
- `yaw_rms_ratio` -> unitless (no change)

Insight-level fields:
- `time_gain_s` -> seconds (no change)

UI impact:
- Update evidence strings in `ui/app.js` `formatEvidence()` to use `ft`/`mph` labels.

### Compare (UI uses `compare.comparison`)
- `delta_by_sector`: seconds (no change)
- `delta_by_segment[].delta_s`: seconds (no change)
- Any `brake_points[].delta_m` -> ft (if present in API payload)

### Track Map / Segments
The UI uses `segment.start_m / end_m / apex_m` to filter map points. To keep consistency:
- Option A (safe): keep map geometry in meters internally and convert nothing; UI does not display units, only uses distances for filtering. If this option is chosen, add `units: "metric"` in `track_map` to signal no conversion.
- Option B (full imperial output): convert these fields to feet in API and convert `reference_points[*][2]` / `target_points[*][2]` distance column to feet as well (x,y can remain meters since they are only for drawing; if you prefer unit purity, convert x,y to feet too).

Recommended: Option A to avoid breaking geometry math, unless you also convert point distances in the same response.

### Summary
- Lap times and deltas are time-based: no change.
- Percentages: no change.
- If any speed or distance appears later, apply mph/ft.

## Implementation Locations (Suggested)
- Add a small conversion module in `api/` (e.g., `api/units.py`) with helpers:
  - `to_feet(m)`, `to_mph(kmh)`
  - `convert_insight_evidence(evidence)`
  - `convert_track_map(map_payload)`
  - `convert_compare(compare_payload)`

- Apply conversion in API handlers after analytics functions return metric data, before JSON serialization.

## UI Formatting Notes (`ui/app.js`)
- Update `formatEvidence()` labels:
  - Replace `m` with `ft`
  - Replace `km/h` with `mph`
- Do not re-convert if API is already imperial.

## Guardrails
- Keep `units` field in all responses (`imperial` or `metric`).
- If `units` is `metric`, UI should display metric labels without converting.
- If `units` is `imperial`, UI should display imperial labels and skip conversion.
