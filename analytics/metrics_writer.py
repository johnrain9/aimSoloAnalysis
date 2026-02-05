"""Write analytics metrics to the derived_metrics table."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

MetricPayload = Mapping[str, Any] | Sequence[Any] | str | int | float | bool


@dataclass(frozen=True)
class LapMetric:
    lap_id: int
    metric_name: str
    metric_value: Optional[float] = None
    metric_json: Optional[MetricPayload] = None


@dataclass(frozen=True)
class SegmentMetric:
    lap_id: int
    segment_key: str | int
    metric_name: str
    metric_value: Optional[float] = None
    metric_json: Optional[MetricPayload] = None


def lap_metrics_from_mapping(
    lap_metrics: Mapping[int, Mapping[str, MetricPayload | None]],
) -> list[LapMetric]:
    """Expand a lap->metric map into LapMetric rows."""
    rows: list[LapMetric] = []
    for lap_id, metrics in lap_metrics.items():
        for metric_name, payload in metrics.items():
            metric_value, metric_json = _split_payload(payload)
            rows.append(
                LapMetric(
                    lap_id=lap_id,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    metric_json=metric_json,
                )
            )
    return rows


def segment_metrics_from_mapping(
    segment_metrics: Mapping[int, Mapping[str | int, Mapping[str, MetricPayload | None]]],
) -> list[SegmentMetric]:
    """Expand a lap->segment->metric map into SegmentMetric rows."""
    rows: list[SegmentMetric] = []
    for lap_id, segments in segment_metrics.items():
        for segment_key, metrics in segments.items():
            for metric_name, payload in metrics.items():
                metric_value, metric_json = _split_payload(payload)
                rows.append(
                    SegmentMetric(
                        lap_id=lap_id,
                        segment_key=segment_key,
                        metric_name=metric_name,
                        metric_value=metric_value,
                        metric_json=metric_json,
                    )
                )
    return rows


def write_lap_metrics(
    conn: sqlite3.Connection,
    session_id: int,
    run_id: Optional[int],
    analytics_version: str,
    metrics: Iterable[LapMetric],
    *,
    commit: bool = True,
) -> int:
    """Persist lap metrics into derived_metrics.

    Returns the number of metrics written.
    """
    rows = [
        _build_row(
            session_id=session_id,
            run_id=run_id,
            lap_id=metric.lap_id,
            analytics_version=analytics_version,
            metric_name=metric.metric_name,
            metric_value=metric.metric_value,
            metric_json=metric.metric_json,
        )
        for metric in metrics
    ]
    return _write_rows(conn, rows, commit=commit)


def write_segment_metrics(
    conn: sqlite3.Connection,
    session_id: int,
    run_id: Optional[int],
    analytics_version: str,
    metrics: Iterable[SegmentMetric],
    *,
    commit: bool = True,
) -> int:
    """Persist segment metrics into derived_metrics using encoded metric names.

    Segment metrics are stored as metric_name values like:
    "segment:{segment_key}:{metric_name}".
    """
    rows = [
        _build_row(
            session_id=session_id,
            run_id=run_id,
            lap_id=metric.lap_id,
            analytics_version=analytics_version,
            metric_name=segment_metric_name(metric.segment_key, metric.metric_name),
            metric_value=metric.metric_value,
            metric_json=metric.metric_json,
        )
        for metric in metrics
    ]
    return _write_rows(conn, rows, commit=commit)


def segment_metric_name(segment_key: str | int, metric_name: str) -> str:
    """Encode a segment metric name for storage."""
    return f"segment:{segment_key}:{metric_name}"


def _split_payload(payload: MetricPayload | None) -> tuple[Optional[float], Optional[MetricPayload]]:
    if payload is None:
        return None, None
    if isinstance(payload, bool):
        return None, payload
    if isinstance(payload, (int, float)):
        return float(payload), None
    return None, payload


def _build_row(
    *,
    session_id: int,
    run_id: Optional[int],
    lap_id: Optional[int],
    analytics_version: str,
    metric_name: str,
    metric_value: Optional[float],
    metric_json: Optional[MetricPayload],
) -> tuple[int, Optional[int], Optional[int], str, str, Optional[float], Optional[str]]:
    if session_id is None:
        raise ValueError("session_id is required")
    if lap_id is None:
        raise ValueError("lap_id is required")
    version = _require_version(analytics_version)
    metric_name = (metric_name or "").strip()
    if not metric_name:
        raise ValueError("metric_name is required")
    metric_value = _validate_metric_value(metric_value)
    metric_json_text = _serialize_metric_json(metric_json)
    return (
        session_id,
        run_id,
        lap_id,
        version,
        metric_name,
        metric_value,
        metric_json_text,
    )


def _require_version(analytics_version: str) -> str:
    if analytics_version is None:
        raise ValueError("analytics_version is required")
    version = str(analytics_version).strip()
    if not version:
        raise ValueError("analytics_version is required")
    return version


def _validate_metric_value(metric_value: Optional[float]) -> Optional[float]:
    if metric_value is None:
        return None
    if isinstance(metric_value, bool):
        raise ValueError("metric_value must be numeric, not bool")
    return float(metric_value)


def _serialize_metric_json(metric_json: Optional[MetricPayload]) -> Optional[str]:
    if metric_json is None:
        return None
    if isinstance(metric_json, str):
        stripped = metric_json.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(metric_json)
                return metric_json
            except json.JSONDecodeError:
                pass
    try:
        return json.dumps(metric_json, separators=(",", ":"), sort_keys=True)
    except TypeError as exc:
        raise ValueError("metric_json is not JSON serializable") from exc


def _write_rows(
    conn: sqlite3.Connection,
    rows: Sequence[tuple[int, Optional[int], Optional[int], str, str, Optional[float], Optional[str]]],
    *,
    commit: bool,
) -> int:
    if not rows:
        return 0

    sql = (
        "INSERT INTO derived_metrics "
        "(session_id, run_id, lap_id, analytics_version, metric_name, metric_value, metric_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(session_id, run_id, lap_id, metric_name, analytics_version) "
        "DO UPDATE SET metric_value = excluded.metric_value, metric_json = excluded.metric_json"
    )
    conn.executemany(sql, rows)
    if commit:
        conn.commit()
    return len(rows)
