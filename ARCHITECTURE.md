# Architecture Overview (Aim Solo Analysis)

Date: 2026-02-05

Goals
- Fast, actionable trackside insights (P0)
- Rich, in-depth at-home analysis (P1)
- Multi-rider + multi-bike support
- Extensible ingestion + analytics pipeline
- Local web app, offline-first
- Track identity is per-track, per-direction (CW/CCW)

Core principles
- Raw data is immutable; derived outputs are versioned
- Ingestion is pluggable (XRK, CSV, future devices)
- Analytics consumes a standardized, time/distance-aligned `RunData`
- Explicit schema + migrations for maintainability
- Caching and precomputation for responsiveness

Directory layout (proposed)
- ingest/
  - xrk/
    - indexer.py (block scanner + registry)
    - decoder.py (channel decoding)
    - mapping.py (tag/channel definitions)
  - csv/
    - importer.py (RaceStudio CSV ingest)
  - normalizers/
    - resample.py (time/distance grid alignment)
- domain/
  - models.py (Rider, Bike, Track, Session, Run, Lap, Channel)
  - run_data.py (aligned series container)
  - segments.py (corner/sector definitions)
- analytics/
  - trackside/
    - rules.py (fast insights)
    - scoring.py (confidence)
  - deep/
    - trends.py (long-term analysis)
  - metrics/
    - lap_stats.py
    - segment_stats.py
    - deltas.py
- storage/
  - schema.sql
  - migrations/
  - blobs.py (compressed arrays)
- api/
  - app.py (local web API)
  - routes/
- ui/
  - (web app)

Data flow
1) Ingest file -> channel registry + raw samples
2) Normalize -> time/distance aligned `RunData`
3) Compute metrics -> store as derived tables
4) Trackside rules -> top insights + confidence
5) UI fetches summaries for fast render

Extensibility points
- New format adapters in ingest/
- New analytics rules registered in analytics/trackside
- New segment strategies in domain/segments
- New metrics computed in analytics/metrics and stored with versioning

Versioning strategy
- `analytics_version` field stored with each derived metric set
- Backfill capability to recompute when rules change

Track direction policy
- Track identity is (track_name, direction)
- Direction is required (CW or CCW)
- Segment/corner definitions are unique per direction
- Reference laps and comparisons must match direction

Notes
- Throttle/brake/RPM not available; derive proxies from longitudinal accel and speed
- GPS + IMU channels vary by file; channel registry must be dynamic
