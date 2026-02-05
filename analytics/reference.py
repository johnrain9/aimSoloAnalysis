"""Reference lap selection with basic outlier filtering.

Inputs
- RunData: aligned time series for a run/session.
- LapCandidate list: lap boundaries plus track identity fields.

Outputs
- Reference selection per (track, direction) key, including reasons for any
  excluded laps. This is intended to feed trackside insight rules that compare
  a target lap to a single reference lap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from domain.run_data import RunData


@dataclass(frozen=True)
class LapCandidate:
    lap_index: int
    start_time_s: float
    end_time_s: float
    direction: str = "UNKNOWN"
    track_id: Optional[int] = None
    track_name: Optional[str] = None
    lap_id: Optional[int] = None
    run_id: Optional[int] = None


@dataclass
class LapFilterResult:
    lap: LapCandidate
    duration_s: float
    distance_m: Optional[float]
    missing_ratio: float
    gps_accuracy_median: Optional[float]
    is_valid: bool
    invalid_reasons: List[str] = field(default_factory=list)


@dataclass
class ReferenceSelection:
    key: Tuple[object, str]
    reference_lap: LapCandidate
    reference_stats: LapFilterResult
    candidates: List[LapFilterResult]


def select_reference_laps(
    run_data: RunData,
    laps: Sequence[LapCandidate],
    *,
    missing_data_threshold: float = 0.03,
    distance_mad_k: float = 3.0,
    max_gps_accuracy_m: float = 2.0,
    gps_accuracy_channel_names: Iterable[str] = ("gps_accuracy_m", "GPS Accuracy", "GPSAccuracy"),
) -> Dict[Tuple[object, str], ReferenceSelection]:
    """Pick fastest valid lap per track+direction with basic outlier filters.

    Filters:
    - Missing data ratio above `missing_data_threshold` (distance or speed).
    - Distance outliers using median absolute deviation (MAD).
    - Median GPS accuracy above `max_gps_accuracy_m` when channel available.
    """
    if not laps:
        return {}

    run_data.validate_lengths()
    grouped = _group_laps(laps)
    selections: Dict[Tuple[object, str], ReferenceSelection] = {}

    for key, group in grouped.items():
        stats = [_evaluate_lap(run_data, lap, gps_accuracy_channel_names) for lap in group]
        _apply_missing_filter(stats, missing_data_threshold)
        _apply_distance_filter(stats, distance_mad_k)
        _apply_gps_accuracy_filter(stats, max_gps_accuracy_m)

        valid = [stat for stat in stats if stat.is_valid]
        if valid:
            reference = min(valid, key=lambda stat: stat.duration_s)
        else:
            reference = min(stats, key=lambda stat: stat.duration_s)
        selections[key] = ReferenceSelection(
            key=key,
            reference_lap=reference.lap,
            reference_stats=reference,
            candidates=stats,
        )

    return selections


def _group_laps(laps: Sequence[LapCandidate]) -> Dict[Tuple[object, str], List[LapCandidate]]:
    grouped: Dict[Tuple[object, str], List[LapCandidate]] = {}
    for lap in laps:
        if lap.track_id is not None:
            track_key: object = lap.track_id
        elif lap.track_name:
            track_key = lap.track_name
        else:
            track_key = "UNKNOWN_TRACK"
        key = (track_key, (lap.direction or "UNKNOWN"))
        grouped.setdefault(key, []).append(lap)
    return grouped


def _evaluate_lap(
    run_data: RunData,
    lap: LapCandidate,
    gps_accuracy_channel_names: Iterable[str],
) -> LapFilterResult:
    start_idx, end_idx = _find_index_range(run_data.time_s, lap.start_time_s, lap.end_time_s)
    if start_idx is None or end_idx is None or end_idx <= start_idx:
        return LapFilterResult(
            lap=lap,
            duration_s=max(lap.end_time_s - lap.start_time_s, 0.0),
            distance_m=None,
            missing_ratio=1.0,
            gps_accuracy_median=None,
            is_valid=False,
            invalid_reasons=["invalid_time_range"],
        )

    duration_s = lap.end_time_s - lap.start_time_s
    distance_m = _lap_distance(run_data.distance_m, start_idx, end_idx)
    missing_ratio = _missing_ratio(run_data, start_idx, end_idx)
    gps_accuracy_median = _median_gps_accuracy(run_data, start_idx, end_idx, gps_accuracy_channel_names)

    return LapFilterResult(
        lap=lap,
        duration_s=duration_s,
        distance_m=distance_m,
        missing_ratio=missing_ratio,
        gps_accuracy_median=gps_accuracy_median,
        is_valid=True,
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


def _lap_distance(
    distance_m: Optional[Sequence[Optional[float]]],
    start_idx: int,
    end_idx: int,
) -> Optional[float]:
    if distance_m is None:
        return None
    start_distance = _first_non_null(distance_m, start_idx, end_idx, forward=True)
    end_distance = _first_non_null(distance_m, start_idx, end_idx, forward=False)
    if start_distance is None or end_distance is None:
        return None
    return max(end_distance - start_distance, 0.0)


def _first_non_null(
    series: Sequence[Optional[float]],
    start_idx: int,
    end_idx: int,
    *,
    forward: bool,
) -> Optional[float]:
    if forward:
        indices = range(start_idx, end_idx + 1)
    else:
        indices = range(end_idx, start_idx - 1, -1)
    for idx in indices:
        value = series[idx]
        if value is not None:
            return value
    return None


def _missing_ratio(run_data: RunData, start_idx: int, end_idx: int) -> float:
    total = 0
    missing = 0
    for series in (run_data.distance_m, run_data.speed):
        if series is None:
            continue
        for idx in range(start_idx, end_idx + 1):
            total += 1
            if series[idx] is None:
                missing += 1
    if total == 0:
        return 1.0
    return missing / total


def _median_gps_accuracy(
    run_data: RunData,
    start_idx: int,
    end_idx: int,
    channel_names: Iterable[str],
) -> Optional[float]:
    channel = _find_channel(run_data, channel_names)
    if channel is None:
        return None
    values: List[float] = []
    for idx in range(start_idx, end_idx + 1):
        value = channel[idx]
        if value is not None:
            values.append(value)
    if not values:
        return None
    return median(values)


def _find_channel(run_data: RunData, channel_names: Iterable[str]) -> Optional[Sequence[Optional[float]]]:
    if not run_data.channels:
        return None
    lower_map = {name.lower(): series for name, series in run_data.channels.items()}
    for name in channel_names:
        series = run_data.channels.get(name)
        if series is not None:
            return series
        series = lower_map.get(name.lower())
        if series is not None:
            return series
    return None


def _apply_missing_filter(stats: List[LapFilterResult], threshold: float) -> None:
    for stat in stats:
        if stat.missing_ratio > threshold:
            stat.is_valid = False
            stat.invalid_reasons.append(f"missing_ratio>{threshold:.2f}")


def _apply_distance_filter(stats: List[LapFilterResult], mad_k: float) -> None:
    distances = [stat.distance_m for stat in stats if stat.distance_m is not None]
    if len(distances) < 3:
        return
    med = median(distances)
    deviations = [abs(value - med) for value in distances]
    mad = median(deviations)
    if mad == 0.0:
        return
    for stat in stats:
        if stat.distance_m is None:
            continue
        if abs(stat.distance_m - med) > mad_k * mad:
            stat.is_valid = False
            stat.invalid_reasons.append("distance_outlier")


def _apply_gps_accuracy_filter(stats: List[LapFilterResult], max_accuracy_m: float) -> None:
    for stat in stats:
        if stat.gps_accuracy_median is None:
            continue
        if stat.gps_accuracy_median > max_accuracy_m:
            stat.is_valid = False
            stat.invalid_reasons.append(f"gps_accuracy>{max_accuracy_m:.1f}m")
