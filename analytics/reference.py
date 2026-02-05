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
    avg_speed_mps: Optional[float] = None
    median_speed_mps: Optional[float] = None
    low_speed_ratio: Optional[float] = None
    entry_speed_mps: Optional[float] = None
    exit_speed_mps: Optional[float] = None


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
    min_distance_ratio: float = 0.9,
    min_duration_ratio: float = 0.9,
    max_distance_ratio: float = 1.1,
    max_duration_ratio: float = 1.35,
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
        stats = filter_valid_laps(
            run_data,
            group,
            missing_data_threshold=missing_data_threshold,
            distance_mad_k=distance_mad_k,
            max_gps_accuracy_m=max_gps_accuracy_m,
            min_distance_ratio=min_distance_ratio,
            min_duration_ratio=min_duration_ratio,
            max_distance_ratio=max_distance_ratio,
            max_duration_ratio=max_duration_ratio,
            gps_accuracy_channel_names=gps_accuracy_channel_names,
        )

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


def filter_valid_laps(
    run_data: RunData,
    laps: Sequence[LapCandidate],
    *,
    missing_data_threshold: float = 0.03,
    distance_mad_k: float = 3.0,
    max_gps_accuracy_m: float = 2.0,
    min_distance_ratio: float = 0.9,
    min_duration_ratio: float = 0.9,
    max_distance_ratio: float = 1.1,
    max_duration_ratio: float = 1.35,
    gps_accuracy_channel_names: Iterable[str] = ("gps_accuracy_m", "GPS Accuracy", "GPSAccuracy"),
) -> List[LapFilterResult]:
    """Evaluate laps and mark invalid out/in laps using distance + duration ratios."""
    stats = [_evaluate_lap(run_data, lap, gps_accuracy_channel_names) for lap in laps]
    _apply_missing_filter(stats, missing_data_threshold)
    _apply_distance_filter(
        stats,
        distance_mad_k,
        min_distance_ratio=min_distance_ratio,
        max_distance_ratio=max_distance_ratio,
    )
    _apply_gps_accuracy_filter(stats, max_gps_accuracy_m)
    _apply_out_in_filter(
        stats,
        min_distance_ratio=min_distance_ratio,
        min_duration_ratio=min_duration_ratio,
        max_distance_ratio=max_distance_ratio,
        max_duration_ratio=max_duration_ratio,
    )
    return stats


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

    avg_speed_mps = None
    if duration_s > 0 and distance_m is not None:
        avg_speed_mps = distance_m / duration_s

    speed_series = run_data.speed
    median_speed_mps = None
    low_speed_ratio = None
    entry_speed_mps = None
    exit_speed_mps = None
    if speed_series is not None:
        speeds = [
            speed_series[idx]
            for idx in range(start_idx, end_idx + 1)
            if speed_series[idx] is not None
        ]
        if speeds:
            median_speed_mps = median(speeds)
            threshold = max(4.0, (median_speed_mps or 0.0) * 0.35)
            low_speed_ratio = sum(1 for v in speeds if v < threshold) / len(speeds)
            window = max(5, int(len(speeds) * 0.1))
            entry_speed_mps = sum(speeds[:window]) / len(speeds[:window]) if speeds[:window] else None
            exit_speed_mps = sum(speeds[-window:]) / len(speeds[-window:]) if speeds[-window:] else None

    return LapFilterResult(
        lap=lap,
        duration_s=duration_s,
        distance_m=distance_m,
        missing_ratio=missing_ratio,
        gps_accuracy_median=gps_accuracy_median,
        avg_speed_mps=avg_speed_mps,
        median_speed_mps=median_speed_mps,
        low_speed_ratio=low_speed_ratio,
        entry_speed_mps=entry_speed_mps,
        exit_speed_mps=exit_speed_mps,
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
    med = median(values)
    return _normalize_gps_accuracy(med)


def _normalize_gps_accuracy(value: float) -> float:
    # Handle mm-scale data already stored as raw numbers.
    # GPS accuracy in meters is typically < 10 for trackside logs.
    if value > 50.0:
        return value / 1000.0
    return value


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


def _apply_distance_filter(
    stats: List[LapFilterResult],
    mad_k: float,
    *,
    min_distance_ratio: float,
    max_distance_ratio: float,
) -> None:
    distances = [stat.distance_m for stat in stats if stat.distance_m is not None]
    if len(distances) < 3:
        return
    med = median(distances)
    deviations = [abs(value - med) for value in distances]
    mad = median(deviations)
    if mad == 0.0:
        return
    min_deviation_m = 10.0
    threshold = max(mad_k * mad, min_deviation_m)
    for stat in stats:
        if stat.distance_m is None:
            continue
        if stat.distance_m >= med * min_distance_ratio and stat.distance_m <= med * max_distance_ratio:
            continue
        if abs(stat.distance_m - med) > threshold:
            stat.is_valid = False
            stat.invalid_reasons.append("distance_outlier")


def _apply_gps_accuracy_filter(stats: List[LapFilterResult], max_accuracy_m: float) -> None:
    values = [stat.gps_accuracy_median for stat in stats if stat.gps_accuracy_median is not None]
    if not values:
        return
    # If all laps exceed the accuracy threshold, skip this filter to avoid
    # invalidating the entire session due to consistently noisy GPS.
    if all(value > max_accuracy_m for value in values):
        return
    for stat in stats:
        if stat.gps_accuracy_median is None:
            continue
        if stat.gps_accuracy_median > max_accuracy_m:
            stat.is_valid = False
            stat.invalid_reasons.append(f"gps_accuracy>{max_accuracy_m:.1f}m")


def _apply_out_in_filter(
    stats: List[LapFilterResult],
    *,
    min_distance_ratio: float,
    min_duration_ratio: float,
    max_distance_ratio: float,
    max_duration_ratio: float,
) -> None:
    distances = [stat.distance_m for stat in stats if stat.distance_m is not None]
    durations = [stat.duration_s for stat in stats if stat.duration_s > 0]
    avg_speeds = [stat.avg_speed_mps for stat in stats if stat.avg_speed_mps is not None]
    if not distances or not durations:
        return
    med_distance = median(distances)
    med_duration = median(durations)
    med_avg_speed = median(avg_speeds) if avg_speeds else None
    for stat in stats:
        if stat.distance_m is not None and stat.distance_m < med_distance * min_distance_ratio:
            stat.is_valid = False
            stat.invalid_reasons.append("short_distance")
        if stat.distance_m is not None and stat.distance_m > med_distance * max_distance_ratio:
            stat.is_valid = False
            stat.invalid_reasons.append("long_distance")
        if stat.duration_s > 0 and stat.duration_s < med_duration * min_duration_ratio:
            stat.is_valid = False
            stat.invalid_reasons.append("short_duration")
        if stat.duration_s > 0 and stat.duration_s > med_duration * max_duration_ratio:
            stat.is_valid = False
            stat.invalid_reasons.append("long_duration")
        if med_avg_speed is not None and stat.avg_speed_mps is not None:
            if stat.avg_speed_mps < med_avg_speed * 0.8:
                stat.is_valid = False
                stat.invalid_reasons.append("slow_avg_speed")
        if stat.median_speed_mps is not None and stat.low_speed_ratio is not None:
            entry_ratio = (
                stat.entry_speed_mps / stat.median_speed_mps
                if stat.entry_speed_mps is not None and stat.median_speed_mps > 0
                else None
            )
            exit_ratio = (
                stat.exit_speed_mps / stat.median_speed_mps
                if stat.exit_speed_mps is not None and stat.median_speed_mps > 0
                else None
            )
            if stat.low_speed_ratio > 0.08 and ((entry_ratio is not None and entry_ratio < 0.6) or (exit_ratio is not None and exit_ratio < 0.6)):
                stat.is_valid = False
                stat.invalid_reasons.append("slow_entry_exit")
