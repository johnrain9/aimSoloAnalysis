-- Schema for AIM Solo analysis (SQLite)
-- Notes:
-- - Raw ingestion data should be treated as immutable. Any corrections or
--   analytics adjustments should be written as new derived data or insights.
-- - Compressed array blobs (per run/channel) are recommended for performance;
--   see implementation notes in project docs.

PRAGMA foreign_keys = ON;

-- Migration tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS riders (
  rider_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS bikes (
  bike_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS tracks (
  track_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('CW', 'CCW', 'UNKNOWN')),
  location_text TEXT,
  length_m REAL,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  UNIQUE (name, direction)
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id INTEGER PRIMARY KEY,
  track_id INTEGER NOT NULL,
  -- Denormalized snapshot to support fast lookups by track + direction
  track_direction TEXT NOT NULL CHECK (track_direction IN ('CW', 'CCW', 'UNKNOWN')),
  start_datetime TEXT,
  sample_rate_hz REAL,
  duration_s REAL,
  source_file TEXT,
  source_format TEXT,
  raw_metadata_json TEXT,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);

CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL,
  rider_id INTEGER,
  bike_id INTEGER,
  run_index INTEGER NOT NULL,
  comment TEXT,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id),
  FOREIGN KEY (rider_id) REFERENCES riders(rider_id),
  FOREIGN KEY (bike_id) REFERENCES bikes(bike_id),
  UNIQUE (session_id, run_index)
);

CREATE TABLE IF NOT EXISTS laps (
  lap_id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL,
  lap_index INTEGER NOT NULL,
  start_time_s REAL,
  end_time_s REAL,
  duration_s REAL,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  UNIQUE (run_id, lap_index)
);

CREATE TABLE IF NOT EXISTS channels (
  channel_id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  unit TEXT,
  source_name TEXT,
  norm_unit TEXT,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  UNIQUE (run_id, name, unit, source_name)
);

CREATE TABLE IF NOT EXISTS channel_series (
  channel_series_id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  unit TEXT,
  source_name TEXT,
  sample_count INTEGER NOT NULL,
  compression TEXT NOT NULL,
  data_blob BLOB NOT NULL,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  UNIQUE (run_id, name, unit, source_name)
);

CREATE TABLE IF NOT EXISTS sample_points (
  sample_point_id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL,
  time_s REAL NOT NULL,
  distance_m REAL,
  latitude REAL,
  longitude REAL,
  gps_speed_kmh REAL,
  gps_heading_deg REAL,
  gps_accuracy_m REAL,
  valid_gps INTEGER NOT NULL DEFAULT 0 CHECK (valid_gps IN (0, 1)),
  -- Optional compressed channel arrays can be linked via run_id + channel metadata
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS derived_metrics (
  derived_metric_id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL,
  run_id INTEGER,
  lap_id INTEGER,
  analytics_version TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  metric_value REAL,
  metric_json TEXT,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (lap_id) REFERENCES laps(lap_id),
  UNIQUE (session_id, run_id, lap_id, metric_name, analytics_version)
);

CREATE TABLE IF NOT EXISTS insights (
  insight_id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL,
  run_id INTEGER,
  lap_id INTEGER,
  severity TEXT,
  insight_type TEXT,
  insight_text TEXT,
  insight_json TEXT,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  FOREIGN KEY (session_id) REFERENCES sessions(session_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (lap_id) REFERENCES laps(lap_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_track_direction
  ON sessions (track_id, track_direction, start_datetime);

CREATE INDEX IF NOT EXISTS idx_runs_session
  ON runs (session_id);

CREATE INDEX IF NOT EXISTS idx_laps_run_index
  ON laps (run_id, lap_index);

CREATE INDEX IF NOT EXISTS idx_sample_points_run_time
  ON sample_points (run_id, time_s);

CREATE INDEX IF NOT EXISTS idx_derived_metrics_session_lap
  ON derived_metrics (session_id, lap_id);

CREATE INDEX IF NOT EXISTS idx_insights_session_lap
  ON insights (session_id, lap_id);
