from analytics.trackside import pipeline, synthesis


def test_cluster_by_apex_threshold():
    samples = [
        {"apex_dist_m": 10.0},
        {"apex_dist_m": 14.0},
        {"apex_dist_m": 30.0},
    ]
    clusters = pipeline._cluster_by_apex(samples, threshold_m=6.0)
    assert len(clusters) == 2
    assert len(clusters[0]) == 2
    assert len(clusters[1]) == 1


def test_pick_cluster_prefers_stable_when_close():
    clusters = [
        {
            "segment_time_median_s": 10.0,
            "apex_stddev_m": 1.0,
            "line_stddev_median_m": 1.0,
        },
        {
            "segment_time_median_s": 9.8,
            "apex_stddev_m": 5.0,
            "line_stddev_median_m": 5.0,
        },
    ]
    picked = pipeline._pick_cluster(clusters)
    assert picked == clusters[0]


def test_summarize_line_trends_marks_recurrence_priority_shift_with_why_now():
    samples = []
    lap_id = 100
    # Historical sessions hold a stable faster apex line near 40 m.
    for session_id, apex_values in ((1, [40.0, 40.2, 40.4]), (2, [39.8, 40.1])):
        for lap_order, apex in enumerate(apex_values, start=1):
            samples.append(
                {
                    "session_id": session_id,
                    "lap_id": lap_id,
                    "lap_index": lap_order,
                    "lap_order": lap_order,
                    "apex_dist_m": apex,
                    "line_stddev_m": 1.1,
                    "segment_time_s": 10.05,
                    "min_speed_kmh": 80.0,
                    "speed_noise_sigma_kmh": 0.2,
                }
            )
            lap_id += 1
    # Current session drifts far from that stable line.
    for lap_order, apex in enumerate([49.0, 49.4, 50.0], start=1):
        samples.append(
            {
                "session_id": 3,
                "lap_id": lap_id,
                "lap_index": lap_order,
                "lap_order": lap_order,
                "apex_dist_m": apex,
                "line_stddev_m": 1.2,
                "segment_time_s": 10.4,
                "min_speed_kmh": 79.0,
                "speed_noise_sigma_kmh": 0.2,
            }
        )
        lap_id += 1

    trends = pipeline._summarize_line_trends({"T1": samples}, current_session_id=3)
    trend = trends["T1"]
    assert trend["recurrence_detected"] is True
    assert trend["recurrence_session_count"] >= 2
    assert trend["recurrence_priority_shift"] is True
    assert isinstance(trend["why_now"], str)
    assert "Current-session apex bias" in trend["why_now"]


def test_filter_segment_samples_deweights_late_fatigue_laps():
    samples = []
    for lap_order in range(1, 9):
        is_late = lap_order >= 6
        samples.append(
            {
                "session_id": 10,
                "lap_id": 200 + lap_order,
                "lap_index": lap_order,
                "lap_order": lap_order,
                "apex_dist_m": 50.0 + (0.1 if is_late else 0.0),
                "line_stddev_m": 1.1 + (0.02 if is_late else 0.0),
                "segment_time_s": 10.0 + (0.38 if is_late else 0.02 * lap_order),
                "min_speed_kmh": 80.0,
                "speed_noise_sigma_kmh": 0.25,
            }
        )

    filtered, stats = pipeline._filter_segment_samples_with_stats(samples)
    assert len(filtered) == 5
    assert stats["drop_reasons"]["fatigue_late_fade"] == 3
    assert stats["fatigue_sessions"] == 1
    assert stats["fatigue_late_laps"] == 3


def test_filter_segment_samples_short_session_skips_fatigue_detection():
    samples = [
        {
            "session_id": 7,
            "lap_id": 300 + idx,
            "lap_index": idx,
            "lap_order": idx,
            "apex_dist_m": 45.0,
            "line_stddev_m": 1.2,
            "segment_time_s": 10.0 + idx * 0.2,
            "min_speed_kmh": 78.0,
            "speed_noise_sigma_kmh": 0.3,
        }
        for idx in range(1, 5)
    ]
    filtered, stats = pipeline._filter_segment_samples_with_stats(samples)
    assert len(filtered) > 0
    assert stats["drop_reasons"]["fatigue_late_fade"] == 0
    assert stats["fatigue_sessions"] == 0
    assert stats["fatigue_late_laps"] == 0


def test_apply_line_trend_copy_adds_recurrence_why_now_and_fatigue_note():
    detail, actions, _options, evidence = synthesis._apply_line_trend_copy(
        "Base detail.",
        ["Use the reference apex marker."],
        {
            "apex_stddev_m": 2.5,
            "recommendation": {"apex_mean_m": 45.0},
            "recurrence_detected": True,
            "recurrence_session_count": 3,
            "recurrence_priority_shift": True,
            "why_now": "Current-session apex bias widened to 5.1 m from 2.9 m.",
            "fatigue_likely": True,
            "fatigue_session_count": 1,
            "fatigue_late_laps": 3,
            "fatigue_max_fade_s": 0.41,
        },
        target_apex_m=50.0,
    )

    assert "Why now:" in detail
    assert "fatigue-driven" in detail
    assert any("fresh laps" in action.lower() for action in actions)
    assert evidence["recurrence_priority_shift"] is True
    assert evidence["fatigue_likely"] is True
