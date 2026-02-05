"""Per-segment metric extraction for trackside insights."""

from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from analytics.deltas import LapWindow
from analytics.segments import Segment
from domain.run_data import RunData


_KMH_PER_MPS = 3.6
_G_MPS2 = 9.80665
_EARTH_RADIUS_M = 6371000.0


INLINE_ACC_NAMES = (
    "Inline Accel",
    "InlineAcc",
    "Long Accel",
    "Longitudinal Accel",
    "LongAccel",
    "Accel X",
    "AccelX",
    "Ax",
    "ax",
    "accel_x",
    "accel_long",
)

YAW_RATE_NAMES = (
    "Yaw Rate",
    "yaw_rate",
    "Gyro Z",
    "gyro_z",
    "YawRate",
)

LAT_ACC_NAMES = (
    "Lateral Accel",
    "Lat Accel",
    "lat_acc",
    "Ay",
    "ay",
)

GPS_RADIUS_NAMES = (
    "GPS Radius",
    "GPSRadius",
    "gps_radius_m",
    "gps_radius",
    "Radius",
)

ROLL_RATE_NAMES = (
    "RollRate",
    "Roll Rate",
    "roll_rate",
)

GPS_SPEED_ACCURACY_NAMES = (
    "GPS SpdAccuracy",
    "GPS Speed Accuracy",
    "GPSSpdAccuracy",
    "gps_speed_accuracy_mps",
    "gps_spd_accuracy_mps",
)

BRAKE_NAMES = (
    "Brake",
    "Brake Pressure",
    "BrakePressure",
    "Brake Pos",
    "Brake Position",
    "Front Brake",
    "Rear Brake",
    "brake",
    "brake_pressure",
)

THROTTLE_NAMES = (
    "Throttle",
    "Throttle Position",
    "Throttle Pos",
    "TPS",
    "throttle",
)

GPS_ACCURACY_NAMES = (
    "gps_accuracy_m",
    "GPS Accuracy",
    "GPSAccuracy",
    "GPS PosAccuracy",
    "GPS Pos Accuracy",
)

SATELLITES_NAMES = (
    "Satellites",
    "GPS Satellites",
    "gps_sats",
)

LINE_ERROR_NAMES = (
    "Cross Track Error",
    "cross_track_error",
    "Cross Track Err",
    "Line Deviation",
    "line_dev",
    "line_deviation",
    "xte",
)


@dataclass
class LapSeries:
    time_s: List[float]
    distance_m: List[float]
    speed_mps: List[Optional[float]]
    inline_acc_g: List[Optional[float]]
    yaw_rate: List[Optional[float]]
    lat_acc_g: List[Optional[float]]
    gps_radius_m: List[Optional[float]]
    roll_rate_dps: List[Optional[float]]
    brake: List[Optional[float]]
    throttle: List[Optional[float]]
    gps_accuracy_m: List[Optional[float]]
    gps_speed_accuracy_mps: List[Optional[float]]
    satellites: List[Optional[float]]
    line_error_m: List[Optional[float]]
    lat: List[Optional[float]]
    lon: List[Optional[float]]
    base_distance: float
    using_speed_proxy: bool


def compute_segment_metrics(
    run_data: RunData,
    lap_window: LapWindow,
    segments: Sequence[Segment],
) -> Dict[str, Dict[str, Any]]:
    """Compute per-segment metrics for a single lap.

    Returns a mapping of segment_id -> metrics dict. The metrics dict keys
    match trackside insight rule expectations (e.g., entry_speed_kmh).
    """
    run_data.validate_lengths()
    lap = _lap_series(run_data, lap_window)
    if not lap.distance_m:
        return {}

    lap_length = lap.distance_m[-1] if lap.distance_m else 0.0
    results: Dict[str, Dict[str, Any]] = {}

    id_prefix = _track_id_prefix(run_data.metadata)
    for idx, segment in enumerate(segments, start=1):
        seg_id = _segment_id(segment, idx, id_prefix=id_prefix)
        corner_id = _corner_id(segment, idx, id_prefix=id_prefix)

        start_m, apex_m, end_m = _normalize_segment_bounds(
            segment,
            base_distance=lap.base_distance,
            lap_length=lap_length,
        )
        if start_m is None or end_m is None or start_m >= end_m:
            continue
        if end_m < -1.0 or start_m > lap_length + 1.0:
            continue

        seg_start = max(0.0, start_m)
        seg_end = min(lap_length, end_m)
        seg_indices = _segment_indices(lap.distance_m, seg_start, seg_end)
        if not seg_indices:
            continue

        min_speed_mps, min_speed_dist = _min_speed(lap, seg_indices)
        if min_speed_dist is None:
            min_speed_dist = apex_m if apex_m is not None else seg_start

        apex_dist_m = min_speed_dist
        entry_dist_m = max(seg_start, apex_dist_m - 25.0)
        exit_dist_m = min(seg_end, apex_dist_m + 30.0)

        entry_speed = _interp_one(lap.distance_m, lap.speed_mps, entry_dist_m)
        apex_speed = _interp_one(lap.distance_m, lap.speed_mps, apex_dist_m)
        exit_speed = _interp_one(lap.distance_m, lap.speed_mps, exit_dist_m)

        segment_time_s = _segment_time(lap, seg_start, seg_end)

        brake_point, brake_time = _brake_point(lap, seg_start, apex_dist_m)
        pickup_point, pickup_time = _throttle_pickup(lap, apex_dist_m, seg_end)
        pickup_time_s = None
        if pickup_time is not None:
            apex_time = _interp_one(lap.distance_m, lap.time_s, apex_dist_m)
            if apex_time is not None:
                pickup_time_s = max(0.0, pickup_time - apex_time)

        decel = _entry_decel_metrics(lap, entry_dist_m, apex_dist_m)
        decel_avg_g = decel.get("decel_avg_g")
        decel_time_s = decel.get("decel_time_s")
        decel_dist_m = decel.get("decel_dist_m")
        decel_g_per_10m = decel.get("decel_g_per_10m")

        neutral = _neutral_throttle_window(lap, seg_indices)
        neutral_throttle_s = neutral.get("neutral_throttle_s")
        neutral_throttle_dist_m = neutral.get("neutral_throttle_dist_m")
        neutral_speed_delta_kmh = neutral.get("neutral_speed_delta_kmh")
        speed_noise_sigma_kmh = neutral.get("speed_noise_sigma_kmh")

        line_stddev = _line_stddev(lap, seg_indices)
        yaw_rms = _rms(_slice_values(lap.yaw_rate, seg_indices))
        inline_acc_var = _variance(_slice_values(lap.inline_acc_g, seg_indices))

        gps_accuracy = _mean(_slice_values(lap.gps_accuracy_m, seg_indices))
        gps_speed_accuracy = _mean(_slice_values(lap.gps_speed_accuracy_mps, seg_indices))
        satellites = _mean(_slice_values(lap.satellites, seg_indices))

        inline_acc_rise = _inline_acc_rise(lap, apex_dist_m, seg_end, seg_start)

        lean_proxy_deg, lean_quality = _lean_proxy(lap, seg_indices)

        using_speed_proxy = _using_speed_proxy(lap)
        imu_present = _imu_present(lap)
        imu_variance_low = inline_acc_var is not None and inline_acc_var <= 0.02
        using_brake_proxy = not _has_valid_values(lap.brake)
        using_throttle_proxy = not _has_valid_values(lap.throttle)

        metrics: Dict[str, Any] = {
            "segment_id": seg_id,
            "corner_id": corner_id,
            "start_dist_m": seg_start,
            "end_dist_m": seg_end,
            "apex_dist_m": apex_dist_m,
            "segment_time_s": segment_time_s,
            "entry_speed_kmh": _mps_to_kmh(entry_speed),
            "apex_speed_kmh": _mps_to_kmh(apex_speed),
            "exit_speed_30m_kmh": _mps_to_kmh(exit_speed),
            "min_speed_kmh": _mps_to_kmh(min_speed_mps),
            "brake_point_dist_m": brake_point,
            "throttle_pickup_dist_m": pickup_point,
            "throttle_pickup_time_s": pickup_time_s,
            "neutral_throttle_s": neutral_throttle_s,
            "neutral_throttle_dist_m": neutral_throttle_dist_m,
            "neutral_speed_delta_kmh": neutral_speed_delta_kmh,
            "decel_avg_g": decel_avg_g,
            "decel_time_s": decel_time_s,
            "decel_dist_m": decel_dist_m,
            "decel_g_per_10m": decel_g_per_10m,
            "line_stddev_m": line_stddev,
            "yaw_rms": yaw_rms,
            "inline_acc_rise_g": inline_acc_rise,
            "using_speed_proxy": using_speed_proxy,
            "using_brake_proxy": using_brake_proxy,
            "using_throttle_proxy": using_throttle_proxy,
            "gps_accuracy_m": gps_accuracy,
            "gps_speed_accuracy_mps": gps_speed_accuracy,
            "satellites": satellites,
            "imu_present": imu_present,
            "imu_variance_low": imu_variance_low,
            "inline_acc_var": inline_acc_var,
            "speed_noise_sigma_kmh": speed_noise_sigma_kmh,
            "lean_proxy_deg": lean_proxy_deg,
            "lean_quality": lean_quality,
        }
        results[seg_id] = metrics

    return results


def _lap_series(run_data: RunData, window: LapWindow) -> LapSeries:
    start_idx, end_idx = _find_index_range(run_data.time_s, window.start_time_s, window.end_time_s)
    if start_idx is None or end_idx is None or end_idx <= start_idx:
        return LapSeries(
            time_s=[],
            distance_m=[],
            speed_mps=[],
            inline_acc_g=[],
            yaw_rate=[],
            lat_acc_g=[],
            gps_radius_m=[],
            roll_rate_dps=[],
            brake=[],
            throttle=[],
            gps_accuracy_m=[],
            gps_speed_accuracy_mps=[],
            satellites=[],
            line_error_m=[],
            lat=[],
            lon=[],
            base_distance=0.0,
            using_speed_proxy=True,
        )

    distance_series = run_data.distance_m
    if distance_series is None:
        return LapSeries(
            time_s=[],
            distance_m=[],
            speed_mps=[],
            inline_acc_g=[],
            yaw_rate=[],
            lat_acc_g=[],
            gps_radius_m=[],
            roll_rate_dps=[],
            brake=[],
            throttle=[],
            gps_accuracy_m=[],
            gps_speed_accuracy_mps=[],
            satellites=[],
            line_error_m=[],
            lat=[],
            lon=[],
            base_distance=0.0,
            using_speed_proxy=True,
        )

    inline_acc_raw = _find_channel(run_data, INLINE_ACC_NAMES)
    yaw_rate = _find_channel(run_data, YAW_RATE_NAMES)
    lat_acc = _find_channel(run_data, LAT_ACC_NAMES)
    gps_radius = _find_channel(run_data, GPS_RADIUS_NAMES)
    roll_rate = _find_channel(run_data, ROLL_RATE_NAMES)
    brake = _find_channel(run_data, BRAKE_NAMES)
    throttle = _find_channel(run_data, THROTTLE_NAMES)
    gps_accuracy = _find_channel(run_data, GPS_ACCURACY_NAMES)
    gps_speed_accuracy = _find_channel(run_data, GPS_SPEED_ACCURACY_NAMES)
    satellites = _find_channel(run_data, SATELLITES_NAMES)
    line_error = _find_channel(run_data, LINE_ERROR_NAMES)

    time: List[float] = []
    distance: List[float] = []
    speed: List[Optional[float]] = []
    inline_acc_values: List[Optional[float]] = []
    yaw_values: List[Optional[float]] = []
    lat_acc_values: List[Optional[float]] = []
    gps_radius_values: List[Optional[float]] = []
    roll_rate_values: List[Optional[float]] = []
    brake_values: List[Optional[float]] = []
    throttle_values: List[Optional[float]] = []
    gps_accuracy_values: List[Optional[float]] = []
    gps_speed_accuracy_values: List[Optional[float]] = []
    satellites_values: List[Optional[float]] = []
    line_error_values: List[Optional[float]] = []
    lat_values: List[Optional[float]] = []
    lon_values: List[Optional[float]] = []

    base_time: Optional[float] = None
    base_distance: Optional[float] = None
    last_distance: Optional[float] = None

    for idx in range(start_idx, end_idx + 1):
        t = run_data.time_s[idx]
        d = distance_series[idx] if distance_series is not None else None
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
        speed.append(_safe_value(run_data.speed, idx))
        inline_acc_values.append(_safe_value(inline_acc_raw, idx))
        yaw_values.append(_safe_value(yaw_rate, idx))
        lat_acc_values.append(_safe_value(lat_acc, idx))
        gps_radius_values.append(_safe_value(gps_radius, idx))
        roll_rate_values.append(_safe_value(roll_rate, idx))
        brake_values.append(_safe_value(brake, idx))
        throttle_values.append(_safe_value(throttle, idx))
        gps_accuracy_values.append(_safe_value(gps_accuracy, idx))
        gps_speed_accuracy_values.append(_safe_value(gps_speed_accuracy, idx))
        satellites_values.append(_safe_value(satellites, idx))
        line_error_values.append(_safe_value(line_error, idx))
        lat_values.append(_safe_value(run_data.lat, idx))
        lon_values.append(_safe_value(run_data.lon, idx))
        last_distance = rel_distance

    if base_distance is None:
        base_distance = 0.0

    speed_proxy = not _has_valid_values(speed)
    speed = _fill_speed_from_distance(time, distance, speed)
    inline_acc_g = _normalize_inline_acc(inline_acc_values)
    lat_acc_g = _normalize_inline_acc(lat_acc_values)
    derived_acc_g = _derive_acc_g(time, speed)
    using_speed_proxy = speed_proxy or not _has_valid_values(inline_acc_g)
    if using_speed_proxy:
        inline_acc_g = derived_acc_g

    return LapSeries(
        time_s=time,
        distance_m=distance,
        speed_mps=speed,
        inline_acc_g=inline_acc_g,
        yaw_rate=yaw_values,
        lat_acc_g=lat_acc_g,
        gps_radius_m=gps_radius_values,
        roll_rate_dps=roll_rate_values,
        brake=brake_values,
        throttle=throttle_values,
        gps_accuracy_m=gps_accuracy_values,
        gps_speed_accuracy_mps=gps_speed_accuracy_values,
        satellites=satellites_values,
        line_error_m=line_error_values,
        lat=lat_values,
        lon=lon_values,
        base_distance=base_distance,
        using_speed_proxy=using_speed_proxy,
    )


def _normalize_segment_bounds(
    segment: Segment,
    *,
    base_distance: float,
    lap_length: float,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    start_m = getattr(segment, "start_m", None)
    apex_m = getattr(segment, "apex_m", None)
    end_m = getattr(segment, "end_m", None)
    if start_m is None or apex_m is None or end_m is None:
        return None, None, None

    if _within_lap(start_m, end_m, lap_length):
        return start_m, apex_m, end_m

    abs_start = start_m - base_distance
    abs_apex = apex_m - base_distance
    abs_end = end_m - base_distance
    if _within_lap(abs_start, abs_end, lap_length):
        return abs_start, abs_apex, abs_end

    return start_m, apex_m, end_m


def _within_lap(start_m: float, end_m: float, lap_length: float) -> bool:
    return start_m >= -5.0 and end_m <= lap_length + 5.0


def _segment_id(segment: Segment, idx: int, *, id_prefix: Optional[str]) -> str:
    for attr in ("turn_id", "lap_turn_id", "label"):
        value = getattr(segment, attr, None)
        if value:
            return _apply_prefix(str(value), id_prefix)
    return _apply_prefix(f"segment_{idx}", id_prefix)


def _corner_id(segment: Segment, idx: int, *, id_prefix: Optional[str]) -> Optional[str]:
    for attr in ("turn_id", "label", "lap_turn_id"):
        value = getattr(segment, attr, None)
        if value:
            return _apply_prefix(str(value), id_prefix)
    return _apply_prefix(f"T{idx}", id_prefix)


def _segment_indices(distance_m: Sequence[float], start_m: float, end_m: float) -> List[int]:
    indices: List[int] = []
    for idx, dist in enumerate(distance_m):
        if dist < start_m:
            continue
        if dist > end_m:
            break
        indices.append(idx)
    return indices


def _segment_time(lap: LapSeries, start_m: float, end_m: float) -> Optional[float]:
    start_t = _interp_one(lap.distance_m, lap.time_s, start_m)
    end_t = _interp_one(lap.distance_m, lap.time_s, end_m)
    if start_t is None or end_t is None:
        return None
    return max(0.0, end_t - start_t)


def _min_speed(lap: LapSeries, indices: Sequence[int]) -> Tuple[Optional[float], Optional[float]]:
    best_speed = None
    best_dist = None
    for idx in indices:
        speed = lap.speed_mps[idx] if idx < len(lap.speed_mps) else None
        if speed is None:
            continue
        if best_speed is None or speed < best_speed:
            best_speed = speed
            best_dist = lap.distance_m[idx]
    return best_speed, best_dist


def _brake_point(lap: LapSeries, start_m: float, apex_m: float) -> Tuple[Optional[float], Optional[float]]:
    indices = _segment_indices(lap.distance_m, start_m, apex_m)
    if not indices:
        return None, None

    brake = _slice_values(lap.brake, indices)
    if _has_valid_values(brake):
        threshold = _dynamic_threshold(brake)
        return _first_sustained(
            lap,
            indices,
            lambda idx: lap.brake[idx] is not None and lap.brake[idx] >= threshold,
            min_duration_s=0.25,
        )

    inline_acc = lap.inline_acc_g
    if not _has_valid_values(inline_acc):
        return None, None

    return _first_sustained(
        lap,
        indices,
        lambda idx: inline_acc[idx] is not None and inline_acc[idx] <= -0.08,
        min_duration_s=0.25,
    )


def _throttle_pickup(lap: LapSeries, apex_m: float, end_m: float) -> Tuple[Optional[float], Optional[float]]:
    indices = _segment_indices(lap.distance_m, apex_m, end_m)
    if not indices:
        return None, None

    throttle = _slice_values(lap.throttle, indices)
    if _has_valid_values(throttle):
        threshold = _dynamic_threshold(throttle)
        return _first_sustained(
            lap,
            indices,
            lambda idx: lap.throttle[idx] is not None and lap.throttle[idx] >= threshold,
            min_duration_s=0.25,
        )

    inline_acc = lap.inline_acc_g
    if not _has_valid_values(inline_acc):
        return None, None

    return _first_sustained(
        lap,
        indices,
        lambda idx: inline_acc[idx] is not None and inline_acc[idx] >= 0.05,
        min_duration_s=0.25,
    )


def _neutral_throttle_window(lap: LapSeries, indices: Sequence[int]) -> Dict[str, Optional[float]]:
    best_duration = 0.0
    best_distance = 0.0
    best_speed_delta = None
    best_sigma = None

    acc = lap.inline_acc_g
    if not _has_valid_values(acc):
        return {
            "neutral_throttle_s": None,
            "neutral_throttle_dist_m": None,
            "neutral_speed_delta_kmh": None,
            "speed_noise_sigma_kmh": None,
        }

    run_start = None
    for idx in indices:
        value = acc[idx] if idx < len(acc) else None
        if value is not None and abs(value) <= 0.03:
            if run_start is None:
                run_start = idx
        else:
            if run_start is not None:
                best_duration, best_distance, best_speed_delta, best_sigma = _evaluate_neutral_window(
                    lap,
                    run_start,
                    idx - 1,
                    best=(best_duration, best_distance, best_speed_delta, best_sigma),
                )
            run_start = None

    if run_start is not None:
        best_duration, best_distance, best_speed_delta, best_sigma = _evaluate_neutral_window(
            lap,
            run_start,
            indices[-1],
            best=(best_duration, best_distance, best_speed_delta, best_sigma),
        )

    return {
        "neutral_throttle_s": best_duration if best_duration > 0 else None,
        "neutral_throttle_dist_m": best_distance if best_distance > 0 else None,
        "neutral_speed_delta_kmh": best_speed_delta,
        "speed_noise_sigma_kmh": best_sigma,
    }


def _evaluate_neutral_window(
    lap: LapSeries,
    start_idx: int,
    end_idx: int,
    *,
    best: Tuple[float, float, Optional[float], Optional[float]],
) -> Tuple[float, float, Optional[float], Optional[float]]:
    best_duration, best_distance, best_speed_delta, best_sigma = best
    if end_idx <= start_idx:
        return best

    start_time = lap.time_s[start_idx]
    end_time = lap.time_s[end_idx]
    duration = max(0.0, end_time - start_time)
    distance = lap.distance_m[end_idx] - lap.distance_m[start_idx]

    if duration < 1.0 and distance < 15.0:
        return best

    speed_start = lap.speed_mps[start_idx]
    speed_end = lap.speed_mps[end_idx]
    if speed_start is None or speed_end is None:
        return best

    speed_delta = abs(speed_end - speed_start) * _KMH_PER_MPS
    if speed_delta > 1.0:
        return best

    sigma = _speed_noise_sigma(lap.speed_mps[start_idx : end_idx + 1])

    if duration > best_duration:
        best_duration = duration
        best_distance = distance
        best_speed_delta = speed_delta
        best_sigma = sigma
    return best_duration, best_distance, best_speed_delta, best_sigma


def _speed_noise_sigma(speed_mps: Sequence[Optional[float]]) -> Optional[float]:
    values = [v for v in speed_mps if v is not None]
    if len(values) < 3:
        return None
    smoothed = _moving_average(values, window=5)
    residuals = [v - s for v, s in zip(values, smoothed)]
    return _stddev([v * _KMH_PER_MPS for v in residuals])


def _line_stddev(lap: LapSeries, indices: Sequence[int]) -> Optional[float]:
    line_values = _slice_values(lap.line_error_m, indices)
    if line_values:
        return _stddev(line_values)
    return _line_stddev_from_latlon(lap.lat, lap.lon, indices)


def _line_stddev_from_latlon(
    lat: Sequence[Optional[float]],
    lon: Sequence[Optional[float]],
    indices: Sequence[int],
) -> Optional[float]:
    coords: List[Tuple[float, float]] = []
    for idx in indices:
        if idx >= len(lat) or idx >= len(lon):
            continue
        la = lat[idx]
        lo = lon[idx]
        if la is None or lo is None or math.isnan(la) or math.isnan(lo):
            continue
        coords.append((float(la), float(lo)))
    if len(coords) < 3:
        return None
    lat0 = statistics.fmean([c[0] for c in coords])
    lon0 = statistics.fmean([c[1] for c in coords])
    xys = [_project_latlon(lat0, lon0, la, lo) for la, lo in coords]
    x0, y0 = xys[0]
    x1, y1 = xys[-1]
    dx = x1 - x0
    dy = y1 - y0
    denom = math.hypot(dx, dy)
    if denom <= 1e-6:
        return None
    distances = [abs(dy * x - dx * y + x1 * y0 - y1 * x0) / denom for x, y in xys]
    return _stddev(distances)


def _project_latlon(lat0: float, lon0: float, lat: float, lon: float) -> Tuple[float, float]:
    lat0_rad = math.radians(lat0)
    dlat = math.radians(lat - lat0)
    dlon = math.radians(lon - lon0)
    x = dlon * math.cos(lat0_rad) * _EARTH_RADIUS_M
    y = dlat * _EARTH_RADIUS_M
    return x, y


def _inline_acc_rise(lap: LapSeries, apex_m: float, end_m: float, start_m: float) -> Optional[float]:
    after_end = min(end_m, apex_m + 30.0)
    before_start = max(start_m, apex_m - 10.0)

    after_idx = _segment_indices(lap.distance_m, apex_m, after_end)
    before_idx = _segment_indices(lap.distance_m, before_start, apex_m)

    after_values = _slice_values(lap.inline_acc_g, after_idx)
    before_values = _slice_values(lap.inline_acc_g, before_idx)

    if not after_values or not before_values:
        return None

    after_mean = _mean(after_values)
    before_mean = _mean(before_values)
    if after_mean is None or before_mean is None:
        return None
    return after_mean - before_mean


def _entry_decel_metrics(
    lap: LapSeries,
    entry_dist_m: float,
    apex_dist_m: float,
) -> Dict[str, Optional[float]]:
    if entry_dist_m >= apex_dist_m:
        return {
            "decel_avg_g": None,
            "decel_time_s": None,
            "decel_dist_m": None,
            "decel_g_per_10m": None,
        }

    v_entry = _interp_one(lap.distance_m, lap.speed_mps, entry_dist_m)
    v_apex = _interp_one(lap.distance_m, lap.speed_mps, apex_dist_m)
    t_entry = _interp_one(lap.distance_m, lap.time_s, entry_dist_m)
    t_apex = _interp_one(lap.distance_m, lap.time_s, apex_dist_m)
    if v_entry is None or v_apex is None or t_entry is None or t_apex is None:
        return {
            "decel_avg_g": None,
            "decel_time_s": None,
            "decel_dist_m": None,
            "decel_g_per_10m": None,
        }

    dt = t_apex - t_entry
    if dt <= 0:
        return {
            "decel_avg_g": None,
            "decel_time_s": None,
            "decel_dist_m": None,
            "decel_g_per_10m": None,
        }

    dv = v_apex - v_entry
    decel_avg_g = (dv / dt) / _G_MPS2
    decel_dist_m = max(0.0, apex_dist_m - entry_dist_m)
    decel_g_per_10m = abs(decel_avg_g) * (10.0 / max(1.0, decel_dist_m))

    return {
        "decel_avg_g": decel_avg_g,
        "decel_time_s": dt,
        "decel_dist_m": decel_dist_m,
        "decel_g_per_10m": decel_g_per_10m,
    }


def _lean_proxy(
    lap: LapSeries,
    indices: Sequence[int],
) -> Tuple[Optional[float], Optional[str]]:
    speed_vals = _slice_values(lap.speed_mps, indices)
    if not speed_vals:
        return None, "bad"
    max_speed = max(speed_vals)
    if max_speed < 8.0:
        return None, "bad"

    lat_acc_vals = _slice_values(lap.lat_acc_g, indices)
    max_lat_acc = max([abs(v) for v in lat_acc_vals], default=0.0)

    imu_lean_vals = [
        math.degrees(math.atan(abs(v)))
        for v in lat_acc_vals
        if v is not None
    ]

    gps_lean_vals: List[float] = []
    for idx in indices:
        if idx >= len(lap.speed_mps) or idx >= len(lap.gps_radius_m):
            continue
        v = lap.speed_mps[idx]
        r = lap.gps_radius_m[idx]
        if v is None or r is None:
            continue
        if v < 8.0:
            continue
        r = max(15.0, abs(r))
        a_lat = (v * v) / r
        lean = math.degrees(math.atan(a_lat / _G_MPS2))
        gps_lean_vals.append(lean)

    lean_imu = _median(imu_lean_vals)
    lean_gps = _median(gps_lean_vals)

    roll_rate_vals = _slice_values(lap.roll_rate_dps, indices)
    roll_rate_max = max([abs(v) for v in roll_rate_vals], default=0.0)
    if roll_rate_max > 150.0:
        return None, "bad"

    gps_accuracy = _mean(_slice_values(lap.gps_accuracy_m, indices))
    gps_speed_accuracy = _mean(_slice_values(lap.gps_speed_accuracy_mps, indices))

    valid_imu = lean_imu is not None and max_lat_acc >= 0.2
    valid_gps = lean_gps is not None and (gps_accuracy is None or gps_accuracy <= 2.5)

    if not valid_imu and not valid_gps:
        return None, "bad"

    if valid_imu and valid_gps:
        diff = 0.0
        if lean_imu and lean_gps and max(lean_imu, lean_gps) > 0:
            diff = abs(lean_imu - lean_gps) / max(lean_imu, lean_gps)
        if diff > 0.35:
            return None, "bad"
        quality = "good"
        if diff > 0.2:
            quality = "warn"
        if gps_accuracy is not None and gps_accuracy > 1.5:
            quality = "warn"
        if gps_speed_accuracy is not None and gps_speed_accuracy > 0.7:
            quality = "warn"
        lean_proxy = 0.6 * lean_imu + 0.4 * lean_gps
        return lean_proxy, quality

    if valid_imu:
        return lean_imu, "warn"

    if valid_gps:
        return lean_gps, "warn"

    return None, "bad"


def _first_sustained(
    lap: LapSeries,
    indices: Sequence[int],
    predicate,
    *,
    min_duration_s: float,
) -> Tuple[Optional[float], Optional[float]]:
    run_start = None
    for idx in indices:
        if predicate(idx):
            if run_start is None:
                run_start = idx
        else:
            run_start = None
        if run_start is not None:
            duration = lap.time_s[idx] - lap.time_s[run_start]
            if duration >= min_duration_s:
                return lap.distance_m[run_start], lap.time_s[run_start]
    return None, None


def _dynamic_threshold(values: Sequence[Optional[float]]) -> float:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return 0.0
    max_val = max(filtered)
    if max_val <= 1.5:
        return max(0.05, 0.2 * max_val)
    return 0.2 * max_val


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


def _safe_value(series: Optional[Sequence[Optional[float]]], idx: int) -> Optional[float]:
    if series is None or idx >= len(series):
        return None
    value = series[idx]
    return None if value is None else float(value)


def _fill_speed_from_distance(
    time_s: Sequence[float],
    distance_m: Sequence[float],
    speed_mps: List[Optional[float]],
) -> List[Optional[float]]:
    if _has_valid_values(speed_mps):
        return speed_mps
    derived: List[Optional[float]] = []
    last_speed = None
    for idx in range(len(distance_m)):
        if idx == 0:
            derived.append(None)
            continue
        dt = time_s[idx] - time_s[idx - 1]
        if dt <= 0:
            derived.append(last_speed)
            continue
        ds = distance_m[idx] - distance_m[idx - 1]
        value = ds / dt
        derived.append(value)
        last_speed = value
    return derived


def _normalize_inline_acc(values: Sequence[Optional[float]]) -> List[Optional[float]]:
    filtered = [abs(v) for v in values if v is not None]
    if not filtered:
        return list(values)
    median_abs = statistics.median(filtered)
    if median_abs > 5.0:
        return [None if v is None else v / _G_MPS2 for v in values]
    return list(values)


def _derive_acc_g(time_s: Sequence[float], speed_mps: Sequence[Optional[float]]) -> List[Optional[float]]:
    acc: List[Optional[float]] = [None]
    for idx in range(1, len(speed_mps)):
        v0 = speed_mps[idx - 1]
        v1 = speed_mps[idx]
        if v0 is None or v1 is None:
            acc.append(None)
            continue
        dt = time_s[idx] - time_s[idx - 1]
        if dt <= 0:
            acc.append(None)
            continue
        acc.append((v1 - v0) / dt / _G_MPS2)
    return _moving_average(acc, window=3)


def _moving_average(values: Sequence[Optional[float]], window: int) -> List[Optional[float]]:
    if not values:
        return []
    window = max(1, window)
    half = window // 2
    out: List[Optional[float]] = []
    for i in range(len(values)):
        start = max(0, i - half)
        end = min(len(values), i + half + 1)
        window_vals = [v for v in values[start:end] if v is not None]
        if not window_vals:
            out.append(None)
        else:
            out.append(sum(window_vals) / len(window_vals))
    return out


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


def _slice_values(values: Sequence[Optional[float]], indices: Sequence[int]) -> List[float]:
    out: List[float] = []
    for idx in indices:
        if idx >= len(values):
            continue
        value = values[idx]
        if value is None or math.isnan(value):
            continue
        out.append(float(value))
    return out


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.fmean(values))


def _median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median(values))


def _stddev(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    return float(statistics.pstdev(values))


def _variance(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    return float(statistics.pvariance(values))


def _rms(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    mean_sq = statistics.fmean([v * v for v in values])
    return math.sqrt(mean_sq)


def _has_valid_values(values: Sequence[Optional[float]], *, min_count: int = 3) -> bool:
    count = 0
    for value in values:
        if value is None:
            continue
        count += 1
        if count >= min_count:
            return True
    return False


def _using_speed_proxy(lap: LapSeries) -> bool:
    return lap.using_speed_proxy


def _imu_present(lap: LapSeries) -> bool:
    if _has_valid_values(lap.yaw_rate):
        return True
    if lap.using_speed_proxy:
        return False
    return _has_valid_values(lap.inline_acc_g)


def _mps_to_kmh(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * _KMH_PER_MPS


def _track_id_prefix(metadata: Optional[Dict[str, str]]) -> Optional[str]:
    if not metadata:
        return None
    track = _first_metadata(metadata, ["Track", "Track Name", "Circuit", "Track Identity"])
    direction = _first_metadata(metadata, ["Track Direction", "Direction", "Dir"])
    if track and direction is None:
        parsed = _parse_track_identity(track)
        if parsed is not None:
            track, direction = parsed
    if track and direction:
        return f"{track}:{direction}"
    return None


def _first_metadata(metadata: Dict[str, str], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        if key in metadata:
            value = metadata.get(key)
            return value.strip() if isinstance(value, str) else str(value)
    lowered = {k.lower(): k for k in metadata}
    for key in keys:
        match = lowered.get(key.lower())
        if match:
            value = metadata.get(match)
            return value.strip() if isinstance(value, str) else str(value)
    return None


def _parse_track_identity(value: str) -> Optional[Tuple[str, str]]:
    text = (value or "").strip()
    if not text:
        return None
    if "(" not in text or ")" not in text:
        return None
    start = text.rfind("(")
    end = text.rfind(")")
    if start < 0 or end <= start:
        return None
    direction = text[start + 1 : end].strip().upper()
    track = text[:start].strip()
    if not track or not direction:
        return None
    return track, direction


def _apply_prefix(value: str, prefix: Optional[str]) -> str:
    if not prefix:
        return value
    if value.startswith(f"{prefix}:"):
        return value
    return f"{prefix}:{value}"
