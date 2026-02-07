from analytics.deltas import SegmentDefinition, SegmentDelta, SegmentSpeedMetrics
from analytics.trackside.corner_identity import rider_corner_label
from analytics.trackside.pipeline import _build_segments_payload


def test_trackside_corner_identity_extracts_turn_token_from_internal_id():
    label = rider_corner_label(None, fallback_internal_id="HPR Full:CW:T4")
    assert label == "T4"


def test_trackside_corner_identity_fallback_phrase_is_deterministic():
    label = rider_corner_label(
        None,
        fallback_internal_id="segment_internal_7",
        apex_m=123.4,
        turn_sign=-1,
    )
    assert label == "left-hander near 123 m"


def test_trackside_corner_identity_payload_uses_rider_label_not_raw_internal_id():
    segment_defs = [
        SegmentDefinition(
            name="HPR Full:CW:T5",
            start_m=80.0,
            apex_m=104.0,
            end_m=140.0,
        )
    ]
    segment_deltas = [
        SegmentDelta(
            name="HPR Full:CW:T5",
            entry_delta=None,
            apex_delta=None,
            exit_delta=None,
            min_delta=None,
            reference=SegmentSpeedMetrics(
                entry_speed=None,
                apex_speed=None,
                exit_speed=None,
                min_speed=None,
            ),
            target=SegmentSpeedMetrics(
                entry_speed=None,
                apex_speed=None,
                exit_speed=None,
                min_speed=None,
            ),
        )
    ]

    payload = _build_segments_payload(
        segment_defs,
        segment_deltas,
        reference_metrics={},
        target_metrics={},
        corner_labels={"HPR Full:CW:T5": "T5"},
    )

    assert payload[0]["segment_id"] == "HPR Full:CW:T5"
    assert payload[0]["corner_id"] == "T5"
    assert payload[0]["corner_label"] == "T5"
    assert payload[0]["target"]["corner_id"] == "T5"
