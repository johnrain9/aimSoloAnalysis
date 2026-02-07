from pathlib import Path
from types import SimpleNamespace

from api import app as api_app
from domain.run_data import RunData


class _FakeConn:
    def close(self) -> None:
        return None


def _mock_compare_dependencies(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(api_app, "DB_PATH", Path(db_path))
    monkeypatch.setattr(api_app.db, "connect", lambda _: _FakeConn())
    monkeypatch.setattr(api_app.db, "init_schema", lambda _: None)
    monkeypatch.setattr(
        api_app,
        "_load_session_meta",
        lambda _conn, _session_id: {
            "track_id": 11,
            "track_name": "Test Track",
            "direction": "CW",
            "track_direction": "Test Track CW",
            "raw_metadata": {},
        },
    )
    monkeypatch.setattr(api_app, "_load_run_id", lambda _conn, _session_id: 20)
    monkeypatch.setattr(
        api_app,
        "_load_laps",
        lambda _conn, _run_id: [
            {"lap_id": 101, "lap_index": 1, "start_time_s": 0.0, "end_time_s": 60.0, "duration_s": 60.0},
            {"lap_id": 102, "lap_index": 2, "start_time_s": 60.0, "end_time_s": 121.0, "duration_s": 61.0},
            {"lap_id": 103, "lap_index": 3, "start_time_s": 121.0, "end_time_s": 183.0, "duration_s": 62.0},
        ],
    )
    monkeypatch.setattr(
        api_app,
        "_load_run_data",
        lambda _conn, _run_id, _metadata: RunData(
            time_s=[0.0, 60.0, 121.0, 183.0],
            distance_m=[0.0, 1000.0, 2000.0, 3000.0],
            lat=[None, None, None, None],
            lon=[None, None, None, None],
            speed=[20.0, 20.0, 20.0, 20.0],
            channels={},
            metadata={},
        ),
    )
    monkeypatch.setattr(api_app, "_filter_valid_lap_rows", lambda _rd, laps, **_kwargs: laps)
    monkeypatch.setattr(api_app, "_load_run_meta", lambda _conn, _run_id: {"rider_name": "Rider", "bike_name": "Bike"})
    monkeypatch.setattr(
        api_app,
        "_pick_reference_and_target",
        lambda _rd, laps, _direction, track_key: (laps[0], laps[2]),
    )
    monkeypatch.setattr(api_app, "detect_segments", lambda _lap_data: SimpleNamespace(segments=[]))
    monkeypatch.setattr(api_app, "convert_compare_payload", lambda payload: payload)


def test_compare_honors_explicit_lap_selection(monkeypatch, tmp_path):
    _mock_compare_dependencies(monkeypatch, tmp_path)

    response = api_app.get_compare("123", reference_lap=2, target_lap=1)

    assert response["comparison"]["reference_lap"] == 2
    assert response["comparison"]["target_lap"] == 1


def test_compare_defaults_unchanged_when_laps_not_provided(monkeypatch, tmp_path):
    _mock_compare_dependencies(monkeypatch, tmp_path)

    response = api_app.get_compare("123", reference_lap=None, target_lap=None)

    assert response["comparison"]["reference_lap"] == 1
    assert response["comparison"]["target_lap"] == 3


def test_compare_invalid_explicit_lap_returns_not_ready(monkeypatch, tmp_path):
    _mock_compare_dependencies(monkeypatch, tmp_path)

    response = api_app.get_compare("123", reference_lap=99, target_lap=None)

    assert response["error"] == "not_ready"
    assert response["detail"] == "reference_lap 99 is not available"
    assert response["session_id"] == "123"
