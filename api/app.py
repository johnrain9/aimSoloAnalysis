from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from analytics.reference import LapCandidate, select_reference_laps, filter_valid_laps
from analytics.segments import detect_segments
from analytics.trackside.corner_identity import rider_corner_label
from analytics.trackside.pipeline import (
    generate_trackside_insights,
    generate_trackside_map,
    generate_compare_map,
)
from api.units import (
    convert_compare_payload,
    convert_evidence,
    convert_map_payload,
    convert_rider_text,
    imperial_unit_contract,
)
from domain.run_data import RunData
from ingest.csv.parser import parse_csv
from ingest.csv.save import save_to_db
from storage import db

ANALYTICS_VERSION = "0.1.0-local"
DB_PATH = Path(__file__).resolve().parent.parent / "aimsolo.db"

app = FastAPI(title="AimSolo Local API", version=ANALYTICS_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImportRequest(BaseModel):
    file_path: Optional[str] = Field(
        default=None,
        description="Local file path for offline import. If omitted, mock data is used.",
    )


class ImportResponse(BaseModel):
    session_id: str
    track_name: str
    direction: str
    track_direction: str
    analytics_version: str
    source: str
    rider_name: Optional[str] = None
    bike_name: Optional[str] = None


def _parse_session_id(session_id: str) -> Optional[int]:
    try:
        return int(session_id)
    except (TypeError, ValueError):
        return None


def _format_duration(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes}:{remainder:06.3f}"


def _format_delta(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    sign = "+" if seconds > 0 else ""
    return f"{sign}{seconds:.3f}"


def _format_percent(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return f"{value:.0f}%"


def _build_error(session_id: str) -> Dict[str, Any]:
    return {
        "error": "unknown_session",
        "session_id": session_id,
        "track_direction": "",
        "analytics_version": ANALYTICS_VERSION,
        "rider_name": None,
        "bike_name": None,
    }


def _build_not_ready(session_id: str, meta: Optional[Dict[str, Any]], detail: str) -> Dict[str, Any]:
    track_name = meta.get("track_name", "") if meta else ""
    direction = meta.get("direction", "") if meta else ""
    track_direction = meta.get("track_direction", "") if meta else ""
    rider_name = meta.get("rider_name") if meta else None
    bike_name = meta.get("bike_name") if meta else None
    return {
        "error": "not_ready",
        "detail": detail,
        "session_id": session_id,
        "track_name": track_name,
        "direction": direction,
        "track_direction": track_direction,
        "analytics_version": ANALYTICS_VERSION,
        "rider_name": rider_name,
        "bike_name": bike_name,
    }


def _load_session_meta(conn, session_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT tracks.track_id AS track_id,
               tracks.name AS track_name,
               tracks.direction AS direction,
               sessions.track_direction AS track_direction,
               sessions.raw_metadata_json AS raw_metadata_json
        FROM sessions
        JOIN tracks ON tracks.track_id = sessions.track_id
        WHERE sessions.session_id = ?
        """,
        (session_id,),
    ).fetchone()
    if not row:
        return None
    raw_metadata = {}
    if row["raw_metadata_json"]:
        try:
            raw_metadata = json.loads(row["raw_metadata_json"])
        except json.JSONDecodeError:
            raw_metadata = {}
    return {
        "track_id": int(row["track_id"]),
        "track_name": row["track_name"],
        "direction": row["direction"],
        "track_direction": f"{row['track_name']} {row['direction']}".strip(),
        "raw_metadata": raw_metadata,
    }


def _load_run_id(conn, session_id: int) -> Optional[int]:
    row = conn.execute(
        """
        SELECT run_id
        FROM runs
        WHERE session_id = ?
        ORDER BY run_index ASC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    return int(row["run_id"]) if row else None


def _load_run_meta(conn, run_id: Optional[int]) -> Dict[str, Optional[str]]:
    if run_id is None:
        return {"rider_name": None, "bike_name": None}
    row = conn.execute(
        """
        SELECT riders.name AS rider_name,
               bikes.name AS bike_name
        FROM runs
        LEFT JOIN riders ON riders.rider_id = runs.rider_id
        LEFT JOIN bikes ON bikes.bike_id = runs.bike_id
        WHERE runs.run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if not row:
        return {"rider_name": None, "bike_name": None}
    return {
        "rider_name": row["rider_name"],
        "bike_name": row["bike_name"],
    }


def _load_laps(conn, run_id: int) -> list[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT lap_id, lap_index, start_time_s, end_time_s, duration_s
        FROM laps
        WHERE run_id = ?
        ORDER BY lap_index ASC
        """,
        (run_id,),
    ).fetchall()
    laps: list[Dict[str, Any]] = []
    for row in rows:
        duration = row["duration_s"]
        if duration is None and row["start_time_s"] is not None and row["end_time_s"] is not None:
            duration = row["end_time_s"] - row["start_time_s"]
        laps.append(
            {
                "lap_id": int(row["lap_id"]),
                "lap_index": int(row["lap_index"]),
                "start_time_s": row["start_time_s"],
                "end_time_s": row["end_time_s"],
                "duration_s": duration,
            }
        )
    return laps


def _load_run_data(conn, run_id: int, metadata: Dict[str, str]) -> Optional[RunData]:
    rows = conn.execute(
        """
        SELECT time_s,
               distance_m,
               latitude,
               longitude,
               gps_speed_kmh,
               gps_heading_deg,
               gps_accuracy_m
        FROM sample_points
        WHERE run_id = ?
        ORDER BY time_s ASC
        """,
        (run_id,),
    ).fetchall()
    if not rows:
        return None
    time_s = [row["time_s"] for row in rows]
    distance_m = [row["distance_m"] for row in rows]
    lat = [row["latitude"] for row in rows]
    lon = [row["longitude"] for row in rows]
    speed = [
        None if row["gps_speed_kmh"] is None else row["gps_speed_kmh"] / 3.6
        for row in rows
    ]
    channels = {
        "gps_heading_deg": [row["gps_heading_deg"] for row in rows],
        "gps_accuracy_m": [row["gps_accuracy_m"] for row in rows],
    }
    return RunData(
        time_s=time_s,
        distance_m=distance_m,
        lat=lat,
        lon=lon,
        speed=speed,
        channels=channels,
        metadata=metadata,
    )


def _slice_lap(run_data: RunData, start_time: float, end_time: float) -> RunData:
    time_s: list[Optional[float]] = []
    distance_m: list[Optional[float]] = []
    lat: list[Optional[float]] = []
    lon: list[Optional[float]] = []
    speed: list[Optional[float]] = []
    channels: Dict[str, list[Optional[float]]] = {name: [] for name in run_data.channels}

    base_time: Optional[float] = None
    base_distance: Optional[float] = None

    for idx, t in enumerate(run_data.time_s):
        if t is None or t < start_time or t > end_time:
            continue
        if base_time is None:
            base_time = t
        d = run_data.distance_m[idx] if run_data.distance_m else None
        if base_distance is None and d is not None:
            base_distance = d

        time_s.append(t - base_time)
        if d is None or base_distance is None:
            distance_m.append(None)
        else:
            distance_m.append(d - base_distance)
        lat.append(run_data.lat[idx] if run_data.lat else None)
        lon.append(run_data.lon[idx] if run_data.lon else None)
        speed.append(run_data.speed[idx] if run_data.speed else None)
        for name, series in run_data.channels.items():
            channels[name].append(series[idx])

    return RunData(
        time_s=time_s,
        distance_m=distance_m if distance_m else None,
        lat=lat if lat else None,
        lon=lon if lon else None,
        speed=speed if speed else None,
        channels=channels,
        metadata=run_data.metadata,
    )


def _lap_series(distance_m: Optional[list[Optional[float]]], time_s: list[Optional[float]]) -> tuple[list[float], list[float]]:
    if not distance_m:
        return [], []
    distances: list[float] = []
    times: list[float] = []
    last_distance = None
    for d, t in zip(distance_m, time_s):
        if d is None or t is None:
            continue
        if last_distance is not None and d <= last_distance:
            continue
        distances.append(float(d))
        times.append(float(t))
        last_distance = float(d)
    return distances, times


def _interp_time(distance: list[float], time: list[float], target: float) -> Optional[float]:
    if not distance or not time:
        return None
    j = 0
    while j < len(distance) - 1 and distance[j + 1] < target:
        j += 1
    if target < distance[0] or target > distance[-1]:
        return None
    if distance[j] == target:
        return time[j]
    if j + 1 >= len(distance):
        return time[-1]
    d0 = distance[j]
    d1 = distance[j + 1]
    t0 = time[j]
    t1 = time[j + 1]
    if d1 == d0:
        return t0
    return t0 + (t1 - t0) * (target - d0) / (d1 - d0)


def _segment_time(distance: list[float], time: list[float], start_m: float, end_m: float) -> Optional[float]:
    start_t = _interp_time(distance, time, start_m)
    end_t = _interp_time(distance, time, end_m)
    if start_t is None or end_t is None:
        return None
    return max(0.0, end_t - start_t)


def _pick_reference_and_target(
    run_data: RunData,
    laps: list[Dict[str, Any]],
    direction: str,
    track_key: object,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not laps:
        return None, None
    candidates = [
        LapCandidate(
            lap_index=lap["lap_index"],
            start_time_s=lap["start_time_s"],
            end_time_s=lap["end_time_s"],
            direction=direction,
            track_id=track_key if isinstance(track_key, int) else None,
            track_name=str(track_key) if not isinstance(track_key, int) else None,
            lap_id=lap["lap_id"],
            run_id=None,
        )
        for lap in laps
        if lap["start_time_s"] is not None and lap["end_time_s"] is not None
    ]
    stats = filter_valid_laps(run_data, candidates)
    valid = [stat.lap for stat in stats if stat.is_valid]
    if not valid:
        valid = list(candidates)
    selections = select_reference_laps(run_data, valid)
    reference = None
    if selections:
        key = (track_key, direction)
        selection = selections.get(key)
        if selection:
            reference = next((lap for lap in laps if lap["lap_id"] == selection.reference_lap.lap_id), None)
    if reference is None:
        reference = min(laps, key=lambda lap: lap["duration_s"] or float("inf"))

    target = max(laps, key=lambda lap: lap["lap_index"])
    if reference and target["lap_id"] == reference["lap_id"] and len(laps) > 1:
        non_ref = [lap for lap in laps if lap["lap_id"] != reference["lap_id"]]
        target = max(non_ref, key=lambda lap: lap["lap_index"])

    return reference, target


def _find_lap_by_index(laps: list[Dict[str, Any]], lap_index: int) -> Optional[Dict[str, Any]]:
    return next((lap for lap in laps if lap["lap_index"] == lap_index), None)


def _filter_valid_lap_rows(
    run_data: RunData,
    laps: list[Dict[str, Any]],
    *,
    direction: str,
    track_key: object,
) -> list[Dict[str, Any]]:
    candidates = [
        LapCandidate(
            lap_index=lap["lap_index"],
            start_time_s=lap["start_time_s"],
            end_time_s=lap["end_time_s"],
            direction=direction,
            track_id=track_key if isinstance(track_key, int) else None,
            track_name=str(track_key) if not isinstance(track_key, int) else None,
            lap_id=lap["lap_id"],
            run_id=None,
        )
        for lap in laps
        if lap["start_time_s"] is not None and lap["end_time_s"] is not None
    ]
    if not candidates:
        return laps
    stats = filter_valid_laps(run_data, candidates)
    valid_ids = {stat.lap.lap_id for stat in stats if stat.is_valid and stat.lap.lap_id is not None}
    if not valid_ids:
        return laps
    return [lap for lap in laps if lap["lap_id"] in valid_ids]


def _summarize_laps(laps: list[Dict[str, Any]]) -> tuple[list[Dict[str, Any]], list[float]]:
    durations = [lap["duration_s"] for lap in laps if lap["duration_s"] is not None]
    best_duration = min(durations) if durations else None
    lap_list: list[Dict[str, Any]] = []
    for lap in laps:
        duration = lap["duration_s"]
        sector_times = None
        if duration is not None:
            sector = duration / 3.0
            sector_times = [_format_duration(sector) or "--"] * 3
        lap_list.append(
            {
                "lap": lap["lap_index"],
                "time": _format_duration(duration) or "--",
                "sector_times": sector_times or ["--", "--", "--"],
                "is_best": best_duration is not None and duration == best_duration,
            }
        )
    return lap_list, durations


def _build_summary_cards(durations: list[float]) -> list[Dict[str, Any]]:
    if not durations:
        return []
    best = min(durations)
    avg = sum(durations) / len(durations)
    variance = 0.0
    if len(durations) > 1:
        variance = sum((value - avg) ** 2 for value in durations) / (len(durations) - 1)
    stddev = variance ** 0.5
    consistency = None
    if avg > 0:
        consistency = max(0.0, min(1.0, 1.0 - stddev / avg)) * 100.0

    cards = [
        {
            "id": "best_lap",
            "label": "Best Lap",
            "value": _format_duration(best) or "--",
            "delta": _format_delta(best - avg) or "--",
            "trend": "up" if best <= avg else "down",
        },
        {
            "id": "avg_lap",
            "label": "Avg Lap",
            "value": _format_duration(avg) or "--",
            "delta": _format_delta(avg - best) or "--",
            "trend": "down" if avg >= best else "up",
        },
        {
            "id": "consistency",
            "label": "Consistency",
            "value": _format_percent(consistency) or "--",
            "delta": _format_percent(consistency - 90.0) if consistency is not None else "--",
            "trend": "up" if (consistency or 0) >= 90.0 else "down",
        },
    ]
    return cards


def _did_vs_should_payload(insight: Dict[str, Any]) -> Dict[str, str]:
    did = str(insight.get("did") or insight.get("detail") or "").strip()
    should = str(insight.get("should") or insight.get("operational_action") or "").strip()
    because = str(insight.get("because") or insight.get("causal_reason") or "").strip()
    success_check = str(insight.get("success_check") or "").strip()

    if not did:
        did = "Current telemetry indicates a controllable issue in this segment, but marker context is unavailable."
    if not should:
        should = (
            "Use one repeatable marker and one small input change; avoid exact-distance targets in this run."
        )
    if not because:
        because = (
            "Evidence is partial, so this fallback keeps the recommendation deterministic without fabricated precision."
        )
    if not success_check:
        success_check = (
            "Run 2 controlled laps with one change only and confirm rider feel improves before escalating."
        )

    return {
        "did": did,
        "should": should,
        "because": because,
        "success_check": success_check,
    }


def _sector_times_for_lap(run_data: Optional[RunData], lap: Dict[str, Any]) -> list[str]:
    if run_data is None:
        return ["--", "--", "--"]
    start_time = lap.get("start_time_s")
    end_time = lap.get("end_time_s")
    if start_time is None or end_time is None:
        return ["--", "--", "--"]
    lap_data = _slice_lap(run_data, start_time, end_time)
    if not lap_data.distance_m or not lap_data.time_s:
        return ["--", "--", "--"]
    distances, times = _lap_series(lap_data.distance_m, lap_data.time_s)
    if not distances or not times:
        return ["--", "--", "--"]
    lap_length = distances[-1]
    if lap_length <= 0:
        return ["--", "--", "--"]
    sector_marks = [lap_length / 3.0, 2.0 * lap_length / 3.0, lap_length]
    sector_times: list[str] = []
    prev_time = 0.0
    for mark in sector_marks:
        current = _interp_time(distances, times, mark)
        if current is None:
            return ["--", "--", "--"]
        sector_times.append(_format_duration(max(0.0, current - prev_time)) or "--")
        prev_time = current
    return sector_times


@app.post("/import", response_model=ImportResponse)
def import_session(payload: ImportRequest) -> ImportResponse:
    if not payload.file_path:
        if not DB_PATH.exists():
            raise HTTPException(status_code=404, detail="No database found for auto-import.")
        conn = db.connect(str(DB_PATH))
        db.init_schema(conn)
        row = conn.execute(
            """
            SELECT sessions.session_id,
                   tracks.name AS track_name,
                   tracks.direction AS direction,
                   sessions.track_direction AS track_direction
            FROM sessions
            JOIN tracks ON tracks.track_id = sessions.track_id
            ORDER BY sessions.session_id DESC
            LIMIT 1
            """
        ).fetchone()
        run_id = _load_run_id(conn, int(row["session_id"])) if row else None
        run_meta = _load_run_meta(conn, run_id)
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="No sessions available in the database.")
        track_name = row["track_name"]
        direction = row["direction"]
        track_direction = row["track_direction"] or f"{track_name} {direction}".strip()
        session_id = str(row["session_id"])
        return ImportResponse(
            session_id=session_id,
            track_name=track_name,
            direction=direction,
            track_direction=track_direction,
            analytics_version=ANALYTICS_VERSION,
            source="db",
            rider_name=run_meta.get("rider_name"),
            bike_name=run_meta.get("bike_name"),
        )

    path = Path(payload.file_path).expanduser()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"file_path not found: {path}")
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"file_path is not a file: {path}")
    try:
        with path.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"file_path is not readable: {path} ({exc})",
        ) from exc

    try:
        parse = parse_csv(str(path))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {exc}") from exc

    try:
        save_result = save_to_db(parse, db_path=str(DB_PATH), source_file=str(path))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to save CSV to DB: {exc}") from exc

    conn = db.connect(str(DB_PATH))
    row = conn.execute(
        """
        SELECT tracks.name AS track_name,
               tracks.direction AS direction,
               sessions.track_direction AS track_direction
        FROM sessions
        JOIN tracks ON tracks.track_id = sessions.track_id
        WHERE sessions.session_id = ?
        """,
        (save_result.session_id,),
    ).fetchone()
    run_meta = _load_run_meta(conn, save_result.run_id)
    conn.close()

    if not row:
        raise HTTPException(
            status_code=500,
            detail=f"Session metadata not found for session_id {save_result.session_id}",
        )

    track_name = row["track_name"]
    direction = row["direction"]
    track_direction = row["track_direction"] or f"{track_name} {direction}".strip()
    session_id = str(save_result.session_id)

    return ImportResponse(
        session_id=session_id,
        track_name=track_name,
        direction=direction,
        track_direction=track_direction,
        analytics_version=ANALYTICS_VERSION,
        source=str(path),
        rider_name=run_meta.get("rider_name"),
        bike_name=run_meta.get("bike_name"),
    )


@app.get("/summary/{session_id}")
def get_summary(session_id: str) -> Dict[str, Any]:
    session_int = _parse_session_id(session_id)
    if session_int is None or not DB_PATH.exists():
        return _build_error(session_id)

    conn = db.connect(str(DB_PATH))
    db.init_schema(conn)
    meta = _load_session_meta(conn, session_int)
    run_id = _load_run_id(conn, session_int)
    if not meta or run_id is None:
        conn.close()
        return _build_error(session_id)
    laps = _load_laps(conn, run_id)
    run_data = _load_run_data(conn, run_id, meta["raw_metadata"])
    track_key = meta["track_id"] if meta.get("track_id") is not None else meta.get("track_name") or "UNKNOWN_TRACK"
    laps = _filter_valid_lap_rows(run_data, laps, direction=meta["direction"], track_key=track_key)
    run_meta = _load_run_meta(conn, run_id)
    conn.close()

    if not laps:
        meta.update(run_meta)
        return _build_not_ready(session_id, meta, "summary requires lap data")

    lap_list, durations = _summarize_laps(laps)
    if not durations:
        meta.update(run_meta)
        return _build_not_ready(session_id, meta, "summary requires lap durations")
    cards = _build_summary_cards(durations)
    if not cards:
        meta.update(run_meta)
        return _build_not_ready(session_id, meta, "summary cards not ready")

    for lap, payload in zip(laps, lap_list):
        payload["sector_times"] = _sector_times_for_lap(run_data, lap)
    response = {
        "session_id": session_id,
        "track_name": meta["track_name"],
        "direction": meta["direction"],
        "track_direction": meta["track_direction"],
        "analytics_version": ANALYTICS_VERSION,
        "rider_name": run_meta.get("rider_name"),
        "bike_name": run_meta.get("bike_name"),
        "units": "imperial",
        "cards": cards,
        "laps": lap_list,
    }
    return response


@app.get("/insights/{session_id}")
def get_insights(session_id: str) -> Dict[str, Any]:
    session_int = _parse_session_id(session_id)
    if session_int is None or not DB_PATH.exists():
        return _build_error(session_id)

    conn = db.connect(str(DB_PATH))
    db.init_schema(conn)
    meta = _load_session_meta(conn, session_int)
    run_id = _load_run_id(conn, session_int)
    if not meta or run_id is None:
        conn.close()
        return _build_error(session_id)
    run_meta = _load_run_meta(conn, run_id)
    conn.close()
    try:
        ranked = generate_trackside_insights(str(DB_PATH), session_int)
    except Exception:  # noqa: BLE001
        ranked = []

    if not ranked:
        meta.update(run_meta)
        return _build_not_ready(session_id, meta, "insights pipeline not ready")

    try:
        track_map = generate_trackside_map(str(DB_PATH), session_int)
    except Exception:  # noqa: BLE001
        track_map = None

    items = []
    for insight in ranked:
        evidence = insight.get("evidence") or {}
        if not isinstance(evidence, dict):
            evidence = {}
        did_vs_should = _did_vs_should_payload(insight)
        corner_label = rider_corner_label(
            insight.get("corner_label") or insight.get("corner_id"),
            fallback_internal_id=insight.get("segment_id"),
            apex_m=evidence.get("apex_dist_m"),
        )
        items.append(
            {
                "id": insight.get("rule_id"),
                "rule_id": insight.get("rule_id"),
                "title": convert_rider_text(insight.get("title")),
                "phase": insight.get("phase"),
                "did": convert_rider_text(did_vs_should["did"]),
                "should": convert_rider_text(did_vs_should["should"]),
                "because": convert_rider_text(did_vs_should["because"]),
                "operational_action": convert_rider_text(insight.get("operational_action")),
                "causal_reason": convert_rider_text(insight.get("causal_reason")),
                "risk_tier": insight.get("risk_tier"),
                "risk_reason": convert_rider_text(insight.get("risk_reason")),
                "data_quality_note": convert_rider_text(insight.get("data_quality_note")),
                "uncertainty_note": convert_rider_text(insight.get("uncertainty_note")),
                "success_check": convert_rider_text(did_vs_should["success_check"]),
                "did_vs_should": convert_rider_text(did_vs_should),
                "expected_gain_s": insight.get("expected_gain_s"),
                "experimental_protocol": convert_rider_text(insight.get("experimental_protocol")),
                "is_primary_focus": bool(insight.get("is_primary_focus")),
                "confidence": insight.get("confidence"),
                "confidence_label": insight.get("confidence_label"),
                "gain": _format_delta(insight.get("time_gain_s")) or "",
                "time_gain_s": insight.get("time_gain_s"),
                "detail": convert_rider_text(insight.get("detail")),
                "actions": convert_rider_text(insight.get("actions") or []),
                "options": convert_rider_text(insight.get("options") or []),
                "segment_id": insight.get("segment_id"),
                "corner_id": corner_label,
                "corner_label": corner_label,
                "evidence": convert_evidence(evidence),
                "comparison": convert_rider_text(insight.get("comparison")),
                "quality_gate": insight.get("quality_gate"),
                "gain_trace": insight.get("gain_trace"),
            }
        )

    if isinstance(track_map, dict):
        track_map = convert_map_payload(track_map)

    return {
        "session_id": session_id,
        "track_name": meta["track_name"],
        "direction": meta["direction"],
        "track_direction": meta["track_direction"],
        "analytics_version": ANALYTICS_VERSION,
        "rider_name": run_meta.get("rider_name"),
        "bike_name": run_meta.get("bike_name"),
        "units": "imperial",
        "unit_contract": imperial_unit_contract(),
        "track_map": track_map,
        "items": items,
    }


@app.get("/compare/{session_id}")
def get_compare(
    session_id: str,
    reference_lap: Optional[int] = Query(default=None),
    target_lap: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    session_int = _parse_session_id(session_id)
    if session_int is None or not DB_PATH.exists():
        return _build_error(session_id)

    conn = db.connect(str(DB_PATH))
    db.init_schema(conn)
    meta = _load_session_meta(conn, session_int)
    run_id = _load_run_id(conn, session_int)
    if not meta or run_id is None:
        conn.close()
        return _build_error(session_id)
    laps = _load_laps(conn, run_id)
    run_data = _load_run_data(conn, run_id, meta["raw_metadata"])
    track_key = meta["track_id"] if meta.get("track_id") is not None else meta.get("track_name") or "UNKNOWN_TRACK"
    laps = _filter_valid_lap_rows(run_data, laps, direction=meta["direction"], track_key=track_key)
    run_meta = _load_run_meta(conn, run_id)
    conn.close()
    if not laps:
        meta.update(run_meta)
        return _build_not_ready(session_id, meta, "comparison requires laps")
    if run_data is None:
        meta.update(run_meta)
        return _build_not_ready(session_id, meta, "comparison requires run data")

    reference, target = _pick_reference_and_target(
        run_data,
        laps,
        meta["direction"],
        track_key=meta["track_id"],
    )
    if reference is None or target is None:
        return _build_not_ready(session_id, meta, "insufficient laps for reference/target selection")

    if reference_lap is not None:
        selected_reference = _find_lap_by_index(laps, reference_lap)
        if selected_reference is None:
            meta.update(run_meta)
            return _build_not_ready(session_id, meta, f"reference_lap {reference_lap} is not available")
        reference = selected_reference
    if target_lap is not None:
        selected_target = _find_lap_by_index(laps, target_lap)
        if selected_target is None:
            meta.update(run_meta)
            return _build_not_ready(session_id, meta, f"target_lap {target_lap} is not available")
        target = selected_target

    delta_by_segment: list[Dict[str, Any]] = []
    try:
        ref_lap_data = _slice_lap(run_data, reference["start_time_s"], reference["end_time_s"])
        ref_segments = detect_segments(ref_lap_data)
    except Exception:  # noqa: BLE001
        ref_segments = None

    if ref_segments and ref_segments.segments:
        ref_distance, ref_time = _lap_series(ref_lap_data.distance_m, ref_lap_data.time_s)
        tgt_lap_data = _slice_lap(run_data, target["start_time_s"], target["end_time_s"])
        tgt_distance, tgt_time = _lap_series(tgt_lap_data.distance_m, tgt_lap_data.time_s)
        for idx, seg in enumerate(ref_segments.segments, start=1):
            ref_seg_time = _segment_time(ref_distance, ref_time, seg.start_m, seg.end_m)
            tgt_seg_time = _segment_time(tgt_distance, tgt_time, seg.start_m, seg.end_m)
            seg_delta = None
            if ref_seg_time is not None and tgt_seg_time is not None:
                seg_delta = tgt_seg_time - ref_seg_time
            delta_by_segment.append(
                {
                    "segment_id": f"T{idx}",
                    "delta_s": seg_delta,
                }
            )

    delta_by_sector: list[str] = []
    if not delta_by_segment:
        ref_duration = reference["duration_s"]
        tgt_duration = target["duration_s"]
        if ref_duration is not None and tgt_duration is not None:
            ref_sector = ref_duration / 3.0
            tgt_sector = tgt_duration / 3.0
            for _ in range(3):
                delta_by_sector.append(_format_delta(tgt_sector - ref_sector) or "--")
        else:
            meta.update(run_meta)
            return _build_not_ready(session_id, meta, "comparison requires segment or sector deltas")

    response = {
        "session_id": session_id,
        "track_name": meta["track_name"],
        "direction": meta["direction"],
        "track_direction": meta["track_direction"],
        "analytics_version": ANALYTICS_VERSION,
        "rider_name": run_meta.get("rider_name"),
        "bike_name": run_meta.get("bike_name"),
        "units": "imperial",
        "unit_contract": imperial_unit_contract(),
        "comparison": {
            "reference_lap": reference["lap_index"],
            "target_lap": target["lap_index"],
            "delta_by_segment": delta_by_segment,
            "delta_by_sector": delta_by_sector if not delta_by_segment else [],
        },
    }
    return convert_compare_payload(response)


@app.get("/map/{session_id}")
def get_map(
    session_id: str,
    lap_a: Optional[int] = Query(default=None),
    lap_b: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    session_int = _parse_session_id(session_id)
    if session_int is None or not DB_PATH.exists():
        return _build_error(session_id)

    conn = db.connect(str(DB_PATH))
    db.init_schema(conn)
    meta = _load_session_meta(conn, session_int)
    run_id = _load_run_id(conn, session_int)
    if not meta or run_id is None:
        conn.close()
        return _build_error(session_id)
    laps = _load_laps(conn, run_id)
    run_data = _load_run_data(conn, run_id, meta["raw_metadata"])
    track_key = meta["track_id"] if meta.get("track_id") is not None else meta.get("track_name") or "UNKNOWN_TRACK"
    laps = _filter_valid_lap_rows(run_data, laps, direction=meta["direction"], track_key=track_key)
    conn.close()

    if not laps:
        return _build_not_ready(session_id, meta, "map requires valid laps")

    reference, target = _pick_reference_and_target(run_data, laps, meta["direction"], track_key=track_key)
    if reference is None or target is None:
        return _build_not_ready(session_id, meta, "map requires reference and target laps")

    lap_a_index = lap_a if lap_a is not None else reference["lap_index"]
    lap_b_index = lap_b if lap_b is not None else target["lap_index"]

    payload = generate_compare_map(str(DB_PATH), session_int, lap_a_index, lap_b_index)
    if not payload:
        return _build_not_ready(session_id, meta, "map data not ready")
    payload["session_id"] = session_id
    return convert_map_payload(payload)


@app.get("/export/{session_id}")
def export_session(
    session_id: str,
    format: str = Query(default="json", description="Export format: 'json' or 'csv'"),
) -> Response:
    """Export session data as a downloadable bundle.

    - ``format=json`` (default): returns a JSON object with summary and insights.
    - ``format=csv``: returns lap times as a CSV file.

    Error responses follow the standard ``unknown_session`` / ``not_ready`` envelope
    but are returned with HTTP 200 so the frontend can inspect them without special
    error-handling for the download path.  Callers that need strict status codes
    should inspect the ``error`` key in the JSON body.
    """
    if format not in ("json", "csv"):
        raise HTTPException(status_code=400, detail=f"Unsupported format '{format}'. Use 'json' or 'csv'.")

    session_int = _parse_session_id(session_id)
    if session_int is None or not DB_PATH.exists():
        body = json.dumps(_build_error(session_id))
        return Response(content=body, media_type="application/json")

    conn = db.connect(str(DB_PATH))
    db.init_schema(conn)
    meta = _load_session_meta(conn, session_int)
    run_id = _load_run_id(conn, session_int)
    if not meta or run_id is None:
        conn.close()
        body = json.dumps(_build_error(session_id))
        return Response(content=body, media_type="application/json")

    laps = _load_laps(conn, run_id)
    run_data = _load_run_data(conn, run_id, meta["raw_metadata"])
    track_key = meta["track_id"] if meta.get("track_id") is not None else meta.get("track_name") or "UNKNOWN_TRACK"
    laps = _filter_valid_lap_rows(run_data, laps, direction=meta["direction"], track_key=track_key)
    run_meta = _load_run_meta(conn, run_id)
    conn.close()

    if not laps:
        meta.update(run_meta)
        body = json.dumps(_build_not_ready(session_id, meta, "export requires lap data"))
        return Response(content=body, media_type="application/json")

    lap_list, durations = _summarize_laps(laps)
    for lap, payload in zip(laps, lap_list):
        payload["sector_times"] = _sector_times_for_lap(run_data, lap)

    if format == "csv":
        import io
        import csv as _csv

        buf = io.StringIO()
        writer = _csv.writer(buf)
        writer.writerow(["lap", "time", "sector_1", "sector_2", "sector_3", "is_best"])
        for lap_row in lap_list:
            sectors = lap_row.get("sector_times") or ["--", "--", "--"]
            writer.writerow([
                lap_row["lap"],
                lap_row["time"],
                sectors[0] if len(sectors) > 0 else "--",
                sectors[1] if len(sectors) > 1 else "--",
                sectors[2] if len(sectors) > 2 else "--",
                lap_row.get("is_best", False),
            ])
        fname = f"session_{session_id}_laps.csv"
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    # JSON bundle
    cards = _build_summary_cards(durations)
    try:
        ranked = generate_trackside_insights(str(DB_PATH), session_int)
    except Exception:  # noqa: BLE001
        ranked = []

    insights_items = []
    for insight in ranked:
        evidence = insight.get("evidence") or {}
        if not isinstance(evidence, dict):
            evidence = {}
        did_vs_should = _did_vs_should_payload(insight)
        corner_label = rider_corner_label(
            insight.get("corner_label") or insight.get("corner_id"),
            fallback_internal_id=insight.get("segment_id"),
            apex_m=evidence.get("apex_dist_m"),
        )
        insights_items.append({
            "rule_id": insight.get("rule_id"),
            "title": convert_rider_text(insight.get("title")),
            "phase": insight.get("phase"),
            "did": convert_rider_text(did_vs_should["did"]),
            "should": convert_rider_text(did_vs_should["should"]),
            "because": convert_rider_text(did_vs_should["because"]),
            "success_check": convert_rider_text(did_vs_should["success_check"]),
            "corner_label": corner_label,
            "confidence": insight.get("confidence"),
            "time_gain_s": insight.get("time_gain_s"),
            "evidence": convert_evidence(evidence),
        })

    bundle = {
        "session_id": session_id,
        "track_name": meta["track_name"],
        "direction": meta["direction"],
        "track_direction": meta["track_direction"],
        "analytics_version": ANALYTICS_VERSION,
        "rider_name": run_meta.get("rider_name"),
        "bike_name": run_meta.get("bike_name"),
        "units": "imperial",
        "summary": {
            "cards": cards,
            "laps": lap_list,
        },
        "insights": insights_items,
    }
    fname = f"session_{session_id}_export.json"
    return Response(
        content=json.dumps(bundle, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
