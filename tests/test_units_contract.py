from pathlib import Path
from types import SimpleNamespace

import pytest

from api import app as api_app
from api.units import KMH_TO_MPH, MPS_TO_MPH, M_TO_FT, convert_compare_payload
from domain.run_data import RunData


class _FakeConn:
    def close(self) -> None:
        return None


def _mock_db(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(api_app, "DB_PATH", Path(db_path))
    monkeypatch.setattr(api_app.db, "connect", lambda _: _FakeConn())
    monkeypatch.setattr(api_app.db, "init_schema", lambda _: None)


def _mock_common_session(monkeypatch) -> None:
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
    monkeypatch.setattr(api_app, "_load_run_meta", lambda _conn, _run_id: {"rider_name": "Rider", "bike_name": "Bike"})


def _mock_compare_laps(monkeypatch) -> None:
    laps = [
        {"lap_id": 101, "lap_index": 1, "start_time_s": 0.0, "end_time_s": 60.0, "duration_s": 60.0},
        {"lap_id": 102, "lap_index": 2, "start_time_s": 60.0, "end_time_s": 121.0, "duration_s": 61.0},
    ]
    monkeypatch.setattr(api_app, "_load_laps", lambda _conn, _run_id: laps)
    monkeypatch.setattr(
        api_app,
        "_load_run_data",
        lambda _conn, _run_id, _metadata: RunData(
            time_s=[0.0, 60.0, 121.0],
            distance_m=[0.0, 1000.0, 2000.0],
            lat=[36.0, 36.1, 36.2],
            lon=[-121.0, -121.1, -121.2],
            speed=[20.0, 20.0, 20.0],
            channels={},
            metadata={},
        ),
    )
    monkeypatch.setattr(api_app, "_filter_valid_lap_rows", lambda _rd, raw_laps, **_kwargs: raw_laps)
    monkeypatch.setattr(api_app, "_pick_reference_and_target", lambda _rd, raw_laps, _direction, track_key: (raw_laps[0], raw_laps[1]))


def test_unit_convert_evidence_converts_meter_kmh_mps_fields():
    converted = api_app.convert_evidence(
        {
            "apex_dist_m": 10.0,
            "entry_speed_delta_kmh": 72.0,
            "gps_speed_accuracy_mps": 2.5,
            "segment_time_delta_s": 0.2,
        }
    )

    assert converted["apex_dist_m"] == pytest.approx(10.0 * M_TO_FT)
    assert converted["entry_speed_delta_kmh"] == pytest.approx(72.0 * KMH_TO_MPH)
    assert converted["gps_speed_accuracy_mps"] == pytest.approx(2.5 * MPS_TO_MPH)
    assert converted["segment_time_delta_s"] == pytest.approx(0.2)


def test_unit_insights_payload_is_imperial_and_explicit(monkeypatch, tmp_path):
    _mock_db(monkeypatch, tmp_path)
    _mock_common_session(monkeypatch)
    monkeypatch.setattr(
        api_app,
        "generate_trackside_insights",
        lambda _db_path, _session_id: [
            {
                "rule_id": "entry_speed",
                "title": "Entry",
                "confidence": 0.7,
                "confidence_label": "medium",
                "time_gain_s": 0.12,
                "detail": "detail",
                "actions": ["a1"],
                "options": [],
                "segment_id": "T1",
                "corner_id": "T1",
                "comparison": "Lap 2 vs Lap 1",
                "evidence": {
                    "brake_point_delta_m": 10.0,
                    "entry_speed_delta_kmh": 90.0,
                    "gps_speed_accuracy_mps": 2.0,
                    "apex_dist_m": 5.0,
                },
            }
        ],
    )
    monkeypatch.setattr(
        api_app,
        "generate_trackside_map",
        lambda _db_path, _session_id: {
            "reference_lap": 1,
            "target_lap": 2,
            "track_direction": "Test Track CW",
            "reference_points": [[1.0, 2.0, 3.0]],
            "target_points": [[4.0, 5.0, 6.0]],
            "segments": [{"id": "T1", "label": "T1", "start_m": 7.0, "apex_m": 8.0, "end_m": 9.0}],
            "units": "metric",
        },
    )

    response = api_app.get_insights("123")

    assert response["units"] == "imperial"
    assert response["unit_contract"] == {"system": "imperial", "distance": "ft", "speed": "mph", "time": "s"}
    evidence = response["items"][0]["evidence"]
    assert evidence["brake_point_delta_m"] == pytest.approx(10.0 * M_TO_FT)
    assert evidence["entry_speed_delta_kmh"] == pytest.approx(90.0 * KMH_TO_MPH)
    assert evidence["gps_speed_accuracy_mps"] == pytest.approx(2.0 * MPS_TO_MPH)
    assert evidence["apex_dist_m"] == pytest.approx(5.0 * M_TO_FT)

    track_map = response["track_map"]
    assert track_map["units"] == "imperial"
    assert track_map["unit_contract"] == {"system": "imperial", "distance": "ft", "speed": "mph", "time": "s"}
    assert track_map["reference_points"][0] == pytest.approx([1.0 * M_TO_FT, 2.0 * M_TO_FT, 3.0 * M_TO_FT])
    assert track_map["segments"][0]["start_m"] == pytest.approx(7.0 * M_TO_FT)
    assert track_map["segments"][0]["apex_m"] == pytest.approx(8.0 * M_TO_FT)
    assert track_map["segments"][0]["end_m"] == pytest.approx(9.0 * M_TO_FT)


def test_unit_compare_payload_conversion_and_contract():
    converted = convert_compare_payload(
        {
            "session_id": "123",
            "comparison": {
                "brake_points": [{"corner": "T1", "delta_m": -10.0}],
                "nested": {"entry_speed_delta_kmh": 80.0, "gps_speed_accuracy_mps": 1.0},
            },
        }
    )

    assert converted["units"] == "imperial"
    assert converted["unit_contract"] == {"system": "imperial", "distance": "ft", "speed": "mph", "time": "s"}
    assert converted["comparison"]["brake_points"][0]["delta_m"] == pytest.approx(-10.0 * M_TO_FT)
    assert converted["comparison"]["nested"]["entry_speed_delta_kmh"] == pytest.approx(80.0 * KMH_TO_MPH)
    assert converted["comparison"]["nested"]["gps_speed_accuracy_mps"] == pytest.approx(1.0 * MPS_TO_MPH)


def test_unit_compare_and_map_endpoints_are_imperial_and_explicit(monkeypatch, tmp_path):
    _mock_db(monkeypatch, tmp_path)
    _mock_common_session(monkeypatch)
    _mock_compare_laps(monkeypatch)
    monkeypatch.setattr(api_app, "detect_segments", lambda _lap_data: SimpleNamespace(segments=[]))
    monkeypatch.setattr(
        api_app,
        "generate_compare_map",
        lambda _db_path, _session_id, _lap_a, _lap_b: {
            "lap_a": 1,
            "lap_b": 2,
            "track_direction": "Test Track CW",
            "points_a": [[1.0, 2.0, 3.0]],
            "points_b": [[4.0, 5.0, 6.0]],
        },
    )

    compare_response = api_app.get_compare("123", reference_lap=None, target_lap=None)
    map_response = api_app.get_map("123", lap_a=None, lap_b=None)

    assert compare_response["units"] == "imperial"
    assert compare_response["unit_contract"] == {"system": "imperial", "distance": "ft", "speed": "mph", "time": "s"}
    assert map_response["units"] == "imperial"
    assert map_response["unit_contract"] == {"system": "imperial", "distance": "ft", "speed": "mph", "time": "s"}
    assert map_response["session_id"] == "123"
    assert map_response["points_a"][0] == pytest.approx([1.0 * M_TO_FT, 2.0 * M_TO_FT, 3.0 * M_TO_FT])
    assert map_response["points_b"][0] == pytest.approx([4.0 * M_TO_FT, 5.0 * M_TO_FT, 6.0 * M_TO_FT])
