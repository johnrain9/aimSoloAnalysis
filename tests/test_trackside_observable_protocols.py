from analytics.trackside import synthesis as synthesis_module


def test_synthesize_uses_rider_observable_success_checks_and_typed_protocols():
    segments = [
        {
            "segment_id": "T1",
            "corner_id": "T1",
            "target": {
                "line_stddev_m": 1.8,
                "entry_speed_kmh": 92.0,
                "min_speed_kmh": 68.0,
                "apex_dist_m": 51.0,
                "segment_time_s": 21.1,
            },
            "reference": {
                "line_stddev_m": 1.0,
                "entry_speed_kmh": 98.0,
                "min_speed_kmh": 72.0,
                "apex_dist_m": 52.0,
                "segment_time_s": 20.9,
            },
            "quality": {"gps_accuracy_m": 2.5, "satellites": 6},
        },
        {
            "segment_id": "T2",
            "corner_id": "T2",
            "target": {
                "entry_speed_kmh": 90.0,
                "brake_point_dist_m": 120.0,
                "segment_time_s": 21.2,
            },
            "reference": {
                "entry_speed_kmh": 95.0,
                "brake_point_dist_m": 135.0,
                "segment_time_s": 20.9,
            },
            "quality": {"gps_accuracy_m": 2.4, "satellites": 6},
        },
        {
            "segment_id": "T3",
            "corner_id": "T3",
            "target": {
                "throttle_pickup_dist_m": 45.0,
                "exit_speed_30m_kmh": 88.0,
                "segment_time_s": 20.8,
            },
            "reference": {
                "throttle_pickup_dist_m": 33.0,
                "exit_speed_30m_kmh": 92.0,
                "segment_time_s": 20.4,
            },
            "quality": {"gps_accuracy_m": 2.3, "satellites": 6},
        },
    ]
    signals = [
        {
            "signal_id": "line_inconsistency",
            "segment_id": "T1",
            "corner_id": "T1",
            "time_gain_s": 0.2,
            "confidence": 0.5,
            "evidence": {"line_stddev_m": 1.8, "line_stddev_delta_m": 0.8},
        },
        {
            "signal_id": "early_braking",
            "segment_id": "T2",
            "corner_id": "T2",
            "time_gain_s": 0.18,
            "confidence": 0.5,
            "evidence": {"entry_speed_delta_kmh": -5.0, "brake_point_delta_m": -15.0},
        },
        {
            "signal_id": "late_throttle_pickup",
            "segment_id": "T3",
            "corner_id": "T3",
            "time_gain_s": 0.16,
            "confidence": 0.5,
            "evidence": {"pickup_delta_m": 12.0, "exit_speed_delta_kmh": -4.0},
        },
    ]

    insights = synthesis_module.synthesize_insights(
        segments,
        signals,
        comparison_label="Lap 6 vs best Lap 2",
    )
    assert len(insights) == 3

    for item in insights:
        assert item["success_check"].startswith("Rider check:")
        assert "Telemetry confirmation (optional):" in item["success_check"]
        assert item["risk_tier"] == "Experimental"
        assert isinstance(item["experimental_protocol"], dict)

    by_rule = {item["rule_id"]: item for item in insights}
    assert by_rule["line_inconsistency"]["experimental_protocol"]["behavior_class"] == "line_trajectory"
    assert by_rule["early_braking"]["experimental_protocol"]["behavior_class"] == "braking"
    assert by_rule["late_throttle_pickup"]["experimental_protocol"]["behavior_class"] == "throttle"
    assert "mid-corner corrections" in by_rule["line_inconsistency"]["experimental_protocol"]["abort_criteria"]
    assert "second brake stab" in by_rule["early_braking"]["experimental_protocol"]["abort_criteria"]
    assert "rear slip" in by_rule["late_throttle_pickup"]["experimental_protocol"]["abort_criteria"]


def test_unknown_behavior_class_uses_conservative_fallback_protocol():
    protocol = synthesis_module._experimental_protocol(
        expected_gain_s=0.12,
        primary_id="unknown_rule",
        behavior_class="unknown",
        phase="mid",
        evidence={},
    )

    assert protocol["behavior_class"] == "generic_safe"
    assert "Unknown behavior class" in protocol["note"]
    assert "Conservative fallback" in protocol["bounds"]
    assert "Abort immediately" in protocol["abort_criteria"]


def test_synthesize_handles_missing_evidence_without_crash():
    segments = [
        {
            "segment_id": "T4",
            "corner_id": "T4",
            "target": {"segment_time_delta_s": 0.12},
            "reference": {},
            "quality": {"gps_accuracy_m": 2.4, "satellites": 6},
        }
    ]
    signals = [
        {
            "signal_id": "late_throttle_pickup",
            "segment_id": "T4",
            "corner_id": "T4",
            "time_gain_s": 0.12,
            "confidence": 0.4,
            "evidence": {},
        }
    ]

    insights = synthesis_module.synthesize_insights(
        segments,
        signals,
        comparison_label="Lap 7 vs best Lap 3",
    )
    assert len(insights) == 1
    protocol = insights[0]["experimental_protocol"]
    assert protocol["behavior_class"] == "throttle"
    assert protocol["risk"]
    assert protocol["bounds"]
    assert protocol["abort_criteria"]
