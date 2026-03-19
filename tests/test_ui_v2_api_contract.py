from pathlib import Path

from api import app as api_app
from domain.run_data import RunData


class _FakeConn:
    def close(self) -> None:
        return None


def _mock_session(monkeypatch, tmp_path):
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
        ],
    )
    monkeypatch.setattr(
        api_app,
        "_load_run_data",
        lambda _conn, _run_id, _metadata: RunData(
            time_s=[0.0, 60.0, 121.0],
            distance_m=[0.0, 1000.0, 2000.0],
            lat=[None, None, None],
            lon=[None, None, None],
            speed=[20.0, 20.0, 20.0],
            channels={},
            metadata={},
        ),
    )
    monkeypatch.setattr(api_app, "_filter_valid_lap_rows", lambda _rd, laps, **_kwargs: laps)
    monkeypatch.setattr(api_app, "_load_run_meta", lambda _conn, _run_id: {"rider_name": "Rider", "bike_name": "Bike"})


def test_summary_contract_has_frozen_required_fields(monkeypatch, tmp_path):
    _mock_session(monkeypatch, tmp_path)
    monkeypatch.setattr(api_app, "_sector_times_for_lap", lambda _rd, _lap: ["0:20.000", "0:20.000", "0:20.000"])

    payload = api_app.get_summary("123")

    assert payload["session_id"] == "123"
    assert payload["track_name"] == "Test Track"
    assert payload["direction"] == "CW"
    assert payload["track_direction"] == "Test Track CW"
    assert payload["units"] == "imperial"
    assert payload["cards"][0]["id"] == "best_lap"
    assert {"lap", "time", "sector_times", "is_best"} <= set(payload["laps"][0].keys())


def test_insights_contract_has_structured_did_vs_should_fields(monkeypatch, tmp_path):
    _mock_session(monkeypatch, tmp_path)
    monkeypatch.setattr(
        api_app,
        "generate_trackside_insights",
        lambda _db_path, _session_id: [
            {
                "rule_id": "line_inconsistency",
                "title": "T3 line consistency",
                "phase": "mid",
                "did": "At T3 (mid phase), line spread is about 3.0 ft wider than reference.",
                "should": "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
                "because": "Because line variance is elevated (6.2 ft), timing and speed consistency drop through mid.",
                "success_check": "Rider check: repeat the same turn-in and apex marker for the next 3 laps.",
                "operational_action": "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
                "causal_reason": "Because line variance is elevated (6.2 ft), timing and speed consistency drop through mid.",
                "risk_tier": "Primary",
                "risk_reason": "Stable context.",
                "data_quality_note": "gps accuracy good (3.3 ft); 10 satellites",
                "uncertainty_note": "High confidence from current telemetry quality.",
                "expected_gain_s": 0.18,
                "confidence": 0.8,
                "confidence_label": "high",
                "time_gain_s": 0.18,
                "detail": "At T3 (mid phase), line spread is about 3.0 ft wider than reference.",
                "segment_id": "T3",
                "corner_id": "T3",
                "corner_label": "T3",
                "evidence": {"line_stddev_delta_m": 0.9},
                "comparison": "Lap 8 vs best Lap 3",
                "quality_gate": {"decision": "pass"},
                "gain_trace": {"final_expected_gain_s": 0.18},
                "is_primary_focus": True,
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
            "reference_points": [[0.0, 0.0, 0.0]],
            "target_points": [[1.0, 1.0, 1.0]],
            "segments": [{"id": "T3", "label": "T3", "start_m": 10.0, "apex_m": 20.0, "end_m": 30.0}],
        },
    )

    payload = api_app.get_insights("123")

    assert payload["session_id"] == "123"
    assert payload["units"] == "imperial"
    assert payload["unit_contract"]["distance"] == "ft"
    item = payload["items"][0]
    assert {"did", "should", "because", "success_check"} <= set(item.keys())
    assert item["corner_label"] == "T3"
    assert payload["track_map"]["segments"][0]["id"] == "T3"


def test_map_contract_has_frozen_required_fields(monkeypatch, tmp_path):
    _mock_session(monkeypatch, tmp_path)
    monkeypatch.setattr(
        api_app,
        "_pick_reference_and_target",
        lambda _rd, laps, _direction, track_key: (laps[0], laps[1]),
    )
    monkeypatch.setattr(
        api_app,
        "generate_compare_map",
        lambda _db_path, _session_id, _lap_a, _lap_b: {
            "lap_a": 1,
            "lap_b": 2,
            "track_direction": "Test Track CW",
            "points_a": [[0.0, 0.0, 0.0]],
            "points_b": [[1.0, 1.0, 1.0]],
        },
    )

    payload = api_app.get_map("123")

    assert payload["session_id"] == "123"
    assert payload["lap_a"] == 1
    assert payload["lap_b"] == 2
    assert payload["units"] == "imperial"
    assert payload["unit_contract"]["speed"] == "mph"
