import unittest

from analytics.trackside import rank, signals


class TestTracksideRules(unittest.TestCase):
    def _signals_for(self, target, reference=None, segment_extra=None):
        segment = {
            "segment_id": "seg-1",
            "corner_id": "T1",
            "target": target,
            "reference": reference or {},
        }
        if segment_extra:
            segment.update(segment_extra)
        return signals.generate_signals([segment], "ref")

    def _signal_ids(self, signals_list):
        return [item["signal_id"] for item in signals_list]

    def test_early_braking_rule(self):
        signals_list = self._signals_for(
            {"segment_time_delta_s": 0.09, "brake_point_dist_m": 90.0},
            {"brake_point_dist_m": 105.0},
        )
        self.assertIn("early_braking", self._signal_ids(signals_list))

        no_time_loss = self._signals_for(
            {"segment_time_delta_s": 0.04, "brake_point_dist_m": 90.0},
            {"brake_point_dist_m": 105.0},
        )
        self.assertNotIn("early_braking", self._signal_ids(no_time_loss))

        not_early = self._signals_for(
            {"segment_time_delta_s": 0.09, "brake_point_dist_m": 98.0},
            {"brake_point_dist_m": 105.0},
        )
        self.assertNotIn("early_braking", self._signal_ids(not_early))

    def test_late_throttle_pickup_rule_distance(self):
        signals_list = self._signals_for(
            {"segment_time_delta_s": 0.1, "throttle_pickup_dist_m": 42.0},
            {"throttle_pickup_dist_m": 28.0},
        )
        self.assertIn("late_throttle_pickup", self._signal_ids(signals_list))

        good = self._signals_for(
            {"segment_time_delta_s": 0.1, "throttle_pickup_dist_m": 34.0},
            {"throttle_pickup_dist_m": 28.0},
        )
        self.assertNotIn("late_throttle_pickup", self._signal_ids(good))

    def test_late_throttle_pickup_rule_proxy_time(self):
        signals_list = self._signals_for(
            {"segment_time_delta_s": 0.1, "throttle_pickup_time_s": 1.5},
            {"throttle_pickup_time_s": 1.3},
            segment_extra={"using_speed_proxy": True},
        )
        signal_ids = self._signal_ids(signals_list)
        self.assertIn("late_throttle_pickup", signal_ids)
        pickup = next(item for item in signals_list if item["signal_id"] == "late_throttle_pickup")
        self.assertAlmostEqual(0.4, pickup["confidence"], places=3)
        self.assertEqual("low", pickup["confidence_label"])

        good = self._signals_for(
            {"segment_time_delta_s": 0.1, "throttle_pickup_time_s": 1.38},
            {"throttle_pickup_time_s": 1.3},
            segment_extra={"using_speed_proxy": True},
        )
        self.assertNotIn("late_throttle_pickup", self._signal_ids(good))

    def test_neutral_throttle_rule_time(self):
        signals_list = self._signals_for(
            {
                "segment_time_delta_s": 0.08,
                "neutral_throttle_s": 1.1,
                "neutral_speed_delta_kmh": 0.4,
                "speed_noise_sigma_kmh": 0.4,
            },
            {},
        )
        self.assertIn("neutral_throttle", self._signal_ids(signals_list))

        speed_not_flat = self._signals_for(
            {
                "segment_time_delta_s": 0.08,
                "neutral_throttle_s": 1.1,
                "neutral_speed_delta_kmh": 1.4,
            },
            {},
        )
        self.assertNotIn("neutral_throttle", self._signal_ids(speed_not_flat))

    def test_neutral_throttle_rule_distance(self):
        signals_list = self._signals_for(
            {
                "segment_time_delta_s": 0.05,
                "neutral_throttle_dist_m": 18.0,
                "neutral_speed_delta_kmh": 0.6,
            },
            {},
        )
        self.assertIn("neutral_throttle", self._signal_ids(signals_list))

        no_time_loss = self._signals_for(
            {
                "segment_time_delta_s": 0.04,
                "neutral_throttle_dist_m": 18.0,
                "neutral_speed_delta_kmh": 0.6,
            },
            {},
        )
        self.assertNotIn("neutral_throttle", self._signal_ids(no_time_loss))

    def test_line_inconsistency_rule(self):
        signals_list = self._signals_for(
            {"segment_time_delta_s": 0.05, "line_stddev_m": 1.6},
            {"line_stddev_m": 0.9},
        )
        self.assertIn("line_inconsistency", self._signal_ids(signals_list))

        delta_trigger = self._signals_for(
            {"segment_time_delta_s": 0.05, "line_stddev_m": 1.4},
            {"line_stddev_m": 0.7},
        )
        self.assertIn("line_inconsistency", self._signal_ids(delta_trigger))

        good = self._signals_for(
            {"segment_time_delta_s": 0.05, "line_stddev_m": 1.2},
            {"line_stddev_m": 0.9},
        )
        self.assertNotIn("line_inconsistency", self._signal_ids(good))

    def test_corner_speed_loss_rule(self):
        signals_list = self._signals_for(
            {"segment_time_delta_s": 0.05, "min_speed_kmh": 70.0, "apex_dist_m": 55.0},
            {"min_speed_kmh": 74.0, "apex_dist_m": 56.0},
        )
        self.assertIn("corner_speed_loss", self._signal_ids(signals_list))

        good = self._signals_for(
            {"segment_time_delta_s": 0.05, "min_speed_kmh": 72.5},
            {"min_speed_kmh": 74.0},
        )
        self.assertNotIn("corner_speed_loss", self._signal_ids(good))

    def test_exit_speed_rule_proxy(self):
        signals_list = self._signals_for(
            {
                "segment_time_delta_s": 0.05,
                "exit_speed_30m_kmh": 90.0,
                "inline_acc_rise_g": 0.05,
            },
            {"exit_speed_30m_kmh": 94.0, "inline_acc_rise_g": 0.08},
            segment_extra={"using_speed_proxy": True},
        )
        self.assertIn("exit_speed", self._signal_ids(signals_list))
        exit_speed = next(item for item in signals_list if item["signal_id"] == "exit_speed")
        self.assertAlmostEqual(0.4, exit_speed["confidence"], places=3)
        self.assertEqual("low", exit_speed["confidence_label"])

        accel_not_low = self._signals_for(
            {
                "segment_time_delta_s": 0.05,
                "exit_speed_30m_kmh": 90.0,
                "inline_acc_rise_g": 0.08,
            },
            {"exit_speed_30m_kmh": 94.0, "inline_acc_rise_g": 0.05},
        )
        self.assertNotIn("exit_speed", self._signal_ids(accel_not_low))

    def test_entry_speed_rule(self):
        signals_list = self._signals_for(
            {"segment_time_delta_s": 0.05, "entry_speed_kmh": 100.0, "brake_point_dist_m": 100.0},
            {"entry_speed_kmh": 104.0, "brake_point_dist_m": 100.0},
        )
        self.assertIn("entry_speed", self._signal_ids(signals_list))

        late_brake = self._signals_for(
            {"segment_time_delta_s": 0.05, "entry_speed_kmh": 100.0, "brake_point_dist_m": 111.0},
            {"entry_speed_kmh": 104.0, "brake_point_dist_m": 100.0},
        )
        self.assertNotIn("entry_speed", self._signal_ids(late_brake))

    def test_steering_smoothness_rule(self):
        signals_list = self._signals_for(
            {"segment_time_delta_s": 0.05, "yaw_rms": 1.2, "min_speed_kmh": 90.0},
            {"yaw_rms": 1.0, "min_speed_kmh": 92.5},
        )
        self.assertIn("steering_smoothness", self._signal_ids(signals_list))

        yaw_ok = self._signals_for(
            {"segment_time_delta_s": 0.05, "yaw_rms": 1.15, "min_speed_kmh": 90.0},
            {"yaw_rms": 1.0, "min_speed_kmh": 92.5},
        )
        self.assertNotIn("steering_smoothness", self._signal_ids(yaw_ok))


class TestTracksideRanking(unittest.TestCase):
    def _item(self, rule_id, time_gain, confidence, corner_id):
        return {
            "rule_id": rule_id,
            "time_gain_s": time_gain,
            "confidence": confidence,
            "corner_id": corner_id,
        }

    def test_rank_insights_min_confidence_respected(self):
        insights = [
            self._item("a", 0.2, 0.8, "T1"),
            self._item("b", 0.18, 0.6, "T2"),
            self._item("c", 0.4, 0.3, "T3"),
        ]
        ranked = rank.rank_insights(
            insights,
            min_count=2,
            max_count=5,
            min_confidence=0.5,
            max_per_corner=2,
        )
        rule_ids = {item["rule_id"] for item in ranked}
        self.assertIn("a", rule_ids)
        self.assertIn("b", rule_ids)
        self.assertNotIn("c", rule_ids)

    def test_rank_insights_min_confidence_fallback(self):
        insights = [
            self._item("a", 0.2, 0.4, "T1"),
            self._item("b", 0.18, 0.3, "T2"),
        ]
        ranked = rank.rank_insights(
            insights,
            min_count=2,
            max_count=5,
            min_confidence=0.5,
            max_per_corner=2,
        )
        rule_ids = {item["rule_id"] for item in ranked}
        self.assertEqual({"a", "b"}, rule_ids)

    def test_rank_insights_max_per_corner(self):
        insights = [
            self._item("a", 0.2, 0.9, "T1"),
            self._item("b", 0.18, 0.8, "T1"),
            self._item("c", 0.17, 0.7, "T1"),
            self._item("d", 0.17, 0.7, "T2"),
        ]
        ranked = rank.rank_insights(
            insights,
            min_count=1,
            max_count=3,
            min_confidence=0.0,
            max_per_corner=1,
        )
        corners = [item["corner_id"] for item in ranked]
        self.assertEqual(1, corners.count("T1"))
        self.assertIn("T2", corners)


if __name__ == "__main__":
    unittest.main()
