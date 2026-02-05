"""Repeatable trend evaluation harness.

Builds a fresh SQLite DB from a manifest of CSV files, computes line-trend
metrics, and compares them against a stored baseline. Use --update-baseline
to refresh the baseline when tuning thresholds intentionally.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.segment_metrics import compute_segment_metrics
from analytics.segments import detect_segments, label_laps_with_reference
from analytics.reference import filter_valid_laps, select_reference_laps
from analytics.trackside import pipeline
from analytics.trackside.config import TREND_FILTERS
from analytics.deltas import LapWindow
from ingest.csv.parser import parse_csv
from ingest.csv.save import save_to_db
from storage import db as db_mod


MANIFEST_DEFAULT = "tests/fixtures/trend_eval_manifest.json"
BASELINE_DEFAULT = "tests/fixtures/trend_eval_baseline.json"
ROUND_DIGITS = 4


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, ROUND_DIGITS)
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_round(v) for v in value]
    return value


def _percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * pct
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def _load_manifest(path: Path) -> List[Dict[str, str]]:
    raw = _read_json(path)
    files = raw.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Manifest must contain a non-empty 'files' list.")
    entries: List[Dict[str, str]] = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("Manifest entries must be objects.")
        entry_id = entry.get("id")
        file_path = entry.get("path")
        if not entry_id or not file_path:
            raise ValueError("Manifest entries require 'id' and 'path'.")
        entries.append({"id": str(entry_id), "path": str(file_path)})
    return entries


def _build_db(entries: List[Dict[str, str]]) -> Tuple[str, Dict[str, Dict[str, int]], tempfile.TemporaryDirectory]:
    temp_dir = tempfile.TemporaryDirectory(prefix="trend_eval_")
    db_path = os.path.join(temp_dir.name, "trend_eval.db")
    session_map: Dict[str, Dict[str, int]] = {}
    for idx, entry in enumerate(entries, start=1):
        path = Path(entry["path"])
        if not path.exists():
            raise FileNotFoundError(f"Missing CSV: {path}")
        parsed = parse_csv(str(path))
        result = save_to_db(parsed, db_path, source_file=str(path), run_index=idx)
        session_map[entry["id"]] = {
            "session_id": int(result.session_id),
            "run_id": int(result.run_id),
        }
    return db_path, session_map, temp_dir


def _collect_samples(
    conn,
    session: pipeline._SessionInfo,
    *,
    run_id: int,
    rider_id: Optional[int],
    bike_id: Optional[int],
) -> Dict[str, List[Dict[str, object]]]:
    related = pipeline._load_related_runs(
        conn,
        session,
        rider_id=rider_id,
        bike_id=bike_id,
        max_sessions=TREND_FILTERS.related_sessions_max,
    )
    if not related:
        return {}

    current_laps = pipeline._load_laps(conn, run_id, session)
    current_pace = pipeline._session_pace(current_laps)

    samples: Dict[str, List[Dict[str, object]]] = {}
    for item in related:
        session_info = pipeline._SessionInfo(
            session_id=int(item["session_id"]),
            track_id=item.get("track_id"),
            track_name=item.get("track_name"),
            track_direction=str(item.get("track_direction") or "UNKNOWN"),
            raw_metadata=item.get("raw_metadata") or {},
        )
        run_id_item = int(item["run_id"])
        run_data = pipeline._load_run_data(conn, run_id_item, session_info.raw_metadata)
        laps = pipeline._load_laps(conn, run_id_item, session_info)
        if not laps or run_data.distance_m is None:
            continue

        pace = pipeline._session_pace(laps)
        if current_pace is not None and pace is not None and pace > current_pace * 1.02:
            continue

        lap_stats = filter_valid_laps(run_data, laps)
        valid_laps = [stat.lap for stat in lap_stats if stat.is_valid]
        if not valid_laps:
            valid_laps = list(laps)

        selections = select_reference_laps(run_data, valid_laps)
        track_key = pipeline._track_key(session_info)
        selection = selections.get((track_key, session_info.track_direction)) or next(
            iter(selections.values()),
            None,
        )
        if selection is None:
            continue

        reference_lap = selection.reference_lap
        laps_for_track = [
            lap
            for lap in valid_laps
            if pipeline._track_key_from_lap(lap) == track_key
            and lap.direction == session_info.track_direction
        ]
        laps_for_track.sort(key=lambda lap: lap.lap_index)
        if not laps_for_track:
            continue

        reference_index = next(
            (idx for idx, lap in enumerate(laps_for_track) if lap.lap_id == reference_lap.lap_id),
            0,
        )
        segmentation_results = [
            detect_segments(pipeline._slice_run_data(run_data, lap.start_time_s, lap.end_time_s))
            for lap in laps_for_track
        ]
        _, labeled_laps = label_laps_with_reference(
            segmentation_results,
            track_key=str(track_key),
            direction=session_info.track_direction,
            reference_index=reference_index,
            lap_ids=None,
        )

        for lap, segments in zip(laps_for_track, labeled_laps):
            lap_window = LapWindow(start_time_s=lap.start_time_s, end_time_s=lap.end_time_s)
            metrics = compute_segment_metrics(run_data, lap_window, segments)
            for seg_id, values in metrics.items():
                sample = {
                    "session_id": session_info.session_id,
                    "lap_id": lap.lap_id,
                    "apex_dist_m": pipeline._as_float(values.get("apex_dist_m")),
                    "line_stddev_m": pipeline._as_float(values.get("line_stddev_m")),
                    "segment_time_s": pipeline._as_float(values.get("segment_time_s")),
                    "exit_speed_kmh": pipeline._as_float(values.get("exit_speed_30m_kmh")),
                    "entry_speed_kmh": pipeline._as_float(values.get("entry_speed_kmh")),
                    "min_speed_kmh": pipeline._as_float(values.get("min_speed_kmh")),
                    "speed_noise_sigma_kmh": pipeline._as_float(values.get("speed_noise_sigma_kmh")),
                }
                samples.setdefault(seg_id, []).append(sample)
    return samples


def _summarize_samples(samples_by_seg: Dict[str, List[Dict[str, object]]]) -> Dict[str, Any]:
    trends = pipeline._summarize_line_trends(samples_by_seg)
    segment_metrics: Dict[str, Dict[str, Any]] = {}
    retention_ratios: List[float] = []
    drop_totals = {
        "line_stddev": 0,
        "speed_noise": 0,
        "segment_time_iqr": 0,
        "min_speed_iqr": 0,
    }
    raw_total = 0
    kept_total = 0
    dropped_total = 0

    for seg_id, samples in samples_by_seg.items():
        raw = len(samples)
        cleaned, stats = pipeline._filter_segment_samples_with_stats(samples)
        filtered = len(cleaned)
        apex = len([s for s in cleaned if s.get("apex_dist_m") is not None])
        retention = (filtered / raw) if raw else 0.0
        retention_ratios.append(retention)
        trend_strength = None
        trend = trends.get(seg_id)
        if trend:
            trend_strength = str(trend.get("trend_strength") or "")
        segment_metrics[seg_id] = {
            "raw": raw,
            "filtered": filtered,
            "apex": apex,
            "retention": retention,
            "trend_strength": trend_strength,
        }
        raw_total += stats.get("raw", 0)
        kept_total += stats.get("kept", 0)
        dropped_total += stats.get("dropped", 0)
        for reason in drop_totals:
            drop_totals[reason] += stats.get("drop_reasons", {}).get(reason, 0)

    strengths = {"strong": 0, "light": 0}
    for trend in trends.values():
        strength = str(trend.get("trend_strength") or "").lower()
        if strength in strengths:
            strengths[strength] += 1

    drop_pct = {
        reason: (count / dropped_total) if dropped_total else 0.0
        for reason, count in drop_totals.items()
    }

    summary = {
        "segment_count": len(samples_by_seg),
        "trend_segments": len(trends),
        "trend_strength": strengths,
        "sample_retention": {
            "mean": statistics.fmean(retention_ratios) if retention_ratios else None,
            "p50": _percentile(retention_ratios, 0.5),
            "p90": _percentile(retention_ratios, 0.9),
        },
        "drop_stats": {
            "raw": raw_total,
            "kept": kept_total,
            "dropped": dropped_total,
            "drop_reasons": drop_totals,
            "drop_reasons_pct": drop_pct,
        },
    }
    return {"summary": summary, "segments": segment_metrics}


def _evaluate_entry(conn, entry: Dict[str, str], session_id: int, run_id: int) -> Dict[str, Any]:
    session = pipeline._load_session(conn, session_id)
    if session is None:
        raise RuntimeError(f"Missing session {session_id} for entry {entry['id']}")
    run_info = pipeline._load_run_info(conn, session_id)
    if run_info is None:
        raise RuntimeError(f"Missing run info for session {session_id}")
    run_id_info, rider_id, bike_id = run_info
    samples_by_seg = _collect_samples(
        conn,
        session,
        run_id=run_id_info,
        rider_id=rider_id,
        bike_id=bike_id,
    )
    metrics = _summarize_samples(samples_by_seg)
    payload = {
        "id": entry["id"],
        "path": entry["path"],
        "session_id": session_id,
        "run_id": run_id,
    }
    payload.update(metrics)
    return _round(payload)


def _compare_entries(current: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if current.get("summary") != baseline.get("summary"):
        errors.append(
            f"{current.get('id')}: summary mismatch (current vs baseline)."
        )
    current_segments = current.get("segments", {})
    baseline_segments = baseline.get("segments", {})
    for seg_id in sorted(set(current_segments) | set(baseline_segments)):
        cur_seg = current_segments.get(seg_id)
        base_seg = baseline_segments.get(seg_id)
        if cur_seg is None:
            errors.append(f"{current.get('id')}: segment {seg_id} missing in current.")
            continue
        if base_seg is None:
            errors.append(f"{current.get('id')}: segment {seg_id} missing in baseline.")
            continue
        if cur_seg != base_seg:
            errors.append(f"{current.get('id')}: segment {seg_id} mismatch.")
    return errors


def _print_report(payload: Dict[str, Any]) -> None:
    entries = payload.get("entries", [])
    seg_total = 0
    trend_segments = 0
    strength_light = 0
    strength_strong = 0
    retention_means = []
    drop_raw = 0
    drop_kept = 0
    drop_dropped = 0
    reasons: Dict[str, int] = {}

    for entry in entries:
        summary = entry.get("summary", {})
        seg_total += summary.get("segment_count", 0)
        trend_segments += summary.get("trend_segments", 0)
        ts = summary.get("trend_strength", {})
        strength_light += ts.get("light", 0)
        strength_strong += ts.get("strong", 0)
        mean = summary.get("sample_retention", {}).get("mean")
        if isinstance(mean, (int, float)):
            retention_means.append(mean)
        ds = summary.get("drop_stats", {})
        drop_raw += ds.get("raw", 0)
        drop_kept += ds.get("kept", 0)
        drop_dropped += ds.get("dropped", 0)
        for key, val in ds.get("drop_reasons", {}).items():
            reasons[key] = reasons.get(key, 0) + int(val)

    print("Trend eval report")
    print(f"- entries: {len(entries)}")
    print(f"- segments_total: {seg_total}")
    print(f"- trend_segments: {trend_segments}")
    print(f"- trend_strength: light {strength_light}, strong {strength_strong}")
    if retention_means:
        avg_mean = sum(retention_means) / len(retention_means)
        print(f"- retention_mean_avg: {avg_mean:.4f}")
    print(f"- drop_raw: {drop_raw}")
    print(f"- drop_kept: {drop_kept}")
    print(f"- drop_dropped: {drop_dropped}")
    if drop_dropped:
        pct = {k: (v / drop_dropped) * 100.0 for k, v in reasons.items()}
        ordered = sorted(pct.items(), key=lambda item: item[1], reverse=True)
        print("- drop_reasons_pct:")
        for key, value in ordered:
            print(f"  - {key}: {value:.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate trend filtering against a baseline.")
    parser.add_argument("--manifest", default=MANIFEST_DEFAULT)
    parser.add_argument("--baseline", default=BASELINE_DEFAULT)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    baseline_path = Path(args.baseline)
    entries = _load_manifest(manifest_path)

    db_path, session_map, temp_dir = _build_db(entries)
    conn = db_mod.connect(db_path)
    try:
        with conn:
            results: List[Dict[str, Any]] = []
            for entry in entries:
                ids = session_map[entry["id"]]
                results.append(_evaluate_entry(conn, entry, ids["session_id"], ids["run_id"]))
    finally:
        conn.close()
        temp_dir.cleanup()

    payload = {
        "manifest": str(manifest_path).replace("\\", "/"),
        "config": asdict(TREND_FILTERS),
        "entries": results,
    }
    payload = _round(payload)

    if args.report:
        _print_report(payload)

    if args.update_baseline or not baseline_path.exists():
        _write_json(baseline_path, payload)
        print(f"Baseline written to {baseline_path}")
        return 0

    baseline = _read_json(baseline_path)
    baseline = _round(baseline)
    errors: List[str] = []

    baseline_entries = {entry["id"]: entry for entry in baseline.get("entries", [])}
    for entry in payload["entries"]:
        base_entry = baseline_entries.get(entry["id"])
        if base_entry is None:
            errors.append(f"{entry.get('id')}: missing from baseline.")
            continue
        errors.extend(_compare_entries(entry, base_entry))

    if errors:
        print("Trend eval mismatches:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Trend eval matches baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
