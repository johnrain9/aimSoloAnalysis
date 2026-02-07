import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from ingest.csv.parser import parse_csv
from ingest.csv.save import save_to_db
from storage import db
import ingest.csv.save as save_module


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def _base_rows() -> list[list[str]]:
    return [
        ["Track", "Metrics Test"],
        ["Track Direction", "CW"],
        ["Racer", "Test Rider"],
        [],
        ["Time", "Distance on GPS Speed", "GPS Speed", "Latitude", "Longitude", "Beacon Markers"],
        ["s", "m", "km/h", "deg", "deg", ""],
        ["0", "0", "80", "37.0000", "-122.0000", "1"],
        ["1", "20", "85", "37.0001", "-122.0000", "1"],
        ["2", "40", "90", "37.0002", "-122.0000", "2"],
        ["3", "60", "92", "37.0002", "-121.9999", "2"],
        ["4", "80", "94", "37.0001", "-121.9998", "3"],
    ]


def test_save_to_db_persists_derived_metrics(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "aimsolo.db"
    csv_path = tmp_path / "session.csv"
    _write_csv(csv_path, _base_rows())

    monkeypatch.setattr(
        save_module,
        "detect_segments",
        lambda _lap_data: SimpleNamespace(segments=[object()]),
    )
    monkeypatch.setattr(
        save_module,
        "compute_segment_metrics",
        lambda _run_data, _lap_window, _segments: {
            "T1": {
                "segment_time_s": 12.3,
                "entry_speed_kmh": 101.0,
                "apex_speed_kmh": 88.0,
            }
        },
    )

    parse = parse_csv(str(csv_path))
    save_to_db(parse, db_path=str(db_path), source_file=str(csv_path))

    conn = db.connect(str(db_path))
    rows = conn.execute(
        """
        SELECT metric_name, metric_value
        FROM derived_metrics
        ORDER BY metric_name
        """
    ).fetchall()
    conn.close()

    names = [row["metric_name"] for row in rows]
    assert "lap_duration_s" in names
    assert "segment:T1:segment_time_s" in names
    assert "segment:T1:entry_speed_kmh" in names


def test_save_to_db_reimport_upserts_derived_metrics(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "aimsolo.db"
    csv_path = tmp_path / "session.csv"
    _write_csv(csv_path, _base_rows())
    parse = parse_csv(str(csv_path))

    monkeypatch.setattr(
        save_module,
        "detect_segments",
        lambda _lap_data: SimpleNamespace(segments=[object()]),
    )
    monkeypatch.setattr(
        save_module,
        "compute_segment_metrics",
        lambda _run_data, _lap_window, _segments: {"T1": {"segment_time_s": 12.0}},
    )
    save_to_db(parse, db_path=str(db_path), source_file=str(csv_path))

    conn = db.connect(str(db_path))
    first_count = conn.execute("SELECT COUNT(*) AS count FROM derived_metrics").fetchone()["count"]
    first_val = conn.execute(
        """
        SELECT metric_value
        FROM derived_metrics
        WHERE metric_name = 'segment:T1:segment_time_s'
        ORDER BY derived_metric_id ASC
        LIMIT 1
        """
    ).fetchone()["metric_value"]
    conn.close()

    monkeypatch.setattr(
        save_module,
        "compute_segment_metrics",
        lambda _run_data, _lap_window, _segments: {"T1": {"segment_time_s": 15.5}},
    )
    save_to_db(parse, db_path=str(db_path), source_file=str(csv_path))

    conn = db.connect(str(db_path))
    second_count = conn.execute("SELECT COUNT(*) AS count FROM derived_metrics").fetchone()["count"]
    second_val = conn.execute(
        """
        SELECT metric_value
        FROM derived_metrics
        WHERE metric_name = 'segment:T1:segment_time_s'
        ORDER BY derived_metric_id ASC
        LIMIT 1
        """
    ).fetchone()["metric_value"]
    conn.close()

    assert first_count == second_count
    assert first_val == pytest.approx(12.0)
    assert second_val == pytest.approx(15.5)


def test_save_to_db_derived_metrics_prereq_failure_rolls_back(tmp_path: Path) -> None:
    db_path = tmp_path / "aimsolo.db"
    csv_path = tmp_path / "session.csv"
    _write_csv(
        csv_path,
        [
            ["Track", "No Distance"],
            ["Track Direction", "CW"],
            [],
            ["Time", "GPS Speed", "Beacon Markers"],
            ["s", "km/h", ""],
            ["0", "80", "1"],
            ["1", "82", "1"],
            ["2", "84", "2"],
            ["3", "86", "2"],
            ["4", "88", "3"],
        ],
    )

    parse = parse_csv(str(csv_path))
    with pytest.raises(RuntimeError, match="derived metrics persistence prerequisites missing"):
        save_to_db(parse, db_path=str(db_path), source_file=str(csv_path))

    conn = db.connect(str(db_path))
    db.init_schema(conn)
    session_count = conn.execute("SELECT COUNT(*) AS count FROM sessions").fetchone()["count"]
    run_count = conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]
    metric_count = conn.execute("SELECT COUNT(*) AS count FROM derived_metrics").fetchone()["count"]
    conn.close()

    assert session_count == 0
    assert run_count == 0
    assert metric_count == 0
