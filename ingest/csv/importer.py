"""CSV ingestion helpers.

This module reads RaceStudio CSV exports and converts parsed data into a
standardized RunData object. It intentionally focuses on format handling;
analytics and lap logic live elsewhere.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ingest.csv.parser import CsvParseResult, parse_csv
from domain.run_data import RunData


_KMH_TO_MPS = 1000.0 / 3600.0
_MPH_TO_MPS = 1609.344 / 3600.0


def _find_column(parse: CsvParseResult, name: str) -> Optional[int]:
    if name in parse.column_index:
        return parse.column_index[name]
    lowered = {key.lower(): idx for key, idx in parse.column_index.items()}
    return lowered.get(name.lower())


def _find_column_any(parse: CsvParseResult, names: Sequence[str]) -> Optional[int]:
    for name in names:
        idx = _find_column(parse, name)
        if idx is not None:
            return idx
    return None


def _convert_speed(values: List[Optional[float]], unit: str) -> List[Optional[float]]:
    unit_norm = (unit or "").strip().lower()
    if unit_norm in {"km/h", "kph", "kmh"}:
        return [None if v is None else v * _KMH_TO_MPS for v in values]
    if unit_norm in {"mph"}:
        return [None if v is None else v * _MPH_TO_MPS for v in values]
    return values


def _convert_distance(values: List[Optional[float]], unit: str) -> List[Optional[float]]:
    unit_norm = (unit or "").strip().lower()
    if unit_norm in {"km"}:
        return [None if v is None else v * 1000.0 for v in values]
    return values


def read_csv(path: str) -> CsvParseResult:
    """Read a RaceStudio CSV export into a parsed structure."""
    return parse_csv(path)


def import_csv(path: str) -> RunData:
    """Read and convert a RaceStudio CSV export into RunData."""
    return build_run_data(read_csv(path))


def build_run_data(parse: CsvParseResult) -> RunData:
    """Build a RunData object from parsed CSV.

    Known columns (if present):
    - Time
    - Distance on GPS Speed
    - GPS Speed (normalized to m/s)
    - Latitude / GPS Latitude
    - Longitude / GPS Longitude
    """
    time_idx = _find_column(parse, "Time")
    if time_idx is None:
        raise ValueError("CSV is missing required Time column")

    distance_idx = _find_column(parse, "Distance on GPS Speed")
    speed_idx = _find_column(parse, "GPS Speed")
    lat_idx = _find_column_any(parse, ["Latitude", "GPS Latitude"])
    lon_idx = _find_column_any(parse, ["Longitude", "GPS Longitude"])

    time_s = [row[time_idx] for row in parse.rows]

    distance_m = None
    if distance_idx is not None:
        distance_vals = [row[distance_idx] for row in parse.rows]
        unit = parse.units[distance_idx] if distance_idx < len(parse.units) else ""
        distance_m = _convert_distance(distance_vals, unit)

    speed = None
    if speed_idx is not None:
        speed_vals = [row[speed_idx] for row in parse.rows]
        unit = parse.units[speed_idx] if speed_idx < len(parse.units) else ""
        speed = _convert_speed(speed_vals, unit)

    lat = None
    if lat_idx is not None:
        lat = [row[lat_idx] for row in parse.rows]

    lon = None
    if lon_idx is not None:
        lon = [row[lon_idx] for row in parse.rows]

    # Dynamic channels: all columns except core fields.
    excluded = {idx for idx in [time_idx, distance_idx, speed_idx, lat_idx, lon_idx] if idx is not None}
    channels: Dict[str, List[Optional[float]]] = {}
    for idx, name in enumerate(parse.header):
        if idx in excluded:
            continue
        channels[name] = [row[idx] for row in parse.rows]

    return RunData(
        time_s=time_s,
        distance_m=distance_m,
        lat=lat,
        lon=lon,
        speed=speed,
        channels=channels,
        metadata=parse.metadata,
    )
