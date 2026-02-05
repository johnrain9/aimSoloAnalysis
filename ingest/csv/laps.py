"""Lap inference helpers for CSV ingestion.

Beacon Markers are preferred when present. If missing, fall back to distance
resets (negative jumps) as a heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ingest.csv.parser import CsvParseResult


@dataclass
class LapBoundary:
    lap_index: int
    start_time_s: float
    end_time_s: float


def infer_laps(parse: CsvParseResult) -> List[LapBoundary]:
    """Infer lap boundaries from Beacon Markers or distance resets.

    Returns an empty list when boundaries cannot be inferred. Downstream code
    can then prompt the user for start/finish confirmation.
    """
    time_idx = _find_column(parse, "Time")
    if time_idx is None:
        return []

    beacon_idx = _find_column(parse, "Beacon Markers")
    if beacon_idx is not None:
        return _laps_from_beacons(parse, time_idx, beacon_idx)

    distance_idx = _find_column(parse, "Distance on GPS Speed")
    if distance_idx is not None:
        laps = _laps_from_distance_resets(parse, time_idx, distance_idx)
        if laps:
            return laps

    lat_idx = _find_column(parse, "Latitude")
    lon_idx = _find_column(parse, "Longitude")
    if lat_idx is not None and lon_idx is not None:
        return _laps_from_gps_crossing(parse, time_idx, lat_idx, lon_idx)

    return []


def _laps_from_beacons(
    parse: CsvParseResult,
    time_idx: int,
    beacon_idx: int,
) -> List[LapBoundary]:
    boundaries: List[float] = []
    last_value: Optional[float] = None
    for row in parse.rows:
        marker = row[beacon_idx]
        if marker is None:
            continue
        if last_value is None or marker != last_value:
            time_value = row[time_idx]
            if time_value is not None:
                boundaries.append(time_value)
        last_value = marker

    return _boundaries_to_laps(boundaries)


def _laps_from_distance_resets(
    parse: CsvParseResult,
    time_idx: int,
    distance_idx: int,
) -> List[LapBoundary]:
    boundaries: List[float] = []
    last_distance: Optional[float] = None
    for row in parse.rows:
        distance = row[distance_idx]
        if distance is None:
            continue
        if last_distance is not None and distance < (last_distance - 5.0):
            time_value = row[time_idx]
            if time_value is not None:
                boundaries.append(time_value)
        last_distance = distance

    return _boundaries_to_laps(boundaries)


def _boundaries_to_laps(boundaries: List[float]) -> List[LapBoundary]:
    if len(boundaries) < 2:
        return []

    laps: List[LapBoundary] = []
    for idx in range(1, len(boundaries)):
        laps.append(
            LapBoundary(
                lap_index=idx,
                start_time_s=boundaries[idx - 1],
                end_time_s=boundaries[idx],
            )
        )
    return laps


def _find_column(parse: CsvParseResult, name: str) -> Optional[int]:
    if name in parse.column_index:
        return parse.column_index[name]
    lowered = {key.lower(): idx for key, idx in parse.column_index.items()}
    return lowered.get(name.lower())


def _laps_from_gps_crossing(
    parse: CsvParseResult,
    time_idx: int,
    lat_idx: int,
    lon_idx: int,
) -> List[LapBoundary]:
    start = _first_valid_gps(parse, lat_idx, lon_idx)
    if start is None:
        return []
    start_lat, start_lon = start

    radius_m = 20.0
    exit_radius_m = 30.0
    min_lap_time_s = 20.0

    boundaries: List[float] = []
    inside = False
    last_boundary_time: Optional[float] = None

    for row in parse.rows:
        t = row[time_idx]
        lat = row[lat_idx]
        lon = row[lon_idx]
        if t is None or lat is None or lon is None:
            continue
        dist = _haversine_m(start_lat, start_lon, lat, lon)
        if dist <= radius_m and not inside:
            if last_boundary_time is None or (t - last_boundary_time) >= min_lap_time_s:
                boundaries.append(t)
                last_boundary_time = t
            inside = True
        elif dist >= exit_radius_m:
            inside = False

    return _boundaries_to_laps(boundaries)


def _first_valid_gps(
    parse: CsvParseResult,
    lat_idx: int,
    lon_idx: int,
) -> Optional[tuple[float, float]]:
    for row in parse.rows:
        lat = row[lat_idx]
        lon = row[lon_idx]
        if lat is None or lon is None:
            continue
        return (lat, lon)
    return None


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
