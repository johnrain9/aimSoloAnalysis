"""Persist CSV ingestion outputs into SQLite."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from analytics.deltas import LapWindow
from analytics.metrics_writer import (
    lap_metrics_from_mapping,
    segment_metrics_from_mapping,
    write_lap_metrics,
    write_segment_metrics,
)
from analytics.segment_metrics import compute_segment_metrics
from analytics.segments import detect_segments
from domain.run_data import RunData
from ingest.csv.importer import build_run_data
from ingest.csv.laps import infer_laps
from ingest.csv.parser import CsvParseResult
from storage import db


_CORE_FIELDS = {
    "time",
    "distance on gps speed",
    "gps speed",
    "latitude",
    "longitude",
    "gps heading",
    "gps accuracy",
}
_ANALYTICS_VERSION = "0.1.0-local"


@dataclass
class SaveResult:
    session_id: int
    run_id: int
    lap_count: int
    channel_count: int
    sample_point_count: int


def save_to_db(
    data: Union[CsvParseResult, RunData],
    db_path: str,
    source_file: Optional[str] = None,
    run_index: int = 1,
    analytics_version: str = _ANALYTICS_VERSION,
) -> SaveResult:
    """Persist a CsvParseResult or RunData into SQLite."""
    if isinstance(data, CsvParseResult):
        parse = data
        run_data = build_run_data(parse)
        laps = infer_laps(parse)
        channel_units = _channel_units_from_parse(parse)
        heading = _column_values(parse, "GPS Heading")
        accuracy = _column_values(parse, "GPS Accuracy")
        accuracy_unit = _column_unit(parse, "GPS Accuracy")
        if accuracy is None:
            accuracy = _column_values(parse, "GPS PosAccuracy")
            accuracy_unit = _column_unit(parse, "GPS PosAccuracy")
        accuracy = _normalize_gps_accuracy(accuracy, accuracy_unit)
    elif isinstance(data, RunData):
        parse = None
        run_data = data
        laps = []
        channel_units = {name: None for name in run_data.channels.keys()}
        heading = None
        accuracy = None
    else:
        raise TypeError("data must be CsvParseResult or RunData")

    run_data.validate_lengths()
    metadata = run_data.metadata

    track_name = _track_name(metadata)
    if not track_name:
        track_name = "UNKNOWN TRACK"

    track_direction = _infer_track_direction(metadata, track_name)
    if track_direction == "UNKNOWN":
        inferred = _infer_direction_from_run_data(run_data)
        if inferred:
            track_direction = inferred
    session_fields = _session_fields(metadata, source_file, track_direction)
    rider_name = _first_metadata_value(metadata, ["Racer", "Driver", "Rider"])
    bike_name = _first_metadata_value(metadata, ["Vehicle", "Bike"])
    comment = _first_metadata_value(metadata, ["Comment", "Session Comment"])

    conn = db.connect(db_path)
    db.init_schema(conn)

    with conn:
        rider_id = db.upsert_rider(conn, rider_name)
        bike_id = db.upsert_bike(conn, bike_name)
        track_id = db.upsert_track(conn, track_name, track_direction)
        session_id = db.upsert_session(
            conn,
            track_id=track_id,
            track_direction=track_direction,
            start_datetime=session_fields.start_datetime,
            sample_rate_hz=session_fields.sample_rate_hz,
            duration_s=session_fields.duration_s,
            source_file=session_fields.source_file,
            source_format=session_fields.source_format,
            raw_metadata=metadata,
        )
        run_id = db.upsert_run(
            conn,
            session_id=session_id,
            run_index=run_index,
            rider_id=rider_id,
            bike_id=bike_id,
            comment=comment,
        )

        channel_count = _persist_channels(conn, run_id, run_data, channel_units)
        sample_point_count = _persist_sample_points(
            conn,
            run_id,
            run_data,
            heading,
            accuracy,
        )
        persisted_laps = _persist_laps(conn, run_id, laps)
        lap_count = len(persisted_laps)
        _persist_derived_metrics(
            conn,
            session_id=session_id,
            run_id=run_id,
            run_data=run_data,
            persisted_laps=persisted_laps,
            analytics_version=analytics_version,
        )

        _persist_channel_blobs_stub(run_id, run_data, channel_units)

    return SaveResult(
        session_id=session_id,
        run_id=run_id,
        lap_count=lap_count,
        channel_count=channel_count,
        sample_point_count=sample_point_count,
    )


def _persist_channels(
    conn,
    run_id: int,
    run_data: RunData,
    channel_units: Dict[str, Optional[str]],
) -> int:
    count = 0
    for name in run_data.channels.keys():
        unit = channel_units.get(name)
        db.upsert_channel(
            conn,
            run_id=run_id,
            name=name,
            unit=unit,
            source_name=name,
            norm_unit=None,
        )
        count += 1
    return count


def _persist_sample_points(
    conn,
    run_id: int,
    run_data: RunData,
    heading: Optional[Sequence[Optional[float]]],
    accuracy: Optional[Sequence[Optional[float]]],
) -> int:
    time_s = run_data.time_s
    distance_m = run_data.distance_m
    lat = run_data.lat
    lon = run_data.lon
    speed_mps = run_data.speed

    rows = []
    for idx, t in enumerate(time_s):
        if t is None:
            continue
        dist = distance_m[idx] if distance_m else None
        lat_val = lat[idx] if lat else None
        lon_val = lon[idx] if lon else None
        speed_kmh = _mps_to_kmh(speed_mps[idx]) if speed_mps else None
        heading_val = heading[idx] if heading else None
        accuracy_val = accuracy[idx] if accuracy else None
        valid_gps = 1 if lat_val is not None and lon_val is not None else 0
        rows.append(
            (
                run_id,
                t,
                dist,
                lat_val,
                lon_val,
                speed_kmh,
                heading_val,
                accuracy_val,
                valid_gps,
            )
        )
    return db.insert_sample_points(conn, rows)


def _persist_laps(conn, run_id: int, laps) -> List[Dict[str, float | int | None]]:
    persisted: List[Dict[str, float | int | None]] = []
    for lap in laps:
        duration = None
        if lap.start_time_s is not None and lap.end_time_s is not None:
            duration = lap.end_time_s - lap.start_time_s
        lap_id = db.upsert_lap(
            conn,
            run_id=run_id,
            lap_index=lap.lap_index,
            start_time_s=lap.start_time_s,
            end_time_s=lap.end_time_s,
            duration_s=duration,
        )
        persisted.append(
            {
                "lap_id": int(lap_id),
                "lap_index": int(lap.lap_index),
                "start_time_s": lap.start_time_s,
                "end_time_s": lap.end_time_s,
                "duration_s": duration,
            }
        )
    return persisted


def _persist_derived_metrics(
    conn,
    *,
    session_id: int,
    run_id: int,
    run_data: RunData,
    persisted_laps: Sequence[Dict[str, float | int | None]],
    analytics_version: str,
) -> None:
    if not persisted_laps:
        return

    lap_rows = [
        lap for lap in persisted_laps
        if lap.get("lap_id") is not None
        and lap.get("start_time_s") is not None
        and lap.get("end_time_s") is not None
    ]
    if not lap_rows:
        return

    if run_data.distance_m is None:
        raise RuntimeError(
            "derived metrics persistence prerequisites missing: distance_m is required"
        )

    lap_metrics: Dict[int, Dict[str, float | None]] = {}
    segment_metrics: Dict[int, Dict[str, Dict[str, float]]] = {}

    for lap in lap_rows:
        lap_id = int(lap["lap_id"])  # type: ignore[arg-type]
        start_time_s = float(lap["start_time_s"])  # type: ignore[arg-type]
        end_time_s = float(lap["end_time_s"])  # type: ignore[arg-type]
        duration_s = lap.get("duration_s")

        lap_payload: Dict[str, float | None] = {
            "lap_duration_s": float(duration_s) if duration_s is not None else max(0.0, end_time_s - start_time_s),
        }
        lap_metrics[lap_id] = lap_payload

        lap_window = LapWindow(start_time_s=start_time_s, end_time_s=end_time_s)
        lap_slice = _slice_run_data(run_data, start_time_s, end_time_s)
        try:
            segmentation = detect_segments(lap_slice)
            computed = compute_segment_metrics(run_data, lap_window, segmentation.segments)
        except Exception as exc:  # noqa: BLE001
            lap_index = lap.get("lap_index")
            raise RuntimeError(
                f"derived metrics persistence failed for lap {lap_index}: {exc}"
            ) from exc

        per_lap_segment: Dict[str, Dict[str, float]] = {}
        for segment_id, values in computed.items():
            metrics: Dict[str, float] = {}
            for metric_name in (
                "segment_time_s",
                "entry_speed_kmh",
                "apex_speed_kmh",
                "exit_speed_30m_kmh",
                "min_speed_kmh",
            ):
                metric_value = _as_float(values.get(metric_name))
                if metric_value is not None:
                    metrics[metric_name] = metric_value
            if metrics:
                per_lap_segment[str(segment_id)] = metrics
        if per_lap_segment:
            segment_metrics[lap_id] = per_lap_segment

    write_lap_metrics(
        conn,
        session_id=session_id,
        run_id=run_id,
        analytics_version=analytics_version,
        metrics=lap_metrics_from_mapping(lap_metrics),
        commit=False,
    )
    write_segment_metrics(
        conn,
        session_id=session_id,
        run_id=run_id,
        analytics_version=analytics_version,
        metrics=segment_metrics_from_mapping(segment_metrics),
        commit=False,
    )


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

    return RunData(
        time_s=_rebase_series(time_slice),
        distance_m=_rebase_series(distance_slice) if distance_slice else None,
        lat=lat_slice,
        lon=lon_slice,
        speed=speed_slice,
        channels=channels,
        metadata=run_data.metadata,
    )


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


def _rebase_series(values: Sequence[Optional[float]]) -> List[Optional[float]]:
    base = next((v for v in values if v is not None), None)
    if base is None:
        return list(values)
    return [None if v is None else v - base for v in values]


def _as_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _channel_units_from_parse(parse: CsvParseResult) -> Dict[str, Optional[str]]:
    units = parse.units or []
    result: Dict[str, Optional[str]] = {}
    for idx, name in enumerate(parse.header):
        if _is_core_field(name):
            continue
        unit = units[idx] if idx < len(units) else None
        result[name] = unit if unit != "" else None
    return result


def _column_values(
    parse: CsvParseResult,
    name: str,
) -> Optional[Sequence[Optional[float]]]:
    idx = parse.column_index.get(name)
    if idx is None:
        lowered = {key.lower(): idx for key, idx in parse.column_index.items()}
        idx = lowered.get(name.lower())
    if idx is None:
        return None
    return [row[idx] for row in parse.rows]


def _column_unit(parse: CsvParseResult, name: str) -> Optional[str]:
    idx = parse.column_index.get(name)
    if idx is None:
        lowered = {key.lower(): idx for key, idx in parse.column_index.items()}
        idx = lowered.get(name.lower())
    if idx is None:
        return None
    if not parse.units or idx >= len(parse.units):
        return None
    unit = parse.units[idx]
    return unit if unit != "" else None


def _persist_channel_blobs_stub(
    run_id: int,
    run_data: RunData,
    channel_units: Dict[str, Optional[str]],
) -> None:
    _ = run_id, run_data, channel_units
    # Placeholder for future compressed array storage.


def _is_core_field(name: str) -> bool:
    return name.strip().lower() in _CORE_FIELDS


def _track_name(metadata: Dict[str, str]) -> Optional[str]:
    track_name = _first_metadata_value(metadata, ["Track", "Track Name", "Circuit"])
    if track_name:
        return track_name
    track_name = _first_metadata_value(metadata, ["Session"])
    if track_name:
        return track_name
    identity = _first_metadata_value(metadata, ["Track Identity"])
    if identity and "(" in identity:
        return identity.split("(")[0].strip()
    return identity


def _infer_track_direction(metadata: Dict[str, str], track_name: str) -> str:
    direction_raw = _first_metadata_value(metadata, ["Track Direction", "Direction", "Dir"])
    direction = _normalize_direction(direction_raw)
    if direction:
        return direction
    identity = _first_metadata_value(metadata, ["Track Identity"])
    direction = _normalize_direction(_extract_paren(identity)) if identity else None
    if direction:
        return direction
    direction = _normalize_direction(_extract_paren(track_name))
    if direction:
        return direction
    return "UNKNOWN"


@dataclass
class _SessionFields:
    start_datetime: Optional[str]
    sample_rate_hz: Optional[float]
    duration_s: Optional[float]
    source_file: Optional[str]
    source_format: Optional[str]


def _session_fields(
    metadata: Dict[str, str],
    source_file: Optional[str],
    track_direction: str,
) -> _SessionFields:
    date = _first_metadata_value(metadata, ["Date", "Session Date"])
    time = _first_metadata_value(metadata, ["Time", "Session Time"])
    start_datetime = _combine_datetime(date, time)
    sample_rate = _first_metadata_value(metadata, ["Sample Rate", "SampleRate"])
    duration = _first_metadata_value(metadata, ["Duration", "Session Duration"])
    source_format = _first_metadata_value(metadata, ["Format", "Source Format"])

    return _SessionFields(
        start_datetime=start_datetime,
        sample_rate_hz=_parse_float(sample_rate),
        duration_s=_parse_float(duration),
        source_file=source_file,
        source_format=source_format,
    )


def _combine_datetime(date: Optional[str], time: Optional[str]) -> Optional[str]:
    if date and time:
        return f"{date} {time}"
    return date or time


def _first_metadata_value(metadata: Dict[str, str], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        if key in metadata:
            return metadata[key]
    lowered = {k.lower(): k for k in metadata}
    for key in keys:
        match = lowered.get(key.lower())
        if match:
            return metadata[match]
    return None


def _normalize_direction(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip().upper()
    if text in {"CW", "CLOCKWISE"}:
        return "CW"
    if text in {"CCW", "COUNTERCLOCKWISE", "COUNTER-CLOCKWISE"}:
        return "CCW"
    return None


def _extract_paren(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = re.search(r"\(([^)]+)\)", value)
    if not match:
        return None
    return match.group(1)


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", value)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _mps_to_kmh(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * 3.6


def _normalize_gps_accuracy(
    values: Optional[Sequence[Optional[float]]],
    unit: Optional[str],
) -> Optional[Sequence[Optional[float]]]:
    if values is None:
        return None
    if unit and unit.strip().lower() == "mm":
        return [None if v is None else v / 1000.0 for v in values]
    return values

def _infer_direction_from_run_data(run_data: RunData) -> Optional[str]:
    lat = run_data.lat
    lon = run_data.lon
    distance = run_data.distance_m
    if not lat or not lon:
        return None
    points = _contiguous_points(lat, lon, distance)
    if len(points) < 3:
        return None
    headings, distances = _headings_and_distances(points)
    if not headings or not distances:
        return None
    curvature = _curvature_from_heading(distances, headings)
    if not curvature:
        return None
    mean = sum(curvature) / len(curvature)
    if mean > 0:
        return "CCW"
    if mean < 0:
        return "CW"
    return None


def _contiguous_points(lat, lon, distance):
    points = []
    last_dist = None
    dist_series = distance if distance is not None else [None] * len(lat)
    for la, lo, dist in zip(lat, lon, dist_series):
        if la is None or lo is None:
            continue
        if distance is not None:
            if dist is None:
                continue
            if last_dist is not None and dist < last_dist:
                break
            last_dist = dist
        points.append((float(la), float(lo)))
    return points


def _headings_and_distances(points):
    import math

    headings = []
    distances = []
    for idx in range(1, len(points)):
        lat1, lon1 = points[idx - 1]
        lat2, lon2 = points[idx]
        d = _haversine_m(lat1, lon1, lat2, lon2)
        if d <= 0:
            continue
        heading = _bearing_rad(lat1, lon1, lat2, lon2)
        headings.append(heading)
        distances.append(d)
    return headings, distances


def _curvature_from_heading(distances, headings):
    import math

    if len(headings) < 2:
        return []
    curvature = []
    last_heading = headings[0]
    acc_dist = 0.0
    for idx in range(1, len(headings)):
        dh = headings[idx] - last_heading
        if dh > math.pi:
            dh -= 2 * math.pi
        elif dh < -math.pi:
            dh += 2 * math.pi
        ds = distances[idx] if idx < len(distances) else distances[-1]
        if ds > 0:
            curvature.append(dh / ds)
        last_heading = headings[idx]
        acc_dist += ds
        if acc_dist > 2000.0:
            break
    return curvature


def _bearing_rad(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    return math.atan2(y, x)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c

