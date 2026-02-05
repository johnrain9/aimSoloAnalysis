# Aim Solo 2 Analysis App Plan (draft)

Date: 2026-02-05
Location: C:\Users\Paul\ai

Context
- Goal: program for quick and in-depth analysis of Aim Solo 2 data (.xrk)
- P0: multi-rider + multi-bike, quick actionable trackside insights
- P1: long-term multi-session analysis
- Mode 1 (trackside) is first priority
- Deployment: local web app on laptop (trackside), no hosted requirement

Sample file
- C:\Users\Paul\OneDrive\aimSolo\Maddie_Ninja 400_HPR Full_Generic testing_a_0151.xrk
- Observations: binary container with repeated <hTAG blocks

XRK structure findings (initial)
- Repeating tagged blocks: <hCNF, <hCHS, <hCDE, <hGPS, <hLAP, <hTRK, <hVEH, <hVTY, <hRAC, <hRCR, <hSRC, <hPDL, <hTMD, <hTMT, <hVET, <hHWN, <hNDV, <hNTE, <hODO, <hCMP
- Apparent block header: 12 bytes
  - 5 bytes: "<hTAG" (ASCII)
  - 1 byte: flags (observed 0)
  - 4 bytes: payload length (little-endian)
  - 1 byte: version (observed 1)
  - 1 byte: '>' (0x3E)
- Followed by payload, then a smaller trailer "<TAG" header (8 bytes) with a 2-byte length

CHS channel metadata observed
- MClk / Master Clk
- LAP / Lap Time
- PreT / Predictive Time
- BestT / Best Time
- +-BR / Best Run Diff
- +-BT / Best Today Diff
- +-PL / Prev Lap Diff
- +-RL / Ref Lap Diff
- InlA / InlineAcc
- LatA / LateralAcc
- VerA / VerticalAcc
- Roll / RollRate
- Ptch / PitchRate
- YawR / YawRate
- IBat / Internal Battery
- VBat / External Voltage
- DistL / Distance Lap
- DistLI / Distance Lap Int
- StrtRec / StrtRec
- iGPS / iGPS

Ingestion plan (P0)
- Dual path
  1) CSV export workflow from AiM RaceStudio (MVP ships with CSV ingest first; unblocks trackside features)
  2) Parallel native .xrk parser (block scanner + channel registry + decoder; R&D track, not blocking MVP)
- Parser steps
  - Scan and index <hTAG blocks; validate lengths
  - Parse CHS blocks -> channel registry (code, name, units, rate)
  - Correlate CDE/GPS/LAP/TRK blocks with CSV exports to map formats
  - Confirm timebase (likely Master Clk) and resample channels to time or distance grid
  - Add tag logging for unknown blocks

Implementation status (as of 2026-02-05)
- CSV ingestion: parser + RunData + lap inference + DB persistence + sample_points done (CSV path working)
- Analytics pipeline + segment metrics implemented; API endpoints wired to DB data
- Trackside insight rules + ranking + tests implemented
- Current run check: CSV import works but sample 87.csv stored track as UNKNOWN and produced 0 insights
- Remaining MVP work: fix metadata mapping for track + direction, tune insight thresholds, add derived_metrics persistence, raw array blobs, ingestion benchmark
- XRK R&D: continue in parallel, non-blocking

Data model (web app)
- riders(id, name, notes, created_at)
- bikes(id, rider_id, make, model, year, notes)
- tracks(id, name, direction, layout, gps_bounds, notes)
- sessions(id, rider_id, bike_id, track_id, date, conditions, source_file)
- runs(id, session_id, start_time, duration, file_hash)
- laps(id, run_id, lap_index, lap_time, valid, start_ts, end_ts)
- channels(id, code, name, units, sample_rate, source)
- sample_series(id, run_id, channel_id, timebase_id, data_blob, compression)
- segments(id, track_id, name, start_dist, end_dist, type)
- lap_metrics(lap_id, ...)
- segment_metrics(lap_id, segment_id, ...)
- trend_metrics(rider_id, track_id, metric_name, date, value)

Storage choice
- SQLite for metadata + metric tables
- Compressed blobs (zstd) for raw arrays
- Indexes for (track, rider, bike, session, lap)

Analysis catalog
P0 trackside (quick actionable)
- Early braking: brake point earlier vs reference by threshold + time loss in segment
- Line inconsistency: lateral position variance high in a corner
- Neutral throttle / low-accel: long section with low longitudinal accel and flat speed
- Late throttle pickup: throttle or accel rises later than reference lap
- Corner speed loss: lower min speed at apex vs reference

P0 session (fast but richer)
- Delta-time plot by distance (last vs best)
- Braking/accel overlays on key corners
- Turn cards: brake point, min speed, throttle pickup, exit speed
- Consistency: lap time std dev, corner std dev, best-of-5 average

P1 long-term analysis
- Trend charts by track: best lap, consistency, brake point drift, apex speed trend
- Rider/bike comparisons normalized by conditions
- Weakness clustering: recurring corners where time is lost
- Fatigue indicators: pace drop across session, consistency drift

Common analytics
- Normalize by distance along lap
- Auto-segment corners by curvature (GPS) + manual override
- Reference lap per rider/bike/track (fastest clean lap)
- Confidence scoring for insights (magnitude + sample size)

UI/UX flow (web app)
Trackside mode (priority)
- Landing: import latest file + use most recent session
- Rider/bike selector defaults to last used
- Quick Insights: top 3-5 actionable items with turn labels + confidence
- Turn Cards: per-corner metrics + what to fix
- Delta map: track map with speed color + lost-time heat
- Fast compare: last lap vs best lap toggle

At-home deep analysis
- Workspace: track map, delta-time vs distance, channel plots
- Multi-lap compare: overlay 2-4 laps, rider vs rider, bike vs bike
- Segment editor: refine corners and re-run insights
- Trends tab: across sessions and tracks

Notes
- CSV exports include GPS quality + IMU fields (Nsat, PosAccuracy/SpdAccuracy, accel/gyro) that can improve confidence scoring.
- Track identity is per track, per direction (CW/CCW).
- No throttle/brake/RPM files currently; aim to infer via acceleration where possible.
- Laptop local app is acceptable for now (trackside).
