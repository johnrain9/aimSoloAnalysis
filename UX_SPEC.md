# Offline-First Trackside Tool UX Spec

## Overview
You’re building an offline-first trackside tool with a fast, priority mode and a deeper at-home mode. Assumption: only GPS/IMU/position/time and derived channels are available (no throttle/brake/RPM).

## Mode 1: Trackside Quick Insights (Priority)
- Track identity is per-track, per-direction (CW/CCW); selectors must include direction
1. Import & Session Picker
- Key components: file drop zone, recent imports list, session list, “Analyze now” CTA, storage status (offline).
- Data shown: file name, timestamp, track guess, rider/bike tags if present, number of laps.
- Interactions: drag/drop, choose session, auto-tag track, “Use last rider/bike”.

2. Run Summary
- Key components: lap time leaderboard, best lap card, consistency sparkline, quick alerts.
- Data shown: best/median lap, lap spread, number of valid laps, outlier count.
- Interactions: tap lap to open lap compare, toggle “valid laps only”.

3. Coaching Insights
- Key components: “Top 3 fixes” cards, corner list with deltas, map/track thumbnail.
- Data shown: time gain estimates, corner IDs (T1, T2), entry/exit speed deltas, line deviation.
- Interactions: tap card to highlight corner on map, swipe for more insights.

4. Lap Compare
- Key components: two-lap selector, overlay map, speed vs distance plot (derived), time delta plot.
- Data shown: path overlay, delta time across lap, corner-segment deltas.
- Interactions: choose laps, auto-align by start/finish, scrub along distance.

5. Corner Detail
- Key components: mini-map of corner, entry/exit markers, line deviation meter, speed trace.
- Data shown: apex position offset, min speed, entry speed, exit speed.
- Interactions: switch to best lap vs selected lap.

## Mode 2: At-Home Deep Analysis
1. Analysis Dashboard
- Key components: session overview, trends, filters, “insights backlog”.
- Data shown: multi-session bests, improvement over time, track conditions tags.
- Interactions: filter by track/rider/bike/date, save views.

2. Multi-Lap Explorer
- Key components: lap table, clustering by pace, session timeline.
- Data shown: lap time distribution, validity flags, weather/notes tags.
- Interactions: pick clusters, compare representative laps.

3. Advanced Corner Analysis
- Key components: corner library, variability heatmap, best-line overlay.
- Data shown: corner-by-corner time loss, line consistency, speed profile variance.
- Interactions: pin corners, export coaching checklist.

4. Rider/Bike Comparison
- Key components: matrix compare, normalized pace, line similarity score.
- Data shown: rider A vs B, bike A vs B, pace deltas by corner.
- Interactions: swap baseline, lock track & conditions.

5. Session Notes & Tags
- Key components: notes editor, tag chips, attachment list.
- Data shown: subjective notes, setup changes, tire info.
- Interactions: add tags, link to sessions.

6. Export & Share (Offline)
- Key components: export presets, PDF summary, data bundle.
- Data shown: selected insights, charts, evidence screenshots.
- Interactions: save to device, generate share pack.

## Default Flow: Import File → View Insights
1. Import & Session Picker
2. Auto-analysis toast: “Analyzing 12 laps…”
3. Run Summary
4. Coaching Insights
5. Tap an insight → Corner Detail or Lap Compare
6. Optional: save insight to checklist

## How Coaching Advice Is Highlighted
- Use “Action Card” format with three fields: Action, Evidence, Estimated gain.
- Example card: “Brake later into T1 by 10–15 m” with evidence “Entry speed −6 km/h vs best lap” and “Est. gain 0.18s”.
- Show only top 3 by estimated gain in Trackside mode; keep the rest behind “More”.
- Use confidence badge (High/Med/Low) and a quick “Why?” tooltip to show data quality.

## Multi-Rider + Multi-Bike Selection
- Global selector in top bar: Rider, Bike, Track (with Direction), Session.
- Trackside mode default: “Last used rider/bike”; switcher is one tap.
- At-home mode: side panel with filters; allow multi-select for compare.
- If multiple riders/bikes in a file, prompt at import: “Split sessions by rider/bike?” with default yes.

## Minimal State Model (Cached for Fast Use)
- Tracks: track map, start/finish, corner definitions.
- Sessions: session metadata, lap list, validity flags.
- Laps: time series of GPS/IMU, derived speed, distance, heading, segment markers.
- Derived metrics: entry/exit speed, apex position offset, time delta by segment.
- Insights: ranked list of coaching actions with evidence and confidence.
- User prefs: last rider/bike/track, units, filters.

## Wireframe Description (Trackside Coaching Insights)
- Top: slim bar with Track, Rider, Bike selectors and “Offline” badge.
- Left: vertical list of “Top 3 fixes” cards; each card shows action + est. gain.
- Right: track map occupying 60% width; highlights selected corner in bold.
- Bottom: mini timeline with lap delta scrubber and lap selector.
- Interaction: tap a card on the left to update the right map highlight and bottom delta chart.

## Confidence / Quality Without Overload
- Use a compact badge: High/Med/Low with tooltip showing “Data quality” and “Sample size”.
- Only show detail on demand; default view uses a simple indicator next to the action.
- If confidence is Low, reduce ranking priority and include a subtle “Verify” label.
