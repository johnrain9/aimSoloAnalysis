"""CSV parser for AiM RaceStudio exports.

Mapping summary (per design docs):
- Metadata rows -> session fields (track, date, time, sample rate, duration, format).
- Header + units rows -> channel registry.
- Each data row -> sample point; channel values -> arrays keyed by channel name.

Beacon Markers:
- If missing, downstream lap inference should fall back to distance resets or
  prompt the user to confirm start/finish. No UI changes are implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
from typing import Iterable, List, Dict, Optional


@dataclass
class CsvParseResult:
    metadata: Dict[str, str]
    header: List[str]
    units: List[str]
    rows: List[List[Optional[float]]]
    column_index: Dict[str, int]

    def column(self, name: str) -> Optional[List[Optional[float]]]:
        idx = self.column_index.get(name)
        if idx is None:
            return None
        return [row[idx] for row in self.rows]


def _is_blank_row(row: List[str]) -> bool:
    return len(row) == 0 or all(cell.strip() == "" for cell in row)


def _to_float(value: str) -> Optional[float]:
    if value is None:
        return None
    text = value.strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_cell(cell: str) -> str:
    if cell is None:
        return ""
    return cell.strip().lstrip("\ufeff")


def parse_csv(path: str) -> CsvParseResult:
    """Parse an AiM RaceStudio CSV export.

    Expected structure:
    1) Metadata key/value rows
    2) Blank row
    3) Header row
    4) Units row
    5) Data rows
    """
    metadata: Dict[str, str] = {}
    header: List[str] = []
    units: List[str] = []
    rows: List[List[Optional[float]]] = []

    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        stage = "metadata"
        for raw_row in reader:
            row = [_normalize_cell(cell) for cell in raw_row]

            if stage == "metadata":
                if _is_blank_row(row):
                    stage = "header"
                    continue
                if len(row) >= 2 and row[0] != "":
                    key = row[0]
                    value = ",".join(row[1:]).strip()
                    metadata[key] = value
                continue

            if stage == "header":
                if _is_blank_row(row):
                    continue
                header = row
                stage = "units"
                continue

            if stage == "units":
                if _is_blank_row(row):
                    units = ["" for _ in header]
                else:
                    units = row
                stage = "data"
                continue

            if stage == "data":
                if _is_blank_row(row):
                    continue
                if len(row) < len(header):
                    row = row + [""] * (len(header) - len(row))
                values = [_to_float(cell) for cell in row[: len(header)]]
                rows.append(values)

    column_index = {name: idx for idx, name in enumerate(header)}
    _ensure_track_identity(metadata)
    return CsvParseResult(
        metadata=metadata,
        header=header,
        units=units,
        rows=rows,
        column_index=column_index,
    )


def _ensure_track_identity(metadata: Dict[str, str]) -> None:
    track_key = _first_key(metadata, ["Track", "Track Name", "Circuit"])
    if track_key is None:
        return
    direction_key = _first_key(metadata, ["Track Direction", "Direction", "Dir"])
    direction_raw = metadata.get(direction_key, "") if direction_key else ""
    direction = _normalize_direction(direction_raw)
    if direction_key is None:
        metadata["Track Direction"] = direction or "UNKNOWN"
        direction_key = "Track Direction"
    elif direction is not None:
        metadata[direction_key] = direction
    if direction is None:
        metadata["Track Identity"] = f"{metadata[track_key]} (UNKNOWN)"
    else:
        metadata["Track Identity"] = f"{metadata[track_key]} ({direction})"


def _first_key(metadata: Dict[str, str], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        if key in metadata:
            return key
    lowered = {k.lower(): k for k in metadata}
    for key in keys:
        match = lowered.get(key.lower())
        if match:
            return match
    return None


def _normalize_direction(value: str) -> Optional[str]:
    text = (value or "").strip().upper()
    if text in {"CW", "CLOCKWISE"}:
        return "CW"
    if text in {"CCW", "COUNTERCLOCKWISE", "COUNTER-CLOCKWISE"}:
        return "CCW"
    return None
