# CSV Ingestion Design (AiM RaceStudio Export)

## Observations From Sample CSV
- Metadata block as key/value rows, then blank line, then header row, then units row, then data rows.
- `Time` starts at 0.000 and increments by 0.050 (20 Hz).
- `Distance on GPS Speed` is cumulative distance derived from GPS speed.
- `Beacon Markers` appear to be session-relative times for lap boundaries.

## Design Goals
- Preserve raw data exactly.
- Normalize into a consistent data model that supports new channels and higher frequency data.
- Support lap boundaries even when only beacon markers are present.
- Keep ingestion format-focused; analytics rules live in `analytics/trackside` docs.

## Required Fields
### Rider
- `rider_id`, `name` (from `Racer`)

### Bike
- `bike_id`, `name` (from `Vehicle`)

### Session
- `session_id`, `track_name`, `track_direction`, `start_datetime`, `sample_rate_hz`, `duration_s`, `source_file`, `source_format`
- Sources: `Session`, `Date`, `Time`, `Sample Rate`, `Duration`, `Format`

### Run
- `run_id`, `session_id`, `rider_id`, `bike_id`, `run_index`, `comment`
- `run_index=1` for a single CSV export

### Lap
- `lap_id`, `run_id`, `lap_index`, `start_time_s`, `end_time_s`, `duration_s`
- Sources: `Beacon Markers`, `Segment Times` (if present)

### Channel
- `channel_id`, `name`, `unit`, `source_name`, `norm_unit` (optional)
- Sources: header row and units row

### Sample
- `sample_id`, `run_id`, `channel_id`, `time_s`, `value`
- Derived: `distance_m` (nullable), `latitude` (nullable), `longitude` (nullable)

## Timestamp vs Distance Assumptions
- `Time` is authoritative for sampling; use the `Time` column even if sample rate is present.
- `Distance on GPS Speed` is secondary and may drift vs true track distance.
- Use time-aligned resampling for dynamics; use distance-aligned resampling for line comparison and corner profiles.

## Proposed Schema Mapping
### Tables
- `riders`: `rider_id`, `name`
- `bikes`: `bike_id`, `name`
- `sessions`: `session_id`, `track_name`, `track_direction`, `start_datetime`, `sample_rate_hz`, `duration_s`, `source_file`, `source_format`, `raw_metadata_json`
- `runs`: `run_id`, `session_id`, `rider_id`, `bike_id`, `run_index`, `comment`
- `laps`: `lap_id`, `run_id`, `lap_index`, `start_time_s`, `end_time_s`, `duration_s`
- `channels`: `channel_id`, `name`, `unit`, `source_name`, `norm_unit`
- `sample_points`: `sample_point_id`, `run_id`, `time_s`, `distance_m`, `latitude`, `longitude`, `gps_speed_kmh`, `gps_heading_deg`, `gps_accuracy_m`, `valid_gps`
- `samples`: `sample_id`, `sample_point_id`, `channel_id`, `value`

### Mapping Rules
- Metadata -> `sessions` and `raw_metadata_json`
- Track direction -> `sessions.track_direction` (CW/CCW), from metadata if present; otherwise infer from lap orientation or prompt user
- `Racer` -> `riders.name`
- `Vehicle` -> `bikes.name`
- Header row -> `channels.name`
- Units row -> `channels.unit`
- Each data row -> one `sample_point` plus `samples` for all channels

### Normalization & Storage Notes
- Normalize common units (km/h -> m/s, g -> m/s^2) into `channels.norm_unit` where possible, but store raw values.
- Consider storing per-channel arrays as compressed blobs for performance; keep `samples` table optional or for debug.
- Build a standardized `RunData` object (time/distance aligned) as the analytics entry point.

## Ingestion Pipeline Steps
1. Parse metadata block until blank line; store raw key/values.
2. Parse channel header row and unit row; validate `Time` exists.
3. Stream data rows, parse numeric values.
4. Create `sample_point` with time, distance, and GPS fields.
5. Create `samples` for each channel value (or write arrays for blob storage).
6. Upsert `rider`, `bike`, `session`, `run`.
7. Create `laps` from `Beacon Markers` (if present).
8. If `Beacon Markers` are missing, infer lap boundaries from distance resets or GPS start/finish crossing.
9. Build optional derived series for time- and distance-aligned analysis.

## Additional Fields That Would Improve Analysis
- Throttle position (TPS)
- Brake pressure (front/rear)
- Gear or RPM
- Wheel speeds (front/rear)
- Steering angle
- Suspension travel (front/rear)
- Traction control or ABS status
- Clutch or engine load
- Track ID or lap beacon ID
- GPS HDOP/VDOP
