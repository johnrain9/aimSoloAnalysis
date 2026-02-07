import csv
from pathlib import Path

from api import app as api_app


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def test_import_file_path_returns_metadata_and_uses_open_connection(monkeypatch, tmp_path):
    db_path = tmp_path / "aimsolo-test.db"
    csv_path = tmp_path / "session.csv"
    _write_csv(
        csv_path,
        [
            ["Track", "Thunderhill"],
            ["Track Direction", "CW"],
            ["Racer", "Jane Doe"],
            ["Vehicle", "S1000RR"],
            [],
            ["Time", "Distance on GPS Speed", "GPS Speed", "Latitude", "Longitude"],
            ["s", "km", "km/h", "deg", "deg"],
            ["0.0", "0.0", "80.0", "39.539", "-122.331"],
            ["1.0", "0.02", "85.0", "39.540", "-122.332"],
        ],
    )

    monkeypatch.setattr(api_app, "DB_PATH", db_path)

    original_load_run_meta = api_app._load_run_meta
    state = {"checked": False}

    def _load_run_meta_guard(conn, run_id):
        conn.execute("SELECT 1").fetchone()
        state["checked"] = True
        return original_load_run_meta(conn, run_id)

    monkeypatch.setattr(api_app, "_load_run_meta", _load_run_meta_guard)

    payload = api_app.import_session(api_app.ImportRequest(file_path=str(csv_path))).model_dump()
    assert payload["track_name"] == "Thunderhill"
    assert payload["direction"] == "CW"
    assert payload["track_direction"] == "CW"
    assert payload["source"] == str(csv_path)
    assert payload["rider_name"] == "Jane Doe"
    assert payload["bike_name"] == "S1000RR"
    assert state["checked"] is True
