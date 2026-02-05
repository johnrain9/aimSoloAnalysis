"""Persist CSV ingestion outputs into SQLite."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Sequence, Tuple, Union

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
        lap_count = _persist_laps(conn, run_id, laps)

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


def _persist_laps(conn, run_id: int, laps) -> int:
    count = 0
    for lap in laps:
        duration = None
        if lap.start_time_s is not None and lap.end_time_s is not None:
            duration = lap.end_time_s - lap.start_time_s
        db.upsert_lap(
            conn,
            run_id=run_id,
            lap_index=lap.lap_index,
            start_time_s=lap.start_time_s,
            end_time_s=lap.end_time_s,
            duration_s=duration,
        )
        count += 1
    return count


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

