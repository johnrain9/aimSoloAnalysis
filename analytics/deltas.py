"""Delta-time and segment speed metrics for trackside insights.

Inputs
- RunData: aligned time/distance series for a run.
- LapBoundary / LapCandidate: lap time window.
- SegmentDefinition list: per-corner start/apex/end distances (meters).

Outputs
- DeltaSeries: time delta by distance between target and reference lap.
- SegmentDelta list: min/entry/exit speed metrics and deltas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from domain.run_data import RunData


@dataclass(frozen=True)
class LapWindow:
    start_time_s: float
    end_time_s: float


@dataclass(frozen=True)
class SegmentDefinition:
    name: str
    start_m: float
    apex_m: float
    end_m: float


@dataclass
class LapSeries:
    time_s: List[float]
    distance_m: List[float]
    speed: List[Optional[float]]


@dataclass
class DeltaSeries:
    distance_m: List[float]
    delta_time_s: List[Optional[float]]


@dataclass
class SegmentSpeedMetrics:
    entry_speed: Optional[float]
    apex_speed: Optional[float]
    exit_speed: Optional[float]
    min_speed: Optional[float]


@dataclass
class SegmentDelta:
    name: str
    entry_delta: Optional[float]
    apex_delta: Optional[float]
    exit_delta: Optional[float]
    min_delta: Optional[float]
    reference: SegmentSpeedMetrics
    target: SegmentSpeedMetrics


def build_delta_series(
    run_data: RunData,
    reference_lap: LapWindow,
    target_lap: LapWindow,
    *,
    distance_step_m: float = 1.0,
) -> DeltaSeries:
    """Compute delta-time by distance (target minus reference)."""
    run_data.validate_lengths()
    ref_series = _lap_series(run_data, reference_lap)
    tgt_series = _lap_series(run_data, target_lap)

    if not ref_series.distance_m or not tgt_series.distance_m:
        return DeltaSeries(distance_m=[], delta_time_s=[])

    end_distance = min(ref_series.distance_m[-1], tgt_series.distance_m[-1])
    if end_distance <= 0.0:
        return DeltaSeries(distance_m=[], delta_time_s=[])

    distance_grid = _distance_grid(end_distance, distance_step_m)
    ref_time = _interp(ref_series.distance_m, ref_series.time_s, distance_grid)
    tgt_time = _interp(tgt_series.distance_m, tgt_series.time_s, distance_grid)
    deltas: List[Optional[float]] = []
    for ref_value, tgt_value in zip(ref_time, tgt_time):
        if ref_value is None or tgt_value is None:
            deltas.append(None)
        else:
            deltas.append(tgt_value - ref_value)
    return DeltaSeries(distance_m=distance_grid, delta_time_s=deltas)


def compute_segment_deltas(
    run_data: RunData,
    reference_lap: LapWindow,
    target_lap: LapWindow,
    segments: Sequence[SegmentDefinition],
    *,
    entry_offset_m: float = 25.0,
    exit_offset_m: float = 30.0,
) -> List[SegmentDelta]:
    """Compute per-segment min/entry/exit speed metrics and deltas."""
    run_data.validate_lengths()
    ref_series = _lap_series(run_data, reference_lap)
    tgt_series = _lap_series(run_data, target_lap)

    results: List[SegmentDelta] = []
    for segment in segments:
        ref_metrics = _segment_metrics(ref_series, segment, entry_offset_m, exit_offset_m)
        tgt_metrics = _segment_metrics(tgt_series, segment, entry_offset_m, exit_offset_m)
        results.append(
            SegmentDelta(
                name=segment.name,
                entry_delta=_delta_value(tgt_metrics.entry_speed, ref_metrics.entry_speed),
                apex_delta=_delta_value(tgt_metrics.apex_speed, ref_metrics.apex_speed),
                exit_delta=_delta_value(tgt_metrics.exit_speed, ref_metrics.exit_speed),
                min_delta=_delta_value(tgt_metrics.min_speed, ref_metrics.min_speed),
                reference=ref_metrics,
                target=tgt_metrics,
            )
        )
    return results


def _lap_series(run_data: RunData, window: LapWindow) -> LapSeries:
    start_idx, end_idx = _find_index_range(run_data.time_s, window.start_time_s, window.end_time_s)
    if start_idx is None or end_idx is None or end_idx <= start_idx:
        return LapSeries(time_s=[], distance_m=[], speed=[])

    time: List[float] = []
    distance: List[float] = []
    speed: List[Optional[float]] = []
    base_time = None
    base_distance = None
    last_distance = None

    for idx in range(start_idx, end_idx + 1):
        t = run_data.time_s[idx]
        d = run_data.distance_m[idx] if run_data.distance_m is not None else None
        if t is None or d is None:
            continue
        if base_time is None:
            base_time = t
        if base_distance is None:
            base_distance = d
        rel_distance = d - base_distance
        if last_distance is not None and rel_distance <= last_distance:
            continue
        time.append(t - base_time)
        distance.append(rel_distance)
        if run_data.speed is None:
            speed.append(None)
        else:
            speed.append(run_data.speed[idx])
        last_distance = rel_distance

    return LapSeries(time_s=time, distance_m=distance, speed=speed)


def _segment_metrics(
    series: LapSeries,
    segment: SegmentDefinition,
    entry_offset_m: float,
    exit_offset_m: float,
) -> SegmentSpeedMetrics:
    entry_m = max(segment.start_m, segment.apex_m - entry_offset_m)
    exit_m = min(segment.end_m, segment.apex_m + exit_offset_m)
    apex_m = segment.apex_m

    entry_speed = _interp_one(series.distance_m, series.speed, entry_m)
    apex_speed = _interp_one(series.distance_m, series.speed, apex_m)
    exit_speed = _interp_one(series.distance_m, series.speed, exit_m)
    min_speed = _min_speed(series, segment.start_m, segment.end_m)

    return SegmentSpeedMetrics(
        entry_speed=entry_speed,
        apex_speed=apex_speed,
        exit_speed=exit_speed,
        min_speed=min_speed,
    )


def _min_speed(series: LapSeries, start_m: float, end_m: float) -> Optional[float]:
    if not series.distance_m or not series.speed:
        return None
    values: List[float] = []
    for distance, speed in zip(series.distance_m, series.speed):
        if distance < start_m or distance > end_m:
            continue
        if speed is None:
            continue
        values.append(speed)
    if not values:
        return None
    return min(values)


def _delta_value(target: Optional[float], reference: Optional[float]) -> Optional[float]:
    if target is None or reference is None:
        return None
    return target - reference


def _distance_grid(end_distance: float, step: float) -> List[float]:
    count = int(end_distance // step) + 1
    return [idx * step for idx in range(count)]


def _interp(
    xs: Sequence[float],
    ys: Sequence[float],
    x_targets: Sequence[float],
) -> List[Optional[float]]:
    results: List[Optional[float]] = []
    if not xs or not ys:
        return [None for _ in x_targets]
    j = 0
    for x in x_targets:
        while j < len(xs) - 1 and xs[j + 1] < x:
            j += 1
        if x < xs[0] or x > xs[-1]:
            results.append(None)
            continue
        if xs[j] == x:
            results.append(ys[j])
            continue
        if j + 1 >= len(xs):
            results.append(ys[-1])
            continue
        x0 = xs[j]
        x1 = xs[j + 1]
        y0 = ys[j]
        y1 = ys[j + 1]
        if x1 == x0:
            results.append(y0)
            continue
        results.append(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
    return results


def _interp_one(
    xs: Sequence[float],
    ys: Sequence[Optional[float]],
    x_target: float,
) -> Optional[float]:
    if not xs or not ys:
        return None
    j = 0
    while j < len(xs) - 1 and xs[j + 1] < x_target:
        j += 1
    if x_target < xs[0] or x_target > xs[-1]:
        return None
    if xs[j] == x_target:
        return ys[j]
    if j + 1 >= len(xs):
        return ys[-1]
    x0 = xs[j]
    x1 = xs[j + 1]
    y0 = ys[j]
    y1 = ys[j + 1]
    if y0 is None or y1 is None:
        return None
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x_target - x0) / (x1 - x0)


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
