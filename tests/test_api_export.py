"""Unit tests for GET /export/{session_id}."""
import csv
import io
import json
from pathlib import Path
from typing import Any

from api import app as api_app


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def _import_session(tmp_path: Path, monkeypatch) -> tuple[str, Path]:
    """Import a minimal CSV session and return (session_id, db_path)."""
    db_path = tmp_path / "aimsolo-test.db"
    csv_path = tmp_path / "session.csv"
    _write_csv(
        csv_path,
        [
            ["Track", "Willow Springs"],
            ["Track Direction", "CW"],
            ["Racer", "Test Rider"],
            ["Vehicle", "CBR600RR"],
            [],
            ["Time", "Distance on GPS Speed", "GPS Speed", "Latitude", "Longitude"],
            ["s", "km", "km/h", "deg", "deg"],
            ["0.0", "0.000", "80.0", "34.539", "-118.331"],
            ["1.0", "0.022", "82.0", "34.540", "-118.332"],
        ],
    )
    monkeypatch.setattr(api_app, "DB_PATH", db_path)
    result = api_app.import_session(api_app.ImportRequest(file_path=str(csv_path)))
    return result.session_id, db_path


_FAKE_LAPS: list[dict[str, Any]] = [
    {"lap_id": 1, "lap_index": 1, "start_time_s": 0.0, "end_time_s": 90.0, "duration_s": 90.0},
    {"lap_id": 2, "lap_index": 2, "start_time_s": 90.0, "end_time_s": 182.0, "duration_s": 92.0},
]


def _patch_laps(monkeypatch) -> None:
    """Replace _load_laps and _filter_valid_lap_rows with deterministic fakes."""
    monkeypatch.setattr(api_app, "_load_laps", lambda conn, run_id: _FAKE_LAPS)
    monkeypatch.setattr(api_app, "_filter_valid_lap_rows", lambda run_data, laps, **kw: laps)


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def test_export_json_returns_bundle(monkeypatch, tmp_path):
    session_id, _db_path = _import_session(tmp_path, monkeypatch)
    _patch_laps(monkeypatch)

    response = api_app.export_session(session_id, format="json")

    assert response.media_type == "application/json"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert f"session_{session_id}_export.json" in response.headers["content-disposition"]

    bundle = json.loads(response.body)
    assert bundle["session_id"] == session_id
    assert bundle["track_name"] == "Willow Springs"
    assert bundle["units"] == "imperial"
    assert "summary" in bundle
    assert "laps" in bundle["summary"]
    assert len(bundle["summary"]["laps"]) == 2
    assert "cards" in bundle["summary"]
    assert "insights" in bundle


def test_export_json_laps_have_expected_shape(monkeypatch, tmp_path):
    session_id, _db_path = _import_session(tmp_path, monkeypatch)
    _patch_laps(monkeypatch)

    response = api_app.export_session(session_id, format="json")
    bundle = json.loads(response.body)

    lap = bundle["summary"]["laps"][0]
    assert "lap" in lap
    assert "time" in lap
    assert "is_best" in lap


def test_export_json_unknown_session_returns_error_envelope(monkeypatch, tmp_path):
    db_path = tmp_path / "empty.db"
    monkeypatch.setattr(api_app, "DB_PATH", db_path)

    response = api_app.export_session("9999", format="json")

    body = json.loads(response.body)
    assert body["error"] == "unknown_session"
    assert body["session_id"] == "9999"


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def test_export_csv_returns_lap_rows(monkeypatch, tmp_path):
    session_id, _db_path = _import_session(tmp_path, monkeypatch)
    _patch_laps(monkeypatch)

    response = api_app.export_session(session_id, format="csv")

    assert response.media_type == "text/csv"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert f"session_{session_id}_laps.csv" in response.headers["content-disposition"]

    content = response.body.decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["lap"] == "1"
    assert rows[0]["sector_1"] != ""
    assert "is_best" in rows[0]


def test_export_csv_best_lap_flagged(monkeypatch, tmp_path):
    session_id, _db_path = _import_session(tmp_path, monkeypatch)
    _patch_laps(monkeypatch)

    response = api_app.export_session(session_id, format="csv")
    content = response.body.decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    best_rows = [r for r in rows if r["is_best"].lower() == "true"]
    assert len(best_rows) == 1
    assert best_rows[0]["lap"] == "1"  # lap 1 is faster (90 s vs 92 s)


def test_export_csv_unknown_session_returns_json_error(monkeypatch, tmp_path):
    db_path = tmp_path / "empty.db"
    monkeypatch.setattr(api_app, "DB_PATH", db_path)

    response = api_app.export_session("9999", format="csv")

    # Falls back to JSON error envelope even for CSV format requests on bad sessions
    body = json.loads(response.body)
    assert body["error"] == "unknown_session"


# ---------------------------------------------------------------------------
# Bad format
# ---------------------------------------------------------------------------

def test_export_invalid_format_raises_400(monkeypatch, tmp_path):
    db_path = tmp_path / "empty.db"
    monkeypatch.setattr(api_app, "DB_PATH", db_path)

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        api_app.export_session("1", format="xml")
    assert exc_info.value.status_code == 400
