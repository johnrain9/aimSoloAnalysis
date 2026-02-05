"""Trackside analytics pipeline for ranked session insights."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import json
import sqlite3
from typing import Dict, List, Optional, Sequence, Tuple

from analytics.deltas import (
    LapWindow,
    SegmentDefinition,
    SegmentDelta,
    compute_segment_deltas,
)
from analytics.reference import LapCandidate, select_reference_laps
from analytics.segments import Segment, detect_segments, label_laps_with_reference
from analytics.segment_metrics import compute_segment_metrics
from analytics.trackside.rank import rank_insights
from analytics.trackside.rules import generate_insights
from domain.run_data import RunData
from storage import db


_KMH_TO_MPS = 1000.0 / 3600.0
_MPS_TO_KMH = 3.6


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
        JSON-serializable insight dicts (top 3-5 by rank).
    """
    conn = db.connect(db_path)
    with conn:
        session = _load_session(conn, session_id)
        if session is None:
            return []
        run_id = _select_run_id(conn, session_id)
        if run_id is None:
            return []
        run_data = _load_run_data(conn, run_id, session.raw_metadata)
        laps = _load_laps(conn, run_id, session)

    if not laps or run_data.distance_m is None:
        return []

    selections = select_reference_laps(run_data, laps)
    track_key = _track_key(session)
    selection = selections.get((track_key, session.track_direction)) or next(
        iter(selections.values()),
        None,
    )
    if selection is None:
        return []

    reference_lap = selection.reference_lap
    target_lap = _select_target_lap(
        laps,
        track_key,
        session.track_direction,
        target_lap_index=target_lap_index,
    )
    if target_lap is None:
        return []

    laps_for_track = [
        lap for lap in laps
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
    segment_defs = _segment_definitions(reference_segments)
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

    reference_metrics = compute_segment_metrics(run_data, reference_window, reference_segments)
    target_metrics = compute_segment_metrics(run_data, target_window, target_segments)

    segments_payload = _build_segments_payload(
        segment_defs,
        segment_deltas,
        reference_metrics,
        target_metrics,
    )
    comparison_label = _comparison_label(reference_lap, target_lap)
    insights = generate_insights(segments_payload, comparison_label=comparison_label)
    return rank_insights(insights, min_count=3, max_count=5)


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


def _segment_definitions(segments: Sequence[Segment]) -> List[SegmentDefinition]:
    definitions: List[SegmentDefinition] = []
    for idx, segment in enumerate(segments, start=1):
        name = segment.turn_id or segment.label or f"T{idx}"
        definitions.append(
            SegmentDefinition(
                name=name,
                start_m=segment.start_m,
                apex_m=segment.apex_m,
                end_m=segment.end_m,
            )
        )
    return definitions


def _build_segments_payload(
    segment_defs: Sequence[SegmentDefinition],
    segment_deltas: Sequence[SegmentDelta],
    reference_metrics: Dict[str, Dict[str, object]],
    target_metrics: Dict[str, Dict[str, object]],
) -> List[Dict[str, object]]:
    payload: List[Dict[str, object]] = []
    for segment_def, delta in zip(segment_defs, segment_deltas):
        seg_id = segment_def.name
        target = dict(target_metrics.get(seg_id, {}))
        reference = dict(reference_metrics.get(seg_id, {}))

        if "segment_id" not in target and "segment_id" not in reference:
            target["segment_id"] = seg_id
        if "corner_id" not in target and "corner_id" not in reference:
            target["corner_id"] = seg_id

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
                "corner_id": target.get("corner_id") or reference.get("corner_id") or seg_id,
                "target": target,
                "reference": reference,
                "quality": _segment_quality(target),
                "using_speed_proxy": bool(target.get("using_speed_proxy")),
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


def _comparison_label(reference: LapCandidate, target: LapCandidate) -> str:
    if reference.lap_index == target.lap_index:
        return f"Lap {target.lap_index} vs Lap {reference.lap_index}"
    return f"Lap {target.lap_index} vs best Lap {reference.lap_index}"
