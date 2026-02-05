# Aim Solo Trackside Build Plan

Scope: Trackside minimal flow (import → run summary → insights → lap compare) for a local, offline-first web app. Track identity is always `(track_name, direction)` and direction must be present in selectors and data.

## A. Implementation Checklist (Prioritized)

1. Data + API foundations
1. Define cached state schema for `tracks`, `sessions`, `laps`, `derived_metrics`, `insights`, `prefs`.
1. Add `direction` to track identity everywhere: storage keys, UI selectors, API filters.
1. Stub API routes for `import`, `summary`, `insights`, `compare`, `corner` with static JSON.
1. Ensure `analytics_version` is included in responses for derived data.

2. UI shell + routing
1. Create static `ui/` app with hash routing for the four trackside screens.
1. Implement a persistent top bar with Track+Direction selector plus Rider/Bike/Session.
1. Add a global Offline badge and toast area.

3. Screen 1: Import
1. File drop area with “Recent imports” list (mocked).
1. Required Track+Direction picker with auto-guess and explicit confirm.
1. Rider/Bike picker defaulting to last-used (mocked).
1. “Analyze now” CTA that transitions to Run Summary route.

4. Screen 2: Run Summary
1. Best lap card, lap leaderboard list, consistency sparkline (static), alerts.
1. Valid laps toggle that re-renders list (mocked data).
1. Tap lap → route to Lap Compare with that lap preselected.

5. Screen 3: Coaching Insights
1. Top 3 action cards with Action/Evidence/Est. gain.
1. Confidence badge (High/Med/Low) + “Why?” tooltip.
1. Track map thumbnail placeholder; selecting a card highlights a corner.

6. Screen 4: Lap Compare
1. Two-lap selectors (A/B).
1. Overlay map placeholder, speed vs distance plot placeholder, delta plot placeholder.
1. Corner delta table and scrubber placeholder.

7. Visual polish for clarity
1. Compact confidence badges aligned to the right.
1. +time-gain estimate aligned to the right.
1. Minimal typography + color system (not default stack).

8. Next expansion hooks (no UI yet)
1. Link to Corner Detail route from Insights.
1. Wire import to real ingest API.

## B. Route Map

Trackside routes:
1. `/import`
1. `/summary/:sessionId`
1. `/insights/:sessionId`
1. `/compare/:sessionId`
1. `/corner/:sessionId/:cornerId`

## C. Minimal Cached State Model (Trackside)

1. `tracks`
1. `track_id`
1. `track_name`
1. `direction` (CW/CCW, required)
1. `map_blob`
1. `start_finish`
1. `corners[]`

2. `sessions`
1. `session_id`
1. `track_id`
1. `rider_id`
1. `bike_id`
1. `timestamp`
1. `file_ref`
1. `lap_ids[]`
1. `valid_lap_ids[]`
1. `analytics_version`

3. `laps`
1. `lap_id`
1. `session_id`
1. `lap_time`
1. `valid`
1. `time_series_ref`
1. `distance_series_ref`
1. `segments[]`

4. `derived_metrics`
1. `lap_stats`
1. `segment_stats`
1. `deltas`
1. `version`

5. `insights`
1. `insight_id`
1. `session_id`
1. `corner_id`
1. `action`
1. `evidence`
1. `est_gain_s`
1. `confidence`
1. `why_summary`

6. `prefs`
1. `last_track_id`
1. `last_direction`
1. `last_rider_id`
1. `last_bike_id`
1. `units`
1. `filters`

## D. Confidence + Time-Gain Display Rules

1. Use a compact badge: `High`, `Med`, `Low`.
1. Place the badge in the action card header, right aligned.
1. Show `+0.18s` as a single right-aligned value on the card.
1. Keep evidence to a single line with truncation.
1. If confidence is `Low`, add a subtle `Verify` label and drop rank.
1. Use a “Why?” tooltip that shows `Sample size` and `Data quality`.

