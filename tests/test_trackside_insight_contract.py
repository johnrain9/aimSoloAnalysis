from pathlib import Path

from analytics.trackside.rank import rank_insights
from analytics.trackside.synthesis import synthesize_insights
from api import app as api_app


class _FakeConn:
    def close(self) -> None:
        return None


def test_synthesize_insight_contract_fields_and_experimental_protocol():
    segments = [
        {
            "segment_id": "T1",
            "corner_id": "T1",
            "target": {
                "line_stddev_m": 1.8,
                "entry_speed_kmh": 95.0,
                "min_speed_kmh": 70.0,
                "exit_speed_30m_kmh": 92.0,
                "apex_dist_m": 50.0,
                "segment_time_s": 21.1,
            },
            "reference": {
                "line_stddev_m": 1.0,
                "entry_speed_kmh": 99.0,
                "min_speed_kmh": 73.0,
                "exit_speed_30m_kmh": 95.0,
                "apex_dist_m": 52.0,
                "segment_time_s": 20.9,
            },
            "quality": {"gps_accuracy_m": 0.9, "satellites": 11, "imu_present": True},
        },
        {
            "segment_id": "T2",
            "corner_id": "T2",
            "target": {
                "throttle_pickup_dist_m": 46.0,
                "segment_time_delta_s": 0.15,
            },
            "reference": {
                "throttle_pickup_dist_m": 30.0,
            },
            "quality": {"gps_accuracy_m": 2.6, "satellites": 6},
        },
    ]
    signals = [
        {
            "signal_id": "line_inconsistency",
            "segment_id": "T1",
            "corner_id": "T1",
            "time_gain_s": 0.21,
            "confidence": 0.8,
            "confidence_label": "high",
            "evidence": {"line_stddev_m": 1.8, "line_stddev_delta_m": 0.8},
            "comparison": "Lap 4 vs best Lap 2",
        },
        {
            "signal_id": "late_throttle_pickup",
            "segment_id": "T2",
            "corner_id": "T2",
            "time_gain_s": 0.18,
            "confidence": 0.4,
            "confidence_label": "low",
            "evidence": {"pickup_delta_m": 16.0, "segment_time_delta_s": 0.15},
            "comparison": "Lap 4 vs best Lap 2",
        },
    ]

    insights = synthesize_insights(segments, signals, comparison_label="Lap 4 vs best Lap 2")
    assert len(insights) == 2

    required = {
        "phase",
        "operational_action",
        "causal_reason",
        "risk_tier",
        "risk_reason",
        "confidence",
        "data_quality_note",
        "uncertainty_note",
        "success_check",
    }
    for insight in insights:
        assert required.issubset(set(insight.keys()))
        assert insight["phase"] in {"entry", "mid", "exit"}
        assert insight["risk_tier"] in {"Primary", "Experimental", "Blocked"}
        assert insight["operational_action"]
        assert insight["causal_reason"]
        assert insight["success_check"]

    experimental = next(item for item in insights if item["rule_id"] == "late_throttle_pickup")
    assert experimental["risk_tier"] == "Experimental"
    protocol = experimental["experimental_protocol"]
    assert isinstance(protocol, dict)
    assert {"expected_gain_s", "risk", "bounds", "abort_criteria"}.issubset(set(protocol.keys()))


def test_rank_insights_enforces_top_n_primary_cap_and_conflict_suppression():
    insights = [
        {
            "rule_id": "entry_speed",
            "corner_id": "T1",
            "phase": "entry",
            "time_gain_s": 0.25,
            "confidence": 0.9,
            "risk_tier": "Primary",
        },
        {
            "rule_id": "early_braking",
            "corner_id": "T1",
            "phase": "entry",
            "time_gain_s": 0.22,
            "confidence": 0.8,
            "risk_tier": "Primary",
        },
        {
            "rule_id": "line_inconsistency",
            "corner_id": "T2",
            "phase": "mid",
            "time_gain_s": 0.2,
            "confidence": 0.85,
            "risk_tier": "Primary",
        },
        {
            "rule_id": "exit_speed",
            "corner_id": "T3",
            "phase": "exit",
            "time_gain_s": 0.18,
            "confidence": 0.8,
            "risk_tier": "Primary",
        },
        {
            "rule_id": "neutral_throttle",
            "corner_id": "T4",
            "phase": "mid",
            "time_gain_s": 0.1,
            "confidence": 0.6,
            "risk_tier": "Experimental",
        },
    ]

    ranked = rank_insights(
        insights,
        min_count=1,
        max_count=3,
        min_confidence=0.0,
        max_per_corner=3,
        max_primary_focus=2,
    )

    assert len(ranked) == 3
    assert any(item["rule_id"] == "entry_speed" for item in ranked)
    assert not any(item["rule_id"] == "early_braking" for item in ranked)

    corner_phase = {(item.get("corner_id"), item.get("phase")) for item in ranked}
    assert len(corner_phase) == len(ranked)

    primary_count = sum(1 for item in ranked if item.get("is_primary_focus"))
    assert primary_count <= 2


def test_insights_endpoint_exposes_contract_fields(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    db_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(api_app, "DB_PATH", Path(db_path))
    monkeypatch.setattr(api_app.db, "connect", lambda _: _FakeConn())
    monkeypatch.setattr(api_app.db, "init_schema", lambda _: None)
    monkeypatch.setattr(
        api_app,
        "_load_session_meta",
        lambda _conn, _session_id: {
            "track_name": "Test Track",
            "direction": "CW",
            "track_direction": "Test Track CW",
        },
    )
    monkeypatch.setattr(api_app, "_load_run_id", lambda _conn, _session_id: 7)
    monkeypatch.setattr(api_app, "_load_run_meta", lambda _conn, _run_id: {"rider_name": "R", "bike_name": "B"})
    monkeypatch.setattr(
        api_app,
        "generate_trackside_insights",
        lambda _db, _session: [
            {
                "rule_id": "line_inconsistency",
                "title": "Make the Line Repeatable",
                "phase": "mid",
                "operational_action": "Pick one turn-in marker and repeat it.",
                "causal_reason": "Line variance is elevated versus reference.",
                "risk_tier": "Primary",
                "risk_reason": "Stable context and strong evidence.",
                "data_quality_note": "gps accuracy good (0.9 m); 11 satellites",
                "uncertainty_note": "High confidence from current telemetry quality.",
                "success_check": "Reduce line_stddev_delta_m to <= +0.30 m for 3 laps.",
                "expected_gain_s": 0.21,
                "experimental_protocol": None,
                "is_primary_focus": True,
                "confidence": 0.8,
                "confidence_label": "high",
                "time_gain_s": 0.21,
                "detail": "Detail",
                "actions": ["Action"],
                "options": [],
                "segment_id": "T1",
                "corner_id": "T1",
                "evidence": {"line_stddev_m": 1.8},
                "comparison": "Lap 4 vs best Lap 2",
            }
        ],
    )
    monkeypatch.setattr(api_app, "generate_trackside_map", lambda _db, _session: None)

    response = api_app.get_insights("123")
    item = response["items"][0]

    assert item["phase"] == "mid"
    assert item["risk_tier"] == "Primary"
    assert item["success_check"]
    assert "data_quality_note" in item
    assert "uncertainty_note" in item
    assert item["is_primary_focus"] is True
