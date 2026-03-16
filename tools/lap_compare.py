#!/usr/bin/env python3
"""Compare two laps corner by corner — shows where time is gained/lost and why.

Usage:
    # Compare lap 2 (target) vs lap 3 (reference)
    PYTHONPATH=. python3 tools/lap_compare.py test_data/87.csv --target 2 --ref 3

    # Compare fastest vs second-fastest
    PYTHONPATH=. python3 tools/lap_compare.py test_data/87.csv

    # JSON output
    PYTHONPATH=. python3 tools/lap_compare.py test_data/87.csv --json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, List, Optional, Tuple

from tools.lap_telemetry import (
    corner_summary,
    get_lap_bounds,
    slice_run_data,
)
from tools.track_references import detect_track, TrackReference
from ingest.csv.parser import parse_csv
from ingest.csv.importer import build_run_data


def match_corners(
    target_summaries: List[Dict],
    ref_summaries: List[Dict],
) -> List[Tuple[Dict, Optional[Dict]]]:
    """Match corners between two laps by label."""
    ref_by_corner = {s["corner"]: s for s in ref_summaries}
    matched = []
    for ts in target_summaries:
        rs = ref_by_corner.get(ts["corner"])
        matched.append((ts, rs))
    return matched


def build_deltas(target: Dict, ref: Dict) -> Dict:
    """Build per-corner delta metrics. Positive = target is more/faster."""
    return {
        "corner": target["corner"],
        "time_delta": round(target["duration"] - ref["duration"], 2),
        "entry_mph_delta": round(target["entry_mph"] - ref["entry_mph"], 1),
        "min_mph_delta": round(target["min_mph"] - ref["min_mph"], 1),
        "exit_mph_delta": round(target["exit_mph"] - ref["exit_mph"], 1),
        "brake_delta": round(target["max_brake_g"] - ref["max_brake_g"], 3),
        "neutral_delta": round(target["neutral_s"] - ref["neutral_s"], 2),
        "trail_brake_delta": round(target["trail_brake_s"] - ref["trail_brake_s"], 2),
        "target": target,
        "ref": ref,
    }


def explain_delta(d: Dict) -> List[str]:
    """Generate human-readable coaching notes from deltas."""
    notes = []
    t = d["target"]
    r = d["ref"]
    corner = d["corner"]

    # Time gained/lost
    if abs(d["time_delta"]) >= 0.1:
        if d["time_delta"] > 0:
            notes.append(f"Lost {d['time_delta']:.1f}s in {corner}")
        else:
            notes.append(f"Gained {-d['time_delta']:.1f}s in {corner}")

    # Entry speed
    if abs(d["entry_mph_delta"]) >= 2:
        if d["entry_mph_delta"] > 0:
            notes.append(f"  Entry {d['entry_mph_delta']:+.0f} mph faster ({t['entry_mph']:.0f} vs {r['entry_mph']:.0f})")
        else:
            notes.append(f"  Entry {d['entry_mph_delta']:+.0f} mph slower ({t['entry_mph']:.0f} vs {r['entry_mph']:.0f})")

    # Min speed
    if abs(d["min_mph_delta"]) >= 2:
        notes.append(f"  Mid-corner {d['min_mph_delta']:+.0f} mph ({t['min_mph']:.0f} vs {r['min_mph']:.0f})")

    # Exit speed
    if abs(d["exit_mph_delta"]) >= 2:
        notes.append(f"  Exit {d['exit_mph_delta']:+.0f} mph ({t['exit_mph']:.0f} vs {r['exit_mph']:.0f})")

    # Braking
    if abs(d["brake_delta"]) >= 0.05:
        if d["brake_delta"] < 0:
            notes.append(f"  Braked harder ({t['max_brake_g']:.2f}g vs {r['max_brake_g']:.2f}g)")
        else:
            notes.append(f"  Braked lighter ({t['max_brake_g']:.2f}g vs {r['max_brake_g']:.2f}g)")

    # Neutral throttle
    if d["neutral_delta"] >= 0.3:
        notes.append(f"  {d['neutral_delta']:.1f}s more neutral throttle ({t['neutral_s']:.1f}s vs {r['neutral_s']:.1f}s)")
    elif d["neutral_delta"] <= -0.3:
        notes.append(f"  {-d['neutral_delta']:.1f}s less neutral throttle")

    # Trail braking
    if abs(d["trail_brake_delta"]) >= 0.2:
        if d["trail_brake_delta"] > 0:
            notes.append(f"  More trail braking ({t['trail_brake_s']:.1f}s vs {r['trail_brake_s']:.1f}s)")
        else:
            notes.append(f"  Less trail braking ({t['trail_brake_s']:.1f}s vs {r['trail_brake_s']:.1f}s)")

    return notes


def main():
    parser = argparse.ArgumentParser(description="Compare two laps corner by corner")
    parser.add_argument("csv_file", help="Path to AiM CSV export")
    parser.add_argument("--target", type=int, default=None, help="Target lap number (default: fastest)")
    parser.add_argument("--ref", type=int, default=None, help="Reference lap number (default: 2nd fastest)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    parsed = parse_csv(args.csv_file)
    rd = build_run_data(parsed)

    laps = get_lap_bounds(rd.metadata)
    if len(laps) < 2:
        print("Need at least 2 laps to compare", file=sys.stderr)
        return 1

    # Sort by duration to find fastest two
    sorted_laps = sorted(range(len(laps)), key=lambda i: laps[i][2])

    target_idx = (args.target - 1) if args.target else sorted_laps[0]
    ref_idx = (args.ref - 1) if args.ref else sorted_laps[1]

    if target_idx < 0 or target_idx >= len(laps) or ref_idx < 0 or ref_idx >= len(laps):
        print(f"Invalid lap numbers (1-{len(laps)})", file=sys.stderr)
        return 1

    t_start, t_end, t_dur = laps[target_idx]
    r_start, r_end, r_dur = laps[ref_idx]

    rd_target = slice_run_data(rd, t_start, t_end)
    rd_ref = slice_run_data(rd, r_start, r_end)

    # Use track reference template for corner identification
    ref = detect_track(rd_target)
    if not ref:
        print("Warning: could not identify track, no corner labels available", file=sys.stderr)
        ref = TrackReference("Unknown", "?", 0, [])

    summ_t = corner_summary(rd_target, ref, lap_start_t=t_start)
    summ_r = corner_summary(rd_ref, ref, lap_start_t=r_start)

    matched = match_corners(summ_t, summ_r)

    if not args.json:
        t_min, t_sec = int(t_dur) // 60, t_dur - (int(t_dur) // 60) * 60
        r_min, r_sec = int(r_dur) // 60, r_dur - (int(r_dur) // 60) * 60
        print(f"Target: Lap {target_idx + 1} ({t_min}:{t_sec:05.2f})")
        print(f"Ref:    Lap {ref_idx + 1} ({r_min}:{r_sec:05.2f})")
        delta = t_dur - r_dur
        print(f"Overall: {delta:+.3f}s")
        print()

        # Summary table
        print(f"{'corner':>7} {'Δtime':>6} {'Δentry':>6} {'Δmin':>5} {'Δexit':>5} "
              f"{'Δbrake':>6} {'Δneut':>5} {'Δtrail':>6}")
        print("-" * 60)

        all_deltas = []
        for ts, rs in matched:
            if rs is None:
                print(f"{ts['corner']:>7}  (no match in ref)")
                continue
            d = build_deltas(ts, rs)
            all_deltas.append(d)
            print(f"{d['corner']:>7} {d['time_delta']:+5.2f}s "
                  f"{d['entry_mph_delta']:+5.0f} {d['min_mph_delta']:+4.0f} "
                  f"{d['exit_mph_delta']:+4.0f} {d['brake_delta']:+6.3f} "
                  f"{d['neutral_delta']:+5.02f} {d['trail_brake_delta']:+5.02f}")

        print()
        print("=== Coaching Notes ===")
        for d in all_deltas:
            notes = explain_delta(d)
            for note in notes:
                print(note)
    else:
        deltas = []
        for ts, rs in matched:
            if rs is None:
                continue
            d = build_deltas(ts, rs)
            d["notes"] = explain_delta(d)
            del d["target"]
            del d["ref"]
            deltas.append(d)
        output = {
            "target_lap": target_idx + 1,
            "ref_lap": ref_idx + 1,
            "target_time": round(t_dur, 3),
            "ref_time": round(r_dur, 3),
            "overall_delta": round(t_dur - r_dur, 3),
            "corners": deltas,
        }
        print(json.dumps(output, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
