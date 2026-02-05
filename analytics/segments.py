"""Corner/segment detection and labeling for distance-aligned GPS laps."""

from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from domain.run_data import RunData


@dataclass
class SegmentationConfig:
    ds_m: float = 1.0
    heading_smooth_window: int = 7
    curvature_median_window: int = 5
    curvature_lowpass_alpha: float = 0.25
    k_straight: float = 0.0008
    k_corner: float = 0.0025
    L_corner_min: float = 25.0
    L_straight_min: float = 50.0
    L_exit_min: float = 15.0
    L_gap_merge: float = 15.0
    L_apex_tolerance: float = 10.0
    speed_min_mps: float = 5.0
    speed_drop_min_frac: float = 0.05
    imu_weight: float = 0.3
    yaw_rate_channel_names: Tuple[str, ...] = (
        "Yaw Rate",
        "yaw_rate",
        "Gyro Z",
        "gyro_z",
        "YawRate",
    )
    lat_acc_channel_names: Tuple[str, ...] = (
        "Lateral Accel",
        "Lat Accel",
        "lat_acc",
        "Ay",
        "ay",
    )
    heading_channel_names: Tuple[str, ...] = (
        "GPS Heading",
        "Heading",
        "gps_heading_deg",
        "heading_deg",
        "Course",
        "course",
    )
    lat_acc_min_g: float = 0.2


@dataclass
class Segment:
    start_idx: int
    apex_idx: int
    end_idx: int
    start_m: float
    apex_m: float
    end_m: float
    sign: int
    kappa_peak: float
    confidence: float
    label: Optional[str] = None
    turn_id: Optional[str] = None
    lap_turn_id: Optional[str] = None
    manual_lock: bool = False


@dataclass
class SegmentationResult:
    distance_m: List[float]
    curvature: List[float]
    heading_rad: List[float]
    segments: List[Segment]
    direction: str


@dataclass
class ReferenceTurn:
    turn_id: str
    label: str
    center_m: float
    sign: int
    entry_bearing_rad: Optional[float]
    exit_bearing_rad: Optional[float]
    radius_proxy: Optional[float]


@dataclass
class ReferenceLap:
    track_key: str
    direction: str
    turns: List[ReferenceTurn]


@dataclass
class MatchConfig:
    D_match_max: float = 50.0


@dataclass
class ManualOverride:
    target_type: str
    target_id: str
    field: str
    new_value: object
    reason: Optional[str] = None
    author: Optional[str] = None
    timestamp: Optional[str] = None


def detect_segments(run_data: RunData, config: SegmentationConfig | None = None) -> SegmentationResult:
    """Detect corner segments from distance-aligned GPS (optional IMU)."""
    config = config or SegmentationConfig()
    run_data.validate_lengths()

    if run_data.distance_m is None:
        raise ValueError("distance_m is required for segmentation")

    distance_m = _prepare_distance_grid(run_data, config)
    heading_rad = _prepare_heading(run_data, config)
    yaw_rate = _prepare_channel(run_data, config.yaw_rate_channel_names)
    lat_acc = _prepare_channel(run_data, config.lat_acc_channel_names)

    raw_speed = run_data.speed or [None] * len(run_data.distance_m)
    speed_resampled = _resample_series(distance_m, run_data.distance_m, raw_speed)
    heading_resampled = _resample_series(distance_m, run_data.distance_m, heading_rad)
    yaw_rate_resampled = _resample_series(distance_m, run_data.distance_m, yaw_rate)
    lat_acc_resampled = _resample_series(distance_m, run_data.distance_m, lat_acc)

    heading_resampled = _smooth_heading(heading_resampled, config.heading_smooth_window)
    speed_resampled = _moving_average(speed_resampled, config.heading_smooth_window)

    curvature = _compute_curvature(distance_m, heading_resampled)
    curvature = _median_filter(curvature, config.curvature_median_window)
    curvature = _lowpass(curvature, config.curvature_lowpass_alpha)

    if yaw_rate_resampled:
        k_imu = _compute_kappa_from_imu(yaw_rate_resampled, speed_resampled)
        curvature = _fuse_curvature(curvature, k_imu, config.imu_weight)

    direction = _infer_direction(curvature)

    segments = _detect_segments_from_curvature(
        distance_m,
        curvature,
        speed_resampled,
        lat_acc_resampled,
        config,
    )

    return SegmentationResult(
        distance_m=distance_m,
        curvature=curvature,
        heading_rad=heading_resampled,
        segments=segments,
        direction=direction,
    )


def build_reference_lap(
    segments: Sequence[Segment],
    track_key: str,
    direction: str,
    heading_rad: Optional[Sequence[float]] = None,
) -> ReferenceLap:
    """Build a reference lap template for stable labeling."""
    turns: List[ReferenceTurn] = []
    for idx, seg in enumerate(segments, start=1):
        entry_bearing = None
        exit_bearing = None
        if heading_rad is not None and 0 <= seg.start_idx < len(heading_rad):
            entry_bearing = heading_rad[seg.start_idx]
        if heading_rad is not None and 0 <= seg.end_idx < len(heading_rad):
            exit_bearing = heading_rad[seg.end_idx]
        turn_id = f"{track_key}:{direction}:T{idx}"
        turns.append(
            ReferenceTurn(
                turn_id=turn_id,
                label=f"T{idx}",
                center_m=seg.apex_m,
                sign=seg.sign,
                entry_bearing_rad=entry_bearing,
                exit_bearing_rad=exit_bearing,
                radius_proxy=_safe_abs(seg.kappa_peak),
            )
        )
    return ReferenceLap(track_key=track_key, direction=direction, turns=turns)


def label_segments_with_reference(
    segments: Sequence[Segment],
    reference: ReferenceLap,
    config: MatchConfig | None = None,
    lap_id: Optional[str] = None,
) -> List[Segment]:
    """Assign stable labels by matching to a reference lap."""
    config = config or MatchConfig()
    if not reference.turns:
        return list(segments)

    segments_sorted = sorted(list(segments), key=lambda s: s.apex_m)
    matched: Dict[int, ReferenceTurn] = {}
    last_apex = -math.inf

    for ref in sorted(reference.turns, key=lambda t: t.center_m):
        candidates = [
            seg for seg in segments_sorted
            if seg.apex_m >= last_apex
            and seg.sign == ref.sign
            and abs(seg.apex_m - ref.center_m) <= config.D_match_max
            and id(seg) not in matched
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda s: abs(s.apex_m - ref.center_m))
        matched[id(best)] = ref
        last_apex = best.apex_m

    labeled: List[Segment] = []
    for seg in segments:
        ref = matched.get(id(seg))
        if ref is None:
            labeled.append(seg)
            continue
        updated = Segment(
            start_idx=seg.start_idx,
            apex_idx=seg.apex_idx,
            end_idx=seg.end_idx,
            start_m=seg.start_m,
            apex_m=seg.apex_m,
            end_m=seg.end_m,
            sign=seg.sign,
            kappa_peak=seg.kappa_peak,
            confidence=seg.confidence,
            label=ref.label,
            turn_id=ref.turn_id,
            lap_turn_id=f"{lap_id}:{ref.label}" if lap_id else seg.lap_turn_id,
            manual_lock=seg.manual_lock,
        )
        labeled.append(updated)
    return labeled


def label_laps_with_reference(
    laps: Sequence[SegmentationResult],
    track_key: str,
    direction: Optional[str] = None,
    reference_index: int = 0,
    match_config: MatchConfig | None = None,
    lap_ids: Optional[Sequence[str]] = None,
) -> Tuple[ReferenceLap, List[List[Segment]]]:
    """Label multiple laps using a single reference lap."""
    if not laps:
        return ReferenceLap(track_key=track_key, direction=direction or "UNKNOWN", turns=[]), []
    ref_idx = max(0, min(reference_index, len(laps) - 1))
    ref_lap = laps[ref_idx]
    ref_direction = direction or ref_lap.direction
    reference = build_reference_lap(
        ref_lap.segments,
        track_key=track_key,
        direction=ref_direction,
        heading_rad=ref_lap.heading_rad,
    )
    labeled_laps: List[List[Segment]] = []
    for idx, lap in enumerate(laps):
        lap_id = None
        if lap_ids and idx < len(lap_ids):
            lap_id = lap_ids[idx]
        labeled = label_segments_with_reference(
            lap.segments,
            reference,
            config=match_config,
            lap_id=lap_id,
        )
        labeled_laps.append(labeled)
    return reference, labeled_laps


def apply_manual_overrides(
    segments: Sequence[Segment],
    overrides: Sequence[ManualOverride],
) -> List[Segment]:
    """Apply manual overrides (stub) to segment output."""
    if not overrides:
        return list(segments)
    updated = list(segments)
    for override in overrides:
        if override.target_type != "Segment":
            continue
        for idx, seg in enumerate(updated):
            if seg.turn_id == override.target_id or seg.lap_turn_id == override.target_id:
                updated[idx] = _apply_override_to_segment(seg, override)
    return updated


def _apply_override_to_segment(segment: Segment, override: ManualOverride) -> Segment:
    if override.field not in {"label", "turn_id", "start_idx", "apex_idx", "end_idx"}:
        return segment
    data = segment.__dict__.copy()
    data[override.field] = override.new_value
    data["manual_lock"] = True
    return Segment(**data)


def _prepare_distance_grid(
    run_data: RunData,
    config: SegmentationConfig,
) -> List[float]:
    distance_raw = _require_series(run_data.distance_m, "distance_m")
    distance_clean, = _filter_increasing(distance_raw)
    return _build_distance_grid(distance_clean, config.ds_m)


def _prepare_heading(
    run_data: RunData,
    config: SegmentationConfig,
) -> List[Optional[float]]:
    heading_deg = _prepare_channel(run_data, config.heading_channel_names)
    if heading_deg:
        return [None if v is None else math.radians(v) for v in heading_deg]
    if run_data.lat is None or run_data.lon is None:
        raise ValueError("Heading or lat/lon is required for segmentation")
    lat = _require_series(run_data.lat, "lat")
    lon = _require_series(run_data.lon, "lon")
    return _compute_heading_from_latlon(lat, lon)


def _prepare_channel(run_data: RunData, names: Iterable[str]) -> List[Optional[float]]:
    for name in names:
        if name in run_data.channels:
            return run_data.channels[name]
    return []


def _require_series(values: Optional[Sequence[Optional[float]]], name: str) -> List[float]:
    if values is None:
        raise ValueError(f"{name} is required for segmentation")
    cleaned: List[float] = []
    for v in values:
        if v is None:
            cleaned.append(float("nan"))
        else:
            cleaned.append(float(v))
    return cleaned


def _filter_increasing(distance: Sequence[Optional[float]], *series: Sequence[Optional[float]]) -> Tuple[List[float], ...]:
    filtered: List[List[float]] = [[] for _ in range(len(series) + 1)]
    last = -math.inf
    for idx, d in enumerate(distance):
        if d is None or math.isnan(d):
            continue
        if d <= last:
            continue
        filtered[0].append(float(d))
        last = float(d)
        for offset, s in enumerate(series, start=1):
            value = s[idx] if idx < len(s) else None
            filtered[offset].append(float("nan") if value is None else float(value))
    return tuple(filtered)


def _build_distance_grid(distance: Sequence[float], ds: float) -> List[float]:
    if not distance:
        return []
    start = distance[0]
    end = distance[-1]
    count = int(math.floor((end - start) / ds)) + 1
    return [start + i * ds for i in range(count)]


def _resample_series(
    distance_grid: Sequence[float],
    distance_raw: Optional[Sequence[Optional[float]]],
    values: Sequence[Optional[float]] | None,
) -> List[Optional[float]]:
    if values is None:
        return []
    if distance_raw is None:
        return list(values)
    distance_clean, values_clean = _filter_increasing(distance_raw, values)
    if not distance_clean:
        return [None] * len(distance_grid)
    output: List[Optional[float]] = []
    j = 0
    for g in distance_grid:
        while j + 1 < len(distance_clean) and distance_clean[j + 1] < g:
            j += 1
        if j + 1 >= len(distance_clean):
            output.append(None)
            continue
        d0 = distance_clean[j]
        d1 = distance_clean[j + 1]
        v0 = values_clean[j]
        v1 = values_clean[j + 1]
        if math.isnan(v0) or math.isnan(v1):
            output.append(None)
            continue
        if d1 == d0:
            output.append(v0)
            continue
        t = (g - d0) / (d1 - d0)
        output.append(v0 + t * (v1 - v0))
    return output


def _moving_average(values: Sequence[Optional[float]], window: int) -> List[float]:
    if not values:
        return []
    window = max(1, window)
    half = window // 2
    out: List[float] = []
    for i in range(len(values)):
        start = max(0, i - half)
        end = min(len(values), i + half + 1)
        window_vals = [v for v in values[start:end] if v is not None]
        if not window_vals:
            out.append(float("nan"))
        else:
            out.append(sum(window_vals) / len(window_vals))
    return out


def _median_filter(values: Sequence[float], window: int) -> List[float]:
    if not values:
        return []
    window = max(1, window)
    half = window // 2
    out: List[float] = []
    for i in range(len(values)):
        start = max(0, i - half)
        end = min(len(values), i + half + 1)
        window_vals = [v for v in values[start:end] if not math.isnan(v)]
        if not window_vals:
            out.append(float("nan"))
        else:
            out.append(float(statistics.median(window_vals)))
    return out


def _lowpass(values: Sequence[float], alpha: float) -> List[float]:
    if not values:
        return []
    out: List[float] = []
    last = values[0]
    out.append(last)
    for v in values[1:]:
        if math.isnan(v):
            out.append(last)
            continue
        last = alpha * v + (1.0 - alpha) * last
        out.append(last)
    return out


def _smooth_heading(values: Sequence[Optional[float]], window: int) -> List[float]:
    smooth = _moving_average(values, window)
    return _unwrap_heading(smooth)


def _unwrap_heading(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    unwrapped = [values[0]]
    offset = 0.0
    last = values[0]
    for v in values[1:]:
        if math.isnan(v):
            unwrapped.append(last)
            continue
        delta = v - last
        if delta > math.pi:
            offset -= 2 * math.pi
        elif delta < -math.pi:
            offset += 2 * math.pi
        last = v
        unwrapped.append(v + offset)
    return unwrapped


def _compute_heading_from_latlon(lat: Sequence[float], lon: Sequence[float]) -> List[Optional[float]]:
    if len(lat) < 2:
        return [None] * len(lat)
    headings: List[Optional[float]] = [None]
    for i in range(1, len(lat)):
        if math.isnan(lat[i - 1]) or math.isnan(lon[i - 1]) or math.isnan(lat[i]) or math.isnan(lon[i]):
            headings.append(None)
            continue
        heading = _bearing_rad(lat[i - 1], lon[i - 1], lat[i], lon[i])
        headings.append(heading)
    return headings


def _bearing_rad(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    return math.atan2(y, x)


def _compute_curvature(distance: Sequence[float], heading: Sequence[float]) -> List[float]:
    n = len(distance)
    if n == 0:
        return []
    curvature = [0.0] * n
    for i in range(1, n - 1):
        ds = distance[i + 1] - distance[i - 1]
        if ds <= 0:
            curvature[i] = 0.0
            continue
        dpsi = heading[i + 1] - heading[i - 1]
        curvature[i] = dpsi / ds
    curvature[0] = curvature[1] if n > 1 else 0.0
    curvature[-1] = curvature[-2] if n > 1 else 0.0
    return curvature


def _compute_kappa_from_imu(
    yaw_rate: Sequence[Optional[float]],
    speed: Sequence[Optional[float]],
) -> List[float]:
    out: List[float] = []
    for r, v in zip(yaw_rate, speed):
        if r is None or v is None or math.isnan(r) or math.isnan(v):
            out.append(float("nan"))
            continue
        denom = max(v, 2.0)
        out.append(r / denom)
    return out


def _fuse_curvature(
    k_gps: Sequence[float],
    k_imu: Sequence[float],
    imu_weight: float,
) -> List[float]:
    out: List[float] = []
    for kg, ki in zip(k_gps, k_imu):
        if math.isnan(ki):
            out.append(kg)
        else:
            out.append((1.0 - imu_weight) * kg + imu_weight * ki)
    return out


def _infer_direction(curvature: Sequence[float]) -> str:
    if not curvature:
        return "UNKNOWN"
    mean = statistics.fmean(curvature)
    if mean > 0:
        return "CCW"
    if mean < 0:
        return "CW"
    return "UNKNOWN"


def _detect_segments_from_curvature(
    distance: Sequence[float],
    curvature: Sequence[float],
    speed: Sequence[Optional[float]],
    lat_acc: Sequence[Optional[float]],
    config: SegmentationConfig,
) -> List[Segment]:
    n = len(distance)
    if n == 0:
        return []

    speed_vals = [v if v is not None else float("nan") for v in speed]
    speed_median = _safe_median([v for v in speed_vals if not math.isnan(v)])

    in_corner = False
    start_idx = 0
    last_above_idx = 0
    below_len = 0.0
    segments: List[Tuple[int, int]] = []

    for i in range(n):
        k = abs(curvature[i])
        v = speed_vals[i]
        if not math.isnan(v) and v < config.speed_min_mps:
            k = 0.0
        if k >= config.k_corner:
            if not in_corner:
                start_idx = i
                in_corner = True
            last_above_idx = i
            below_len = 0.0
        elif in_corner:
            if k <= config.k_straight:
                below_len += _segment_step(distance, i)
                if below_len >= config.L_exit_min:
                    end_idx = last_above_idx
                    if _segment_length(distance, start_idx, end_idx) >= config.L_corner_min:
                        segments.append((start_idx, end_idx))
                    in_corner = False
                    below_len = 0.0
            else:
                below_len = 0.0

    if in_corner:
        end_idx = last_above_idx
        if _segment_length(distance, start_idx, end_idx) >= config.L_corner_min:
            segments.append((start_idx, end_idx))

    merged = _merge_segments(distance, segments, config.L_gap_merge)
    final_segments: List[Segment] = []
    for start, end in merged:
        apex_idx = _find_apex(curvature, start, end)
        if apex_idx is None:
            continue
        if not _segment_speed_drop_ok(speed_vals, curvature, start, end, speed_median, config):
            continue
        if not _segment_lat_acc_ok(lat_acc, start, end, config):
            continue
        kappa_peak = curvature[apex_idx]
        confidence = _segment_confidence(distance, curvature, start, end, apex_idx, config)
        final_segments.append(
            Segment(
                start_idx=start,
                apex_idx=apex_idx,
                end_idx=end,
                start_m=distance[start],
                apex_m=distance[apex_idx],
                end_m=distance[end],
                sign=1 if kappa_peak >= 0 else -1,
                kappa_peak=kappa_peak,
                confidence=confidence,
            )
        )
    return final_segments


def _segment_step(distance: Sequence[float], idx: int) -> float:
    if idx <= 0:
        return 0.0
    return max(0.0, distance[idx] - distance[idx - 1])


def _segment_length(distance: Sequence[float], start: int, end: int) -> float:
    if start >= end:
        return 0.0
    return max(0.0, distance[end] - distance[start])


def _merge_segments(
    distance: Sequence[float],
    segments: Sequence[Tuple[int, int]],
    gap_max: float,
) -> List[Tuple[int, int]]:
    if not segments:
        return []
    merged: List[Tuple[int, int]] = []
    current_start, current_end = segments[0]
    for start, end in segments[1:]:
        gap = distance[start] - distance[current_end]
        if gap <= gap_max:
            current_end = end
        else:
            merged.append((current_start, current_end))
            current_start, current_end = start, end
    merged.append((current_start, current_end))
    return merged


def _find_apex(curvature: Sequence[float], start: int, end: int) -> Optional[int]:
    if start >= end:
        return None
    peak_idx = start
    peak_val = 0.0
    for i in range(start, end + 1):
        val = abs(curvature[i])
        if val > peak_val:
            peak_val = val
            peak_idx = i
    return peak_idx


def _segment_speed_drop_ok(
    speed: Sequence[float],
    curvature: Sequence[float],
    start: int,
    end: int,
    speed_median: Optional[float],
    config: SegmentationConfig,
) -> bool:
    if speed_median is None:
        return True
    segment_speed = [v for v in speed[start:end + 1] if not math.isnan(v)]
    if not segment_speed:
        return True
    drop = max(segment_speed) - min(segment_speed)
    segment_kappa = [
        abs(curvature[i]) for i in range(start, end + 1)
        if not math.isnan(curvature[i])
    ]
    max_kappa = max(segment_kappa) if segment_kappa else 0.0
    if drop < config.speed_drop_min_frac * speed_median and max_kappa < config.k_corner * 1.2:
        return False
    return True


def _segment_lat_acc_ok(
    lat_acc: Sequence[Optional[float]],
    start: int,
    end: int,
    config: SegmentationConfig,
) -> bool:
    if not lat_acc:
        return True
    segment_acc = [
        abs(v) for v in lat_acc[start:end + 1]
        if v is not None and not math.isnan(v)
    ]
    if not segment_acc:
        return True
    return max(segment_acc) >= config.lat_acc_min_g


def _segment_confidence(
    distance: Sequence[float],
    curvature: Sequence[float],
    start: int,
    end: int,
    apex_idx: int,
    config: SegmentationConfig,
) -> float:
    length = _segment_length(distance, start, end)
    peak = abs(curvature[apex_idx])
    length_score = min(1.0, length / config.L_corner_min) if config.L_corner_min > 0 else 1.0
    peak_score = min(1.0, peak / config.k_corner) if config.k_corner > 0 else 1.0
    return 0.5 * length_score + 0.5 * peak_score


def _safe_median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median(values))


def _safe_abs(value: float) -> Optional[float]:
    if math.isnan(value):
        return None
    return abs(value)
