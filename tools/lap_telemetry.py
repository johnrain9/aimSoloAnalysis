#!/usr/bin/env python3
"""Dump per-lap telemetry with corner labels for interactive analysis.

Usage:
    # Show lap 2 at 1-second intervals with corner labels
    PYTHONPATH=. python3 tools/lap_telemetry.py test_data/87.csv --lap 2

    # Show only corner sections (skip straights)
    PYTHONPATH=. python3 tools/lap_telemetry.py test_data/87.csv --lap 2 --corners-only

    # Show corner summary
    PYTHONPATH=. python3 tools/lap_telemetry.py test_data/87.csv --lap 2 --summary

    # JSON output for piping
    PYTHONPATH=. python3 tools/lap_telemetry.py test_data/87.csv --lap 2 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ingest.csv.parser import parse_csv
from ingest.csv.importer import build_run_data
from domain.run_data import RunData
from tools.track_references import TrackCorner, TrackReference, detect_track


MPS_TO_MPH = 2.23694
M_TO_FT = 3.28084
SPEED_TO_MPH = MPS_TO_MPH  # RunData speed is in m/s


def parse_beacon_times(metadata: Dict[str, str]) -> List[float]:
    raw = metadata.get("Beacon Markers", "")
    if not raw:
        return []
    times: List[float] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if tok:
            try:
                times.append(float(tok))
            except ValueError:
                pass
    return times


def get_lap_bounds(metadata: Dict[str, str]) -> List[Tuple[float, float, float]]:
    beacons = parse_beacon_times(metadata)
    laps = []
    for i in range(len(beacons) - 1):
        start = beacons[i]
        end = beacons[i + 1]
        laps.append((start, end, end - start))
    return laps


def slice_run_data(rd: RunData, start_t: float, end_t: float) -> RunData:
    start_i = None
    end_i = None
    for i, t in enumerate(rd.time_s):
        if t is None:
            continue
        if start_i is None and t >= start_t:
            start_i = i
        if t >= end_t:
            end_i = i
            break
    if start_i is None:
        start_i = 0
    if end_i is None:
        end_i = len(rd.time_s)
    return RunData(
        time_s=rd.time_s[start_i:end_i],
        distance_m=rd.distance_m[start_i:end_i] if rd.distance_m else None,
        lat=rd.lat[start_i:end_i] if rd.lat else None,
        lon=rd.lon[start_i:end_i] if rd.lon else None,
        speed=rd.speed[start_i:end_i] if rd.speed else None,
        channels={k: v[start_i:end_i] for k, v in rd.channels.items()},
        metadata=rd.metadata,
    )


def corner_label_at_index(
    idx: int,
    rd: RunData,
    ref: TrackReference,
) -> str:
    """Return corner label + phase for a sample index using track reference."""
    if not rd.distance_m or not ref:
        return ""
    d0 = rd.distance_m[0] or 0
    d = (rd.distance_m[idx] or 0) - d0
    corner, phase = ref.corner_phase_at_distance(d)
    if corner is None:
        return ""
    return f"{corner.name}{corner.direction} {phase}"


def format_table(
    rd: RunData,
    ref: TrackReference,
    dt: float = 1.0,
    corners_only: bool = False,
    lap_start_t: float = 0.0,
) -> List[str]:
    lines = []
    header = (
        f"{'t':>5} {'mph':>5} {'brk/acc':>7} {'latG':>5} "
        f"{'head':>6} {'dist_ft':>7}  corner"
    )
    lines.append(header)
    lines.append("-" * len(header))

    if not rd.time_s:
        return lines

    lon_acc = rd.channels.get("GPS LonAcc", [])
    lat_acc = rd.channels.get("GPS LatAcc", [])
    heading = rd.channels.get("GPS Heading", [])

    d0 = rd.distance_m[0] if rd.distance_m else 0

    step = max(1, int(dt * 20))  # 20Hz
    for i in range(0, len(rd.time_s), step):
        t = rd.time_s[i]
        if t is None:
            continue
        t_lap = t - lap_start_t

        spd = (rd.speed[i] if rd.speed else 0) or 0
        spd_mph = spd * SPEED_TO_MPH

        la = lon_acc[i] if i < len(lon_acc) and lon_acc[i] is not None else 0
        ta = lat_acc[i] if i < len(lat_acc) and lat_acc[i] is not None else 0
        h = heading[i] if i < len(heading) and heading[i] is not None else 0
        d = ((rd.distance_m[i] if rd.distance_m else 0) or 0)
        d_ft = (d - d0) * M_TO_FT

        corner = corner_label_at_index(i, rd, ref)

        if corners_only and not corner:
            continue

        lines.append(
            f"{t_lap:5.1f} {spd_mph:5.0f} {la:+6.2f}g {ta:+5.2f} "
            f"{h:6.1f} {d_ft:7.0f}  {corner}"
        )

    return lines


def corner_summary(
    rd: RunData,
    ref: TrackReference,
    lap_start_t: float = 0.0,
) -> List[Dict]:
    """Build per-corner summary metrics using track reference."""
    lon_acc = rd.channels.get("GPS LonAcc", [])
    lat_acc = rd.channels.get("GPS LatAcc", [])
    heading = rd.channels.get("GPS Heading", [])

    d0 = rd.distance_m[0] if rd.distance_m else 0
    summaries = []

    for c in ref.corners:
        # Find all sample indices within this corner's distance range
        indices = []
        for i in range(len(rd.time_s)):
            d = rd.distance_m[i] if rd.distance_m else None
            if d is not None:
                rel_d = d - d0
                if c.entry_dist_m <= rel_d <= c.exit_dist_m:
                    indices.append(i)

        if not indices:
            continue

        speeds_mph = []
        braking_gs = []
        accel_gs = []
        lat_gs = []
        neutral_samples = 0

        for i in indices:
            spd = (rd.speed[i] if rd.speed else 0) or 0
            speeds_mph.append(spd * SPEED_TO_MPH)

            la = lon_acc[i] if i < len(lon_acc) and lon_acc[i] is not None else 0
            ta = lat_acc[i] if i < len(lat_acc) and lat_acc[i] is not None else 0

            if la < -0.1:
                braking_gs.append(la)
            elif la > 0.1:
                accel_gs.append(la)
            else:
                neutral_samples += 1

            lat_gs.append(abs(ta))

        entry_speed = speeds_mph[0] if speeds_mph else 0
        min_speed = min(speeds_mph) if speeds_mph else 0
        exit_speed = speeds_mph[-1] if speeds_mph else 0
        max_braking = min(braking_gs) if braking_gs else 0
        max_accel = max(accel_gs) if accel_gs else 0
        max_lat = max(lat_gs) if lat_gs else 0
        neutral_time = neutral_samples / 20.0  # 20Hz

        # Time in corner
        t_start = rd.time_s[indices[0]] - lap_start_t
        t_end = rd.time_s[indices[-1]] - lap_start_t
        duration = t_end - t_start

        # Heading change through corner
        h_entry = heading[indices[0]] if indices[0] < len(heading) and heading[indices[0]] is not None else 0
        h_exit = heading[indices[-1]] if indices[-1] < len(heading) and heading[indices[-1]] is not None else 0
        h_delta = h_exit - h_entry
        while h_delta > 180:
            h_delta -= 360
        while h_delta < -180:
            h_delta += 360

        # Trail braking: braking + cornering simultaneously
        trail_samples = 0
        for i in indices:
            la = lon_acc[i] if i < len(lon_acc) and lon_acc[i] is not None else 0
            ta = lat_acc[i] if i < len(lat_acc) and lat_acc[i] is not None else 0
            if la < -0.1 and abs(ta) > 0.3:
                trail_samples += 1
        trail_brake_time = trail_samples / 20.0

        # Braking duration
        brake_time = len(braking_gs) / 20.0

        summaries.append({
            "corner": f"{c.name}{c.direction}",
            "name": c.name,
            "t_start": round(t_start, 1),
            "t_end": round(t_end, 1),
            "duration": round(duration, 1),
            "entry_mph": round(entry_speed, 1),
            "min_mph": round(min_speed, 1),
            "exit_mph": round(exit_speed, 1),
            "max_brake_g": round(max_braking, 3),
            "max_accel_g": round(max_accel, 3),
            "max_lat_g": round(max_lat, 3),
            "neutral_s": round(neutral_time, 2),
            "trail_brake_s": round(trail_brake_time, 2),
            "brake_time_s": round(brake_time, 2),
            "heading_change": round(h_delta, 1),
            "dist_start_ft": round(c.entry_dist_m * M_TO_FT),
            "dist_end_ft": round(c.exit_dist_m * M_TO_FT),
        })

    return summaries


def main():
    parser = argparse.ArgumentParser(description="Lap telemetry viewer")
    parser.add_argument("csv_file", help="Path to AiM CSV export")
    parser.add_argument("--lap", type=int, default=None, help="Lap number (1-based, default: fastest)")
    parser.add_argument("--dt", type=float, default=1.0, help="Time step in seconds (default: 1.0)")
    parser.add_argument("--corners-only", action="store_true", help="Only show corner sections")
    parser.add_argument("--summary", action="store_true", help="Show corner summary table instead of full trace")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    parsed = parse_csv(args.csv_file)
    rd = build_run_data(parsed)

    laps = get_lap_bounds(rd.metadata)
    if not laps:
        print("No laps found in data", file=sys.stderr)
        return 1

    # Print lap overview
    if not args.json:
        print(f"Session: {rd.metadata.get('Session', '?')} | "
              f"Rider: {rd.metadata.get('Racer', '?')} | "
              f"Bike: {rd.metadata.get('Vehicle', '?')}")
        print(f"Laps: {len(laps)}")
        for i, (s, e, d) in enumerate(laps, 1):
            mins = int(d) // 60
            secs = d - mins * 60
            marker = " <-- fastest" if d == min(l[2] for l in laps) else ""
            print(f"  Lap {i}: {mins}:{secs:05.2f}{marker}")
        print()

    # Select lap
    if args.lap is not None:
        lap_idx = args.lap - 1
    else:
        lap_idx = min(range(len(laps)), key=lambda i: laps[i][2])

    if lap_idx < 0 or lap_idx >= len(laps):
        print(f"Invalid lap number (1-{len(laps)})", file=sys.stderr)
        return 1

    start_t, end_t, dur = laps[lap_idx]
    rd_lap = slice_run_data(rd, start_t, end_t)

    # Detect track from lap data
    ref = detect_track(rd_lap)
    if not ref:
        print("Warning: could not identify track, no corner labels available", file=sys.stderr)
        # Create an empty reference so the tools still work
        from tools.track_references import TrackReference
        ref = TrackReference("Unknown", "?", 0, [])

    if not args.json:
        mins = int(dur) // 60
        secs = dur - mins * 60
        track_str = f"{ref.track_name} {ref.track_direction}" if ref.corners else "unknown track"
        print(f"Lap {lap_idx + 1}: {mins}:{secs:05.2f} | "
              f"{track_str} | {len(ref.corners)} corners")
        print()

    if args.summary:
        summaries = corner_summary(rd_lap, ref, lap_start_t=start_t)
        if args.json:
            print(json.dumps(summaries, indent=2))
        else:
            print(f"{'corner':>5} {'time':>10} {'dur':>4} {'entry':>5} {'min':>5} "
                  f"{'exit':>5} {'brake':>6} {'accel':>6} {'latG':>5} "
                  f"{'neut':>5} {'trail':>5} {'Δhdg':>5}")
            print("-" * 90)
            for s in summaries:
                print(f"{s['corner']:>5} {s['t_start']:4.1f}-{s['t_end']:<5.1f} "
                      f"{s['duration']:4.1f} {s['entry_mph']:5.0f} {s['min_mph']:5.0f} "
                      f"{s['exit_mph']:5.0f} {s['max_brake_g']:6.3f} {s['max_accel_g']:6.3f} "
                      f"{s['max_lat_g']:5.3f} {s['neutral_s']:5.2f} {s['trail_brake_s']:5.2f} "
                      f"{s['heading_change']:+5.0f}")
    else:
        table = format_table(rd_lap, ref, dt=args.dt,
                           corners_only=args.corners_only, lap_start_t=start_t)
        if args.json:
            print(json.dumps(table))
        else:
            for line in table:
                print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
