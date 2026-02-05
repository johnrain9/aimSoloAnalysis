from analytics.trackside import pipeline


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
