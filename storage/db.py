"""SQLite helpers for AIM Solo ingestion."""

from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection, schema_path: str | Path = "storage/schema.sql") -> None:
    path = Path(schema_path)
    schema_sql = path.read_text(encoding="utf-8")
    conn.executescript(schema_sql)


def upsert_rider(conn: sqlite3.Connection, name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    existing = conn.execute("SELECT rider_id FROM riders WHERE name = ?", (name,)).fetchone()
    if existing:
        return int(existing["rider_id"])
    cur = conn.execute("INSERT INTO riders (name) VALUES (?)", (name,))
    return int(cur.lastrowid)


def upsert_bike(conn: sqlite3.Connection, name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    existing = conn.execute("SELECT bike_id FROM bikes WHERE name = ?", (name,)).fetchone()
    if existing:
        return int(existing["bike_id"])
    cur = conn.execute("INSERT INTO bikes (name) VALUES (?)", (name,))
    return int(cur.lastrowid)


def upsert_track(
    conn: sqlite3.Connection,
    name: str,
    direction: str,
    location_text: Optional[str] = None,
    length_m: Optional[float] = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO tracks (name, direction, location_text, length_m)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name, direction) DO UPDATE SET
          location_text = COALESCE(excluded.location_text, tracks.location_text),
          length_m = COALESCE(excluded.length_m, tracks.length_m)
        RETURNING track_id
        """,
        (name, direction, location_text, length_m),
    )
    row = cur.fetchone()
    if row:
        return int(row["track_id"])
    row = conn.execute(
        "SELECT track_id FROM tracks WHERE name = ? AND direction = ?",
        (name, direction),
    ).fetchone()
    if not row:
        raise RuntimeError("Failed to upsert track")
    return int(row["track_id"])


def upsert_session(
    conn: sqlite3.Connection,
    track_id: int,
    track_direction: str,
    start_datetime: Optional[str],
    sample_rate_hz: Optional[float],
    duration_s: Optional[float],
    source_file: Optional[str],
    source_format: Optional[str],
    raw_metadata: Optional[dict],
) -> int:
    session_id = None
    if source_file:
        row = conn.execute(
            "SELECT session_id FROM sessions WHERE source_file = ?",
            (source_file,),
        ).fetchone()
        if row:
            session_id = int(row["session_id"])
    if session_id is None and start_datetime:
        row = conn.execute(
            "SELECT session_id FROM sessions WHERE track_id = ? AND start_datetime = ?",
            (track_id, start_datetime),
        ).fetchone()
        if row:
            session_id = int(row["session_id"])

    raw_metadata_json = json.dumps(raw_metadata or {})
    if session_id is None:
        cur = conn.execute(
            """
            INSERT INTO sessions (
              track_id,
              track_direction,
              start_datetime,
              sample_rate_hz,
              duration_s,
              source_file,
              source_format,
              raw_metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                track_id,
                track_direction,
                start_datetime,
                sample_rate_hz,
                duration_s,
                source_file,
                source_format,
                raw_metadata_json,
            ),
        )
        return int(cur.lastrowid)

    conn.execute(
        """
        UPDATE sessions
        SET track_id = ?,
            track_direction = ?,
            start_datetime = ?,
            sample_rate_hz = ?,
            duration_s = ?,
            source_format = ?,
            raw_metadata_json = ?
        WHERE session_id = ?
        """,
        (
            track_id,
            track_direction,
            start_datetime,
            sample_rate_hz,
            duration_s,
            source_format,
            raw_metadata_json,
            session_id,
        ),
    )
    return session_id


def upsert_run(
    conn: sqlite3.Connection,
    session_id: int,
    run_index: int,
    rider_id: Optional[int] = None,
    bike_id: Optional[int] = None,
    comment: Optional[str] = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO runs (session_id, rider_id, bike_id, run_index, comment)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(session_id, run_index) DO UPDATE SET
          rider_id = excluded.rider_id,
          bike_id = excluded.bike_id,
          comment = excluded.comment
        RETURNING run_id
        """,
        (session_id, rider_id, bike_id, run_index, comment),
    )
    row = cur.fetchone()
    if row:
        return int(row["run_id"])
    row = conn.execute(
        "SELECT run_id FROM runs WHERE session_id = ? AND run_index = ?",
        (session_id, run_index),
    ).fetchone()
    if not row:
        raise RuntimeError("Failed to upsert run")
    return int(row["run_id"])


def upsert_lap(
    conn: sqlite3.Connection,
    run_id: int,
    lap_index: int,
    start_time_s: Optional[float],
    end_time_s: Optional[float],
    duration_s: Optional[float],
) -> int:
    cur = conn.execute(
        """
        INSERT INTO laps (run_id, lap_index, start_time_s, end_time_s, duration_s)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(run_id, lap_index) DO UPDATE SET
          start_time_s = excluded.start_time_s,
          end_time_s = excluded.end_time_s,
          duration_s = excluded.duration_s
        RETURNING lap_id
        """,
        (run_id, lap_index, start_time_s, end_time_s, duration_s),
    )
    row = cur.fetchone()
    if row:
        return int(row["lap_id"])
    row = conn.execute(
        "SELECT lap_id FROM laps WHERE run_id = ? AND lap_index = ?",
        (run_id, lap_index),
    ).fetchone()
    if not row:
        raise RuntimeError("Failed to upsert lap")
    return int(row["lap_id"])


def upsert_channel(
    conn: sqlite3.Connection,
    run_id: int,
    name: str,
    unit: Optional[str],
    source_name: Optional[str],
    norm_unit: Optional[str],
) -> int:
    cur = conn.execute(
        """
        INSERT INTO channels (run_id, name, unit, source_name, norm_unit)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(run_id, name, unit, source_name) DO UPDATE SET
          norm_unit = COALESCE(excluded.norm_unit, channels.norm_unit)
        RETURNING channel_id
        """,
        (run_id, name, unit, source_name, norm_unit),
    )
    row = cur.fetchone()
    if row:
        return int(row["channel_id"])
    row = conn.execute(
        """
        SELECT channel_id FROM channels
        WHERE run_id = ? AND name = ? AND unit IS ? AND source_name IS ?
        """,
        (run_id, name, unit, source_name),
    ).fetchone()
    if not row:
        raise RuntimeError("Failed to upsert channel")
    return int(row["channel_id"])


def insert_sample_points(
    conn: sqlite3.Connection,
    rows: Iterable[tuple],
) -> int:
    cur = conn.executemany(
        """
        INSERT INTO sample_points (
          run_id,
          time_s,
          distance_m,
          latitude,
          longitude,
          gps_speed_kmh,
          gps_heading_deg,
          gps_accuracy_m,
          valid_gps
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return cur.rowcount


def upsert_channel_series(
    conn: sqlite3.Connection,
    run_id: int,
    name: str,
    unit: Optional[str],
    source_name: Optional[str],
    samples: Iterable[Optional[float]],
    compression: str = "gzip",
) -> None:
    samples_list = list(samples)
    payload = json.dumps(samples_list, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if compression != "gzip":
        raise ValueError(f"Unsupported compression: {compression}")
    compressed = gzip.compress(payload)
    sample_count = len(samples_list)
    conn.execute(
        """
        INSERT INTO channel_series (
          run_id,
          name,
          unit,
          source_name,
          sample_count,
          compression,
          data_blob
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, name, unit, source_name) DO UPDATE SET
          sample_count = excluded.sample_count,
          compression = excluded.compression,
          data_blob = excluded.data_blob
        """,
        (run_id, name, unit, source_name, sample_count, compression, compressed),
    )
