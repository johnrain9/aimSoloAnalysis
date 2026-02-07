"""Trackside analytics pipeline for ranked session insights."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import json
import sqlite3
from typing import Dict, List, Optional, Sequence, Tuple
import math

from analytics.deltas import (
    LapWindow,
    SegmentDefinition,
    SegmentDelta,
    compute_segment_deltas,
)
from analytics.reference import LapCandidate, select_reference_laps, filter_valid_laps
from analytics.segments import Segment, detect_segments, label_laps_with_reference
from analytics.segment_metrics import compute_segment_metrics
from analytics.trackside.corner_identity import rider_corner_label
from analytics.trackside.rank import rank_insights
from analytics.trackside.config import TREND_FILTERS
from analytics.trackside.signals import generate_signals
from analytics.trackside.synthesis import synthesize_insights
from domain.run_data import RunData
from storage import db


_KMH_TO_MPS = 1000.0 / 3600.0
_MPS_TO_KMH = 3.6

_FATIGUE_MIN_LAPS = 6
_FATIGUE_EARLY_SHARE = 0.65
_FATIGUE_MIN_FADE_S = 0.18
_FATIGUE_MIN_FADE_RATIO = 0.015
_FATIGUE_MAX_APEX_SHIFT_M = 4.0
_FATIGUE_MAX_LINE_SHIFT_M = 0.35
_RECURRENCE_PRIORITY_BIAS_MIN_M = 2.0
_RECURRENCE_PRIORITY_GROWTH_MIN_M = 1.0

# Line trend filtering (configurable, balanced defaults).


@dataclass(frozen=True)
class _SessionInfo:
    session_id: int
    track_id: Optional[int]
    track_name: Optional[str]
    track_direction: str
    raw_metadata: Dict[str, str]


def generate_trackside_insights(
    db_path: str,
    session_id: int,
    target_lap_index: Optional[int] = None,
) -> List[Dict[str, object]]:
    """Generate ranked trackside insights for a session.

    Args:
        db_path: Path to the SQLite database (aimsolo.db).
        session_id: Session identifier to analyze.
        target_lap_index: Optional lap index to compare against the reference lap.

    Returns:
        JSON-serializable insight dicts (top 3 by rank).
    """
    conn = db.connect(db_path)
    with conn:
        session = _load_session(conn, session_id)
        if session is None:
            return []
        run_info = _load_run_info(conn, session_id)
        if run_info is None:
            return []
        run_id, rider_id, bike_id = run_info
        run_data = _load_run_data(conn, run_id, session.raw_metadata)
        laps = _load_laps(conn, run_id, session)

    if not laps or run_data.distance_m is None:
        return []

    lap_stats = filter_valid_laps(run_data, laps)
    valid_laps = [stat.lap for stat in lap_stats if stat.is_valid]
    if not valid_laps:
        valid_laps = list(laps)

    selections = select_reference_laps(run_data, valid_laps)
    track_key = _track_key(session)
    selection = selections.get((track_key, session.track_direction)) or next(
        iter(selections.values()),
        None,
    )
    if selection is None:
        return []

    reference_lap = selection.reference_lap
    target_lap = _select_target_lap(
        valid_laps,
        track_key,
        session.track_direction,
        target_lap_index=target_lap_index,
    )
    if target_lap is None:
        return []

    laps_for_track = [
        lap for lap in valid_laps
        if _track_key_from_lap(lap) == track_key and lap.direction == session.track_direction
    ]
    laps_for_track.sort(key=lambda lap: lap.lap_index)

    reference_index = next(
        (idx for idx, lap in enumerate(laps_for_track) if lap.lap_id == reference_lap.lap_id),
        0,
    )
    target_index = next(
        (idx for idx, lap in enumerate(laps_for_track) if lap.lap_id == target_lap.lap_id),
        None,
    )
    if target_index is None:
        return []

    segmentation_results = [
        detect_segments(_slice_run_data(run_data, lap.start_time_s, lap.end_time_s))
        for lap in laps_for_track
    ]
    _, labeled_laps = label_laps_with_reference(
        segmentation_results,
        track_key=str(track_key),
        direction=session.track_direction,
        reference_index=reference_index,
        lap_ids=None,
    )

    reference_segments = labeled_laps[reference_index]
    target_segments = labeled_laps[target_index]
    segment_defs, corner_labels = _segment_definitions(reference_segments)
    if not segment_defs:
        return []

    reference_window = LapWindow(
        start_time_s=reference_lap.start_time_s,
        end_time_s=reference_lap.end_time_s,
    )
    target_window = LapWindow(
        start_time_s=target_lap.start_time_s,
        end_time_s=target_lap.end_time_s,
    )

    segment_deltas = compute_segment_deltas(
        run_data,
        reference_window,
        target_window,
        segment_defs,
    )

    line_trends = _compute_line_trends(
        conn,
        session,
        run_id=run_id,
        rider_id=rider_id,
        bike_id=bike_id,
        max_sessions=TREND_FILTERS.related_sessions_max,
    )

    reference_metrics = compute_segment_metrics(run_data, reference_window, reference_segments)
    target_metrics = compute_segment_metrics(run_data, target_window, target_segments)

    segments_payload = _build_segments_payload(
        segment_defs,
        segment_deltas,
        reference_metrics,
        target_metrics,
        line_trends=line_trends,
        corner_labels=corner_labels,
    )
    comparison_label = _comparison_label(reference_lap, target_lap)
    signals = generate_signals(segments_payload, comparison_label=comparison_label)
    insights = synthesize_insights(
        segments_payload,
        signals,
        comparison_label=comparison_label,
    )
    return rank_insights(insights, min_count=3, max_count=3, max_primary_focus=2)


def generate_trackside_map(
    db_path: str,
    session_id: int,
    target_lap_index: Optional[int] = None,
    max_points: int = 600,
) -> Optional[Dict[str, object]]:
    """Return a lightweight track map polyline and segment bounds for UI overlays."""
    conn = db.connect(db_path)
    with conn:
        session = _load_session(conn, session_id)
        if session is None:
            return None
        run_id = _select_run_id(conn, session_id)
        if run_id is None:
            return None
        run_data = _load_run_data(conn, run_id, session.raw_metadata)
        laps = _load_laps(conn, run_id, session)

    if not laps or run_data.distance_m is None:
        return None

    selections = select_reference_laps(run_data, laps)
    track_key = _track_key(session)
    selection = selections.get((track_key, session.track_direction)) or next(
        iter(selections.values()),
        None,
    )
    if selection is None:
        return None

    reference_lap = selection.reference_lap
    target_lap = _select_target_lap(
        laps,
        track_key,
        session.track_direction,
        target_lap_index=target_lap_index,
    )
    if target_lap is None:
        return None

    laps_for_track = [
        lap for lap in laps
        if _track_key_from_lap(lap) == track_key and lap.direction == session.track_direction
    ]
    laps_for_track.sort(key=lambda lap: lap.lap_index)
    if not laps_for_track:
        return None

    reference_index = next(
        (idx for idx, lap in enumerate(laps_for_track) if lap.lap_id == reference_lap.lap_id),
        0,
    )

    segmentation_results = [
        detect_segments(_slice_run_data(run_data, lap.start_time_s, lap.end_time_s))
        for lap in laps_for_track
    ]
    _, labeled_laps = label_laps_with_reference(
        segmentation_results,
        track_key=str(track_key),
        direction=session.track_direction,
        reference_index=reference_index,
        lap_ids=None,
    )
    reference_segments = labeled_laps[reference_index] if labeled_laps else []
    segment_defs, corner_labels = _segment_definitions(reference_segments)

    ref_slice = _slice_run_data(run_data, reference_lap.start_time_s, reference_lap.end_time_s)
    ref_points = _track_polyline(ref_slice, max_points=max_points)
    tgt_slice = _slice_run_data(run_data, target_lap.start_time_s, target_lap.end_time_s)
    tgt_points = _track_polyline(tgt_slice, max_points=max_points)
    if not ref_points:
        return None

    segments = [
        {
            "id": seg.name,
            "label": corner_labels.get(seg.name)
            or rider_corner_label(
                None,
                fallback_internal_id=seg.name,
                apex_m=seg.apex_m,
            ),
            "start_m": seg.start_m,
            "apex_m": seg.apex_m,
            "end_m": seg.end_m,
        }
        for seg in segment_defs
    ]

    return {
        "reference_lap": reference_lap.lap_index,
        "target_lap": target_lap.lap_index,
        "track_direction": session.track_direction,
        "reference_points": ref_points,
        "target_points": tgt_points,
        "segments": segments,
    }


def generate_compare_map(
    db_path: str,
    session_id: int,
    lap_a_index: int,
    lap_b_index: int,
    max_points: int = 600,
) -> Optional[Dict[str, object]]:
    """Return polylines for two laps to support compare overlays."""
    conn = db.connect(db_path)
    with conn:
        session = _load_session(conn, session_id)
        if session is None:
            return None
        run_id = _select_run_id(conn, session_id)
        if run_id is None:
            return None
        run_data = _load_run_data(conn, run_id, session.raw_metadata)
        laps = _load_laps(conn, run_id, session)

    if not laps or run_data.distance_m is None:
        return None

    lap_a = next((lap for lap in laps if lap.lap_index == lap_a_index), None)
    lap_b = next((lap for lap in laps if lap.lap_index == lap_b_index), None)
    if lap_a is None or lap_b is None:
        return None

    lap_a_slice = _slice_run_data(run_data, lap_a.start_time_s, lap_a.end_time_s)
    lap_b_slice = _slice_run_data(run_data, lap_b.start_time_s, lap_b.end_time_s)
    points_a = _track_polyline(lap_a_slice, max_points=max_points)
    points_b = _track_polyline(lap_b_slice, max_points=max_points)
    if not points_a or not points_b:
        return None

    return {
        "lap_a": lap_a.lap_index,
        "lap_b": lap_b.lap_index,
        "track_direction": session.track_direction,
        "points_a": points_a,
        "points_b": points_b,
    }


def _load_session(conn: sqlite3.Connection, session_id: int) -> Optional[_SessionInfo]:
    row = conn.execute(
        """
        SELECT s.session_id,
               s.track_id,
               s.track_direction,
               s.raw_metadata_json,
               t.name AS track_name
        FROM sessions s
        LEFT JOIN tracks t ON t.track_id = s.track_id
        WHERE s.session_id = ?
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    raw_metadata: Dict[str, str] = {}
    raw_json = row["raw_metadata_json"]
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                raw_metadata = {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            raw_metadata = {}
    return _SessionInfo(
        session_id=int(row["session_id"]),
        track_id=row["track_id"],
        track_name=row["track_name"],
        track_direction=row["track_direction"] or "UNKNOWN",
        raw_metadata=raw_metadata,
    )


def _select_run_id(conn: sqlite3.Connection, session_id: int) -> Optional[int]:
    row = conn.execute(
        """
        SELECT run_id
        FROM runs
        WHERE session_id = ?
        ORDER BY run_index ASC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return int(row["run_id"])


def _load_run_info(conn: sqlite3.Connection, session_id: int) -> Optional[Tuple[int, Optional[int], Optional[int]]]:
    row = conn.execute(
        """
        SELECT run_id, rider_id, bike_id
        FROM runs
        WHERE session_id = ?
        ORDER BY run_index ASC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return int(row["run_id"]), row["rider_id"], row["bike_id"]


def _load_related_runs(
    conn: sqlite3.Connection,
    session: _SessionInfo,
    *,
    rider_id: Optional[int],
    bike_id: Optional[int],
    max_sessions: int,
) -> List[Dict[str, object]]:
    if session.track_id is None:
        return []
    where = ["s.track_id = ?", "s.track_direction = ?"]
    params: List[object] = [session.track_id, session.track_direction]
    if rider_id is not None:
        where.append("r.rider_id = ?")
        params.append(rider_id)
    if bike_id is not None:
        where.append("r.bike_id = ?")
        params.append(bike_id)

    clause = " AND ".join(where)
    params.append(max_sessions)

    rows = conn.execute(
        f"""
        SELECT s.session_id,
               s.track_id,
               s.track_direction,
               s.raw_metadata_json,
               t.name AS track_name,
               s.start_datetime,
               r.run_id,
               r.rider_id,
               r.bike_id
        FROM sessions s
        JOIN runs r ON r.session_id = s.session_id
        LEFT JOIN tracks t ON t.track_id = s.track_id
        WHERE {clause}
        ORDER BY s.start_datetime DESC, s.session_id DESC
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()

    related: List[Dict[str, object]] = []
    for row in rows:
        raw_metadata: Dict[str, str] = {}
        raw_json = row["raw_metadata_json"]
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    raw_metadata = {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                raw_metadata = {}
        related.append(
            {
                "session_id": int(row["session_id"]),
                "track_id": row["track_id"],
                "track_name": row["track_name"],
                "track_direction": row["track_direction"] or "UNKNOWN",
                "raw_metadata": raw_metadata,
                "run_id": int(row["run_id"]),
                "rider_id": row["rider_id"],
                "bike_id": row["bike_id"],
            }
        )
    return related


def _load_run_data(conn: sqlite3.Connection, run_id: int, metadata: Dict[str, str]) -> RunData:
    columns = _sample_point_columns(conn)
    if "time_s" not in columns:
        return RunData(
            time_s=[],
            distance_m=[],
            lat=[],
            lon=[],
            speed=[],
            channels={},
            metadata=metadata,
        )

    base_columns = [
        "time_s",
        "distance_m",
        "latitude",
        "longitude",
        "gps_speed_kmh",
        "gps_heading_deg",
        "gps_accuracy_m",
    ]
    ignored = {"sample_point_id", "run_id", "valid_gps", "created_at"}
    extra_columns = sorted(
        col for col in columns
        if col not in base_columns and col not in ignored
    )
    selected_columns = [col for col in base_columns if col in columns] + extra_columns

    select_cols = ", ".join(f'"{col}"' for col in selected_columns)
    rows = conn.execute(
        f"""
        SELECT {select_cols}
        FROM sample_points
        WHERE run_id = ?
        ORDER BY time_s ASC
        """,
        (run_id,),
    ).fetchall()

    series: Dict[str, List[Optional[float]]] = {col: [] for col in selected_columns}
    for row in rows:
        for col in selected_columns:
            series[col].append(row[col])

    time_s = series.get("time_s", [])
    distance_m = series.get("distance_m")
    lat = series.get("latitude")
    lon = series.get("longitude")
    speed_kmh = series.get("gps_speed_kmh")
    heading_deg = series.get("gps_heading_deg")
    accuracy_m = series.get("gps_accuracy_m")

    speed_mps = None
    if speed_kmh is not None:
        speed_mps = [
            None if value is None else value * _KMH_TO_MPS
            for value in speed_kmh
        ]

    channels: Dict[str, List[Optional[float]]] = {}
    if heading_deg is not None:
        channels["gps_heading_deg"] = heading_deg
    if accuracy_m is not None:
        channels["gps_accuracy_m"] = accuracy_m
    for col in extra_columns:
        channels[col] = series[col]

    channel_series = _load_channel_series(conn, run_id)
    if channel_series and time_s:
        sample_count = len(time_s)
        for name, samples in channel_series.items():
            if name in channels:
                continue
            channels[name] = _align_series(samples, sample_count)

    return RunData(
        time_s=time_s,
        distance_m=distance_m,
        lat=lat,
        lon=lon,
        speed=speed_mps,
        channels=channels,
        metadata=metadata,
    )


def _sample_point_columns(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute("PRAGMA table_info(sample_points)").fetchall()
    return [row["name"] for row in rows]


def _load_channel_series(conn: sqlite3.Connection, run_id: int) -> Dict[str, List[Optional[float]]]:
    rows = conn.execute(
        """
        SELECT name, compression, data_blob
        FROM channel_series
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchall()

    series: Dict[str, List[Optional[float]]] = {}
    for row in rows:
        name = row["name"]
        compression = row["compression"]
        payload = row["data_blob"]
        if not name or payload is None:
            continue
        try:
            if compression == "gzip":
                decoded = gzip.decompress(payload).decode("utf-8")
            else:
                continue
            values = json.loads(decoded)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(values, list):
            continue
        series[name] = [None if v is None else float(v) for v in values]
    return series


def _align_series(values: Sequence[Optional[float]], sample_count: int) -> List[Optional[float]]:
    if sample_count <= 0:
        return list(values)
    if len(values) == sample_count:
        return list(values)
    if len(values) > sample_count:
        return list(values[:sample_count])
    return list(values) + [None] * (sample_count - len(values))


def _load_laps(
    conn: sqlite3.Connection,
    run_id: int,
    session: _SessionInfo,
) -> List[LapCandidate]:
    rows = conn.execute(
        """
        SELECT lap_id, lap_index, start_time_s, end_time_s
        FROM laps
        WHERE run_id = ?
        ORDER BY lap_index ASC
        """,
        (run_id,),
    ).fetchall()

    laps: List[LapCandidate] = []
    for row in rows:
        if row["start_time_s"] is None or row["end_time_s"] is None:
            continue
        laps.append(
            LapCandidate(
                lap_index=int(row["lap_index"]),
                start_time_s=float(row["start_time_s"]),
                end_time_s=float(row["end_time_s"]),
                direction=session.track_direction or "UNKNOWN",
                track_id=session.track_id,
                track_name=session.track_name,
                lap_id=row["lap_id"],
                run_id=run_id,
            )
        )
    return laps


def _track_key(session: _SessionInfo) -> object:
    if session.track_id is not None:
        return session.track_id
    if session.track_name:
        return session.track_name
    return "UNKNOWN_TRACK"


def _track_key_from_lap(lap: LapCandidate) -> object:
    if lap.track_id is not None:
        return lap.track_id
    if lap.track_name:
        return lap.track_name
    return "UNKNOWN_TRACK"


def _select_target_lap(
    laps: Sequence[LapCandidate],
    track_key: object,
    direction: str,
    *,
    target_lap_index: Optional[int],
) -> Optional[LapCandidate]:
    candidates = [
        lap for lap in laps
        if _track_key_from_lap(lap) == track_key and lap.direction == direction
    ]
    if not candidates:
        return None
    if target_lap_index is not None:
        for lap in candidates:
            if lap.lap_index == target_lap_index:
                return lap
        return None
    return max(candidates, key=lambda lap: lap.lap_index)


def _slice_run_data(run_data: RunData, start_time_s: float, end_time_s: float) -> RunData:
    start_idx, end_idx = _find_index_range(run_data.time_s, start_time_s, end_time_s)
    if start_idx is None or end_idx is None or end_idx <= start_idx:
        return RunData(
            time_s=[],
            distance_m=[],
            lat=[],
            lon=[],
            speed=[],
            channels={},
            metadata=run_data.metadata,
        )

    time_slice = run_data.time_s[start_idx : end_idx + 1]
    distance_slice = run_data.distance_m[start_idx : end_idx + 1] if run_data.distance_m else None
    lat_slice = run_data.lat[start_idx : end_idx + 1] if run_data.lat else None
    lon_slice = run_data.lon[start_idx : end_idx + 1] if run_data.lon else None
    speed_slice = run_data.speed[start_idx : end_idx + 1] if run_data.speed else None

    channels: Dict[str, List[Optional[float]]] = {}
    for name, series in run_data.channels.items():
        channels[name] = series[start_idx : end_idx + 1]

    time_rebased = _rebase_series(time_slice)
    distance_rebased = _rebase_distance(distance_slice)

    return RunData(
        time_s=time_rebased,
        distance_m=distance_rebased,
        lat=lat_slice,
        lon=lon_slice,
        speed=speed_slice,
        channels=channels,
        metadata=run_data.metadata,
    )


def _rebase_series(values: Sequence[Optional[float]]) -> List[Optional[float]]:
    base = next((v for v in values if v is not None), None)
    if base is None:
        return list(values)
    return [None if v is None else v - base for v in values]


def _rebase_distance(values: Optional[Sequence[Optional[float]]]) -> Optional[List[Optional[float]]]:
    if values is None:
        return None
    base = next((v for v in values if v is not None), None)
    if base is None:
        return list(values)
    return [None if v is None else v - base for v in values]


def _segment_definitions(
    segments: Sequence[Segment],
) -> Tuple[List[SegmentDefinition], Dict[str, str]]:
    definitions: List[SegmentDefinition] = []
    corner_labels: Dict[str, str] = {}
    for idx, segment in enumerate(segments, start=1):
        name = segment.turn_id or segment.label or f"T{idx}"
        corner_labels[name] = rider_corner_label(
            segment.label,
            fallback_internal_id=name,
            apex_m=segment.apex_m,
            turn_sign=segment.sign,
        )
        definitions.append(
            SegmentDefinition(
                name=name,
                start_m=segment.start_m,
                apex_m=segment.apex_m,
                end_m=segment.end_m,
            )
        )
    return definitions, corner_labels


def _build_segments_payload(
    segment_defs: Sequence[SegmentDefinition],
    segment_deltas: Sequence[SegmentDelta],
    reference_metrics: Dict[str, Dict[str, object]],
    target_metrics: Dict[str, Dict[str, object]],
    *,
    line_trends: Optional[Dict[str, Dict[str, object]]] = None,
    corner_labels: Optional[Dict[str, str]] = None,
) -> List[Dict[str, object]]:
    payload: List[Dict[str, object]] = []
    for segment_def, delta in zip(segment_defs, segment_deltas):
        seg_id = segment_def.name
        target = dict(target_metrics.get(seg_id, {}))
        reference = dict(reference_metrics.get(seg_id, {}))

        if "segment_id" not in target and "segment_id" not in reference:
            target["segment_id"] = seg_id

        corner_label = rider_corner_label(
            target.get("corner_id")
            or reference.get("corner_id")
            or (corner_labels or {}).get(seg_id),
            fallback_internal_id=seg_id,
            apex_m=segment_def.apex_m,
        )
        target["corner_id"] = corner_label

        _apply_speed_deltas(target, delta)

        segment_time_delta = _delta_value(
            _as_float(target.get("segment_time_s")),
            _as_float(reference.get("segment_time_s")),
        )
        if segment_time_delta is not None:
            target["segment_time_delta_s"] = segment_time_delta

        payload.append(
            {
                "segment_id": seg_id,
                "corner_id": corner_label,
                "corner_label": corner_label,
                "target": target,
                "reference": reference,
                "quality": _segment_quality(target),
                "using_speed_proxy": bool(target.get("using_speed_proxy")),
                "trend": (line_trends or {}).get(seg_id) if line_trends else None,
            }
        )
    return payload


def _apply_speed_deltas(target: Dict[str, object], delta: SegmentDelta) -> None:
    if delta.entry_delta is not None:
        target["entry_speed_delta_kmh"] = _to_kmh(delta.entry_delta)
    if delta.apex_delta is not None:
        target["apex_speed_delta_kmh"] = _to_kmh(delta.apex_delta)
    if delta.exit_delta is not None:
        target["exit_speed_delta_kmh"] = _to_kmh(delta.exit_delta)
    if delta.min_delta is not None:
        target["min_speed_delta_kmh"] = _to_kmh(delta.min_delta)


def _segment_quality(target: Dict[str, object]) -> Dict[str, object]:
    quality: Dict[str, object] = {}
    for key in ("gps_accuracy_m", "satellites", "imu_present", "imu_variance_low", "inline_acc_var"):
        if key in target:
            quality[key] = target.get(key)
    return quality


def _find_index_range(
    time_s: Sequence[Optional[float]],
    start_time_s: float,
    end_time_s: float,
) -> Tuple[Optional[int], Optional[int]]:
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    for idx, value in enumerate(time_s):
        if value is None:
            continue
        if start_idx is None and value >= start_time_s:
            start_idx = idx
        if value <= end_time_s:
            end_idx = idx
        if value > end_time_s and end_idx is not None:
            break
    return start_idx, end_idx


def _to_kmh(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * _MPS_TO_KMH


def _delta_value(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


def _as_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _stddev(values: Sequence[float]) -> Optional[float]:
    if not values or len(values) < 2:
        return None
    mean = _mean(values)
    if mean is None:
        return None
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return variance ** 0.5


def _iqr(values: Sequence[float]) -> Optional[float]:
    if not values or len(values) < 4:
        return None
    ordered = sorted(values)
    n = len(ordered)
    q1 = ordered[n // 4]
    q3 = ordered[(3 * n) // 4]
    return q3 - q1


def _comparison_label(reference: LapCandidate, target: LapCandidate) -> str:
    if reference.lap_index == target.lap_index:
        return f"Lap {target.lap_index} vs Lap {reference.lap_index}"
    return f"Lap {target.lap_index} vs best Lap {reference.lap_index}"


def _compute_line_trends(
    conn: sqlite3.Connection,
    session: _SessionInfo,
    *,
    run_id: int,
    rider_id: Optional[int],
    bike_id: Optional[int],
    max_sessions: int,
) -> Dict[str, Dict[str, object]]:
    related = _load_related_runs(
        conn,
        session,
        rider_id=rider_id,
        bike_id=bike_id,
        max_sessions=max_sessions,
    )
    if not related:
        return {}

    current_laps = _load_laps(conn, run_id, session)
    current_pace = _session_pace(current_laps)

    samples: Dict[str, List[Dict[str, object]]] = {}
    for item in related:
        session_info = _SessionInfo(
            session_id=int(item["session_id"]),
            track_id=item.get("track_id"),
            track_name=item.get("track_name"),
            track_direction=str(item.get("track_direction") or "UNKNOWN"),
            raw_metadata=item.get("raw_metadata") or {},
        )
        run_id_item = int(item["run_id"])
        run_data = _load_run_data(conn, run_id_item, session_info.raw_metadata)
        laps = _load_laps(conn, run_id_item, session_info)
        if not laps or run_data.distance_m is None:
            continue

        pace = _session_pace(laps)
        if current_pace is not None and pace is not None and pace > current_pace * 1.02:
            continue

        lap_stats = filter_valid_laps(run_data, laps)
        valid_laps = [stat.lap for stat in lap_stats if stat.is_valid]
        if not valid_laps:
            valid_laps = list(laps)

        selections = select_reference_laps(run_data, valid_laps)
        track_key = _track_key(session_info)
        selection = selections.get((track_key, session_info.track_direction)) or next(
            iter(selections.values()),
            None,
        )
        if selection is None:
            continue

        reference_lap = selection.reference_lap
        laps_for_track = [
            lap for lap in valid_laps
            if _track_key_from_lap(lap) == track_key and lap.direction == session_info.track_direction
        ]
        laps_for_track.sort(key=lambda lap: lap.lap_index)
        if not laps_for_track:
            continue

        reference_index = next(
            (idx for idx, lap in enumerate(laps_for_track) if lap.lap_id == reference_lap.lap_id),
            0,
        )
        segmentation_results = [
            detect_segments(_slice_run_data(run_data, lap.start_time_s, lap.end_time_s))
            for lap in laps_for_track
        ]
        _, labeled_laps = label_laps_with_reference(
            segmentation_results,
            track_key=str(track_key),
            direction=session_info.track_direction,
            reference_index=reference_index,
            lap_ids=None,
        )

        lap_count = len(laps_for_track)
        for lap_order, (lap, segments) in enumerate(zip(laps_for_track, labeled_laps), start=1):
            lap_window = LapWindow(start_time_s=lap.start_time_s, end_time_s=lap.end_time_s)
            metrics = compute_segment_metrics(run_data, lap_window, segments)
            for seg_id, values in metrics.items():
                sample = {
                    "session_id": session_info.session_id,
                    "lap_id": lap.lap_id,
                    "lap_index": lap.lap_index,
                    "lap_order": lap_order,
                    "lap_count": lap_count,
                    "start_dist_m": _as_float(values.get("start_dist_m")),
                    "apex_dist_m": _as_float(values.get("apex_dist_m")),
                    "line_stddev_m": _as_float(values.get("line_stddev_m")),
                    "segment_time_s": _as_float(values.get("segment_time_s")),
                    "exit_speed_kmh": _as_float(values.get("exit_speed_30m_kmh")),
                    "entry_speed_kmh": _as_float(values.get("entry_speed_kmh")),
                    "min_speed_kmh": _as_float(values.get("min_speed_kmh")),
                    "speed_noise_sigma_kmh": _as_float(values.get("speed_noise_sigma_kmh")),
                }
                samples.setdefault(seg_id, []).append(sample)

    return _summarize_line_trends(samples, current_session_id=session.session_id)


def _summarize_line_trends(
    samples_by_seg: Dict[str, List[Dict[str, object]]],
    *,
    current_session_id: Optional[int] = None,
) -> Dict[str, Dict[str, object]]:
    trends: Dict[str, Dict[str, object]] = {}
    for seg_id, samples in samples_by_seg.items():
        cleaned, filter_stats = _filter_segment_samples_with_stats(samples)
        apex_samples = [s for s in cleaned if s.get("apex_dist_m") is not None]
        if len(apex_samples) < TREND_FILTERS.min_samples:
            continue
        total = len(apex_samples)
        clusters = _cluster_by_apex(
            apex_samples,
            threshold_m=TREND_FILTERS.cluster_apex_threshold_m,
        )
        min_count = max(TREND_FILTERS.min_samples, math.ceil(total * 0.2))
        strong = [c for c in clusters if len(c) >= min_count]
        if not strong:
            continue
        cluster_stats = [_cluster_stats(c) for c in strong]
        recommendation = _pick_cluster(cluster_stats)
        recurrence = _recurrence_context(
            apex_samples,
            recommendation,
            current_session_id=current_session_id,
        )
        fatigue_sessions = int(filter_stats.get("fatigue_sessions") or 0)
        fatigue_late_laps = int(filter_stats.get("fatigue_late_laps") or 0)
        fatigue_max_fade_s = _as_float(filter_stats.get("fatigue_max_fade_s"))
        recent_turn_in = _recent_turn_in_history(
            cleaned,
            current_session_id=current_session_id,
            limit=4,
        )
        trends[seg_id] = {
            "trend_laps": total,
            "session_count": len({s.get("session_id") for s in apex_samples if s.get("session_id") is not None}),
            "trend_strength": "strong"
            if total >= TREND_FILTERS.strong_min_samples
            else "light",
            "apex_mean_m": _mean([s["apex_dist_m"] for s in apex_samples]),
            "apex_stddev_m": _stddev([s["apex_dist_m"] for s in apex_samples]),
            "line_stddev_mean_m": _mean([s["line_stddev_m"] for s in apex_samples if s.get("line_stddev_m") is not None]),
            "clusters": cluster_stats,
            "recommendation": recommendation,
            "recurrence_detected": bool(recurrence["detected"]),
            "recurrence_session_count": int(recurrence["session_count"]),
            "recurrence_priority_shift": bool(recurrence["priority_shift"]),
            "why_now": recurrence["why_now"],
            "fatigue_likely": fatigue_sessions > 0 and fatigue_late_laps > 0,
            "fatigue_session_count": fatigue_sessions,
            "fatigue_late_laps": fatigue_late_laps,
            "fatigue_max_fade_s": fatigue_max_fade_s,
            "recent_turn_in_dist_m": recent_turn_in,
        }
    return trends


def _filter_segment_samples(samples: List[Dict[str, object]]) -> List[Dict[str, object]]:
    filtered, _ = _filter_segment_samples_with_stats(samples)
    return filtered


def _filter_segment_samples_with_stats(
    samples: List[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    if not samples:
        return [], {"raw": 0, "kept": 0, "dropped": 0, "drop_reasons": {}}
    fatigue_late_samples, fatigue_stats = _detect_fatigue_late_samples(samples)
    times = [float(s["segment_time_s"]) for s in samples if s.get("segment_time_s") is not None]
    min_speeds = [float(s["min_speed_kmh"]) for s in samples if s.get("min_speed_kmh") is not None]
    time_median = _median(times)
    time_iqr = _iqr(times)
    min_speed_median = _median(min_speeds)
    min_speed_iqr = _iqr(min_speeds)

    stats = {
        "raw": len(samples),
        "kept": 0,
        "dropped": 0,
        "drop_reasons": {
            "fatigue_late_fade": 0,
            "line_stddev": 0,
            "speed_noise": 0,
            "segment_time_iqr": 0,
            "min_speed_iqr": 0,
        },
        "fatigue_sessions": fatigue_stats["sessions"],
        "fatigue_late_laps": fatigue_stats["late_laps"],
        "fatigue_max_fade_s": fatigue_stats["max_fade_s"],
    }
    filtered: List[Dict[str, object]] = []
    for sample in samples:
        seg_time = _as_float(sample.get("segment_time_s"))
        line_std = _as_float(sample.get("line_stddev_m"))
        speed_noise = _as_float(sample.get("speed_noise_sigma_kmh"))
        min_speed = _as_float(sample.get("min_speed_kmh"))
        sample_id = _sample_identity(sample)

        reason = None
        if sample_id in fatigue_late_samples:
            reason = "fatigue_late_fade"
        elif line_std is not None and line_std > TREND_FILTERS.line_stddev_cap_m:
            reason = "line_stddev"
        elif speed_noise is not None and speed_noise > TREND_FILTERS.speed_noise_cap_kmh:
            reason = "speed_noise"
        elif seg_time is not None and time_median is not None and time_iqr is not None:
            if seg_time > time_median + TREND_FILTERS.iqr_k * time_iqr:
                reason = "segment_time_iqr"
        elif min_speed is not None and min_speed_median is not None and min_speed_iqr is not None:
            if min_speed < min_speed_median - TREND_FILTERS.iqr_k * min_speed_iqr:
                reason = "min_speed_iqr"

        if reason:
            stats["drop_reasons"][reason] += 1
            continue

        filtered.append(sample)
        stats["kept"] += 1

    stats["dropped"] = stats["raw"] - stats["kept"]
    return filtered, stats


def _sample_identity(sample: Dict[str, object]) -> Tuple[object, ...]:
    lap_id = sample.get("lap_id")
    if lap_id is not None:
        return ("lap_id", lap_id)
    return (
        "session_lap",
        sample.get("session_id"),
        sample.get("lap_order"),
        sample.get("lap_index"),
    )


def _sample_order(sample: Dict[str, object]) -> Tuple[float, float]:
    lap_order = _as_float(sample.get("lap_order"))
    lap_index = _as_float(sample.get("lap_index"))
    if lap_order is None:
        lap_order = lap_index
    if lap_order is None:
        lap_order = float("inf")
    if lap_index is None:
        lap_index = lap_order
    return lap_order, lap_index


def _recent_turn_in_history(
    samples: Sequence[Dict[str, object]],
    *,
    current_session_id: Optional[int],
    limit: int,
) -> List[float]:
    ordered = sorted(samples, key=_sample_order)
    if current_session_id is not None:
        current = [s for s in ordered if s.get("session_id") == current_session_id]
        if len(current) >= 2:
            ordered = current
    values: List[float] = []
    for sample in ordered:
        start_dist = _as_float(sample.get("start_dist_m"))
        if start_dist is not None:
            values.append(start_dist)
    if len(values) < 2:
        return []
    return values[-max(2, limit) :]


def _detect_fatigue_late_samples(
    samples: Sequence[Dict[str, object]],
) -> Tuple[set[Tuple[object, ...]], Dict[str, object]]:
    by_session: Dict[int, List[Dict[str, object]]] = {}
    for sample in samples:
        session_id = sample.get("session_id")
        try:
            if session_id is None:
                continue
            session_key = int(session_id)
        except (TypeError, ValueError):
            continue
        by_session.setdefault(session_key, []).append(sample)

    fatigue_sample_ids: set[Tuple[object, ...]] = set()
    flagged_sessions = 0
    max_fade_s: Optional[float] = None

    for session_samples in by_session.values():
        ordered = sorted(session_samples, key=_sample_order)
        if len(ordered) < _FATIGUE_MIN_LAPS:
            continue
        split_idx = max(3, int(math.floor(len(ordered) * _FATIGUE_EARLY_SHARE)))
        if split_idx >= len(ordered) - 1:
            continue

        early = ordered[:split_idx]
        late = ordered[split_idx:]

        early_times = [_as_float(sample.get("segment_time_s")) for sample in early]
        early_times = [value for value in early_times if value is not None]
        late_times = [_as_float(sample.get("segment_time_s")) for sample in late]
        late_times = [value for value in late_times if value is not None]
        if len(early_times) < 2 or len(late_times) < 2:
            continue

        early_median = _median(early_times)
        late_median = _median(late_times)
        if early_median is None or late_median is None or early_median <= 0:
            continue

        fade_s = late_median - early_median
        fade_threshold = max(_FATIGUE_MIN_FADE_S, early_median * _FATIGUE_MIN_FADE_RATIO)
        if fade_s < fade_threshold:
            continue

        early_apex = [_as_float(sample.get("apex_dist_m")) for sample in early]
        early_apex = [value for value in early_apex if value is not None]
        late_apex = [_as_float(sample.get("apex_dist_m")) for sample in late]
        late_apex = [value for value in late_apex if value is not None]

        early_line = [_as_float(sample.get("line_stddev_m")) for sample in early]
        early_line = [value for value in early_line if value is not None]
        late_line = [_as_float(sample.get("line_stddev_m")) for sample in late]
        late_line = [value for value in late_line if value is not None]

        apex_shift = 0.0
        if early_apex and late_apex:
            early_apex_median = _median(early_apex)
            late_apex_median = _median(late_apex)
            if early_apex_median is not None and late_apex_median is not None:
                apex_shift = abs(late_apex_median - early_apex_median)

        line_shift = 0.0
        if early_line and late_line:
            early_line_median = _median(early_line)
            late_line_median = _median(late_line)
            if early_line_median is not None and late_line_median is not None:
                line_shift = abs(late_line_median - early_line_median)

        if apex_shift > _FATIGUE_MAX_APEX_SHIFT_M or line_shift > _FATIGUE_MAX_LINE_SHIFT_M:
            continue

        flagged_sessions += 1
        max_fade_s = fade_s if max_fade_s is None else max(max_fade_s, fade_s)
        for sample in late:
            fatigue_sample_ids.add(_sample_identity(sample))

    return fatigue_sample_ids, {
        "sessions": flagged_sessions,
        "late_laps": len(fatigue_sample_ids),
        "max_fade_s": max_fade_s,
    }


def _recurrence_context(
    apex_samples: Sequence[Dict[str, object]],
    recommendation: Optional[Dict[str, object]],
    *,
    current_session_id: Optional[int],
) -> Dict[str, object]:
    session_ids = {
        int(session_id)
        for session_id in (sample.get("session_id") for sample in apex_samples)
        if session_id is not None
    }
    session_count = len(session_ids)
    detected = session_count >= 2
    rec_apex = _as_float((recommendation or {}).get("apex_mean_m"))
    if not detected or rec_apex is None:
        return {
            "detected": detected,
            "session_count": session_count,
            "priority_shift": False,
            "why_now": None,
        }

    current_apex_values = [
        _as_float(sample.get("apex_dist_m"))
        for sample in apex_samples
        if current_session_id is not None and sample.get("session_id") == current_session_id
    ]
    current_apex_values = [value for value in current_apex_values if value is not None]
    historical_apex_values = [
        _as_float(sample.get("apex_dist_m"))
        for sample in apex_samples
        if current_session_id is None or sample.get("session_id") != current_session_id
    ]
    historical_apex_values = [value for value in historical_apex_values if value is not None]

    current_apex = _median(current_apex_values) if current_apex_values else None
    historical_apex = _median(historical_apex_values) if historical_apex_values else None
    if current_apex is None:
        return {
            "detected": detected,
            "session_count": session_count,
            "priority_shift": False,
            "why_now": None,
        }

    current_bias = abs(current_apex - rec_apex)
    historical_bias = abs(historical_apex - rec_apex) if historical_apex is not None else None
    priority_shift = current_bias >= _RECURRENCE_PRIORITY_BIAS_MIN_M and (
        historical_bias is None
        or current_bias >= historical_bias + _RECURRENCE_PRIORITY_GROWTH_MIN_M
    )

    why_now = None
    if priority_shift:
        if historical_bias is not None:
            why_now = (
                f"Current-session apex bias widened to {current_bias:.1f} m "
                f"from {historical_bias:.1f} m in prior same-track sessions."
            )
        else:
            why_now = (
                f"Current-session apex bias is {current_bias:.1f} m versus the recurring stable line."
            )

    return {
        "detected": detected,
        "session_count": session_count,
        "priority_shift": priority_shift,
        "why_now": why_now,
    }


def _cluster_by_apex(
    samples: List[Dict[str, object]],
    *,
    threshold_m: float,
) -> List[List[Dict[str, object]]]:
    ordered = sorted(samples, key=lambda s: float(s.get("apex_dist_m") or 0.0))
    clusters: List[List[Dict[str, object]]] = []
    current: List[Dict[str, object]] = []
    last = None
    for sample in ordered:
        value = sample.get("apex_dist_m")
        if value is None:
            continue
        if last is None or abs(float(value) - last) <= threshold_m:
            current.append(sample)
        else:
            if current:
                clusters.append(current)
            current = [sample]
        last = float(value)
    if current:
        clusters.append(current)
    return clusters


def _cluster_stats(cluster: List[Dict[str, object]]) -> Dict[str, object]:
    apex_vals = [float(s["apex_dist_m"]) for s in cluster if s.get("apex_dist_m") is not None]
    line_vals = [float(s["line_stddev_m"]) for s in cluster if s.get("line_stddev_m") is not None]
    time_vals = [float(s["segment_time_s"]) for s in cluster if s.get("segment_time_s") is not None]
    exit_vals = [float(s["exit_speed_kmh"]) for s in cluster if s.get("exit_speed_kmh") is not None]
    entry_vals = [float(s["entry_speed_kmh"]) for s in cluster if s.get("entry_speed_kmh") is not None]
    min_vals = [float(s["min_speed_kmh"]) for s in cluster if s.get("min_speed_kmh") is not None]
    return {
        "count": len(cluster),
        "session_count": len({s.get("session_id") for s in cluster if s.get("session_id") is not None}),
        "apex_mean_m": _mean(apex_vals),
        "apex_stddev_m": _stddev(apex_vals),
        "line_stddev_median_m": _median(line_vals),
        "segment_time_median_s": _median(time_vals),
        "exit_speed_median_kmh": _median(exit_vals),
        "entry_speed_median_kmh": _median(entry_vals),
        "min_speed_median_kmh": _median(min_vals),
    }


def _pick_cluster(clusters: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    if not clusters:
        return None
    with_time = [c for c in clusters if c.get("segment_time_median_s") is not None]
    if with_time:
        best_time = min(c["segment_time_median_s"] for c in with_time)  # type: ignore[arg-type]
        close = [
            c for c in with_time
            if c.get("segment_time_median_s") is not None
            and c["segment_time_median_s"] <= best_time + 0.4
        ]
        if close:
            return max(close, key=_cluster_stability_score)
        return min(with_time, key=lambda c: c.get("segment_time_median_s") or float("inf"))
    return max(clusters, key=_cluster_stability_score)


def _cluster_stability_score(cluster: Dict[str, object]) -> float:
    apex_std = cluster.get("apex_stddev_m") or 0.0
    line_std = cluster.get("line_stddev_median_m") or 0.0
    return 1.0 / (1.0 + float(apex_std)) + 1.0 / (1.0 + float(line_std))


def _session_pace(laps: Sequence[LapCandidate]) -> Optional[float]:
    durations = []
    for lap in laps:
        if lap.start_time_s is None or lap.end_time_s is None:
            continue
        durations.append(float(lap.end_time_s - lap.start_time_s))
    if not durations:
        return None
    med = _median(durations)
    if med is None or med <= 0:
        return None
    lower = med * 0.7
    upper = med * 1.3
    trimmed = [d for d in durations if lower <= d <= upper]
    values = trimmed if len(trimmed) >= 3 else durations
    return _median(values)


def _track_polyline(run_data: RunData, *, max_points: int = 600) -> List[List[float]]:
    lat = run_data.lat or []
    lon = run_data.lon or []
    dist = run_data.distance_m or []
    points: List[Tuple[float, float, float]] = []
    origin_lat = None
    origin_lon = None
    last_dist = None
    for la, lo, d in zip(lat, lon, dist):
        if la is None or lo is None or d is None:
            continue
        if origin_lat is None:
            origin_lat = float(la)
            origin_lon = float(lo)
        rel_dist = float(d)
        if last_dist is not None and rel_dist <= last_dist:
            continue
        x, y = _project_latlon(origin_lat, origin_lon, float(la), float(lo))
        points.append((x, y, rel_dist))
        last_dist = rel_dist

    if not points:
        return []
    if max_points > 0 and len(points) > max_points:
        stride = max(1, len(points) // max_points)
        points = points[::stride]
    return [[x, y, d] for x, y, d in points]


def _project_latlon(lat0: float, lon0: float, lat: float, lon: float) -> Tuple[float, float]:
    import math

    r = 6371000.0
    lat0_rad = math.radians(lat0)
    dlat = math.radians(lat - lat0)
    dlon = math.radians(lon - lon0)
    x = dlon * math.cos(lat0_rad) * r
    y = dlat * r
    return x, y
